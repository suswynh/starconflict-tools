#!/usr/bin/env python3
"""
Star Conflict .sot (Scene Object Table) binary parser.

Parses OT02-format Scene Object Table files into structured data and
generates human-readable .sot.txt sidecar files.

Usage:
    python sot_parser.py <file.sot> [--stdout]

Or import:
    from sot_parser import parse_sot
    result = parse_sot("path/to/file.sot")
"""

import struct
import sys
import os
from typing import List, Dict, Any


def parse_sot(filepath: str) -> dict:
    """Parse a Star Conflict .sot binary file.

    Returns a dict with keys:
        magic          - 4-byte magic string ("OT02")
        object_count   - uint32 at 0x04
        param          - uint32 at 0x08
        entries        - list of parsed entry dicts
        entry_count    - number of detected entries
        block_count    - number of non-zero blocks
        block_gaps     - list of gap sizes between blocks (bytes)
        file_size      - total file size in bytes
    """
    with open(filepath, "rb") as f:
        data = f.read()

    file_size = len(data)

    if len(data) < 0x80:
        raise ValueError(f"File too small ({len(data)} bytes); minimum 0x80 required.")

    # --- Header ---
    magic = data[0:4].decode("ascii", errors="replace")
    object_count = struct.unpack_from("<I", data, 0x04)[0]
    param = struct.unpack_from("<I", data, 0x08)[0]
    # 0x0C – 0x7F: reserved zeros (29x uint32)

    # --- Scan for 64-byte entries starting at offset 0x80 (128) ---
    # Note: user says first entry at 0x40, but header reserved is 0x0C + 116 = 0x80.
    # We use 0x40 as the start per the spec, but guard against tiny files either way.
    scan_start = 0x40
    entry_size = 64
    entries = []
    entry_offsets = []

    for offset in range(scan_start, file_size - entry_size + 1, entry_size):
        chunk = data[offset:offset + entry_size]
        if chunk == b"\x00" * entry_size:
            continue
        entry = _parse_entry(chunk, offset)
        entries.append(entry)
        entry_offsets.append(offset)

    # --- Block grouping ---
    # A block is a run of consecutive entries with no large zero gap between them.
    # Gap threshold: at least one full entry (64 bytes) of zeros separates blocks.
    # The user mentions gaps of ~192 bytes between blocks.
    GAP_THRESHOLD = 64

    blocks = []
    block_gaps = []
    if entry_offsets:
        current_block = [entries[0]]
        for i in range(1, len(entry_offsets)):
            gap = entry_offsets[i] - (entry_offsets[i - 1] + entry_size)
            if gap > GAP_THRESHOLD:
                blocks.append(current_block)
                block_gaps.append(gap)
                current_block = [entries[i]]
            else:
                current_block.append(entries[i])
        blocks.append(current_block)

    return {
        "magic": magic,
        "object_count": object_count,
        "param": param,
        "entries": entries,
        "entry_count": len(entries),
        "block_count": len(blocks),
        "block_gaps": block_gaps,
        "file_size": file_size,
    }


def _parse_entry(chunk: bytes, offset: int) -> dict:
    """Parse a single 64-byte entry chunk."""
    # Bytes 0-15:  4x float32
    bbox_param = struct.unpack_from("<ffff", chunk, 0)

    # Bytes 16-23: 8x uint8 flags
    flags = list(chunk[16:24])

    # Bytes 24-27: uint32 zero separator
    separator = struct.unpack_from("<I", chunk, 24)[0]

    # Bytes 28-31: padding zeros (4 bytes before child indices)
    # Bytes 32-63: 8x uint32 child indices
    children = list(struct.unpack_from("<8I", chunk, 32))

    # Count non-zero children
    non_zero_children = sum(1 for c in children if c != 0)

    return {
        "offset": offset,
        "bbox_param": bbox_param,
        "flags": flags,
        "separator": separator,
        "children": children,
        "non_zero_children": non_zero_children,
    }


def format_output(result: dict, filepath: str) -> str:
    """Format parse result as human-readable text report."""
    lines = []
    lines.append("Star Conflict .sot Scene Object Table")
    lines.append("=======================================")
    lines.append(f"File: {os.path.basename(filepath)}")
    lines.append(f"Size: {result['file_size']} bytes")
    lines.append("")
    lines.append("Header:")
    lines.append(f"  Magic: {result['magic']}")
    lines.append(f"  Object Count: {result['object_count']}")
    lines.append(f"  Param: {result['param']}")
    lines.append(f"  Detected Entries: {result['entry_count']}")
    lines.append(f"  Blocks: {result['block_count']}")
    if result["block_gaps"]:
        gaps_str = ", ".join(str(g) for g in result["block_gaps"])
        lines.append(f"  Block Gap Sizes (bytes): [{gaps_str}]")
    lines.append("")

    for i, entry in enumerate(result["entries"], 1):
        bbox = entry["bbox_param"]
        lines.append(f"Entry #{i} @ 0x{entry['offset']:04X}:")
        lines.append(
            f"  BBox/Transform: ({bbox[0]:.2f}, {bbox[1]:.2f}, {bbox[2]:.2f}, {bbox[3]:.2f})"
        )
        lines.append(f"  Flags: {entry['flags']}")
        lines.append(f"  Child Indices: {entry['children']}")
        lines.append(f"  Children (non-zero): {entry['non_zero_children']}")
        lines.append("")

    return "\n".join(lines)


def _write_sidecar(filepath: str, result: dict) -> str:
    """Write .sot.txt sidecar file next to the original file. Returns the output path."""
    out_path = filepath + ".txt"
    text = format_output(result, filepath)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python sot_parser.py <file.sot> [--stdout]", file=sys.stderr)
        sys.exit(1)

    filepath = sys.argv[1]
    stdout_mode = "--stdout" in sys.argv

    if not os.path.isfile(filepath):
        print(f"Error: file not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    result = parse_sot(filepath)

    if stdout_mode:
        print(format_output(result, filepath))
    else:
        out_path = _write_sidecar(filepath, result)
        print(f"Parsed {result['entry_count']} entries in {result['block_count']} block(s).")
        print(f"Sidecar written: {out_path}")


if __name__ == "__main__":
    main()
