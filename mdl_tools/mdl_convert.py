#!/usr/bin/env python3
"""Star Conflict MDL 文件格式统一转换工具。

支持五种格式：mdl-hdr, mdl-geo, mdp, sot, mdl-zon
用法：
    # Solo 模式（单个或多个文件）
    python mdl_convert.py file1.mdl-hdr file2.mdl-geo file3.mdp

    # 批量模式（整个目录）
    python mdl_convert.py --batch <目录路径>

    # 拖拽模式（Windows .bat 调用时自动识别）
    python mdl_convert.py %*

输出：每种格式对应一个 .txt 文本文件，生成在源文件同目录下。
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ── 动态导入各解析器 ──
_TOOLS_DIR = Path(__file__).resolve().parent

_PARSER_MAP = {
    ".mdl-hdr": None,
    ".mdl-geo": None,
    ".mdp": None,
    ".sot": None,
    ".mdl-zon": None,
}

# 扩展名映射：处理 .mdl-zon000 → .mdl-zon 的情况
_EXT_CANONICAL = {
    ".mdl-hdr": ".mdl-hdr",
    ".mdl-geo": ".mdl-geo",
    ".mdp": ".mdp",
    ".sot": ".sot",
}


def _canonical_ext(filepath: str) -> str:
    """将文件名映射到标准扩展名。.mdl-zon000 → .mdl-zon"""
    name = os.path.basename(filepath).lower()
    for key in _EXT_CANONICAL:
        if key in name:
            return key
    # .mdl-zonXXX
    if ".mdl-zon" in name:
        return ".mdl-zon"
    return os.path.splitext(name)[1].lower()


def _load_parsers():
    """延迟导入解析器模块。"""
    parsers = {}
    _dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(_dir))

    parser_modules = {
        ".mdl-hdr": "mdl_hdr_parser",
        ".mdl-geo": "mdl_geo_parser",
        ".mdp": "mdp_parser",
        ".sot": "sot_parser",
        ".mdl-zon": "mdl_zon_parser",
    }

    for ext, mod_name in parser_modules.items():
        try:
            mod = __import__(mod_name)
            fn_name = f"parse_{mod_name.replace('_parser', '')}"
            parse_fn = getattr(mod, fn_name, None)
            if parse_fn is None:
                # fallback: try common naming pattern
                for attr in dir(mod):
                    if attr.startswith("parse_"):
                        parse_fn = getattr(mod, attr)
                        break
            if parse_fn:
                parsers[ext] = parse_fn
        except ImportError:
            pass
    return parsers


def process_file(filepath: str, parsers: dict, quiet: bool = False) -> bool:
    """解析单个文件并写入 .txt 侧车文件。

    Returns:
        True 成功，False 失败。
    """
    ext = _canonical_ext(filepath)
    parse_fn = parsers.get(ext)

    if parse_fn is None:
        if not quiet:
            print(f"  [跳过] 不支持的格式: {filepath}")
        return False

    try:
        result = parse_fn(filepath)
    except Exception as e:
        print(f"  [错误] {filepath}: {e}")
        return False

    # 写入 .txt 侧车文件
    txt_path = filepath + ".txt"
    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            _write_text_output(f, filepath, ext, result)
    except OSError as e:
        print(f"  [错误] 写入失败 {txt_path}: {e}")
        return False

    if not quiet:
        print(f"  [OK] {os.path.basename(filepath)} -> {os.path.basename(txt_path)}")
    return True


def _write_text_output(f, filepath: str, ext: str, result: dict):
    """写人类可读的文本输出。"""
    name = os.path.basename(filepath)
    size = os.path.getsize(filepath)

    f.write(f"Star Conflict {ext} File\n")
    f.write("=" * 60 + "\n")
    f.write(f"File: {name}\n")
    f.write(f"Size: {size} bytes ({size/1024:.1f} KB)\n")
    f.write("\n")

    if ext == ".mdl-hdr":
        bmin = result.get("bbox_min", (0, 0, 0))
        bmax = result.get("bbox_max", (0, 0, 0))
        center = result.get("center", (0, 0, 0))
        _size = tuple(bmax[i] - bmin[i] for i in range(3))
        f.write("Model Header — 包围盒\n")
        f.write("-" * 40 + "\n")
        f.write(f"BBox Min:  ({bmin[0]:.2f}, {bmin[1]:.2f}, {bmin[2]:.2f})\n")
        f.write(f"BBox Max:  ({bmax[0]:.2f}, {bmax[1]:.2f}, {bmax[2]:.2f})\n")
        f.write(f"Size:      ({_size[0]:.2f}, {_size[1]:.2f}, {_size[2]:.2f})\n")
        f.write(f"Center:    ({center[0]:.2f}, {center[1]:.2f}, {center[2]:.2f})\n")
        flags = result.get("flags", "N/A")
        f.write(f"Flags:     {flags}\n")

    elif ext == ".mdl-geo":
        f.write("Simplified Geometry — 简化网格\n")
        f.write("-" * 40 + "\n")
        f.write(f"Version:       {result.get('version', '?')}\n")
        f.write(f"VBytes/VStride: {result.get('vbytes', '?')}/{result.get('vstride', '?')}\n")
        f.write(f"Vertices:      {result.get('vcount', 0)}\n")
        f.write(f"Face Indices:  {result.get('fcount', 0)} ({result.get('fcount', 0)//3} triangles)\n")
        bbox = result.get("bbox", {})
        bmin = bbox.get("min", (0, 0, 0))
        bmax = bbox.get("max", (0, 0, 0))
        f.write(f"\nBBox Min:  ({bmin[0]:.2f}, {bmin[1]:.2f}, {bmin[2]:.2f})\n")
        f.write(f"BBox Max:  ({bmax[0]:.2f}, {bmax[1]:.2f}, {bmax[2]:.2f})\n")

        verts = result.get("_vertices", [])
        sample_n = min(20, len(verts))
        f.write(f"\n前 {sample_n} 个顶点:\n")
        for i in range(sample_n):
            v = verts[i]
            f.write(f"  v[{i}]: ({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f})\n")
        if len(verts) > 20:
            f.write(f"\n后 5 个顶点:\n")
            for i in range(max(20, len(verts) - 5), len(verts)):
                v = verts[i]
                f.write(f"  v[{i}]: ({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f})\n")

    elif ext == ".mdp":
        f.write("Physics Data (TCF) — 碰撞物理\n")
        f.write("-" * 40 + "\n")
        f.write(f"Magic:     {result.get('magic', 'N/A')}\n")
        f.write(f"Version:   {result.get('version', '?')}\n")
        f.write(f"Submeshes: {result.get('submesh_count', 0)}\n")
        f.write(f"Faces:     {result.get('face_count', 0)}\n")
        f.write(f"Vertices:  {result.get('vertex_count', 0)}\n")
        tags = result.get("material_tags", [])
        if tags:
            f.write(f"\nMaterial Tags:\n")
            for tag in tags:
                f.write(f"  {tag}\n")
        strings = result.get("embedded_strings", [])
        if strings:
            f.write(f"\nEmbedded Strings ({len(strings)} 个):\n")
            for s in strings[:30]:
                f.write(f"  {s}\n")

    elif ext == ".sot":
        f.write("Scene Object Table — 场景对象表\n")
        f.write("-" * 40 + "\n")
        f.write(f"Magic:          {result.get('magic', 'N/A')}\n")
        f.write(f"Object Count:   {result.get('object_count', 0)}\n")
        f.write(f"Param:          {result.get('param', 0)}\n")
        f.write(f"Entries Found:  {result.get('entry_count', 0)}\n")
        f.write(f"Blocks:         {result.get('block_count', 0)}\n")
        entries = result.get("entries", [])
        for i, entry in enumerate(entries[:20]):
            f.write(f"\nEntry #{i+1} @ offset {entry.get('offset', '?')}:\n")
            bbox = entry.get("bbox_param", ())
            f.write(f"  Transform: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})\n")
            flags = entry.get("flags", [])
            f.write(f"  Flags: {flags}\n")
            children = entry.get("children", [])
            nonzero = [c for c in children if c != 0]
            f.write(f"  Child Indices: {children} ({len(nonzero)} non-zero)\n")

    elif ext == ".mdl-zon":
        f.write("Trigger Zone — 触发区域\n")
        f.write("-" * 40 + "\n")
        f.write(f"Maya Shape:   {result.get('maya_name', 'N/A')}\n")
        f.write(f"Version:      {result.get('format_version', 'N/A')}\n")
        f.write(f"Vertices:     {result.get('vertex_count', 0)}\n")
        f.write(f"Triangles:    {result.get('triangle_count', 0)}\n")
        f.write(f"Indices:      {result.get('index_count', 0)}\n")
        f.write(f"Texture:      {result.get('texture_path', 'N/A')}\n")
        verts = result.get("vertices", [])
        if verts:
            f.write(f"\nVertices:\n")
            for i, v in enumerate(verts):
                f.write(f"  v[{i}]: ({v[0]:.4f}, {v[1]:.4f}, {v[2]:.4f})\n")
        faces = result.get("face_indices", [])
        if faces:
            f.write(f"\nTriangles:\n")
            for i, tri in enumerate(faces):
                f.write(f"  [{tri[0]}, {tri[1]}, {tri[2]}]\n")

    f.write("\n")


def batch_process(directory: str, parsers: dict, quiet: bool = False) -> tuple:
    """批量处理目录下所有支持的 MDL 文件。

    Returns:
        (success_count, fail_count)
    """
    dirpath = Path(directory)
    if not dirpath.is_dir():
        print(f"[错误] 目录不存在: {directory}")
        return (0, 0)

    # 收集所有支持格式的文件
    extensions = tuple(_PARSER_MAP.keys())
    # 对于 .mdl-zon，匹配 .mdl-zon*
    all_files = []
    for ext in extensions:
        if ext == ".mdl-zon":
            all_files.extend(dirpath.rglob(f"*{ext}*"))
        else:
            all_files.extend(dirpath.rglob(f"*{ext}"))

    # 去重排序
    all_files = sorted(set(all_files), key=lambda p: (str(p).lower()))

    if not all_files:
        print(f"[信息] 目录中未找到支持的 MDL 文件: {directory}")
        return (0, 0)

    print(f"\n{'='*60}")
    print(f"批量转换: {directory}")
    print(f"找到 {len(all_files)} 个文件")
    print(f"{'='*60}")

    success = fail = 0
    for i, fpath in enumerate(all_files):
        print(f"[{i+1}/{len(all_files)}] {fpath.name}")
        if process_file(str(fpath), parsers, quiet=True):
            success += 1
        else:
            fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败")
    return (success, fail)


def main():
    parser = argparse.ArgumentParser(
        description="Star Conflict MDL 文件格式转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python mdl_convert.py model.mdl-hdr              # 单个文件
  python mdl_convert.py a.mdl-geo b.mdp c.sot      # 多个文件
  python mdl_convert.py --batch ./mapskit/mainmenu  # 批量目录
        """,
    )
    parser.add_argument(
        "files", nargs="*",
        help="要转换的 MDL 文件（一个或多个）",
    )
    parser.add_argument(
        "--batch", "-b", metavar="DIR",
        help="批量模式：转换整个目录下的所有 MDL 文件",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="额外输出 JSON 摘要到 stdout（调试用）",
    )

    args = parser.parse_args()

    # 加载解析器
    parsers = _load_parsers()
    if not parsers:
        print("[错误] 未找到任何解析器模块。请确保 mdl_tools/ 目录下有各 parser 文件。")
        sys.exit(1)

    available = ", ".join(sorted(parsers.keys()))
    print(f"已加载解析器: {available}\n")

    # 批量模式
    if args.batch:
        batch_process(args.batch, parsers)
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
        if process_file(filepath, parsers):
            success += 1
        else:
            fail += 1

    print(f"\n完成: {success} 成功, {fail} 失败")


if __name__ == "__main__":
    main()
