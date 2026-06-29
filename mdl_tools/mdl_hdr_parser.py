"""Star Conflict .mdl-hdr 模型头文件 / 包围盒解析器。

.mdl-hdr 文件格式 (80 字节, 小端序):
  偏移 0x00: float32x3 bbox_min (x, y, z)     —— 包围盒最小值
  偏移 0x0C: float32 填充 (=0)
  偏移 0x10: float32x3 bbox_max (x, y, z)     —— 包围盒最大值
  偏移 0x1C: float32 填充 (=0)
  偏移 0x20: 6× float32 零 (保留区域, 可能用于材质变换槽位)
  偏移 0x38: uint32 标志位 (位域或子模型计数)
  偏移 0x3C: uint32 0
  偏移 0x40: uint32 0xFFFFFFFF (终止标记)
  偏移 0x44: 3× uint32 零 (对齐填充)
"""

import struct
import os
import sys
import json
from pathlib import Path

# struct 格式: 3f + 4字节填充 + 3f + 4字节填充 + 6f (保留) + 4×I + 3I(填充)
_STRUCT_FMT = '<3f 4x 3f 4x 6f I I I 3I'
_EXPECTED_SIZE = struct.calcsize(_STRUCT_FMT)  # 80 字节


def parse_mdl_hdr(filepath: str) -> dict:
    """Parse a Star Conflict .mdl-hdr binary file.

    Args:
        filepath: Absolute or relative path to the .mdl-hdr file.

    Returns:
        dict with keys:
            bbox_min: (x, y, z) float tuple — bounding box minimum.
            bbox_max: (x, y, z) float tuple — bounding box maximum.
            size:     (dx, dy, dz) float tuple — bbox dimensions.
            center:   (cx, cy, cz) float tuple — bbox centroid.
            flags:    str e.g. '0x00001CF0' — flags / sub-model count.
            raw_size: int — file size in bytes (always 80).

    Raises:
        FileNotFoundError: ``filepath`` does not exist.
        ValueError: File is not exactly 80 bytes or binary layout is corrupt.
    """
    filepath = Path(filepath)

    if not filepath.is_file():
        raise FileNotFoundError(f"File not found: {filepath}")

    raw_size = filepath.stat().st_size
    if raw_size != _EXPECTED_SIZE:
        raise ValueError(
            f"Expected {_EXPECTED_SIZE} bytes, got {raw_size} bytes: {filepath.name}"
        )

    with open(filepath, 'rb') as fh:
        data = fh.read()

    try:
        vals = struct.unpack(_STRUCT_FMT, data)
    except struct.error as exc:
        raise ValueError(f"Corrupt binary data in {filepath.name}: {exc}") from exc

    # vals 结构:
    #   [0:3]  → bbox_min (3 floats)
    #   [3:6]  → bbox_max (3 floats)
    #   [6:12] → 6 reserved floats
    #   [12]   → flags uint32
    #   [13]   → uint32 0
    #   [14]   → uint32 0xFFFFFFFF
    #   [15:18] → uint32 padding zeros

    bbox_min = (vals[0], vals[1], vals[2])
    bbox_max = (vals[3], vals[4], vals[5])
    flags_raw = vals[12]

    size = (
        bbox_max[0] - bbox_min[0],
        bbox_max[1] - bbox_min[1],
        bbox_max[2] - bbox_min[2],
    )
    center = (
        (bbox_min[0] + bbox_max[0]) / 2.0,
        (bbox_min[1] + bbox_max[1]) / 2.0,
        (bbox_min[2] + bbox_max[2]) / 2.0,
    )

    return {
        'bbox_min': bbox_min,
        'bbox_max': bbox_max,
        'size': size,
        'center': center,
        'flags': f'0x{flags_raw:08X}',
        'raw_size': raw_size,
    }


# ---------------------------------------------------------------------------
# 文本输出辅助
# ---------------------------------------------------------------------------

def _format_vec3(label: str, vec: tuple) -> str:
    """返回带标签的三元组字符串，每项保留两位小数。"""
    return f"  {label}: ({vec[0]:.2f}, {vec[1]:.2f}, {vec[2]:.2f})"


def format_result(filepath: str, result: dict) -> str:
    """将解析结果格式化为人类可读的文本块（用于 .txt 附属文件）。"""
    lines = [
        "Star Conflict .mdl-hdr Model Header",
        "=====================================",
        f"File: {Path(filepath).name}",
        f"Size: {result['raw_size']} bytes",
        "",
        "Bounding Box:",
        _format_vec3("Min", result['bbox_min']),
        _format_vec3("Max", result['bbox_max']),
        _format_vec3("Size", result['size']),
        _format_vec3("Center", result['center']),
        "",
        f"Flags: {result['flags']}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def main() -> None:
    """命令行入口：解析一个或多个 .mdl-hdr 文件，输出 JSON 到 stdout，
    同时在与源文件相同目录下生成 .mdl_hdr.txt 附属文件。"""
    if len(sys.argv) < 2:
        print(
            "Usage: python mdl_hdr_parser.py <file1.mdl-hdr> [file2.mdl-hdr ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    exit_code = 0

    for arg in sys.argv[1:]:
        fp = Path(arg)
        try:
            result = parse_mdl_hdr(str(fp))
            result['file'] = fp.name

            # JSON 输出到 stdout
            print(json.dumps(result, indent=2, default=str))

            # 写入 .mdl_hdr.txt 附属文件（位于同一目录）
            txt_path = fp.with_suffix(fp.suffix + '.txt')
            txt_content = format_result(str(fp), result)
            with open(txt_path, 'w', encoding='utf-8') as fh:
                fh.write(txt_content)
            print(f"  -> wrote {txt_path.name}", file=sys.stderr)

        except (FileNotFoundError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            exit_code = 1
        except Exception as exc:
            print(f"ERROR [{fp.name}]: {exc}", file=sys.stderr)
            exit_code = 1

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
