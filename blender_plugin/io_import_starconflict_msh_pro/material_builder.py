# ============================================================================
# Material Builder — Create Blender materials from MDF + textures
# ============================================================================
"""Build Blender materials with Principled BSDF node networks from
parsed MDF material blocks and found texture files.

Key features:
  - DX→OpenGL normal map conversion (DXT5nm: A=NormalX, G=NormalY, R=AO)
  - _msk multi-channel extraction (shader-verified: R=Height, G=AO, B=Glossiness)
  - _pdo lightmap R-channel AO extraction (cosine-weighted, object.fx L629)
  - _nm R-channel AO extraction (FetchBumpOccl.z, object.fx L493)
  - Glossiness → Roughness conversion (invert, for Blender Principled BSDF)
  - UV tiling from MDF UserParam2_Float4
  - UV2 lightmap channel support (separate UV map for _pdo textures)
  - Material deduplication with params-aware hashing
"""

import os
import bpy

from . import shader_presets


# ──────────────────────────────────────────────────────────────
# Image loading
# ──────────────────────────────────────────────────────────────

def _get_or_create_image(texture_path, name_hint="", colorspace='sRGB', alpha_mode='STRAIGHT'):
    """Load an image into Blender's data system, or return existing."""
    if not texture_path or not os.path.isfile(texture_path):
        return None

    basename = os.path.basename(texture_path)
    existing = bpy.data.images.get(basename)
    if existing:
        if existing.filepath != texture_path:
            existing.filepath = texture_path
            existing.reload()
        existing.alpha_mode = alpha_mode
        return existing

    img = bpy.data.images.load(texture_path, check_existing=True)
    img.name = name_hint or basename
    img.colorspace_settings.name = colorspace
    img.alpha_mode = alpha_mode
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


def _create_mapping_node(node_tree, location, scale_xy=(1.0, 1.0), uv_map_name=None):
    """Create Texture Coordinate + Mapping nodes for UV tiling.
    
    Args:
        uv_map_name: If provided, use ShaderNodeUVMap pointing to this UV layer
                     (for lightmap UV2). If None, use default ShaderNodeTexCoord.UV.
    """
    if uv_map_name:
        uv_node = node_tree.nodes.new(type='ShaderNodeUVMap')
        uv_node.uv_map = uv_map_name
        uv_node.location = (location[0] - 300, location[1])
        uv_output = uv_node.outputs['UV']
    else:
        tex_coord = node_tree.nodes.new(type='ShaderNodeTexCoord')
        tex_coord.location = (location[0] - 300, location[1])
        uv_output = tex_coord.outputs['UV']

    mapping = node_tree.nodes.new(type='ShaderNodeMapping')
    mapping.location = location
    mapping.vector_type = 'TEXTURE'
    mapping.inputs['Scale'].default_value = (scale_xy[0], scale_xy[1], 1.0)

    node_tree.links.new(uv_output, mapping.inputs['Vector'])
    return mapping


# ──────────────────────────────────────────────────────────────
# DXT5nm → OpenGL normal map conversion
# ──────────────────────────────────────────────────────────────
# Star Conflict normal maps use DXT5nm-like packed format:
#   R = Ambient Occlusion (NOT normal!)
#   G = Normal Y (tangent space, DirectX: +Y up)
#   B = unused / noise
#   A = Normal X
#
# shader FetchBump():  return bump.wy * 2 - 1  → X=A, Y=G
# shader FetchBumpOccl(): return float3(bump.wy * 2 - 1, bump.x)
#   → X=A*2-1, Y=G*2-1, Occlusion=R
#
# Blender (OpenGL) expects: R=X, G=-Y (inverted), B=Z
# Z = sqrt(1 - X² - Y²)

def _build_dxt5nm_normal(node_tree, tex_node, location):
    """Decode DXT5nm packed normal map → OpenGL tangent-space normal.

    DXT5nm: R=AO, G=NormalY, A=NormalX (stored in [0,1] range)
    Blender Normal Map node internally does `rgb * 2 - 1`,
    so we must feed it the raw [0,1] values.
    
    Node chain (feeding raw [0,1] to Normal Map):
      tex.Alpha ─────────────────────────────→ Comb.R (X raw)
      tex.Green ────────────────────────────→ Comb.G (Y raw)
      (A*2-1)² + (G*2-1)² → 1-sum → sqrt → (z+1)/2 → Comb.B (Z encoded)
      Combine XYZ → Normal Map node → BSDF Normal
    """
    base_x = location[0] + 200
    base_y = location[1]

    def _math(op, value=0.0, loc=(0,0), label=""):
        m = node_tree.nodes.new(type='ShaderNodeMath')
        m.operation = op
        if op in ('SUBTRACT', 'MULTIPLY_ADD'):
            m.inputs[1].default_value = value
        elif op == 'MULTIPLY':
            m.inputs[1].default_value = value
        m.location = loc
        if label:
            m.label = label
            m.name = label
        return m

    sep = _create_separate_rgb(node_tree, (base_x, base_y), "Sep NM")
    node_tree.links.new(tex_node.outputs['Color'], sep.inputs['Color'])

    # ---- Z computation ----
    # X_decoded = Alpha*2 - 1, Y_decoded = Green*2 - 1
    # We feed raw Alpha/Green as R/G to Normal Map, so it does *2-1 automatically.
    # For Z: compute sqrt(1 - Xd² - Yd²), then encode back to [0,1]: (z + 1)/2
    # Xd = Alpha*2-1: Alpha * 2 → - 1
    mul_ax = _math('MULTIPLY', 2.0, (base_x, base_y - 60), "A×2")
    sub_ax = _math('SUBTRACT', 1.0, (base_x + 140, base_y - 60), "-1")
    node_tree.links.new(tex_node.outputs['Alpha'], mul_ax.inputs[0])
    node_tree.links.new(mul_ax.outputs['Value'], sub_ax.inputs[0])
    # Xd²
    sq_x = _math('MULTIPLY', 0.0, (base_x + 280, base_y - 60), "Xd²")
    node_tree.links.new(sub_ax.outputs['Value'], sq_x.inputs[0])
    node_tree.links.new(sub_ax.outputs['Value'], sq_x.inputs[1])

    mul_gy = _math('MULTIPLY', 2.0, (base_x, base_y - 180), "G×2")
    sub_gy = _math('SUBTRACT', 1.0, (base_x + 140, base_y - 180), "-1")
    node_tree.links.new(sep.outputs['Green'], mul_gy.inputs[0])
    node_tree.links.new(mul_gy.outputs['Value'], sub_gy.inputs[0])
    sq_y = _math('MULTIPLY', 0.0, (base_x + 280, base_y - 180), "Yd²")
    node_tree.links.new(sub_gy.outputs['Value'], sq_y.inputs[0])
    node_tree.links.new(sub_gy.outputs['Value'], sq_y.inputs[1])

    add_xy = _math('ADD', 0.0, (base_x + 420, base_y - 120), "X²+Y²")
    node_tree.links.new(sq_x.outputs['Value'], add_xy.inputs[0])
    node_tree.links.new(sq_y.outputs['Value'], add_xy.inputs[1])

    one_minus = _math('SUBTRACT', 0.0, (base_x + 560, base_y - 120), "1-sum")
    one_minus.inputs[0].default_value = 1.0
    node_tree.links.new(add_xy.outputs['Value'], one_minus.inputs[1])

    sqrt_z = _math('SQRT', 0.0, (base_x + 700, base_y - 120), "Z")
    node_tree.links.new(one_minus.outputs['Value'], sqrt_z.inputs[0])

    # Encode Z back to [0,1] for Normal Map: (z + 1) / 2
    add_one = _math('ADD', 1.0, (base_x + 840, base_y - 120), "z+1")
    node_tree.links.new(sqrt_z.outputs['Value'], add_one.inputs[0])
    div_two = _math('MULTIPLY', 0.5, (base_x + 980, base_y - 120), "/2")
    node_tree.links.new(add_one.outputs['Value'], div_two.inputs[0])

    # ---- Combine RGB (raw [0,1] values for Normal Map) ----
    comb = _create_combine_rgb(node_tree, (base_x + 1120, base_y - 60), "Cmb NM")
    node_tree.links.new(tex_node.outputs['Alpha'], comb.inputs['Red'])    # X raw
    node_tree.links.new(sep.outputs['Green'],    comb.inputs['Green'])    # Y raw
    node_tree.links.new(div_two.outputs['Value'], comb.inputs['Blue'])   # Z encoded

    nm = _create_normal_map_node(node_tree, (base_x + 1280, base_y - 60))
    node_tree.links.new(comb.outputs['Color'], nm.inputs['Color'])

    # Return Normal Map node AND the R channel (AO from FetchBumpOccl)
    # object.fx L493: float3 bumpOccl = FetchBumpOccl( NormalSampler, bumpUv );
    # bumpOccl.z = AO (R channel), used to override texOcclusion in certain modes
    return nm, sep.outputs['Red']


# ──────────────────────────────────────────────────────────────
# AO / Lightmap channel extraction
# ──────────────────────────────────────────────────────────────

def _build_ao_channel_extract(node_tree, tex_node, location):
    """Extract lightmap/AO data from the R channel of a _pdo texture.

    _pdo (Precomputed Directional Occlusion) textures store
    cosine-weighted AO in the R channel (verified in object.fx L629:
    globalOcclusion = pdoTex.x). Used by LightmapSampler.
    """
    sep = _create_separate_rgb(node_tree, (location[0] + 200, location[1]), "Sep LM")
    node_tree.links.new(tex_node.outputs['Color'], sep.inputs['Color'])
    return sep.outputs['Red']


def _build_msk_pbr_extract(node_tree, tex_node, location):
    """Extract PBR channels from _msk (AmbOcclSampler) texture.

    VERIFIED from object.fx shader source (L422-428):
      float3 masks = tex2D( AmbOcclSampler, baseUv ).rgb;
      float glossFactor = masks.b;    // B = Glossiness
      texOcclusion = masks.g * ...;   // G = AO / Occlusion
      // R channel: used for Parallax height offset (L330-331),
      //            unused in default rendering path.

    Star Conflict uses a Blinn-Phong SPECULAR-GLOSS workflow:
      specPower = exp2( 9 * glossFactor + 2 )  (L683)

    Returns:
        (height_r, ao_g, gloss_b): R=Height, G=AO, B=Glossiness.
    """
    sep = _create_separate_rgb(node_tree, (location[0] + 200, location[1]), "Sep MSK")
    node_tree.links.new(tex_node.outputs['Color'], sep.inputs['Color'])
    # R = Height (parallax), G = AO, B = Glossiness
    return sep.outputs['Red'], sep.outputs['Green'], sep.outputs['Blue']


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

    # ── UV Tiling: create Texture Coordinate + Mapping ──
    tiling = _extract_uv_tiling(material_block)
    scale_xy = tiling if tiling else (1.0, 1.0)
    mapping_node = _create_mapping_node(node_tree,
                                        location=(-700, 200),
                                        scale_xy=scale_xy)
    
    # ── Lightmap UV2 mapping (separate UV channel) ──
    has_lightmap = "LightmapSampler" in texture_map and texture_map["LightmapSampler"] is not None
    lightmap_mapping = None
    if has_lightmap:
        lightmap_mapping = _create_mapping_node(node_tree,
                                                location=(-700, -80),
                                                scale_xy=(1.0, 1.0),
                                                uv_map_name="lightmap")

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

        # RGBA 颜色贴图使用 CHANNEL_PACKED 模式
        _rgba_samplers = {"DiffuseSampler", "ColormapSampler",
                          "Diffuse2Sampler", "SpecularColorSampler"}
        alpha_mode = 'CHANNEL_PACKED' if sampler_name in _rgba_samplers else 'STRAIGHT'

        basename = os.path.basename(texture_path)
        img = _get_or_create_image(texture_path, name_hint=basename,
                                   colorspace=colorspace, alpha_mode=alpha_mode)
        if img is None:
            continue

        tex_node = _create_tex_node(
            node_tree, img,
            location=(x_offset, y_offset),
            label=sampler_name,
            colorspace=colorspace,
        )

        # ── Connect Mapping to Image Texture Vector input ──
        if sampler_name == "LightmapSampler" and lightmap_mapping:
            node_tree.links.new(lightmap_mapping.outputs['Vector'],
                               tex_node.inputs['Vector'])
        else:
            node_tree.links.new(mapping_node.outputs['Vector'],
                               tex_node.inputs['Vector'])

        # ── Normal sampler → DXT5nm decode → Normal Map + AO ──
        if sampler_name == "NormalSampler":
            nm_out, nm_ao = _build_dxt5nm_normal(node_tree, tex_node, (x_offset, y_offset))
            node_tree.links.new(nm_out.outputs['Normal'], bsdf.inputs['Normal'])
            # R channel from _nm = AO (FetchBumpOccl.z)
            # object.fx L493-550: bumpOccl.z = occlusion from normal map
            ao_outputs.append(nm_ao)

        # ── Detail normal ──
        elif sampler_name == "DetailSampler":
            if complexity == 'FULL':
                # Simplified: treat as secondary normal (skip for now)
                pass

        # ── Lightmap → extract R channel only ──
        elif sampler_name == "LightmapSampler":
            r_out = _build_ao_channel_extract(node_tree, tex_node, (x_offset, y_offset))
            lightmap_output = r_out

        # ── AmbOccl (_msk) → extract R/G/B (shader-verified channel mapping) ──
        elif sampler_name == "AmbOcclSampler":
            h_out, ao_out, gloss_out = _build_msk_pbr_extract(node_tree, tex_node, (x_offset, y_offset))
            # G channel → AO (multiplied with Base Color, object.fx L428: texOcclusion = masks.g)
            ao_outputs.append(ao_out)
            # B channel → Glossiness → Invert → Roughness
            # object.fx L427: glossFactor = masks.b
            # object.fx L683: specPower = exp2(9 * glossFactor + 2)
            # Blender Principled BSDF expects Roughness (0-1), so invert:
            gloss_inv = _create_invert(node_tree, (x_offset + 440, y_offset - 60), "Gloss→Rough")
            node_tree.links.new(gloss_out, gloss_inv.inputs['Color'])
            node_tree.links.new(gloss_inv.outputs['Color'], bsdf.inputs['Roughness'])
            # R channel → Height/Parallax (unused in default path, left for manual use)

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
    # AO sources (multiplied with Base Color in order):
    #   1. _nm R channel (FetchBumpOccl.z) — primary static AO
    #   2. _msk G channel (masks.g) — texture-based AO/detail occlusion
    #   3. _pdo R channel (pdoTex.x) — precomputed lightmap AO (UV2)
    # Glossiness from _msk B is inverted → Roughness (connected above).
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
# Global material cache — cross-object deduplication (legacy)
# ──────────────────────────────────────────────────────────────

# Session-level cache: signature_key → bpy.types.Material
# NOTE: 新版推荐使用 MaterialRegistry 替代此缓存。
# 保留此方法以保持向后兼容。
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


def get_or_create_material(block, texture_map, mesh_name, complexity='FULL',
                           registry=None):
    """Get existing material from cache or create a new one.
    
    优先使用 registry（基于贴图指纹的全局去重），
    回退到 legacy 缓存。
    
    Args:
        block: MaterialBlock from mdf_parser.
        texture_map: dict {sampler_name: texture_path}.
        mesh_name: Clean mesh name (e.g. "bigship_fed_msh000").
        complexity: 'FULL' or 'SIMPLE'.
        registry: MaterialRegistry 实例（可选，推荐）
    
    Returns:
        bpy.types.Material
    """
    # ── 优先使用 Registry（全局去重 + 指纹ID命名）──
    if registry is not None:
        return registry.get_or_create(block, texture_map, complexity)
    
    # ── Legacy 回退 ──
    key = _make_signature_key(block)
    if key in _material_cache:
        return _material_cache[key]
    
    mat_name = f"m_{mesh_name}"
    mat = build_material_from_mdf(block, texture_map, name=mat_name, complexity=complexity)
    _material_cache[key] = mat
    return mat


# ──────────────────────────────────────────────────────────────
# Fallback material — when no textures are available
# ──────────────────────────────────────────────────────────────

def build_fallback_material(name="SC_Fallback", color=(0.5, 0.5, 0.5, 1.0)):
    """创建一个简单的降级材质（无贴图时使用）。
    
    Args:
        name: 材质名
        color: RGBA 基础色
    
    Returns:
        bpy.types.Material
    """
    import bpy
    
    existing = bpy.data.materials.get(name)
    if existing:
        return existing
    
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs['Base Color'].default_value = color
        bsdf.inputs['Roughness'].default_value = 0.5
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


def get_block_for_msh(mdf_blocks, msh_index, is_map=False,
                      mapping_db=None, mdf_path=None):
    """Get the material block for a specific MSH LOD index.
    
    Lookup order:
      1. Static Mapping DB override (if available) → verified mapping
      2. 1:1 index match (for in-range indices)
      3. Modulo spread (for out-of-range map tiles)
    
    For ship models (is_map=False): exact 1:1 mapping, LODs ≤ block count.
    For map tiles (is_map=True): MSH count >> MDF block count.
      - DB override takes priority over all defaults
      - In-range indices: matched 1:1 (best effort)
      - Out-of-range: spread via modulo hash to avoid everything
        collapsing to block[0] (visually diverse fallback)
    
    Args:
        mdf_blocks: List of MaterialBlock (original order from MDF file).
        msh_index: Integer index extracted from filename (e.g. 0 for msh000).
        is_map: True if this is a map-level import (many MSH, few MDF blocks).
        mapping_db: Optional MaterialMappingDB instance for override lookup.
        mdf_path: Path to the .mdf file (required if mapping_db is provided).
    
    Returns:
        (MaterialBlock or None, is_fallback: bool, confidence: str or None)
        is_fallback: True when block was assigned by heuristic, not exact match.
        confidence: DB confidence level if from override, else None.
    """
    if not mdf_blocks:
        return None, False, None
    
    # ── Strategy 0: Static Mapping DB override ──
    if mapping_db is not None and mdf_path:
        override = mapping_db.get_override(mdf_path, msh_index)
        if override is not None:
            block_idx, confidence = override
            if 0 <= block_idx < len(mdf_blocks):
                return mdf_blocks[block_idx], False, confidence
            # DB override out of range → warn, fall through to default
            print(f"  [MappingDB] 警告: msh{msh_index:03d} DB覆盖 block={block_idx} "
                  f"超出MDF范围({len(mdf_blocks)})，回退默认")
    
    # ── Strategy 1: 1:1 index match ──
    if 0 <= msh_index < len(mdf_blocks):
        return mdf_blocks[msh_index], False, None
    
    # ── Strategy 2: Modulo spread (map only) ──
    if is_map and len(mdf_blocks) > 0:
        return mdf_blocks[msh_index % len(mdf_blocks)], True, None
    
    return mdf_blocks[0], True, None
