"""
Noesis 批量 MSH → FBX 导出脚本 (Python)
扫描 .mdl-msh* 文件，调用 Noesis 命令行模式导出为 FBX
命名规则：plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1h000.fbx
输出保持多层级目录结构

用法：
  python batch_noesis_fbx.py --input quickbms_unpacksource --output fbx_output
  python batch_noesis_fbx.py --input models/weapons --output fbx_output/weapons
  python batch_noesis_fbx.py --dry-run
  python batch_noesis_fbx.py --workers 4  # 多进程并行
"""
import os, sys, subprocess, time, argparse, logging, re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import Counter

# ---------------------------------------------------------------------------
# 默认路径
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_NOESIS = SCRIPT_DIR / "NOESIS" / "Noesis64.exe"
DEFAULT_INPUT  = SCRIPT_DIR / "quickbms_unpacksource"
DEFAULT_OUTPUT = SCRIPT_DIR / "fbx_output"


def setup_logging(log_path):
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger(__name__)


def msh_to_fbx_name(filename):
    """plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1000.fbx"""
    return re.sub(r"\.mdl-msh(\d+)$", r"\1.fbx", filename)


# A-Z 插件覆盖范围
PLUGIN_MAX_NUM = 987

def extract_msh_number(filename):
    """提取 .mdl-msh 后的数字"""
    m = re.search(r"\.mdl-msh(\d+)$", filename)
    return int(m.group(1)) if m else -1

def scan_msh_files(input_dir, filter_range=True):
    """扫描所有 .mdl-mshXXX 文件。filter_range=True 只返回 000-987 范围"""
    files = []
    out_of_range = []
    for root, _, filenames in os.walk(input_dir):
        for f in filenames:
            if ".mdl-msh" in f:
                name_parts = f.rsplit(".mdl-msh", 1)
                if len(name_parts) == 2 and name_parts[1].isdigit():
                    num = int(name_parts[1])
                    fp = Path(root) / f
                    if filter_range and num > PLUGIN_MAX_NUM:
                        out_of_range.append(fp)
                    else:
                        files.append(fp)
    return files, out_of_range


def export_single(args):
    """
    单个文件导出函数（供多进程调用）
    args = (noesis_exe, input_path, output_path, timeout)
    返回 (input_rel, success, error_msg)
    """
    noesis_exe, input_path, output_path, timeout = args

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and output_path.stat().st_size > 0:
        return (str(input_path), True, "skipped")

    cmd = [str(noesis_exe), "?cmode", str(input_path), str(output_path)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            return (str(input_path), False,
                    f"exit code {result.returncode}: {result.stderr[:200]}")
        if output_path.exists() and output_path.stat().st_size > 0:
            return (str(input_path), True, "")
        else:
            return (str(input_path), False, "output file missing or empty")
    except subprocess.TimeoutExpired:
        return (str(input_path), False, f"timeout ({timeout}s)")
    except Exception as e:
        return (str(input_path), False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Noesis 批量 MSH → FBX 导出")
    parser.add_argument("--noesis", default=str(DEFAULT_NOESIS),
                        help=f"Noesis64.exe 路径")
    parser.add_argument("--input", default=str(DEFAULT_INPUT),
                        help=f"输入目录")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT),
                        help=f"输出目录")
    parser.add_argument("--workers", type=int, default=1,
                        help="并行进程数 (默认: 1)")
    parser.add_argument("--timeout", type=int, default=300,
                        help="单个文件超时秒数 (默认: 300)")
    parser.add_argument("--dry-run", action="store_true",
                        help="预演模式")
    parser.add_argument("--force", action="store_true",
                        help="强制覆盖")
    parser.add_argument("--limit", type=int, default=0,
                        help="限制处理文件数")
    parser.add_argument("--log", default="", help="日志文件路径")
    args = parser.parse_args()

    noesis_exe = Path(args.noesis)
    input_dir  = Path(args.input)
    output_dir = Path(args.output)

    if not noesis_exe.exists():
        print(f"错误: 未找到 Noesis: {noesis_exe}")
        sys.exit(1)
    if not input_dir.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        sys.exit(1)

    log_path = args.log or str(SCRIPT_DIR / "batch_noesis_fbx.log")
    log = setup_logging(log_path)

    log.info("=" * 60)
    log.info("Noesis 批量 MSH → FBX 导出")
    log.info(f"Noesis:    {noesis_exe}")
    log.info(f"输入目录:  {input_dir}")
    log.info(f"输出目录:  {output_dir}")
    log.info(f"命名规则:  .mdl-msh000 → 000.fbx")
    log.info(f"目录结构:  保持多层级")
    log.info("=" * 60)

    # 扫描文件（只取插件覆盖范围 000-987）
    print("\n[1/3] 扫描模型文件...")
    msh_files, out_of_range = scan_msh_files(input_dir, filter_range=True)
    total = len(msh_files)
    total_oor = len(out_of_range)
    print(f"       插件范围 (000-987): {total} 个")
    if total_oor > 0:
        print(f"       超出范围 (988-1308): {total_oor} 个 (跳过)")

    if total == 0:
        print("没有可处理的模型文件，退出。")
        return

    # 统计
    ext_counter = Counter()
    for f in msh_files:
        name = f.name
        idx = name.rfind(".mdl-msh")
        if idx >= 0:
            ext_counter[name[idx:]] += 1
    print(f"       扩展名分布 (前10):")
    for ext, count in ext_counter.most_common(10):
        print(f"         {ext}: {count}")

    # 预演
    if args.dry_run:
        print(f"\n[预演模式] 前20个文件示例:")
        for f in msh_files[:20]:
            rel = f.relative_to(input_dir)
            out_rel = Path(msh_to_fbx_name(rel.name))
            out_full = Path(str(rel.parent)) / out_rel if str(rel.parent) != "." else out_rel
            print(f"  {rel}  →  {out_full}")
        # 目录层级示例
        dirs = set()
        for f in msh_files:
            d = f.relative_to(input_dir).parent
            dirs.add(str(d))
        print(f"\n  保持 {len(dirs)} 个目录层级")
        for d in sorted(dirs)[:10]:
            print(f"    {d}/")
        if len(dirs) > 10:
            print(f"    ... 共 {len(dirs)} 个")
        print(f"\n预演完成。共 {total} 个文件待导出。")
        return

    if args.limit > 0:
        msh_files = msh_files[:args.limit]

    # -------------------------------------------------------------------
    # 导出
    # -------------------------------------------------------------------
    print(f"\n[2/3] 开始批量导出...")

    tasks = []
    for f in msh_files:
        rel = f.relative_to(input_dir)
        out_name = msh_to_fbx_name(f.name)
        out_path = output_dir / rel.parent / out_name

        if not args.force and out_path.exists() and out_path.stat().st_size > 0:
            continue

        tasks.append((str(noesis_exe), f, out_path, args.timeout))

    tasks_total = len(tasks)
    skipped = total - tasks_total
    log.info(f"待处理: {tasks_total}, 已跳过: {skipped}")

    success = 0
    fail = 0
    fail_files = []
    start_time = time.time()

    if args.workers > 1 and tasks_total > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(export_single, t): t for t in tasks}
            for i, future in enumerate(as_completed(futures), 1):
                in_path, ok, err = future.result()
                if ok:
                    success += 1
                else:
                    fail += 1
                    fail_files.append((in_path, err))
                    log.error(f"失败: {in_path} - {err}")
                if i % 100 == 0 or i == tasks_total:
                    elapsed = time.time() - start_time
                    print(f"  [{i}/{tasks_total}] {i/tasks_total*100:.1f}% | "
                          f"成功: {success} | 失败: {fail} | "
                          f"耗时: {elapsed:.0f}s")
    else:
        for i, task in enumerate(tasks, 1):
            in_path, ok, err = export_single(task)
            if ok:
                success += 1
            else:
                fail += 1
                fail_files.append((in_path, err))
                log.error(f"失败: {in_path} - {err}")
            if i % 100 == 0 or i == tasks_total:
                elapsed = time.time() - start_time
                print(f"  [{i}/{tasks_total}] {i/tasks_total*100:.1f}% | "
                      f"成功: {success} | 失败: {fail} | "
                      f"耗时: {elapsed:.0f}s")

    # -------------------------------------------------------------------
    # 结果
    # -------------------------------------------------------------------
    total_elapsed = time.time() - start_time
    print(f"\n[3/3] 导出完成!")
    print(f"\n{'='*60}")
    print(f"  命名规则:   .mdl-msh000 → h000.fbx")
    print(f"  总文件数:   {total}")
    print(f"  成功导出:   {success}")
    print(f"  导出失败:   {fail}")
    print(f"  已跳过:     {skipped}")
    print(f"  总耗时:     {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")
    print(f"{'='*60}\n")

    log.info(f"完成 - 总: {total}, 成功: {success}, 失败: {fail}, "
             f"跳过: {skipped}, 耗时: {total_elapsed:.0f}s")

    if fail_files:
        fail_log = log_path.replace(".log", "_failed.log")
        with open(fail_log, "w", encoding="utf-8") as fh:
            for path, err in fail_files:
                fh.write(f"{path}\t{err}\n")
        print(f"失败列表: {fail_log}")

    print(f"输出目录: {output_dir}")


if __name__ == "__main__":
    main()
