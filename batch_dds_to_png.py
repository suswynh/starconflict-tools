#!/usr/bin/env python3
"""
批量 DDS → PNG 转换脚本
将 tex_universe_check 中所有 DDS 贴图转为 PNG，保持源文件夹层级输出到 tex_png。

使用 DirectXTex texconv.exe (2024) 作为转换引擎。
支持增量续传：已存在且比源文件新的 PNG 会自动跳过。

Usage:
    python batch_dds_to_png.py [--dry-run] [--workers N]
"""
import os
import sys
import subprocess
import argparse
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 路径配置 ────────────────────────────────────────────────
# 项目根目录 = 脚本所在目录的上一级（脚本位于 starconflict-tools/ 下）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_BASE = Path(os.environ.get("DDS_SOURCE", PROJECT_ROOT / "scunpack" / "tex_universe_check"))
TARGET_BASE = Path(os.environ.get("DDS_TARGET", PROJECT_ROOT / "scunpack" / "tex_png"))
TEXCONV = Path(os.environ.get("TEXCONV", PROJECT_ROOT / "DS_Textures" / "RawTex" / "texconv.exe"))

# ── 命令行参数 ──────────────────────────────────────────────
parser = argparse.ArgumentParser(description="批量 DDS → PNG 转换")
parser.add_argument("--dry-run", action="store_true", help="仅列出待转换文件，不实际转换")
parser.add_argument("--workers", type=int, default=4, help="并行线程数 (默认 4)")
args = parser.parse_args()


def collect_tasks():
    """扫描所有 DDS 文件，按源文件夹分组，返回任务列表。"""
    tasks_by_folder = defaultdict(list)
    total = 0
    skip_count = 0

    for dds_path in SOURCE_BASE.rglob("*.dds"):
        rel = dds_path.relative_to(SOURCE_BASE)
        png_path = TARGET_BASE / rel.with_suffix(".png")

        # 增量跳过
        if png_path.exists() and png_path.stat().st_mtime >= dds_path.stat().st_mtime:
            skip_count += 1
            continue

        folder = str(dds_path.parent)
        tasks_by_folder[folder].append(str(dds_path))
        total += 1

    return tasks_by_folder, total, skip_count


def convert_folder(folder, dds_files, dry_run=False):
    """转换一个文件夹内的所有 DDS 文件到对应的 PNG 目录。"""
    folder_path = Path(folder)
    rel_dir = folder_path.relative_to(SOURCE_BASE)
    out_dir = TARGET_BASE / rel_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        return len(dds_files), 0, []

    success = 0
    fail = 0
    failures = []

    # 将 texconv 调用分批，避免命令行过长 (Windows 限制 ~8191 字符)
    # 每个文件路径约 150 字符，一批最多 50 个文件
    batch_size = 50
    for i in range(0, len(dds_files), batch_size):
        batch = dds_files[i:i + batch_size]
        cmd = [str(TEXCONV), "-nologo", "-ft", "png", "-o", str(out_dir), "-y"] + batch

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 分钟超时（大纹理可能较慢）
            )
            if result.returncode == 0:
                success += len(batch)
            else:
                # 部分成功也可能返回非零，逐文件检查
                for f in batch:
                    png_name = Path(f).with_suffix(".png").name
                    png_out = out_dir / png_name
                    if png_out.exists() and png_out.stat().st_size > 0:
                        success += 1
                    else:
                        fail += 1
                        failures.append(f)
        except subprocess.TimeoutExpired:
            fail += len(batch)
            failures.extend(batch)
        except Exception as e:
            fail += len(batch)
            failures.extend(batch)

    return success, fail, failures


def main():
    print("=" * 60)
    print("  DDS → PNG 批量转换")
    print(f"  源目录: {SOURCE_BASE}")
    print(f"  目标目录: {TARGET_BASE}")
    print(f"  转换引擎: {TEXCONV.name}")
    print(f"  并行线程: {args.workers}")
    if args.dry_run:
        print("  *** DRY RUN 模式 — 不实际转换 ***")
    print("=" * 60)

    # 检查 texconv 存在
    if not TEXCONV.is_file():
        print(f"\n错误: 找不到 texconv.exe ({TEXCONV})")
        sys.exit(1)

    # 收集任务
    print("\n扫描 DDS 文件...")
    t0 = time.time()
    tasks_by_folder, total, skip_count = collect_tasks()
    t1 = time.time()

    print(f"  发现 {len(tasks_by_folder)} 个文件夹, {total} 个待转换文件")
    print(f"  已跳过 {skip_count} 个 (已存在且较新)")
    print(f"  扫描耗时: {t1 - t0:.1f}s")

    if total == 0:
        print("\n没有需要转换的文件。")
        return

    if args.dry_run:
        print("\n待转换文件 (前 20 个):")
        count = 0
        for folder, files in tasks_by_folder.items():
            for f in files:
                rel = Path(f).relative_to(SOURCE_BASE)
                print(f"  {rel}")
                count += 1
                if count >= 20:
                    break
            if count >= 20:
                break
        print(f"  ... 共 {total} 个文件")
        return

    # 开始转换
    print(f"\n开始转换 ({args.workers} 线程并行)...")
    print("-" * 60)

    total_success = 0
    total_fail = 0
    all_failures = []
    completed_folders = 0
    total_folders = len(tasks_by_folder)

    t_start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(convert_folder, folder, files, args.dry_run): folder
            for folder, files in tasks_by_folder.items()
        }

        for future in as_completed(futures):
            folder = futures[future]
            try:
                success, fail, failures = future.result()
            except Exception as e:
                print(f"  线程异常 [{folder}]: {e}")
                continue

            total_success += success
            total_fail += fail
            all_failures.extend(failures)
            completed_folders += 1

            # 进度报告
            elapsed = time.time() - t_start
            rate = total_success / elapsed if elapsed > 0 else 0
            pct = completed_folders / total_folders * 100
            print(f"  [{completed_folders}/{total_folders} 文件夹, {pct:.1f}%] "
                  f"成功 {total_success}, 失败 {total_fail}, "
                  f"速率 {rate:.0f} 文件/秒")

    t_end = time.time()
    elapsed = t_end - t_start

    # 结果汇总
    print("\n" + "=" * 60)
    print("  转换完成!")
    print(f"  总耗时: {elapsed:.1f}s ({elapsed/60:.1f} 分钟)")
    print(f"  成功: {total_success}")
    print(f"  失败: {total_fail}")
    print(f"  跳过: {skip_count}")
    print(f"  速率: {total_success/elapsed:.1f} 文件/秒" if elapsed > 0 else "")

    if all_failures:
        print(f"\n  失败文件 (前 20 个):")
        for f in all_failures[:20]:
            rel = Path(f).relative_to(SOURCE_BASE)
            print(f"    {rel}")
        if len(all_failures) > 20:
            print(f"    ... 共 {len(all_failures)} 个")

    print("=" * 60)


if __name__ == "__main__":
    main()
