# ============================================================================
# MSH Importer — Mesh import + material linking logic
# ============================================================================
"""Blender mesh builder and import orchestration for Star Conflict MSH files.

Handles:
  - Building Blender meshes from parsed MSH data
  - Coordinate system conversion
  - MDF lookup and material linking
"""

import os
import math

import bpy
from mathutils import Matrix, Euler

from . import msh_parser
from . import mdf_parser
from . import texture_finder
from . import material_builder


# ──────────────────────────────────────────────────────────────
# Mesh Builder
# ──────────────────────────────────────────────────────────────

def build_mesh(name, positions, uvs, indices):
    """Create a Blender mesh from parsed MSH data.

    Args:
        name: Mesh name.
        positions: List of (x,y,z) tuples.
        uvs: List of (u,v) tuples.
        indices: List of triangle indices.

    Returns:
        bpy.types.Mesh
    """
    faces = []
    # 反转三角形卷绕方向：Hammer Engine 的卷绕与 Blender 正面约定相反。
    # 交换每个三角形的第二和第三索引以匹配 Noesis RPGOPT_TRIWINDBACKWARD 行为。
    for i in range(0, len(indices) - 2, 3):
        faces.append((indices[i], indices[i+2], indices[i+1]))

    mesh = bpy.data.meshes.new(name=name)
    mesh.from_pydata(positions, [], faces)

    if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
        uv_layer = mesh.uv_layers.new(name="map1")
        loop_idx = 0
        for face in faces:
            for vert_idx in face:
                if vert_idx < len(uvs):
                    uv_layer.data[loop_idx].uv = uvs[vert_idx]
                loop_idx += 1

    mesh.validate()
    mesh.update()
    return mesh


# ──────────────────────────────────────────────────────────────
# Coordinate System
# ──────────────────────────────────────────────────────────────

def apply_up_axis(obj, up_axis):
    """Apply coordinate system rotation to a Blender object."""
    if up_axis == 'NONE':
        return

    if up_axis == 'Y_UP_TO_Z_UP':
        obj.rotation_euler = Euler((math.radians(-90), 0, 0), 'XYZ')
    elif up_axis == 'Z_UP_TO_Y_UP':
        obj.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')
    elif up_axis == 'NOESIS_COMPAT':
        obj.rotation_euler = Euler((
            math.radians(0),
            math.radians(290),
            math.radians(130),
        ), 'XYZ')
    elif up_axis == 'AUTO_FLIP_YZ':
        mesh = obj.data
        for v in mesh.vertices:
            v.co = (v.co.x, v.co.z, -v.co.y)


# ──────────────────────────────────────────────────────────────
# Name utilities
# ──────────────────────────────────────────────────────────────

def extract_msh_index(filename):
    """Extract the LOD index from an MSH filename.
    
    e.g. 'bigship_empire_02.mdl-msh005' → 5
         'plasma_gun_mod1.mdl-msh000' → 0
    Returns 0 if no index found.
    """
    import re
    m = re.search(r'\.mdl-msh(\d+)', filename)
    if m:
        return int(m.group(1))
    return 0


def extract_base_name(filename):
    """Extract base name from .mdl-mshXXX filename.

    plasma_gun_mod1.mdl-msh000 -> plasma_gun_mod1
    """
    dot = filename.rfind(".mdl-msh")
    if dot >= 0:
        return filename[:dot]
    return os.path.splitext(filename)[0]


def clean_name(filename):
    """Convert MSH filename to a clean Blender object name."""
    name = filename
    name = name.replace(".mdl-msh", "_msh")
    name = name.replace(" ", "_")
    if len(name) > 63:
        name = name[:63]
    return name


# ──────────────────────────────────────────────────────────────
# MDF Lookup
# ──────────────────────────────────────────────────────────────

def find_mdf_for_msh(msh_filepath, mdf_search_dirs=None):
    """Find the MDF file corresponding to an MSH file.

    Strategy:
      1. Look for <base_name>.mdf in the same directory as the MSH file.
      2. Search in each mdf_search_dir recursively.

    Args:
        msh_filepath: Path to the .mdl-mshXXX file.
        mdf_search_dirs: Additional directories to search.

    Returns:
        str or None: Path to the .mdf file.
    """
    base = extract_base_name(os.path.basename(msh_filepath))
    mdf_name = base + ".mdf"

    # Strategy 1: Same directory
    msh_dir = os.path.dirname(msh_filepath)
    candidate = os.path.join(msh_dir, mdf_name)
    if os.path.isfile(candidate):
        return candidate

    # Strategy 2: Search directories
    search_dirs = [msh_dir]
    if mdf_search_dirs:
        search_dirs.extend(mdf_search_dirs)

    for sdir in search_dirs:
        if not os.path.isdir(sdir):
            continue
        for root, dirs, files in os.walk(sdir):
            if mdf_name in files:
                return os.path.join(root, mdf_name)

    return None


# ──────────────────────────────────────────────────────────────
# Main Import Function
# ──────────────────────────────────────────────────────────────

def import_msh_with_materials(filepath, context,
                               scale=1.0,
                               up_axis='Y_UP_TO_Z_UP',
                               auto_link=True,
                               tex_search_dirs=None,
                               mdf_search_dirs=None,
                               tex_extensions=".dds,.png,.tga",
                               complexity='FULL'):
    """Import a single MSH file with optional material linking.

    Args:
        filepath: Path to the .mdl-mshXXX file.
        context: Blender context.
        scale: Scale factor.
        up_axis: Coordinate system conversion.
        auto_link: Whether to auto-link materials.
        tex_search_dirs: Texture search directories.
        mdf_search_dirs: MDF search directories.
        tex_extensions: Comma-separated extensions.
        complexity: 'FULL' or 'SIMPLE'.

    Returns:
        bpy.types.Object or None
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        positions, uvs, indices = msh_parser.parse_msh(data)

        name = clean_name(os.path.basename(filepath))
        mesh = build_mesh(name, positions, uvs, indices)

        obj = bpy.data.objects.new(name=name, object_data=mesh)
        apply_up_axis(obj, up_axis)

        if scale != 1.0:
            obj.scale = (scale, scale, scale)

        collection = context.collection or context.scene.collection
        collection.objects.link(obj)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        # ── Material linking ──
        if auto_link:
            mdf_path = find_mdf_for_msh(filepath, mdf_search_dirs)
            if mdf_path:
                try:
                    blocks = mdf_parser.parse_mdf(mdf_path)
                    extensions = texture_finder._get_search_extensions(tex_extensions)

                    # Build texture maps for each block
                    texture_maps = []
                    for block in blocks:
                        tex_map = texture_finder.find_textures_for_material(
                            block, tex_search_dirs or [], extensions
                        )
                        texture_maps.append(tex_map)

                    # ── Material linking (cross-object deduplicated) ──
                    # MDF blocks map to MSH files by order:
                    #   deduped block 0 → .mdl-msh000
                    #   deduped block 1 → .mdl-msh001
                    # Identical blocks across different MSH files share
                    # the same Blender material via the global cache.
                    msh_idx = extract_msh_index(os.path.basename(filepath))
                    target_block = material_builder.get_block_for_msh(blocks, msh_idx)

                    if target_block is not None:
                        # Get the texture map for this specific block
                        block_idx = blocks.index(target_block)
                        tex_map = texture_maps[block_idx] if block_idx < len(texture_maps) else {}

                        mat = material_builder.get_or_create_material(
                            target_block, tex_map,
                            mesh_name=name,
                            complexity=complexity,
                        )
                        obj.data.materials.append(mat)
                        print(f"  [MSH Pro] msh{msh_idx:03d} → {mat.name} "
                              f"({len(blocks)} blocks → {len(material_builder.get_deduplicated_blocks(blocks))} unique, "
                              f"cache={len(material_builder._material_cache)})")
                    else:
                        print(f"  [MSH Pro] msh{msh_idx:03d}: no matching material block")
                except Exception as e:
                    print(f"  [MSH Pro] Material link warning: {e}")
            else:
                print(f"  [MSH Pro] No MDF found for {os.path.basename(filepath)}")

        return obj

    except ValueError as e:
        print(f"  [MSH Pro] Parse error [{filepath}]: {e}")
        return None
    except Exception as e:
        print(f"  [MSH Pro] Unexpected error [{filepath}]: {e}")
        return None
