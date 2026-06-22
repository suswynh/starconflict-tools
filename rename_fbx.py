# ============================================================================
# FBX 批量重命名脚本
# plasma_gun_mod1.mdl-msh000.fbx → plasma_gun_mod1000.fbx
# 用法（预演）：
#   python rename_fbx.py --dir fbx_output --dry-run
# 用法（实际）：
#   python rename_fbx.py --dir fbx_output
# ============================================================================
import os, sys, re, argparse
from pathlib import Path

def rename_fbx_files(root_dir, dry_run=True):
    """递归重命名所有 .mdl-msh*.fbx → 纯编号.fbx"""
    count = 0
    for dirpath, _, filenames in os.walk(root_dir):
        for f in filenames:
            m = re.match(r'^(.+)\.mdl-msh(\d+)\.fbx$', f)
            if m:
                new_name = m.group(1) + m.group(2) + '.fbx'
                old_path = os.path.join(dirpath, f)
                new_path = os.path.join(dirpath, new_name)

                if dry_run:
                    print(f"  {f}  →  {new_name}")
                else:
                    if os.path.exists(new_path):
                        print(f"  跳过（已存在）: {new_name}")
                        continue
                    os.rename(old_path, new_path)
                count += 1

    print(f"\n{'[预演] ' if dry_run else ''}共 {count} 个文件")
    return count

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='FBX 批量重命名')
    parser.add_argument('--dir', default='.', help='目标目录')
    parser.add_argument('--dry-run', action='store_true', help='预演模式')
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        print(f"目录不存在: {args.dir}")
        sys.exit(1)

    rename_fbx_files(args.dir, dry_run=args.dry_run)
