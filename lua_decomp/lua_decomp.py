#!/usr/bin/env python3
"""Star Conflict LuaJIT 字节码反编译工具。

将 LuaJIT 2.0 字节码 (.lua 二进制文件) 反编译为可读的 Lua 源码。

依赖: ljd (LuaJIT Decompiler) — pip install ljd

用法：
    # Solo 模式（单个或多个文件）
    python lua_decomp.py file1.lua file2.lua

    # 批量模式（整个目录）
    python lua_decomp.py --batch <目录路径> [--output <输出目录>]

    # 批量模式（输出到源文件同目录，默认）
    python lua_decomp.py --batch <目录路径>

输出：反编译后的 .lua 源码文件。
"""

import argparse
import os
import sys
from pathlib import Path

try:
    import ljd.rawdump.parser as _parser
    import ljd.tools as _tools
    import ljd.lua.writer as _writer
    LJD_AVAILABLE = True
except ImportError:
    LJD_AVAILABLE = False


# ── LuaJIT bytecode magic ──
LUAJIT_MAGIC = b'\x1b\x4c\x4a'  # ESC L J


def is_luajit_bytecode(filepath: str) -> bool:
    """检查文件是否为 LuaJIT 字节码。"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(4)
        return header[:3] == LUAJIT_MAGIC
    except (OSError, IOError):
        return False


def decompile_file(filepath: str, output_path: str = None) -> bool:
    """反编译单个 LuaJIT 字节码文件。

    Args:
        filepath: 源字节码文件路径。
        output_path: 输出 .lua 文件路径。若为 None，则输出到同目录同名文件。

    Returns:
        True 成功，False 失败。
    """
    if not LJD_AVAILABLE:
        print(f"  [错误] ljd 库未安装。请运行: pip install ljd")
        return False

    if output_path is None:
        p = Path(filepath)
        # 单文件模式：输出到同目录，文件名为 <原名>_decompiled.lua
        stem = p.stem  # "bindings" from "bindings.lua"
        output_path = str(p.parent / f"{stem}_decompiled.lua")

    try:
        # 解析字节码 → AST
        header, prototype = _parser.parse(filepath)

        # AST → Lua 源码
        ast = _tools.decompile(header, prototype)

        # 写入输出
        with open(output_path, 'w', encoding='utf-8') as f:
            _writer.write(f, ast)

        return True

    except Exception as e:
        print(f"  [错误] 反编译失败: {e}")
        return False


def batch_decompile(input_dir: str, output_dir: str = None) -> tuple:
    """批量反编译目录下所有 LuaJIT 字节码文件。

    Args:
        input_dir: 输入目录路径。
        output_dir: 输出目录。若为 None，则在同目录下创建 scripts_decompiled 子目录。

    Returns:
        (success_count, fail_count)
    """
    inpath = Path(input_dir)
    if not inpath.is_dir():
        print(f"[错误] 目录不存在: {input_dir}")
        return (0, 0)

    if output_dir is None:
        output_dir = str(inpath.parent / (inpath.name + '_decompiled'))

    outpath = Path(output_dir)
    outpath.mkdir(parents=True, exist_ok=True)

    # 收集所有 .lua 文件
    lua_files = list(inpath.rglob('*.lua'))
    # 过滤掉已经是纯文本的文件
    bytecode_files = [f for f in lua_files if is_luajit_bytecode(str(f))]

    if not bytecode_files:
        print(f"[信息] 目录中未找到 LuaJIT 字节码文件: {input_dir}")
        print(f"  (共找到 {len(lua_files)} 个 .lua 文件，其中 0 个是字节码)")
        return (0, 0)

    print(f"\n{'='*60}")
    print(f"批量反编译: {input_dir}")
    print(f"找到 {len(bytecode_files)} 个 LuaJIT 字节码文件")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")

    success = fail = 0
    for i, fpath in enumerate(bytecode_files):
        rel_path = fpath.relative_to(inpath)
        dest = outpath / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)

        print(f"[{i+1}/{len(bytecode_files)}] {rel_path}")
        if decompile_file(str(fpath), str(dest)):
            success += 1
            print(f"  -> {dest.name}")
        else:
            fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败, {len(lua_files) - len(bytecode_files)} 跳过(非字节码)")
    return (success, fail)


def main():
    parser = argparse.ArgumentParser(
        description="Star Conflict LuaJIT 字节码反编译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python lua_decomp.py bindings.lua              # 单个文件
  python lua_decomp.py a.lua b.lua c.lua         # 多个文件
  python lua_decomp.py --batch ./scripts          # 批量目录（输出到 scripts_decompiled/）
  python lua_decomp.py --batch ./scripts -o ./out # 指定输出目录
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="要反编译的 LuaJIT 字节码文件（一个或多个）",
    )
    parser.add_argument(
        "--batch", "-b", metavar="DIR",
        help="批量模式：反编译整个目录下的所有 LuaJIT 字节码文件",
    )
    parser.add_argument(
        "--output", "-o", metavar="DIR",
        help="输出目录（仅批量模式）。默认：<输入目录>_decompiled/",
    )

    args = parser.parse_args()

    if not LJD_AVAILABLE:
        print("=" * 60)
        print("错误: ljd (LuaJIT Decompiler) 未安装")
        print("=" * 60)
        print("请运行以下命令安装:")
        print("  pip install ljd")
        print()
        print("或从源码安装:")
        print("  git clone https://github.com/NightNord/ljd.git")
        print("  cd ljd && python setup.py install")
        sys.exit(1)

    # 批量模式
    if args.batch:
        batch_decompile(args.batch, args.output)
        return

    # 文件模式
    if not args.files:
        parser.print_help()
        sys.exit(1)

    success = fail = 0
    for filepath in args.files:
        if not os.path.isfile(filepath):
            print(f"  [警告] 文件不存在: {filepath}")
            fail += 1
            continue

        if not is_luajit_bytecode(filepath):
            print(f"  [跳过] 非 LuaJIT 字节码: {filepath}")
            fail += 1
            continue

        print(f"反编译: {filepath}")
        if decompile_file(filepath):
            success += 1
            print(f"  [OK]")
        else:
            fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败")


if __name__ == "__main__":
    main()
