# ============================================================================
# MSH Format Parser (extracted from io_import_starconflict_msh)
# ============================================================================
"""Hammer Engine .mdl-mshXXX binary mesh parser.

File layout (little-endian):
  [0x00] uint32 material_block_index  (index into MDF material blocks)
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
    """Calculate UV1 byte offset within vertex structure.
    
    Known vertex layouts (offset, vbytes, flag):
      - VBytes=44 flag=0x16: UV1 @ 20, UV2 @ 28 (uint16_unorm)
      - VBytes=40 flag=0x13: [0]Pos(12)|[12]Data(8)|[20]UV1(8)|[28]Data(4)|[32]UV2(8 float2)  -- loader, reptile_01
      - VBytes=40 flag=0x10: [0]Pos(12)|[12]Data(4)|[16]UV1(8)|[24]Sentinel(7FFF)|[28]Data(4)|[32]UV2(4 uint16)  -- skinned char
      - VBytes=32 flag=0x0F: [0]Pos(12)|[12]Data(4)|[16]UV1(8)|[24]Sentinel(7FFF)|[28]Data(4)  -- fed_mercenary_tool
    """
    if vbytes == 20:
        return 12
    elif vbytes == 24:
        return 16
    elif vbytes == 28:
        if flag == 0xE:
            return 16
        elif flag == 5 or flag == 0x11:
            return 20   # flag=0x0005 UV is at 20 (verified: pvp_omega map_510/512/513 vs map_511)
        return 16
    elif vbytes == 32:
        if flag == 0x0F:
            return 16   # Fixed: was 20, UV1 at offset 16 (verified: fed_mercenary_tool_001)
        return 20
    elif vbytes == 36:
        return 20
    elif vbytes == 40:
        if flag == 0x13:
            return 20   # Fixed: was 24, UV1 at offset 20 (verified: loader_01, reptile_01_000)
        elif flag == 0x10:
            return 16   # Fixed: was 24, UV1 at offset 16 for skinned character (verified: fed_mercenary_man)
            # Layout: [0]Pos(12) | [12]Data(4) | [16]UV1(8) | [24]Sentinel(7FFF0000) | [28]Data(4) | [32]UV2(4 uint16)
        return 24
    elif vbytes == 44:
        return 20   # Fixed: was 24, but UV1 starts at offset 20 for flag=0x16
    elif vbytes == 48:
        return 24
    return -1


def get_uv2_info(vbytes, flag):
    """Get UV2 (lightmap) byte offset and format within vertex structure.
    
    Returns (offset, format) or None if no UV2 space.
    format: 'float2' or 'uint16_unorm'
    
    Verified layouts:
      VBytes=32 flag=0x14: UV2 @ 28 (uint16 UNORM, maps/bigships, verified 2026-06)
      VBytes=32 flag=0x12: UV2 @ 28 (uint16 UNORM, asteroids)
      VBytes=36:           UV2 @ 28 (uint16 UNORM)
      VBytes=40 flag=0x1C: UV2 @ 32 (uint16 UNORM)
      VBytes=40 flag=0x13: UV2 @ 32 (float2, often all-zero)
      VBytes=40 flag=0x10: UV2 @ 32 (uint16 UNORM, character models)
      VBytes=44 flag=0x16: UV2 @ 28 (uint16 UNORM)
      VBytes=48:           UV2 @ 40 (float2, tentative)
      VBytes=28 flag=0x0E: UV2 @ 24 (uint16 UNORM, animated_mock airwalls/gates)
    """
    # VBytes=28 with flag=0x0E: animated_mock airwall models have compressed UV2
    # at offset 24-27 (2 × uint16_unorm), used for ColormapSampler (gate_mask02)
    if vbytes == 28 and flag == 0x0E:
        return (24, 'uint16_unorm')

    if vbytes < 32:
        return None  # No room for UV2
    
    if vbytes == 32:
        return (28, 'uint16_unorm')  # Verified: dreadnought_control_cab_imp lightmap UV2
    
    if vbytes == 36:
        return (28, 'uint16_unorm')
    
    if vbytes == 40:
        if flag == 0x1C or flag == 0x10:
            return (32, 'uint16_unorm')
        elif flag == 0x13:
            return (32, 'float2')  # May be all-zero for models without lightmap
        return (32, 'float2')  # unknown flag, try float2
    
    if vbytes == 44:
        return (28, 'uint16_unorm')
    
    if vbytes == 48:
        return (40, 'float2')
    
    return None


def parse_msh(data):
    """Parse .mdl-mshXXX binary data.

    Returns (positions, uvs, uvs2, indices, material_block_index) or raises ValueError.
    positions: list of (x,y,z) tuples
    uvs:       list of (u,v) tuples, same length as positions (UV1 / diffuse)
    uvs2:      list of (u,v) tuples or None (UV2 / lightmap)
    indices:   list of int (triangle list, every 3 = 1 triangle)
    material_block_index: int, index into MDF material blocks (0-based)
    """
    if len(data) < 0x44 + 12:
        raise ValueError("File too small")

    material_block_index = struct.unpack_from("<I", data, 0x00)[0]
    flag = struct.unpack_from("<I", data, 0x04)[0]
    vbytes = struct.unpack_from("<I", data, 0x08)[0]
    vcount = struct.unpack_from("<I", data, 0x0C)[0]
    fcount = struct.unpack_from("<I", data, 0x10)[0]

    if material_block_index > 200:
        raise ValueError(f"Bad material_block_index: {material_block_index}")
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
    uv2_info = get_uv2_info(vbytes, flag)

    vert_base = 0x44
    positions = []
    uvs = []
    uvs2 = [] if uv2_info else None
    
    for i in range(vcount):
        off = vert_base + i * vbytes
        px, py, pz = struct.unpack_from("<fff", data, off)
        positions.append((px, py, pz))

        # UV1 (diffuse/color)
        if uv_off >= 0:
            u, v = struct.unpack_from("<ff", data, off + uv_off)
            uvs.append((u, 1.0 - v))
        else:
            uvs.append((0.0, 0.0))
        
        # UV2 (lightmap)
        if uv2_info:
            uv2_off, uv2_fmt = uv2_info
            if uv2_fmt == 'float2':
                u2, v2 = struct.unpack_from("<ff", data, off + uv2_off)
                uvs2.append((u2, 1.0 - v2))
            elif uv2_fmt == 'uint16_unorm':
                u2_raw = struct.unpack_from("<H", data, off + uv2_off)[0]
                v2_raw = struct.unpack_from("<H", data, off + uv2_off + 2)[0]
                u2 = u2_raw / 32767.0
                v2 = 1.0 - (v2_raw / 32767.0)
                uvs2.append((u2, v2))

    idx_base = vert_base + vcount * vbytes
    indices = list(struct.unpack_from(f"<{fcount}H", data, idx_base))

    return positions, uvs, uvs2, indices, material_block_index
