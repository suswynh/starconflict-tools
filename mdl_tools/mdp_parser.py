"""
Star Conflict .mdp (Model Data Physics / TCF collision mesh) binary file parser.

Format: TCF STATIC_PHYS — Targem Collision Format, static physics mesh.
Little-endian binary with ASCII magic, fixed header, then collision data blocks
with embedded material tags.
"""

import struct
import os
import sys
import re
from typing import Dict, List


# ---------------------------------------------------------------------------
# Header layout (little-endian)
# ---------------------------------------------------------------------------
_HEADER_FMT = "<16s 9I f"       # magic (16 bytes) + 9 uint32 + 1 float32
_HEADER_SIZE = struct.calcsize(_HEADER_FMT)   # 16 + 9*4 + 4 = 56 bytes

_MAGIC_EXPECTED = b"TCF STATIC_PHYS\x00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_ascii_strings(data: bytes, min_len: int = 4) -> List[str]:
    """Scan *data* for contiguous printable-ASCII runs ≥ *min_len* characters.

    Returns a list of unique strings in order of first occurrence.
    """
    seen: set[str] = set()
    result: List[str] = []

    buf: List[int] = []
    for byte in data:
        # printable ASCII: space (0x20) .. tilde (0x7E)
        if 0x20 <= byte <= 0x7E:
            buf.append(byte)
        else:
            if len(buf) >= min_len:
                s = bytes(buf).decode("ascii")
                if s not in seen:
                    seen.add(s)
                    result.append(s)
            buf.clear()

    # flush trailing run
    if len(buf) >= min_len:
        s = bytes(buf).decode("ascii")
        if s not in seen:
            seen.add(s)
            result.append(s)

    return result


def _looks_like_material_tag(s: str) -> bool:
    """Heuristic: does *s* look like a collision-material tag / identifier?

    Accepts strings that:
      - Are 3-50 characters long
      - Consist only of letters, digits, underscore, '#', '-', '.'
      - Contain at least one letter or '#'
      - Do NOT look like a floating-point literal
    """
    if not (3 <= len(s) <= 50):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_#\-.]+", s):
        return False
    if not re.search(r"[A-Za-z#]", s):
        return False
    # Reject obvious float-literal patterns (e.g. "1.0000", "-0.5")
    if re.fullmatch(r"-?\d+\.?\d*", s):
        return False
    return True


def _hex_preview(data: bytes, length: int = 256) -> str:
    """Return a hex+ASCII preview of the first *length* bytes."""
    chunk = data[:length]
    lines: List[str] = []
    for i in range(0, len(chunk), 16):
        row = chunk[i:i + 16]
        hex_part = " ".join(f"{b:02X}" for b in row)
        ascii_part = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in row)
        lines.append(f"  {i:04X}: {hex_part:<48s}  {ascii_part}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_mdp(filepath: str) -> dict:
    """Parse a Star Conflict .mdp file and return its contents as a dictionary.

    Parameters
    ----------
    filepath : str
        Path to the .mdp binary file.

    Returns
    -------
    dict
        Keys:
          magic            (str)          – Magic string (always "TCF STATIC_PHYS")
          version          (int)          – Format version
          submesh_count    (int)          – Number of submeshes
          face_count       (int)          – Triangle / face count
          vertex_count     (int)          – Vertex count
          scale            (float)        – Uniform scale factor
          data_size        (int)          – Bytes of data following the header
          unknown_0x30     (int)          – Unknown field at offset 0x30
          material_tags    (list[str])    – Unique material-tag strings found in data
          embedded_strings (list[str])    – All unique ASCII strings ≥4 chars
          raw_size         (int)          – Total file size in bytes
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    raw_size = os.path.getsize(filepath)

    with open(filepath, "rb") as fh:
        data = fh.read()

    if len(data) < _HEADER_SIZE:
        raise ValueError(
            f"File too small for header ({len(data)} < {_HEADER_SIZE} bytes)"
        )

    # Unpack header
    (
        magic,
        version,
        submesh_count,
        data_size,
        _zero_1c,
        face_count,
        vertex_count,
        _zero_28,
        _zero_2c,
        unknown_0x30,
        scale,
    ) = struct.unpack_from(_HEADER_FMT, data, 0)

    # Validate magic
    magic_str = magic.rstrip(b"\x00").decode("ascii", errors="replace")
    if magic != _MAGIC_EXPECTED:
        # Try to be forgiving – check the ASCII part at least
        if not magic.startswith(b"TCF STATIC_PHYS"):
            raise ValueError(
                f"Bad magic: expected {_MAGIC_EXPECTED!r}, got {magic!r}"
            )

    # Extract all embedded ASCII strings from the whole file
    embedded_strings = _extract_ascii_strings(data, min_len=4)

    # Extract material tags from the data portion only (after header)
    body = data[_HEADER_SIZE:]
    body_strings = _extract_ascii_strings(body, min_len=3)
    material_tags = [s for s in body_strings if _looks_like_material_tag(s)]

    return {
        "magic": magic_str,
        "version": version,
        "submesh_count": submesh_count,
        "face_count": face_count,
        "vertex_count": vertex_count,
        "scale": scale,
        "data_size": data_size,
        "unknown_0x30": unknown_0x30,
        "material_tags": material_tags,
        "embedded_strings": embedded_strings,
        "raw_size": raw_size,
    }


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def _print_report(info: dict, filepath: str, data: bytes) -> None:
    """Write a human-readable report to stdout."""
    fname = os.path.basename(filepath)

    print("Star Conflict .mdp Physics Data (TCF)")
    print("=======================================")
    print(f"File: {fname}")
    print(f"Size: {info['raw_size']} bytes")
    print()
    print("Header:")
    print(f"  Magic: {info['magic']}")
    print(f"  Version: {info['version']}")
    print(f"  Submeshes: {info['submesh_count']}")
    print(f"  Faces: {info['face_count']}")
    print(f"  Vertices: {info['vertex_count']}")
    print(f"  Scale: {info['scale']:.4f}")
    print(f"  Data size (after header): {info['data_size']} bytes")
    print(f"  Unknown @ 0x30: 0x{info['unknown_0x30']:04X}")
    print()

    tags = info["material_tags"]
    if tags:
        print("Material Tags:")
        for t in tags:
            print(f"  {t}")
    else:
        print("Material Tags: (none found)")
    print()

    estr = info["embedded_strings"]
    print(f"Embedded Strings ({len(estr)} found):")
    for s in estr:
        print(f"  {s}")
    print()

    print("Hex Preview (first 256 bytes):")
    print(_hex_preview(data, 256))


def _write_sidecar(filepath: str, info: dict, data: bytes) -> None:
    """Write a .mdp.txt sidecar file next to *filepath*."""
    out_path = filepath + ".txt"
    with open(out_path, "w", encoding="utf-8") as fh:
        # Redirect stdout into the file
        old_stdout = sys.stdout
        try:
            sys.stdout = fh
            _print_report(info, filepath, data)
        finally:
            sys.stdout = old_stdout
    print(f"  -> wrote {out_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python mdp_parser.py <file.mdp> [file2.mdp ...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        if not os.path.isfile(path):
            print(f"  [SKIP] not a file: {path}")
            continue
        try:
            print(f"\nProcessing: {path}")
            with open(path, "rb") as fh:
                raw = fh.read()
            info = parse_mdp(path)
            _print_report(info, path, raw)
            _write_sidecar(path, info, raw)
        except Exception as exc:
            print(f"  [ERROR] {path}: {exc}")


if __name__ == "__main__":
    main()
