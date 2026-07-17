# ============================================================================
# Decal Parser — Star Conflict levels/*/decals.dat binary parser
# ============================================================================
"""Parse Star Conflict levels/*/decals.dat binary files.

Extracts decal instances with world-space transforms and texture references.

DECALS.DAT binary format (Little Endian):
  Offset  Size  Field
  0x00    4     version (uint32, always 5)
  0x04    4     count (uint32)
  0x08    8     padding (zeros)
  0x10    —     records array

  Each record (96 bytes, padded):
    +0x00  12    Position: 3× float32 (x, y, z)     Hammer Y-up
    +0x0C   4    padding (0x00000000)
    +0x10  16    Rotation: 4× float32 (x, y, z, w)  Quaternion
    +0x20  12    Direction: 3× float32 (x, y, z)    Surface normal / facing vector
    +0x2C   4    padding
    +0x30  12    Scale: 3× float32 (x, y, z)
    +0x3C   4    padding
    +0x40   N    Texture name (null-terminated ASCII string)
    —      —    Padding to 96-byte record boundary

Coordinate system notes:
  - Hammer Engine: Y-up
  - Blender: Z-up
  - Positions returned raw; conversion handled by level_assembler.
"""

import os
import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Constants
# ============================================================================

EXPECTED_VERSION = 5
RECORD_SIZE = 96
HEADER_SIZE = 16          # 4 (version) + 4 (count) + 8 (padding)
POS_OFFSET = 0x00         # Position: 3× float32 (x, y, z)
ROT_OFFSET = 0x10         # Rotation: 4× float32 (x, y, z, w) quaternion
DIR_OFFSET = 0x20         # Direction/normal: 3× float32 (x, y, z)
SCALE_OFFSET = 0x30       # Scale: 3× float32 (x, y, z)
STRING_OFFSET = 0x40      # Offset of null-terminated texture name within record


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class DecalInstance:
    """A single decal instance from decals.dat."""
    name: str                                        # Auto-generated name
    pos: Tuple[float, float, float]                  # World position (x, y, z)
    rot: Tuple[float, float, float, float]           # Quaternion (x, y, z, w)
    scale: Tuple[float, float, float]                # Scale (x, y, z)
    texture: str                                     # Texture name (e.g. "rust_znak1")
    direction: Tuple[float, float, float] = (0, 0, 0)  # Surface normal / direction vector


# ============================================================================
# Parser
# ============================================================================

def parse_decals(filepath: str) -> List[DecalInstance]:
    """Parse a Star Conflict levels/*/decals.dat binary file.

    Args:
        filepath: Absolute path to decals.dat.

    Returns:
        List of DecalInstance objects. Returns empty list on any error.

    Raises:
        This function never raises; all errors are caught and logged.
    """
    try:
        if not os.path.isfile(filepath):
            print(f"[DecalParser] File not found: {filepath}")
            return []

        with open(filepath, 'rb') as f:
            data = f.read()

        file_size = len(data)
        if file_size < HEADER_SIZE:
            print(f"[DecalParser] File too small ({file_size} bytes), expected at least {HEADER_SIZE}")
            return []

        # ── Parse header ──
        version, count = struct.unpack_from('<II', data, 0)

        if version != EXPECTED_VERSION:
            print(f"[DecalParser] Unexpected version {version}, expected {EXPECTED_VERSION}")
            return []

        if count == 0:
            return []

        # ── Verify expected file size ──
        expected_size = HEADER_SIZE + count * RECORD_SIZE
        if file_size < expected_size:
            print(f"[DecalParser] File size {file_size} too small for {count} records "
                  f"(expected {expected_size})")
            return []

        # ── Parse records ──
        decals = []
        for i in range(count):
            offset = HEADER_SIZE + i * RECORD_SIZE

            # Unpack position (3 floats), skip padding
            px, py, pz = struct.unpack_from('<fff', data, offset + POS_OFFSET)
            pos = (px, py, pz)

            # Unpack rotation (4 floats: x, y, z, w)
            qx, qy, qz, qw = struct.unpack_from('<ffff', data, offset + ROT_OFFSET)
            rot = (qx, qy, qz, qw)

            # Unpack direction/normal (3 floats)
            dx, dy, dz = struct.unpack_from('<fff', data, offset + DIR_OFFSET)
            direction = (dx, dy, dz)

            # Unpack scale (3 floats)
            sx, sy, sz = struct.unpack_from('<fff', data, offset + SCALE_OFFSET)
            scale = (sx, sy, sz)

            # Read null-terminated texture name at offset + STRING_OFFSET (0x40)
            string_start = offset + STRING_OFFSET
            string_end = string_start
            while string_end < offset + RECORD_SIZE and data[string_end] != 0:
                string_end += 1
            texture_bytes = data[string_start:string_end]
            texture = texture_bytes.decode('ascii', errors='replace')

            name = f"Decal_{texture}_{i}"

            decals.append(DecalInstance(
                name=name,
                pos=pos,
                rot=rot,
                scale=scale,
                texture=texture,
                direction=direction,
            ))

        return decals

    except Exception as exc:
        print(f"[DecalParser] Failed to parse {filepath}: {exc}")
        return []


# ============================================================================
# Text format parser — gamedata/decals.dat material definitions
# ============================================================================

@dataclass
class DecalMaterialDef:
    """Material definition for a named decal from gamedata/decals.dat."""
    name: str                                  # Decal name (e.g. "empire_signs04yellow")
    diffuse: str = ""                          # Diffuse texture path (e.g. "textures\decals\empire_signs01")
    normal: str = ""                           # Normal map path
    glow: str = ""                             # Glow map path
    spec: str = ""                             # Specular map path
    uv: Tuple[float, float, float, float] = (0, 0, 1, 1)  # UV rect: (u, v, width, height)
    blend: str = ""                            # Blend mode (e.g. "alpha_glow")
    material: str = ""                         # Material type (e.g. "bump")
    spec_color: Tuple[float, float, float] = (0, 0, 0)  # Specular color (0-255)
    gloss: float = 0.0                         # Gloss value
    extra: dict = field(default_factory=dict)  # Any other fields


def parse_decals_material(filepath: str) -> Dict[str, DecalMaterialDef]:
    """Parse gamedata/decals.dat text format — decal material definitions.

    Format:
        name {
            diffuse "path"
            normal "path"
            glow "path"
            spec "path"
            uv ( u v w h )
            blend mode
            material type
            spec_color ( r g b )
            gloss value
        }

    Args:
        filepath: Path to gamedata/decals.dat text file.

    Returns:
        Dict mapping decal name (lowercase) → DecalMaterialDef.
        Returns empty dict on error.
    """
    definitions: Dict[str, DecalMaterialDef] = {}
    try:
        if not os.path.isfile(filepath):
            return definitions

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        # Regex to match each decal block: name { ... }
        block_pattern = re.compile(
            r'^(\w[^\s{]*)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}',
            re.MULTILINE)

        for match in block_pattern.finditer(content):
            name = match.group(1).strip()
            body = match.group(2)

            defn = DecalMaterialDef(name=name)

            # ── Parse key-value pairs ──
            for line in body.strip().split('\n'):
                line = line.strip()
                if not line:
                    continue

                # key "value"
                m_str = re.match(r'^(\w+)\s+"([^"]*)"', line)
                if m_str:
                    key, val = m_str.group(1), m_str.group(2)
                    if key == 'diffuse':
                        defn.diffuse = val
                    elif key == 'normal':
                        defn.normal = val
                    elif key == 'glow':
                        defn.glow = val
                    elif key == 'spec':
                        defn.spec = val
                    else:
                        defn.extra[key] = val
                    continue

                # key ( n1 n2 n3 n4 )
                m_vec = re.match(r'^(\w+)\s*\(\s*([\d.\-eE\s]+)\s*\)', line)
                if m_vec:
                    key = m_vec.group(1)
                    vals = [float(x) for x in m_vec.group(2).split()]
                    if key == 'uv':
                        if len(vals) >= 4:
                            defn.uv = (vals[0], vals[1], vals[2], vals[3])
                        elif len(vals) >= 2:
                            defn.uv = (vals[0], vals[1], 0, 0)
                    elif key == 'spec_color':
                        if len(vals) >= 3:
                            defn.spec_color = (vals[0], vals[1], vals[2])
                    else:
                        defn.extra[key] = tuple(vals)
                    continue

                # key value (bare identifier — blend, material, gloss)
                m_bare = re.match(r'^(\w+)\s+([\w.\-]+)', line)
                if m_bare:
                    key, val = m_bare.group(1), m_bare.group(2)
                    if key == 'blend':
                        defn.blend = val
                    elif key == 'material':
                        defn.material = val
                    elif key == 'gloss':
                        try:
                            defn.gloss = float(val)
                        except ValueError:
                            pass
                    else:
                        defn.extra[key] = val
                    continue

            definitions[name.lower()] = defn

    except Exception as exc:
        print(f"[DecalParser] Failed to parse material definitions {filepath}: {exc}")

    return definitions
