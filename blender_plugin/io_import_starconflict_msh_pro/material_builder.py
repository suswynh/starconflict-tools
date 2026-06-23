# ============================================================================
# Material Builder — Create Blender materials from MDF + textures
# ============================================================================
"""Build Blender materials with Principled BSDF node networks from
parsed MDF material blocks and found texture files.

Key features:
  - DX→OpenGL normal map conversion (G-channel invert)
  - AO single-channel extraction (R channel from _msk/_pdo)
  - UV tiling from MDF UserParam2_Float4
  - Material deduplication with params-aware hashing
"""

import os
import bpy

from . import shader_presets


# ──────────────────────────────────────────────────────────────
# Image loading
# ──────────────────────────────────────────────────────────────

def _get_or_create_image(texture_path, name_hint="", colorspace='sRGB'):
    """Load an image into Blender's data system, or return existing."""
    if not texture_path or not os.path.isfile(texture_path):
        return None

    basename = os.path.basename(texture_path)
    existing = bpy.data.images.get(basename)
    if existing:
        if existing.filepath != texture_path:
            existing.filepath = texture_path
            existing.reload()
        return existing

    img = bpy.data.images.load(texture_path, check_existing=True)
    img.name = name_hint or basename
    img.colorspace_settings.name = colorspace
    return img


# ──────────────────────────────────────────────────────────────
# Node helpers
# ──────────────────────────────────────────────────────────────

def _find_material_node_tree(material):
    if not material.use_nodes:
        material.use_nodes = True
    return material.node_tree


def _get_or_create_bsdf(node_tree):
    for node in node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            return node
    bsdf = node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    return bsdf


def _get_or_create_output(node_tree):
    for node in node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            return node
    out = node_tree.nodes.new(type='ShaderNodeOutputMaterial')
    out.location = (800, 0)
    return out


def _create_tex_node(node_tree, image, location, label="", colorspace='sRGB'):
    tex = node_tree.nodes.new(type='ShaderNodeTexImage')
    tex.image = image
    tex.location = location
    if label:
        tex.label = label
        tex.name = label
    tex.image.colorspace_settings.name = colorspace
    return tex


def _create_normal_map_node(node_tree, location):
    nm = node_tree.nodes.new(type='ShaderNodeNormalMap')
    nm.location = location
    nm.label = "Normal Map"
    nm.inputs['Strength'].default_value = 1.0
    return nm


def _create_mix_node(node_tree, location, blend_type='MULTIPLY', label="", factor=1.0):
    mix = node_tree.nodes.new(type='ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.blend_type = blend_type
    mix.location = location
    if label:
        mix.label = label
    mix.inputs['Factor'].default_value = factor
    return mix


def _create_separate_rgb(node_tree, location, label=""):
    sep = node_tree.nodes.new(type='ShaderNodeSeparateColor')
    sep.location = location
    if label:
        sep.label = label
    return sep


def _create_combine_rgb(node_tree, location, label=""):
    comb = node_tree.nodes.new(type='ShaderNodeCombineColor')
    comb.location = location
    if label:
        comb.label = label
    return comb


def _create_invert(node_tree, location, label=""):
    inv = node_tree.nodes.new(type='ShaderNodeInvert')
    inv.location = location
    if label:
        inv.label = label
    inv.inputs['Fac'].default_value = 1.0
    return inv


def _create_mapping_node(node_tree, location, scale_xy=(1.0, 1.0)):
    """Create Texture Coordinate + Mapping nodes for UV tiling."""
    tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
    tex_coord.location = (location[0] - 300, location[1])

    mapping = node_tree.nodes.new(type='ShaderNodeMapping')
    mapping.location = location
    mapping.vector_type = 'TEXTURE'
    mapping.inputs['Scale'].default_value = (scale_xy[0], scale_xy[1], 1.0)

    node_tree.links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])
    return mapping


# ──────────────────────────────────────────────────────────────
# DX → OpenGL normal map conversion
# ──────────────────────────────────────────────────────────────

def _build_dx_normal_fix(node_tree, tex_node, location):
    """Insert DX→OpenGL normal map conversion chain:
    Separate RGB → Invert G → Combine RGB → Normal Map.

    Star Conflict uses DirectX normal maps (G channel inverted vs OpenGL).
    """
    base_x = location[0] + 200
    base_y = location[1]

    sep = _create_separate_rgb(node_tree, (base_x, base_y), "Sep DX Norm")
    inv_g = _create_invert(node_tree, (base_x, base_y - 120), "Inv G")
    comb = _create_combine_rgb(node_tree, (base_x + 160, base_y), "Cmb GL Norm")
    nm = _create_normal_map_node(node_tree, (base_x + 320, base_y))

    node_tree.links.new(tex_node.outputs['Color'], sep.inputs['Color'])
    node_tree.links.new(sep.outputs['Red'], comb.inputs['Red'])
    node_tree.links.new(sep.outputs['Green'], inv_g.inputs['Color'])
    node_tree.links.new(inv_g.outputs['Color'], comb.inputs['Green'])
    node_tree.links.new(sep.outputs['Blue'], comb.inputs['Blue'])
    node_tree.links.new(comb.outputs['Color'], nm.inputs['Color'])

    return nm


# ──────────────────────────────────────────────────────────────
# AO single-channel extraction
# ──────────────────────────────────────────────────────────────

def _build_ao_channel_extract(node_tree, tex_node, location):
    """Extract AO data from the R channel of an AO/Lightmap texture.

    Star Conflict _msk and _pdo textures pack AO into the R channel;
    other channels may contain roughness/metallic/height data.
    The green tint users see is G/B channel leakage.
    """
    sep = _create_separate_rgb(node_tree, (location[0] + 200, location[1]), "Sep AO")
    node_tree.links.new(tex_node.outputs['Color'], sep.inputs['Color'])
    # Return the R channel output socket
    return sep.outputs['Red']


# ──────────────────────────────────────────────────────────────
# UV Tiling extraction
# ──────────────────────────────────────────────────────────────

def _extract_uv_tiling(material_block):
    """Extract UV tiling values from MDF parameters.

    For ship_hull: UserParam2_Float4 ( tiling_x tiling_y ? ? )
    For dyn_animated_mock: UserParam1_Float4 ( ??? tiling? )
    For blended objects: UserParam3_Float4 ( tiling_uv0 tiling_uv1 ... )

    Returns:
        tuple[float, float] or None if no tiling info found.
    """
    # Priority: UserParam2_Float4 (common for ship_hull)
    param = material_block.params.get("UserParam2_Float4")
    if param:
        try:
            parts = [float(x) for x in param.strip('() ').split()]
            if len(parts) >= 2 and (parts[0] != 0 or parts[1] != 0):
                u, v = parts[0], parts[1]
                if u != 1.0 or v != 1.0:
                    return (u, v)
        except (ValueError, IndexError):
            pass

    # Fallback: UserParam3_Float4 (blend objects)
    param = material_block.params.get("UserParam3_Float4")
    if param:
        try:
            parts = [float(x) for x in param.strip('() ').split()]
            if len(parts) >= 2 and parts[0] > 0 and parts[1] > 0:
                return (parts[0], parts[1])
        except (ValueError, IndexError):
            pass

    return None


# ──────────────────────────────────────────────────────────────
# Main material builder
# ──────────────────────────────────────────────────────────────

def build_material_from_mdf(material_block, texture_map, name,
                            complexity='FULL'):
    """Create a Blender material from a parsed MDF material block.

    Args:
        material_block: MaterialBlock from mdf_parser.
        texture_map: dict {sampler_name: full_texture_path}.
        name: Name for the Blender material.
        complexity: 'FULL' or 'SIMPLE'.

    Returns:
        bpy.types.Material
    """
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)

    node_tree = _find_material_node_tree(mat)
    for node in list(node_tree.nodes):
        node_tree.nodes.remove(node)

    bsdf = _get_or_create_bsdf(node_tree)
    output = _get_or_create_output(node_tree)
    node_tree.links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    # ── UV Tiling: always create Texture Coordinate + Mapping ──
    tiling = _extract_uv_tiling(material_block)
    scale_xy = tiling if tiling else (1.0, 1.0)
    mapping_node = _create_mapping_node(node_tree,
                                        location=(-700, 200),
                                        scale_xy=scale_xy)

    x_offset = -400
    y_offset = 300
    spacing_y = -280

    ao_outputs = []
    lightmap_output = None
    diffuse_source = None  # for AO multiplication linking

    for sampler_name, texture_path in texture_map.items():
        if texture_path is None:
            continue

        suffix = shader_presets.get_sampler_suffix(sampler_name)
        colorspace = shader_presets.get_colorspace(suffix) if suffix else 'sRGB'

        basename = os.path.basename(texture_path)
        img = _get_or_create_image(texture_path, name_hint=basename,
                                   colorspace=colorspace)
        if img is None:
            continue

        tex_node = _create_tex_node(
            node_tree, img,
            location=(x_offset, y_offset),
            label=sampler_name,
            colorspace=colorspace,
        )

        # ── Connect Mapping to Image Texture Vector input ──
        node_tree.links.new(mapping_node.outputs['Vector'],
                           tex_node.inputs['Vector'])

        # ── Normal sampler → DX fix → Normal Map ──
        if sampler_name == "NormalSampler":
            nm_out = _build_dx_normal_fix(node_tree, tex_node, (x_offset, y_offset))
            node_tree.links.new(nm_out.outputs['Normal'], bsdf.inputs['Normal'])

        # ── Detail normal ──
        elif sampler_name == "DetailSampler":
            if complexity == 'FULL':
                # Simplified: treat as secondary normal (skip for now)
                pass

        # ── AO / Lightmap → extract R channel ──
        elif sampler_name in ("LightmapSampler", "AmbOcclSampler"):
            r_out = _build_ao_channel_extract(node_tree, tex_node, (x_offset, y_offset))
            if sampler_name == "LightmapSampler":
                lightmap_output = r_out
            else:
                ao_outputs.append(r_out)

        # ── Diffuse → Base Color ──
        elif sampler_name == "DiffuseSampler":
            node_tree.links.new(tex_node.outputs['Color'],
                               bsdf.inputs['Base Color'])
            diffuse_source = tex_node

        # ── Glow → Emission ──
        elif sampler_name == "Diffuse2Sampler":
            node_tree.links.new(tex_node.outputs['Color'],
                               bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0

        # ── Specular ──
        elif sampler_name == "SpecularColorSampler":
            node_tree.links.new(tex_node.outputs['Color'],
                               bsdf.inputs['Specular IOR Level'])

        # ── Colormap ──
        elif sampler_name == "ColormapSampler":
            # Store for blending — currently just visible as a node
            pass

        y_offset += spacing_y

    # ── AO/Lightmap blending (FULL mode) ──
    if complexity == 'FULL' and (ao_outputs or lightmap_output):
        bsdf_base = bsdf.inputs['Base Color']
        existing_links = [l for l in node_tree.links
                          if l.to_socket == bsdf_base]

        if existing_links:
            base_src = existing_links[0].from_socket
            node_tree.links.remove(existing_links[0])

            # Chain all AO sources through Multiply nodes
            prev_output = base_src
            mix_x = 200
            mix_y = y_offset - 100

            for ao_out in ao_outputs:
                ao_mix = _create_mix_node(node_tree, (mix_x, mix_y),
                                          blend_type='MULTIPLY', label="AO Mix")
                node_tree.links.new(prev_output, ao_mix.inputs['A'])
                node_tree.links.new(ao_out, ao_mix.inputs['B'])
                prev_output = ao_mix.outputs['Result']
                mix_y -= 80

            if lightmap_output:
                lm_mix = _create_mix_node(node_tree, (mix_x + 200, mix_y),
                                          blend_type='MULTIPLY', label="LM Mix")
                node_tree.links.new(prev_output, lm_mix.inputs['A'])
                node_tree.links.new(lightmap_output, lm_mix.inputs['B'])
                prev_output = lm_mix.outputs['Result']

            node_tree.links.new(prev_output, bsdf_base)

    # ── Material type-specific defaults ──
    mat_type = material_block.shader_type

    if mat_type == "dyn_glass":
        bsdf.inputs['Transmission Weight'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.05
        bsdf.inputs['IOR'].default_value = 1.45

    elif mat_type in ("dyn_fresnel", "fresnel"):
        bsdf.inputs['Transmission Weight'].default_value = 0.3
        bsdf.inputs['Roughness'].default_value = 0.1

    elif mat_type in ("sky", "skybackground"):
        # Sky materials should be emission-only
        bsdf.inputs['Emission Strength'].default_value = 1.0

    # ── Apply UserParam overrides ──
    for param_name, param_val in material_block.params.items():
        try:
            parts = [float(x) for x in param_val.strip('() ').split()]
            if param_name == "UserParam0_Float4" and len(parts) >= 3:
                # Often specular tint / fresnel color
                if parts[0] != 1.0:
                    bsdf.inputs['Specular IOR Level'].default_value = parts[0]
        except (ValueError, IndexError):
            pass

    # ── Transparent material blend mode ──
    if shader_presets.is_transparent_material(mat_type):
        mat.blend_method = 'BLEND'
        mat.shadow_method = 'HASHED'
        # Glass gets full transmission
        if mat_type == "dyn_glass":
            mat.shadow_method = 'NONE'

    return mat


# ──────────────────────────────────────────────────────────────
# Global material cache — cross-object deduplication
# ──────────────────────────────────────────────────────────────

# Session-level cache: signature_key → bpy.types.Material
# Ensures that identical material blocks across different MSH files
# share the same Blender material (e.g. ccc_msh000, ccc_msh006, ccc_msh008
# all using the first-encountered material).
_material_cache = {}


def _make_signature_key(block):
    """Build a normalized cache key from a MaterialBlock.
    
    Paths are normalized (lowercase, forward slashes) so that minor
    path differences don't cause false cache misses.
    """
    sampler_sorted = tuple(
        sorted((k, v.lower().replace('\\', '/')) for k, v in block.samplers.items())
    )
    param_sorted = tuple(sorted(block.params.items()))
    return (block.shader_type, sampler_sorted, param_sorted)


def clear_material_cache():
    """Clear the session material cache (call when changing search paths)."""
    _material_cache.clear()


def get_or_create_material(block, texture_map, mesh_name, complexity='FULL'):
    """Get existing material from cache or create a new one.
    
    Cross-object deduplication: if an identical material (same shader_type,
    samplers, params) was already created for a different mesh, reuse it.
    Otherwise create a new material named m_<mesh_name>.
    
    Args:
        block: MaterialBlock from mdf_parser.
        texture_map: dict {sampler_name: texture_path}.
        mesh_name: Clean mesh name (e.g. "bigship_fed_msh000").
        complexity: 'FULL' or 'SIMPLE'.
    
    Returns:
        bpy.types.Material
    """
    key = _make_signature_key(block)
    if key in _material_cache:
        return _material_cache[key]
    
    mat_name = f"m_{mesh_name}"
    mat = build_material_from_mdf(block, texture_map, name=mat_name, complexity=complexity)
    _material_cache[key] = mat
    return mat


# ──────────────────────────────────────────────────────────────
# Single material extraction (for per-object assignment)
# ──────────────────────────────────────────────────────────────

def get_deduplicated_blocks(mdf_blocks):
    """Return deduplicated material blocks from an MDF, preserving order.
    
    Blocks with identical (shader_type, samplers, params) are collapsed.
    Order is preserved: the Nth unique block corresponds to .mdl-msh<N>.
    
    Args:
        mdf_blocks: List of MaterialBlock.
    
    Returns:
        list[MaterialBlock]: Deduplicated, order-preserved blocks.
    """
    seen = set()
    result = []
    for block in mdf_blocks:
        sig = _make_signature_key(block)
        if sig in seen:
            continue
        seen.add(sig)
        result.append(block)
    return result


def get_block_for_msh(mdf_blocks, msh_index):
    """Get the material block for a specific MSH LOD index.
    
    MDF blocks (deduplicated) map to MSH files by order:
      block 0 → .mdl-msh000
      block 1 → .mdl-msh001
      ...
    Falls back to block 0 if index is out of range.
    
    Args:
        mdf_blocks: List of MaterialBlock.
        msh_index: Integer index extracted from filename (e.g. 0 for msh000).
    
    Returns:
        MaterialBlock or None.
    """
    deduped = get_deduplicated_blocks(mdf_blocks)
    if not deduped:
        return None
    if 0 <= msh_index < len(deduped):
        return deduped[msh_index]
    # Fallback: wrap or use first
    return deduped[0]
