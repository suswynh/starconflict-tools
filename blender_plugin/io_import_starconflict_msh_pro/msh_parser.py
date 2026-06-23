# ============================================================================
# MSH Format Parser (extracted from io_import_starconflict_msh)
# ============================================================================
"""Hammer Engine .mdl-mshXXX binary mesh parser.

File layout (little-endian):
  [0x00] uint32 version      (0/1/2/3)
  [0x04] uint32 flag         (affects UV offset)
  [0x08] uint32 VBytes       (vertex stride: 20/24/28/32/36/40/44)
  [0x0C] uint32 VCount       (vertex count)
  [0x10] uint32 FCount       (index count, triangles*3)
  [0x14~0x43]                (reserved)
  [0x44]                     vertex data (VCount * VBytes)
  [0x44 + VCount*VBytes]     index data (FCount * uint16)
"""

import struct


def get_uv_offset(vbytes, flag):
    """Calculate UV byte offset within vertex structure."""
    if vbytes == 20:
        return 12
    elif vbytes == 24:
        return 16
    elif vbytes == 28:
        if flag == 0xE or flag == 5:
            return 16
        elif flag == 0x11:
            return 20
        return 16
    elif vbytes == 32:
        return 20
    elif vbytes == 36:
        return 20
    elif vbytes == 40:
        return 24
    elif vbytes == 44:
        return 24
    return -1


def parse_msh(data):
    """Parse .mdl-mshXXX binary data.

    Returns (positions, uvs, indices) or raises ValueError.
    positions: list of (x,y,z) tuples
    uvs:       list of (u,v) tuples, same length as positions
    indices:   list of int (triangle list, every 3 = 1 triangle)
    """
    if len(data) < 0x44 + 12:
        raise ValueError("File too small")

    version = struct.unpack_from("<I", data, 0x00)[0]
    flag = struct.unpack_from("<I", data, 0x04)[0]
    vbytes = struct.unpack_from("<I", data, 0x08)[0]
    vcount = struct.unpack_from("<I", data, 0x0C)[0]
    fcount = struct.unpack_from("<I", data, 0x10)[0]

    if version > 200:
        raise ValueError(f"Bad version: {version}")
    if vbytes < 20 or vbytes > 48:
        raise ValueError(f"Unsupported VBytes: {vbytes}")
    if vcount < 1 or vcount > 500000:
        raise ValueError(f"Bad VCount: {vcount}")
    if fcount < 3 or fcount > 1000000:
        raise ValueError(f"Bad FCount: {fcount}")

    expected = 0x44 + vcount * vbytes + fcount * 2
    if abs(expected - len(data)) > 100:
        raise ValueError(f"Size mismatch: expected {expected}, got {len(data)}")

    uv_off = get_uv_offset(vbytes, flag)

    vert_base = 0x44
    positions = []
    uvs = []
    for i in range(vcount):
        off = vert_base + i * vbytes
        px, py, pz = struct.unpack_from("<fff", data, off)
        positions.append((px, py, pz))

        if uv_off >= 0:
            u, v = struct.unpack_from("<ff", data, off + uv_off)
            uvs.append((u, 1.0 - v))
        else:
            uvs.append((0.0, 0.0))

    idx_base = vert_base + vcount * vbytes
    indices = list(struct.unpack_from(f"<{fcount}H", data, idx_base))

    return positions, uvs, indices
