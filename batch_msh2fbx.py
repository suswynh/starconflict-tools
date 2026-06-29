"""
batch_msh2fbx.py — 使用 msh2fbx.exe 批量 MSH→FBX 转换

比 Noesis 版本更快、更可靠（~175 files/s），
保持源目录层级结构输出。

用法:
    python batch_msh2fbx.py --input scunpack/output/models/weapons --output scunpack/fbx_output/weapons
    python batch_msh2fbx.py --input . --output ./fbx_out --limit 50
"""
import os, sys, subprocess, time, argparse, re
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_MSH2FBX = SCRIPT_DIR / "msh2fbx" / "msh2fbx.exe"


def msh_to_fbx_name(filename):
    """plasma_gun_mod1.mdl-msh000 → plasma_gun_mod1000.fbx"""
    return re.sub(r"\.mdl-msh(\d+)$", r"\1.fbx", filename)


def convert_single(args):
    """转换单个文件 (子进程安全)"""
    msh2fbx_path, input_path, output_path, timeout = args
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        result = subprocess.run(
            [str(msh2fbx_path), str(input_path), str(output_path)],
            capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0 and os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            return (input_path, True, None)
        else:
            return (input_path, False, result.stderr.strip() or "empty output")
    except subprocess.TimeoutExpired:
        return (input_path, False, "timeout")
    except Exception as e:
        return (input_path, False, str(e))


def main():
    parser = argparse.ArgumentParser(description="msh2fbx 批量 MSH→FBX")
    parser.add_argument("--msh2fbx", default=str(DEFAULT_MSH2FBX), help="msh2fbx.exe 路径")
    parser.add_argument("--input", required=True, help="输入目录")
    parser.add_argument("--output", required=True, help="输出目录")
    parser.add_argument("--limit", type=int, default=0, help="限制文件数 (0=全部)")
    parser.add_argument("--workers", type=int, default=1, help="并行数")
    parser.add_argument("--timeout", type=int, default=30, help="单文件超时(秒)")
    parser.add_argument("--dry-run", action="store_true", help="仅列出，不转换")
    args = parser.parse_args()

    msh2fbx = Path(args.msh2fbx)
    if not msh2fbx.is_file():
        print(f"错误: msh2fbx.exe 未找到: {msh2fbx}")
        sys.exit(1)

    input_dir = Path(args.input)
    output_dir = Path(args.output)

    # 收集文件
    print("[1/3] 扫描 MSH 文件...")
    msh_files = sorted(input_dir.rglob("*.mdl-msh*"))
    # 过滤: 仅保留编号格式的 (.mdl-msh000 ~ .mdl-msh999)
    msh_files = [f for f in msh_files if re.search(r"\.mdl-msh\d{3}$", f.name)]
    total = len(msh_files)
    print(f"  找到 {total} 个 MSH 文件")

    if args.limit > 0:
        msh_files = msh_files[:args.limit]
        print(f"  限制为 {args.limit} 个")

    if args.dry_run:
        print("\n[Dry Run] 前10个文件:")
        for f in msh_files[:10]:
            rel = f.relative_to(input_dir)
            out_name = msh_to_fbx_name(f.name)
            out_path = output_dir / rel.parent / out_name
            print(f"  {rel} → {out_path}")
        return

    # 构建任务
    tasks = []
    for f in msh_files:
        rel = f.relative_to(input_dir)
        out_name = msh_to_fbx_name(f.name)
        out_path = output_dir / rel.parent / out_name
        tasks.append((str(msh2fbx), str(f), str(out_path), args.timeout))

    print(f"\n[2/3] 开始转换 {len(tasks)} 个文件...")
    start = time.time()
    success = 0
    fail = 0
    fail_files = []

    if args.workers > 1:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(convert_single, t): t[1] for t in tasks}
            for i, future in enumerate(as_completed(futures), 1):
                in_path, ok, err = future.result()
                if ok:
                    success += 1
                else:
                    fail += 1
                    fail_files.append((in_path, err))
                if i % 100 == 0 or i == len(tasks):
                    elapsed = time.time() - start
                    print(f"  [{i}/{len(tasks)}] 成功:{success} 失败:{fail} 耗时:{elapsed:.0f}s")
    else:
        for i, task in enumerate(tasks, 1):
            in_path, ok, err = convert_single(task)
            if ok: success += 1
            else: fail += 1; fail_files.append((in_path, err))
            if i % 100 == 0 or i == len(tasks):
                print(f"  [{i}/{len(tasks)}] 成功:{success} 失败:{fail} 耗时:{time.time()-start:.0f}s")

    elapsed = time.time() - start
    print(f"\n[3/3] 完成! {success}/{len(tasks)} 成功, {fail} 失败, {elapsed:.1f}s")
    print(f"输出: {output_dir}")

    if fail_files:
        fail_log = output_dir / "_failed.log"
        with open(fail_log, "w", encoding="utf-8") as fh:
            for path, err in fail_files:
                fh.write(f"{path}\t{err}\n")
        print(f"失败列表: {fail_log}")


if __name__ == "__main__":
    main()
