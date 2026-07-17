# ============================================================================
# MSH Importer — Mesh import + material linking logic
# ============================================================================
"""Blender mesh builder and import orchestration for Star Conflict MSH files.

Handles:
  - Building Blender meshes from parsed MSH data
  - Coordinate system conversion
  - MDF lookup and material linking
  - Name resolution (prefix + Collection) via NameResolver
  - Material deduplication via MaterialRegistry
"""

import os
import math
import struct
import sys
import traceback

import bpy
from mathutils import Matrix, Euler

from . import msh_parser
from . import mdf_parser
from . import texture_finder
from . import material_builder


# ──────────────────────────────────────────────────────────────
# Mesh Builder
# ──────────────────────────────────────────────────────────────

def build_mesh(name, positions, uvs, indices, uvs2=None):
    """Create a Blender mesh from parsed MSH data.

    Args:
        name: Mesh name.
        positions: List of (x,y,z) tuples.
        uvs: List of (u,v) tuples (UV1 / diffuse).
        indices: List of triangle indices.
        uvs2: Optional list of (u,v) tuples (UV2 / lightmap).

    Returns:
        bpy.types.Mesh
    """
    faces = []
    # X 轴取反已同步翻转卷绕方向（与 Noesis v1.1 修复一致）
    for i in range(0, len(indices) - 2, 3):
        faces.append((indices[i], indices[i+1], indices[i+2]))

    # 修复前向轴：MSH 前向 -Z → +Z（与 Noesis v1.2 一致）
    positions = [(x, y, -z) for x, y, z in positions]

    mesh = bpy.data.meshes.new(name=name)
    mesh.from_pydata(positions, [], faces)

    # UV1 (diffuse/color) — "map1"
    if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
        uv_layer = mesh.uv_layers.new(name="map1")
        uv_data_len = len(uv_layer.data)
        loop_idx = 0
        for face in faces:
            for vert_idx in face:
                if loop_idx < uv_data_len and vert_idx < len(uvs):
                    uv_layer.data[loop_idx].uv = uvs[vert_idx]
                loop_idx += 1

    # UV2 (lightmap) — "lightmap"
    if uvs2 and any(u != 0.0 or v != 0.0 for u, v in uvs2):
        uv2_layer = mesh.uv_layers.new(name="lightmap")
        uv2_data_len = len(uv2_layer.data)
        loop_idx = 0
        for face in faces:
            for vert_idx in face:
                if loop_idx < uv2_data_len and vert_idx < len(uvs2):
                    uv2_layer.data[loop_idx].uv = uvs2[vert_idx]
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
                               complexity='FULL',
                               resolver=None,
                               registry=None,
                               unpack_root=None,
                                smooth_angle=30.0):
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
        resolver: NameResolver 实例（可选）
        registry: MaterialRegistry 实例（可选，推荐）
        unpack_root: 解包根目录（用于库反查）
        smooth_angle: Auto-smooth angle in degrees (0=flat shading)

    Returns:
        bpy.types.Object or None
    """
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        positions, uvs, uvs2, indices, material_block_index = msh_parser.parse_msh(data)

        raw_name = os.path.basename(filepath)

        # ── Name resolution ──
        if resolver is not None:
            obj_name = resolver.resolve_name(filepath)
            coll_path = resolver.get_collection_path(filepath)
        else:
            obj_name = clean_name(raw_name)
            coll_path = []

        mesh = build_mesh(obj_name, positions, uvs, indices, uvs2)

        # ── VBytes=28 flag=0x0E: duplicate UV2 as "FX" for animated_mock materials ──
        # These models use VTEXCOORD1 (Tex1) for ColormapSampler (gate_mask02),
        # NOT for lightmap. The separate layer name avoids naming conflicts.
        if uvs2 and any(u != 0.0 or v != 0.0 for u, v in uvs2):
            flag = struct.unpack_from("<I", data, 0x04)[0]
            vbytes = struct.unpack_from("<I", data, 0x08)[0]
            if vbytes == 28 and flag == 0x0E:
                colormap_uv = mesh.uv_layers.new(name="FX")
                cm_data_len = len(colormap_uv.data)
                for loop_idx, face in enumerate(indices[i:i+3] for i in range(0, len(indices), 3)):
                    for vi, vert_idx in enumerate(face):
                        li = loop_idx * 3 + vi
                        if li < cm_data_len and vert_idx < len(uvs2):
                            colormap_uv.data[li].uv = uvs2[vert_idx]

        # ── Auto-smooth (matching in-game normal splitting) ──
        if smooth_angle > 0.0:
            mesh.use_auto_smooth = True
            mesh.auto_smooth_angle = math.radians(smooth_angle)

        # ── Compute tangents (must be AFTER auto_smooth) ──
        if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
            try:
                mesh.calc_tangents(uvmap="map1")
            except Exception:
                pass

        obj = bpy.data.objects.new(name=obj_name, object_data=mesh)
        apply_up_axis(obj, up_axis)

        if scale != 1.0:
            obj.scale = (scale, scale, scale)

        # ── Collection linking ──
        if resolver is not None and coll_path:
            target_coll = resolver.create_collections(coll_path)
        else:
            target_coll = context.collection or context.scene.collection
        target_coll.objects.link(obj)

        obj.select_set(True)
        context.view_layer.objects.active = obj

        # ── Material linking ──
        if auto_link:
            _link_materials(obj, filepath, obj_name, raw_name,
                           tex_search_dirs, mdf_search_dirs,
                           tex_extensions, complexity,
                            registry, unpack_root,
                            material_block_index=material_block_index)

        return obj

    except ValueError as e:
        print(f"  [MSH Pro] Parse error [{filepath}]: {e}")
        return None
    except Exception as e:
        print(f"  [MSH Pro] Unexpected error [{filepath}]: {e}")
        return None


def _link_materials(obj, filepath, obj_name, raw_name,
                    tex_search_dirs, mdf_search_dirs,
                    tex_extensions, complexity,
                    registry, unpack_root,
                    material_block_index=None):
    """材质链接逻辑（独立函数，便于维护）。

    优先级:
      1. 本地 MDF → 直接解析
      2. 本地无 MDF → 库反查 → registry.get_materials_for_model()
      3. 库无记录 → 降级材质
    """
    extensions = texture_finder._get_search_extensions(tex_extensions)
    msh_idx = extract_msh_index(raw_name)

    # ── 策略1: 查找本地 MDF ──
    mdf_path = find_mdf_for_msh(filepath, mdf_search_dirs)

    if mdf_path:
        # 有 MDF → 正常解析
        try:
            blocks = mdf_parser.parse_mdf(mdf_path)
            texture_maps = []
            for block in blocks:
                tex_map = texture_finder.find_textures_for_material(
                    block, tex_search_dirs or [], extensions
                )
                texture_maps.append(tex_map)

            # 检测是否为 map 场景（MSH 数量远超 MDF block 数量）
            is_map = 'map.mdf' in mdf_path.lower() or 'map_' in mdf_path.lower()
            target_block, is_fallback = material_builder.get_block_for_msh(
                blocks, msh_idx, is_map=is_map,
                material_block_index=material_block_index
            )
            if target_block is not None:
                block_idx = blocks.index(target_block)
                tex_map = texture_maps[block_idx] if block_idx < len(texture_maps) else {}

                mat = material_builder.get_or_create_material(
                    target_block, tex_map,
                    mesh_name=obj_name,
                    complexity=complexity,
                    registry=registry,
                )
                obj.data.materials.append(mat)

                # ── Lightmap variant: if block has LightmapSampler with real _pdo ──
                # The core material always uses a neutral white lightmap.
                # If a scene-specific _pdo is available, create a variant that
                # replaces it with the actual lightmap texture.
                if "LightmapSampler" in target_block.samplers:
                    lm_path = tex_map.get("LightmapSampler")
                    if lm_path and os.path.isfile(lm_path):
                        variant = material_builder.create_lightmap_variant(
                            mat, lm_path
                        )
                        if variant:
                            obj.data.materials[-1] = variant
                            print(f"  [MSH Pro] msh{msh_idx:03d} → LM variant: {variant.name}")

                deduped = material_builder.get_deduplicated_blocks(blocks)
                cache_info = ""
                if registry:
                    cache_info = f"registry={registry.stats()['cache_size']}"
                else:
                    cache_info = f"cache={len(material_builder._material_cache)}"

                fallback_tag = " [header]" if material_block_index is not None else " [fallback]" if is_fallback else ""
                print(f"  [MSH Pro] msh{msh_idx:03d} → {mat.name}{fallback_tag} "
                      f"({len(blocks)} blocks, {len(deduped)} unique, {cache_info})")
            else:
                print(f"  [MSH Pro] msh{msh_idx:03d}: no matching material block → fallback")
                fallback = material_builder.build_fallback_material(
                    name=f"SC_Fallback_{obj_name}",
                    color=(0.4, 0.4, 0.5, 1.0)
                )
                obj.data.materials.append(fallback)
        except Exception as e:
            print(f"  [MSH Pro] msh{msh_idx:03d} material link FAILED: {e}")
            print(f"    File: {os.path.basename(filepath)}")
            traceback.print_exc(file=sys.stderr)
            # Create fallback material so object is not left without a material
            fallback = material_builder.build_fallback_material(
                name=f"SC_Fallback_{obj_name}",
                color=(0.4, 0.4, 0.5, 1.0)
            )
            obj.data.materials.append(fallback)

    elif registry is not None:
        # ── 策略2: 无本地 MDF → 库反查 ──
        _link_from_library(obj, raw_name, msh_idx, registry,
                          tex_search_dirs, extensions, complexity)

    else:
        # ── 策略3: 既无 MDF 也无库 → 降级 ──
        fallback = material_builder.build_fallback_material(
            name=f"SC_Fallback_{obj_name}",
            color=(0.4, 0.4, 0.5, 1.0)
        )
        obj.data.materials.append(fallback)
        print(f"  [MSH Pro] msh{msh_idx:03d}: No MDF/library → fallback material")


def _link_from_library(obj, raw_name, msh_idx, registry,
                       tex_search_dirs, extensions, complexity):
    """通过 MaterialRegistry 从静态库反查材质。

    适用场景: 用户只有 MSH，没有 MDF 文件。
    """
    basename = extract_base_name(raw_name)

    # 构建 texture_map_builder
    def _find_texture(rel_path):
        if not tex_search_dirs:
            return None
        # 从 MDF 的 sampler 路径查找实际贴图
        base = os.path.basename(rel_path)
        name_no_ext = os.path.splitext(base)[0]
        for sdir in tex_search_dirs:
            if not os.path.isdir(sdir):
                continue
            for root, dirs, files in os.walk(sdir):
                for f in files:
                    fname_no_ext = os.path.splitext(f)[0]
                    if fname_no_ext.lower() == name_no_ext.lower():
                        ext = os.path.splitext(f)[1].lower()
                        if ext in extensions:
                            return os.path.join(root, f)

        # 尝试后缀匹配（_d, _nm 等）
        from . import shader_presets
        for suffix in ['_d', '_nm', '_sc', '_glow', '_pdo', '_msk']:
            for sdir in tex_search_dirs:
                if not os.path.isdir(sdir):
                    continue
                for root, dirs, files in os.walk(sdir):
                    for f in files:
                        fname_no_ext = os.path.splitext(f)[0]
                        if fname_no_ext.lower() == (name_no_ext + suffix).lower():
                            ext = os.path.splitext(f)[1].lower()
                            if ext in extensions:
                                return os.path.join(root, f)
        return None

    # 从库获取材质列表
    materials = registry.get_materials_for_model(basename, texture_map_builder=_find_texture)

    if materials and materials[msh_idx % len(materials)]:
        obj.data.materials.append(materials[msh_idx % len(materials)])
        print(f"  [MSH Pro] msh{msh_idx:03d}: library → {materials[msh_idx % len(materials)].name}")
    else:
        # 库也无 → 降级
        fallback = material_builder.build_fallback_material(
            name=f"SC_Fallback_{obj_name}",
            color=(0.4, 0.5, 0.4, 1.0)
        )
        obj.data.materials.append(fallback)
        print(f"  [MSH Pro] msh{msh_idx:03d}: library miss → fallback material")
