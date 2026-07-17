"""
Star Conflict decals.dat 解析器。

支持两种 decals.dat 格式，自动检测：

  1. gamedata/decals.dat — 文本格式（Hammer Engine 材质描述）
  2. levels/*/decals.dat — 二进制格式（贴花实例放置数据）

─────────────────────────────────────────────────────────────────────
二进制格式 (levels/*/decals.dat, Little Endian)
─────────────────────────────────────────────────────────────────────
  偏移      大小    内容
  0x00      4       version (uint32, 始终为 5)
  0x04      4       count (uint32, 贴花实例数)
  0x08      8       padding (零填充)
  0x10      —       记录数组 (每条 96 字节)

  每条记录 (96 字节):
  偏移      大小    内容
  0x00      12      position: float32×3 (x, y, z)  — Hammer Y-up 世界坐标
  0x0C      4       padding
  0x10      16      rotation: float32×4 (x, y, z, w) — 四元数
  0x20      12      direction: float32×3 — 法向/朝向向量
  0x2C      4       padding
  0x30      12      scale: float32×3 (x, y, z)
  0x3C      4       padding
  0x40      N       texture name: null-terminated ASCII
  —         —       padding 填充至 96 字节
  (末尾 0x50~0x5F 可能含额外 float: uv_scale, uint32: flags)

─────────────────────────────────────────────────────────────────────
文本格式 (gamedata/decals.dat)
─────────────────────────────────────────────────────────────────────
  name {
      diffuse "path"
      normal "path"
      glow "path"
      spec "path"
      uv ( u1 u2 v1 v2 )
      blend mode
      material type
      spec_color ( r g b )
      gloss value
  }
"""

import os
import re
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# ── 二进制格式常量 ──────────────────────────────────────────────────

EXPECTED_VERSION = 5
RECORD_SIZE = 96
HEADER_SIZE = 16        # 4 (version) + 4 (count) + 8 (padding)
STRING_OFFSET = 0x40    # 纹理名字符串在记录内的偏移
POS_OFFSET   = 0x00
ROT_OFFSET   = 0x10
DIR_OFFSET   = 0x20     # 法向/朝向向量
SCALE_OFFSET = 0x30

# ── 格式检测 ──────────────────────────────────────────────────────

def _is_binary_format(filepath: str) -> bool:
    """检测 decals.dat 是否为二进制格式（非文本 gamedata 格式）。"""
    with open(filepath, 'rb') as f:
        header = f.read(4)
    if len(header) < 4:
        return False
    version = struct.unpack('<I', header)[0]
    # 二进制格式 version 字段为 5
    # 文本格式以 ASCII 字母开头（'a' = 0x61）
    return version == EXPECTED_VERSION


# ── 二进制格式解析 ─────────────────────────────────────────────────

def _parse_binary(filepath: str) -> Dict[str, Any]:
    """解析 levels/*/decals.dat 二进制文件。"""
    with open(filepath, 'rb') as f:
        data = f.read()

    file_size = len(data)
    if file_size < HEADER_SIZE:
        raise ValueError(
            f"文件太小 ({file_size} bytes)，至少需要 {HEADER_SIZE} bytes"
        )

    # 头部
    version, count = struct.unpack_from('<II', data, 0)

    if version != EXPECTED_VERSION:
        raise ValueError(
            f"不支持的版本号 {version}，期望 {EXPECTED_VERSION}"
        )

    if count == 0:
        return {
            "format": "binary",
            "version": version,
            "count": 0,
            "records": [],
        }

    # 验证文件大小
    expected_size = HEADER_SIZE + count * RECORD_SIZE
    if file_size < expected_size:
        raise ValueError(
            f"文件大小 {file_size} 不足以容纳 {count} 条记录 "
            f"(期望 {expected_size} bytes)"
        )

    records = []
    for i in range(count):
        offset = HEADER_SIZE + i * RECORD_SIZE

        # position (3 floats + 4 bytes padding)
        px, py, pz = struct.unpack_from('<fff', data, offset + POS_OFFSET)

        # rotation quaternion (4 floats)
        qx, qy, qz, qw = struct.unpack_from('<ffff', data, offset + ROT_OFFSET)

        # direction / normal vector (3 floats + 4 bytes padding)
        dx, dy, dz = struct.unpack_from('<fff', data, offset + DIR_OFFSET)

        # scale (3 floats + 4 bytes padding)
        sx, sy, sz = struct.unpack_from('<fff', data, offset + SCALE_OFFSET)

        # texture name (null-terminated ASCII)
        string_start = offset + STRING_OFFSET
        string_end = string_start
        record_end = offset + RECORD_SIZE
        while string_end < record_end and data[string_end] != 0:
            string_end += 1
        texture = data[string_start:string_end].decode("ascii", errors="replace")

        records.append({
            "index": i,
            "texture": texture,
            "position": (round(px, 3), round(py, 3), round(pz, 3)),
            "rotation": (round(qx, 6), round(qy, 6), round(qz, 6), round(qw, 6)),
            "direction": (round(dx, 6), round(dy, 6), round(dz, 6)),
            "scale": (round(sx, 3), round(sy, 3), round(sz, 3)),
        })

    return {
        "format": "binary",
        "version": version,
        "count": count,
        "records": records,
    }


# ── 文本格式解析 ──────────────────────────────────────────────────

# 匹配: name { ... }
_BLOCK_RE = re.compile(
    r'^(\w[^\s{]*)\s*\{', re.MULTILINE
)

# 匹配: key "value"
_KEY_STRING_RE = re.compile(r'^(\w+)\s+"([^"]*)"')

# 匹配: key ( n1 n2 ... )
_KEY_VEC_RE = re.compile(r'^(\w+)\s*\(\s*([\d.\-eE\s]+)\s*\)')

# 匹配: key value (裸标识符)
_KEY_BARE_RE = re.compile(r'^(\w+)\s+([\w.\-]+)')


def _parse_text(filepath: str) -> Dict[str, Any]:
    """解析 gamedata/decals.dat 文本格式（材质描述文件）。"""
    with open(filepath, 'rb') as f:
        raw = f.read()

    # 尝试 UTF-8 解码，失败则用 latin-1
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")

    records = []
    pos = 0

    while pos < len(text):
        # 跳过空白和空行
        m_blank = re.match(r'\s*', text[pos:])
        if m_blank:
            pos += m_blank.end()
            if pos >= len(text):
                break

        # 匹配 name {
        m_block = _BLOCK_RE.search(text, pos)
        if not m_block or m_block.start() != pos:
            # 跳过无法识别的行
            eol = text.find('\n', pos)
            if eol == -1:
                break
            pos = eol + 1
            continue

        name = m_block.group(1)
        pos = m_block.end()

        props = {"name": name}
        nesting = 1

        # 读取块内容直到匹配的 }
        while nesting > 0 and pos < len(text):
            # 跳过空白
            m_ws = re.match(r'\s+', text[pos:])
            if m_ws:
                pos += m_ws.end()

            if pos >= len(text):
                break

            ch = text[pos]

            if ch == '{':
                nesting += 1
                pos += 1
                continue
            elif ch == '}':
                nesting -= 1
                pos += 1
                if nesting == 0:
                    break
                continue
            elif ch == '#':
                # 跳过注释行（如果存在）
                eol = text.find('\n', pos)
                pos = eol + 1 if eol != -1 else len(text)
                continue

            # 尝试匹配 key "value"
            remaining = text[pos:]
            m_str = _KEY_STRING_RE.match(remaining)
            if m_str:
                props[m_str.group(1)] = m_str.group(2)
                pos += m_str.end()
                continue

            # 尝试匹配 key ( n1 n2 ... )
            m_vec = _KEY_VEC_RE.match(remaining)
            if m_vec:
                key = m_vec.group(1)
                values = [float(x) for x in m_vec.group(2).split()]
                props[key] = tuple(values)
                pos += m_vec.end()
                continue

            # 尝试匹配 key value (裸标识符/数字)
            m_bare = _KEY_BARE_RE.match(remaining)
            if m_bare:
                key = m_bare.group(1)
                val = m_bare.group(2)
                # 尝试转为数字
                try:
                    val = int(val)
                except ValueError:
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                props[key] = val
                pos += m_bare.end()
                continue

            # 无法匹配，跳过当前字符
            pos += 1

        records.append(props)

    return {
        "format": "text",
        "count": len(records),
        "records": records,
    }


# ── 主解析入口 ────────────────────────────────────────────────────

def parse_decals(filepath: str) -> Dict[str, Any]:
    """解析 Star Conflict decals.dat 文件，自动检测二进制或文本格式。

    Args:
        filepath: decals.dat 文件的绝对或相对路径。

    Returns:
        dict:
            二进制格式:
                format: "binary"
                version: int
                count: int
                records: list of dict
                    { index, texture, position, rotation, scale }

            文本格式:
                format: "text"
                count: int
                records: list of dict
                    { name, diffuse, normal, glow, spec, uv, blend, ... }

    Raises:
        FileNotFoundError: 文件不存在。
        ValueError: 格式无法识别或数据损坏。
    """
    filepath = str(Path(filepath).resolve())

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        return {"format": "unknown", "count": 0, "records": []}

    if _is_binary_format(filepath):
        return _parse_binary(filepath)
    else:
        return _parse_text(filepath)


# ── 命令行入口 ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("用法: python decals_parser.py <decals.dat> [--json]")
        print()
        print("  自动检测并解析 gamedata/decals.dat (文本格式)")
        print("  或 levels/*/decals.dat (二进制格式)")
        print()
        print("选项:")
        print("  --json    输出 JSON 格式（默认输出可读文本）")
        sys.exit(1)

    filepath = sys.argv[1]
    use_json = "--json" in sys.argv

    try:
        result = parse_decals(filepath)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)

    if use_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        name = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        fmt = result.get("format", "unknown")

        print(f"Star Conflict decals.dat")
        print("=" * 60)
        print(f"文件:       {name}")
        print(f"大小:       {size} bytes ({size/1024:.1f} KB)")
        print(f"格式:       {fmt}")

        if fmt == "binary":
            print(f"版本:       {result.get('version', '?')}")
        print(f"条目数:     {result.get('count', 0)}")
        print()

        records = result.get("records", [])

        if fmt == "binary":
            # 二进制: 列表视图
            print(f"{'#':>4}  {'纹理名称':<32} {'位置 (x, y, z)':<38} {'缩放 (x, y, z)':<32}")
            print("-" * 110)
            for r in records:
                texture = r["texture"][:30] if r["texture"] else "(空)"
                pos = f"({r['position'][0]:.2f}, {r['position'][1]:.2f}, {r['position'][2]:.2f})"
                scl = f"({r['scale'][0]:.2f}, {r['scale'][1]:.2f}, {r['scale'][2]:.2f})"
                print(f"{r['index']:4}  {texture:<32} {pos:<38} {scl:<32}")

            # 方向向量 + 四元数汇总
            print()
            print(f"{'#':>4}  {'方向 (dx, dy, dz)':<40} {'四元数 (qx, qy, qz, qw)':<52}")
            print("-" * 100)
            for r in records:
                d = r['direction']
                rot = r['rotation']
                d_str = f"({d[0]:+.4f}, {d[1]:+.4f}, {d[2]:+.4f})"
                r_str = f"({rot[0]:+.4f}, {rot[1]:+.4f}, {rot[2]:+.4f}, {rot[3]:+.4f})"
                print(f"{r['index']:4}  {d_str:<40} {r_str:<52}")

        elif fmt == "text":
            # 文本: 键值对视图
            for i, mat in enumerate(records):
                print(f"[{i}] {mat.get('name', '(无名称)')}")
                for key, val in mat.items():
                    if key == "name":
                        continue
                    if isinstance(val, tuple):
                        print(f"      {key}: ({', '.join(str(v) for v in val)})")
                    else:
                        print(f"      {key}: {val}")
                print()
