#!/usr/bin/env python3
"""
Star Conflict .mdl-zonXXX (Model Zone / Trigger Volume) Parser

Parses binary .mdl-zon files into structured data and text sidecar files.
Supports multi-LOD numbering (e.g. .mdl-zon000, .mdl-zon001).

Usage:
    python mdl_zon_parser.py file1.mdl-zon000 file2.mdl-zon001 ...
    python -m mdl_tools.mdl_zon_parser file.mdl-zon000

    import mdl_zon_parser
    data = mdl_zon_parser.parse_mdl_zon("path/to/file.mdl-zon000")
"""

import os
import struct
import sys


def parse_mdl_zon(filepath: str) -> dict:
    """Parse a single .mdl-zon file.

    格式 (部分解码):
      [0x00-0x1F] name block (32 bytes, null-padded)
      [0x20-0x3F] header: 7×uint32 + 2×uint16 + 1×uint32 (counts/metadata)
      [0x40-0x6F] bbox / metadata (48 bytes, 4×float32×3)
      [0x70~]     texture path (null-terminated ASCII)
      之后          transform 矩阵行 + 顶点数据 (16-byte stride, float32×4)

    Returns dict with keys:
        maya_name      - str, null-terminated Maya shape name
        format_version - str, "0x..."
        vertex_count   - int (header field)
        triangle_count - int (header field)
        index_count    - int (header field)
        vertices       - list of (x, y, z) float tuples (actual mesh vertices)
        bbox_verts     - list of (x, y, z) float tuples (bounding box corners)
        face_indices   - list of [i0, i1, i2] (may be empty if implicit strips)
        texture_path   - str or None
        raw_size       - int, file size in bytes
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, "rb") as f:
        data = f.read()

    raw_size = len(data)
    if raw_size < 4:
        raise ValueError(f"File too small ({raw_size} bytes)")

    # --- 1. Maya shape name (32-byte block, null-padded) ---
    name_end = data.find(b"\0", 0, 32)
    if name_end == -1:
        name_end = 32
    maya_name = data[0:name_end].decode("ascii", errors="replace")
    offset = 32  # fixed 32-byte name block

    # --- 2. Header (7 uint32 + 2 uint16 = 32 bytes, from 0x20 to 0x40) ---
    HEADER_SIZE = 7 * 4 + 2 * 2
    _reserved = struct.unpack_from("<I", data, offset)[0]        # 0x20
    unknown1 = struct.unpack_from("<I", data, offset + 4)[0]     # 0x24
    vertex_count = struct.unpack_from("<I", data, offset + 8)[0] # 0x28 (header field, not always mesh verts)
    triangle_count = struct.unpack_from("<I", data, offset + 12)[0] # 0x2C
    unknown2 = struct.unpack_from("<I", data, offset + 16)[0]    # 0x30
    total_idx = struct.unpack_from("<I", data, offset + 20)[0]   # 0x34
    idx_field = struct.unpack_from("<H", data, offset + 24)[0]   # 0x38
    extra_field = struct.unpack_from("<H", data, offset + 26)[0] # 0x3A
    unknown3 = struct.unpack_from("<I", data, offset + 28)[0]    # 0x3C
    offset += HEADER_SIZE  # now at 0x40

    # --- 3. Bounding box corners (4× float32×3 = 48 bytes) ---
    bbox_verts = []
    for _ in range(4):
        if offset + 12 <= raw_size:
            x, y, z = struct.unpack_from("<3f", data, offset)
            bbox_verts.append((x, y, z))
            offset += 12

    # --- 4. Texture path ---
    tex_start = data.find(b"textures", offset)
    texture_path = None
    if tex_start >= 0:
        tex_end = data.find(b"\0", tex_start)
        if tex_end == -1:
            tex_end = raw_size
        texture_path = data[tex_start:tex_end].decode("ascii", errors="replace")
        offset = tex_end + 1

    # --- 5. Find actual mesh vertices ---
    # 顶点数据位于 texture 之后的变换矩阵区域之后。
    # 搜索策略：找到 w≈0 且 xyz 不全为零的连续 float32×4 序列（跳过零填充和变换矩阵）
    vertices = []
    face_indices = []

    def _is_valid_vertex(x, y, z, w):
        """顶点判定：w≈0, 坐标非NaN, 不全为零"""
        if abs(w) > 0.01:
            return False
        if x != x or y != y or z != z:
            return False
        if abs(x) > 1e6 or abs(y) > 1e6 or abs(z) > 1e6:
            return False
        if x == 0.0 and y == 0.0 and z == 0.0:
            return False  # 跳过全零顶点（零填充区域）
        return True

    best_start = None
    best_count = 0
    for scan in range(offset, raw_size - 64, 4):
        count = 0
        pos = scan
        while pos + 16 <= raw_size:
            x, y, z, w = struct.unpack_from("<4f", data, pos)
            if not _is_valid_vertex(x, y, z, w):
                break
            count += 1
            pos += 16
        if count > best_count:
            best_count = count
            best_start = scan

    if best_start and best_count >= 4:
        for i in range(best_count):
            off = best_start + i * 16
            x, y, z, _ = struct.unpack_from("<4f", data, off)
            vertices.append((round(x, 6), round(y, 6), round(z, 6)))

        # 生成 triangle strip 面索引
        for i in range(len(vertices) - 2):
            face_indices.append([i, i + 1, i + 2])

    return {
        "maya_name": maya_name,
        "format_version": f"0x{_reserved:08X}",
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "index_count": idx_field,
        "vertices": vertices,
        "bbox_verts": bbox_verts,
        "face_indices": face_indices,
        "texture_path": texture_path,
        "raw_size": raw_size,
        "total_index_count": total_idx,
        "extra_field": extra_field,
        "unique_vertex_count": len(set(vertices)),
    }


def format_mdl_zon_output(parsed: dict, display_path: str = None) -> str:
    """Render parsed data as a human-readable text block."""
    if display_path is None:
        display_path = parsed.get("filepath", "unknown")

    lines = []
    lines.append("Star Conflict .mdl-zon Trigger Zone")
    lines.append("=" * 37)
    lines.append(f"File: {display_path}")
    lines.append(f"Size: {parsed['raw_size']} bytes")
    lines.append("")
    lines.append(f"Maya Shape: {parsed['maya_name']}")
    lines.append(f"Format Version: {parsed['format_version']}")
    lines.append("")
    lines.append("Header Counts (metadata):")
    lines.append(f"  vertex_count field: {parsed['vertex_count']}")
    lines.append(f"  triangle_count field: {parsed['triangle_count']}")
    lines.append(f"  index_count field: {parsed['index_count']}")
    lines.append(f"  extra_field: {parsed.get('extra_field', 'N/A')}")
    lines.append(f"  total_index_count: {parsed.get('total_index_count', 'N/A')}")
    lines.append("")

    # BBox vertices
    bbox = parsed.get("bbox_verts", [])
    if bbox:
        lines.append("BBox / Metadata Vertices (header区域后4个float3):")
        for i, (x, y, z) in enumerate(bbox):
            lines.append(f"  v[{i}]: ({x:.4f}, {y:.4f}, {z:.4f})")
        lines.append("")

    # Actual mesh vertices
    lines.append(f"Mesh Vertices: {len(parsed['vertices'])} total, {parsed.get('unique_vertex_count', 0)} unique")
    for i, (x, y, z) in enumerate(parsed["vertices"]):
        lines.append(f"  v[{i}]: ({x:.6f}, {y:.6f}, {z:.6f})")
        if i >= 30:
            lines.append(f"  ... ({len(parsed['vertices']) - i - 1} more)")
            break
    lines.append("")

    # Triangles
    faces = parsed["face_indices"]
    lines.append(f"Face Indices (triangle strip, {len(faces)} triangles):")
    for i, tri in enumerate(faces[:20]):
        lines.append(f"  [{tri[0]}, {tri[1]}, {tri[2]}]")
    if len(faces) > 20:
        lines.append(f"  ... ({len(faces) - 20} more)")

    # Texture
    tex = parsed["texture_path"]
    lines.append(f"Texture: {tex if tex else '(none)'}\n")

    return "\n".join(lines)


def write_sidecar(filepath: str, content: str) -> str:
    """Write a .mdl_zon.txt sidecar file beside the source file."""
    sidecar_path = filepath + ".txt"
    with open(sidecar_path, "w", encoding="utf-8") as f:
        f.write(content)
    return sidecar_path


def extract_display_name(filepath: str) -> str:
    """Extract the filename (with multi-LOD suffix) for display."""
    return os.path.basename(filepath)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    exit_code = 0
    for filepath in sys.argv[1:]:
        try:
            parsed = parse_mdl_zon(filepath)
            parsed["filepath"] = filepath
            display_name = extract_display_name(filepath)
            output = format_mdl_zon_output(parsed, display_name)

            print(output)
            print()  # blank separator between files

            sidecar = write_sidecar(filepath, output)
            print(f"[sidecar] {sidecar}")
            print()

        except Exception as e:
            print(f"ERROR parsing {filepath}: {e}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
