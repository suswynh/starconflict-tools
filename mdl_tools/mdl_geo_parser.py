"""Star Conflict .mdl-geo binary parser.

Model Geometry (simplified collision / LOD mesh) files.
Zero external dependencies. Importable module and standalone CLI.
"""

import json
import os
import struct
import sys
import textwrap
from typing import Dict, List, Tuple


def parse_mdl_geo(filepath: str) -> dict:
    """Parse a .mdl-geo file, return dict with header, bbox, vertex sample."""
    with open(filepath, "rb") as f:
        data = f.read()

    file_size = len(data)

    # --- header: 9 uint32s + 9 uint32s reserved (36 bytes) ---
    if len(data) < 0x44:
        raise ValueError("File too small for valid header")

    version, unknown, _, _, vbytes, vstride, vcount, fcount = struct.unpack_from(
        "<IIIIIIII", data, 0
    )

    vertex_data_offset = 0x44
    index_data_offset = vertex_data_offset + (vcount * vstride)

    expected_size = index_data_offset + (fcount * 2)
    if len(data) < expected_size:
        raise ValueError(
            f"File truncated: expected >= {expected_size} bytes, got {len(data)}"
        )

    # --- parse vertices ---
    vertices: List[Tuple[float, float, float]] = []
    for i in range(vcount):
        offset = vertex_data_offset + (i * vstride)
        x, y, z = struct.unpack_from("<fff", data, offset)
        vertices.append((x, y, z))

    # --- parse face indices ---
    faces: List[int] = list(
        struct.unpack_from(f"<{fcount}H", data, index_data_offset)
    )

    # --- bounding box ---
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    zs = [v[2] for v in vertices]
    bbox_min = (min(xs), min(ys), min(zs))
    bbox_max = (max(xs), max(ys), max(zs))

    # closest to origin and farthest from origin
    def dist_sq(v):
        return v[0] ** 2 + v[1] ** 2 + v[2] ** 2

    sorted_by_dist = sorted(vertices, key=dist_sq)
    max_vertex = sorted_by_dist[0]  # closest
    min_vertex = sorted_by_dist[-1]  # farthest

    # vertex sample (first 5)
    vertex_sample = vertices[:5]

    return {
        "version": version,
        "vbytes": vbytes,
        "vstride": vstride,
        "vcount": vcount,
        "fcount": fcount,
        "file_size": file_size,
        "max_vertex": max_vertex,
        "min_vertex": min_vertex,
        "bbox": {"min": bbox_min, "max": bbox_max},
        "vertex_sample": vertex_sample,
        "_vertices": vertices,
        "_faces": faces,
    }


def format_vertex(v: Tuple[float, float, float]) -> str:
    """Format a vertex tuple as a rounded string."""
    return f"({v[0]:.2f}, {v[1]:.2f}, {v[2]:.2f})"


def produce_text_output(result: dict, filepath: str) -> str:
    """Build the human-readable .mdl_geo.txt sidecar content."""
    vcount = result["vcount"]
    fcount = result["fcount"]
    bbox = result["bbox"]
    vertices: List[Tuple[float, float, float]] = result["_vertices"]

    lines = []
    lines.append("Star Conflict .mdl-geo Simplified Geometry")
    lines.append("=" * 44)
    lines.append(f"File: {os.path.basename(filepath)}")
    lines.append(f"Size: {result['file_size']} bytes")
    lines.append("")
    lines.append("Header:")
    lines.append(f"  Version: {result['version']}")
    lines.append(f"  VBytes: {result['vbytes']}, VStride: {result['vstride']}")
    lines.append(f"  Vertices: {vcount}")
    lines.append(f"  Face Indices: {fcount} ({fcount // 3} triangles)")
    lines.append("")

    bmin = bbox["min"]
    bmax = bbox["max"]
    size = (bmax[0] - bmin[0], bmax[1] - bmin[1], bmax[2] - bmin[2])
    lines.append("Bounding Box:")
    lines.append(f"  Min: ({bmin[0]:.2f}, {bmin[1]:.2f}, {bmin[2]:.2f})")
    lines.append(f"  Max: ({bmax[0]:.2f}, {bmax[1]:.2f}, {bmax[2]:.2f})")
    lines.append(f"  Size: ({size[0]:.2f}, {size[1]:.2f}, {size[2]:.2f})")
    lines.append("")

    is_large = vcount > 100
    show_first = 20

    lines.append(f"First {show_first} Vertices (x, y, z):")
    for i in range(min(show_first, vcount)):
        lines.append(f"  v[{i}]: {format_vertex(vertices[i])}")

    if not is_large:
        remaining = vcount - show_first
        if remaining > 0:
            lines.append("")
            lines.append(f"Remaining {remaining} Vertices:")
            for i in range(show_first, vcount):
                lines.append(f"  v[{i}]: {format_vertex(vertices[i])}")
    else:
        lines.append("  ...")
        lines.append("")
        lines.append(f"Last {min(5, vcount - show_first)} Vertices:")
        for i in range(max(show_first, vcount - 5), vcount):
            lines.append(f"  v[{i}]: {format_vertex(vertices[i])}")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: python mdl_geo_parser.py <file1.mdl-geo> [file2.mdl-geo ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    for filepath in sys.argv[1:]:
        print(f"Parsing: {filepath}")
        try:
            result = parse_mdl_geo(filepath)

            # JSON summary to stdout
            json_out = {
                k: result[k]
                for k in [
                    "version",
                    "vbytes",
                    "vstride",
                    "vcount",
                    "fcount",
                    "file_size",
                    "max_vertex",
                    "min_vertex",
                    "bbox",
                    "vertex_sample",
                ]
            }
            # tuple -> list for valid JSON
            json_out["max_vertex"] = list(json_out["max_vertex"])
            json_out["min_vertex"] = list(json_out["min_vertex"])
            json_out["vertex_sample"] = [
                list(v) for v in json_out["vertex_sample"]
            ]
            print(json.dumps(json_out, indent=2))

            # Text sidecar
            txt_path = filepath + ".txt"
            text_content = produce_text_output(result, filepath)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text_content)
            print(f"  -> wrote {txt_path}")

        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
