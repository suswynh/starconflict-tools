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
    """Load an image into Blender's data system, or return existing.

    Returns None gracefully if the image cannot be loaded (e.g. unsupported
    format in Blender 5.0's updated OIIO/OCIO pipeline), so callers can
    fall back to a default material rather than crashing the entire import.
    """
    if not texture_path or not os.path.isfile(texture_path):
        return None

    basename = os.path.basename(texture_path)
    existing = bpy.data.images.get(basename)
    if existing:
        try:
            if existing.filepath != texture_path:
                existing.filepath = texture_path
                existing.reload()
            if hasattr(existing, 'alpha_mode'):
                existing.alpha_mode = alpha_mode
            return existing
        except Exception:
            # Reload failed → remove stale image and try fresh load below
            try:
                bpy.data.images.remove(existing)
            except Exception:
                pass

    try:
        img = bpy.data.images.load(texture_path, check_existing=True)
    except Exception:
        # Blender 5.0 may reject certain DDS sub-formats that 4.x accepted
        return None

    if img is None:
        return None

    try:
        img.name = name_hint or basename
        img.colorspace_settings.name = colorspace
        if hasattr(img, 'alpha_mode'):
            img.alpha_mode = alpha_mode
    except Exception:
        # Name conflict or colorspace error → remove and fail gracefully
        try:
            bpy.data.images.remove(img)
        except Exception:
            pass
        return None

    return img


def _get_neutral_lightmap():
    """Create or retrieve a shared 1×1 white image for default lightmap.

    All core materials use this neutral lightmap by default, so the
    lightmap AO multiplication chain has no visual effect (×1.0).
    Scene-specific lightmaps are applied via create_lightmap_variant().

    Returns:
        bpy.types.Image: A 1×1 white Non-Color image shared globally.
    """
    name = "__lightmap_neutral__"
    img = bpy.data.images.get(name)
    # Recreate if invalid (e.g. from a previous failed run)
    if img is None or img.size[0] != 1 or img.size[1] != 1:
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, 1, 1, alpha=True, float_buffer=False)
        img.pixels = [1.0, 1.0, 1.0, 1.0]  # RGBA: 4 channels match alpha=True
        img.colorspace_settings.name = 'Non-Color'
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
    mix.factor_mode = 'UNIFORM'  # explicit default for Blender 5.0 compat
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


def _create_vector_math_node(node_tree, location, operation='ADD', label=""):
    """Create a Vector Math node (for normal blending)."""
    vm = node_tree.nodes.new(type='ShaderNodeVectorMath')
    vm.operation = operation
    vm.location = location
    if label:
        vm.label = label
    return vm


def _create_bump_node(node_tree, location, label="", strength=1.0):
    """Create a Bump node in Normal Map mode (for detail normal overlay)."""
    bump = node_tree.nodes.new(type='ShaderNodeBump')
    bump.location = location
    bump.inputs['Strength'].default_value = strength
    bump.inputs['Distance'].default_value = 1.0
    if label:
        bump.label = label
    return bump


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

def _parse_float4(param_str):
    """Parse a float parameter string like '(0.174 0.174 0.174)' into a list."""
    try:
        return [float(x) for x in param_str.strip('() ').split()]
    except (ValueError, AttributeError):
        return []


def _extract_uv_tiling(material_block, mat_type=None):
    """Extract UV tiling values from MDF parameters.

    object.fx L40 (CB_MATERIAL_PARAMS):
      // tailig factors (base/detail/armor) / uniform fog / glow intencity
      ufloat4 UserParam2_Float4;

    object.fx L186-187 (vertex shader, BUMP_DETAIL || ALBEDO_DETAIL):
      o.uv0.xy = o.uv0.xy * UserParam2_Float4.x;   // base tiling (isotropic scalar)
      o.uv0.wz = o.uv0.xy * UserParam2_Float4.y;    // detail tiling (isotropic scalar)

    Note: .x and .y are ISOTROPIC scalars (same multiplier for U and V),
    NOT a 2D (tiling_u, tiling_v) vector. .x = base tiling, .y = detail tiling.

    Returns:
        dict {'base': float, 'detail': float} or None if no tiling info found.
        detail is the compound factor (base × detail) since the shader chain is:
        detailUV = baseUV(scaled by .x) * .y = originalUV * .x * .y
    """
    # Blend types: UserParam2_Float4 controls ColormapSampler blend params,
    # NOT global UV tiling. Don't attempt to extract — use default.
    # Decals: decals.fx L11: UserParam2_Float4 = "stay / falloff times", NOT tiling.
    if mat_type in ("object_norm_blend", "dyn_object_norm_blend",
                    "ship_decals", "ship_static_decals", "decals"):
        return None

    # Primary: UserParam2_Float4 (object.fx: ship_hull, object_norm, dyn_object_norm)
    param = material_block.params.get("UserParam2_Float4")
    if param:
        try:
            parts = [float(x) for x in param.strip('() ').split()]
            if len(parts) >= 2:
                base_tiling = parts[0]
                detail_tiling = parts[1] if len(parts) >= 2 else 1.0
                # Compound detail = base × detail (shader chain: L186→L187)
                compound_detail = base_tiling * detail_tiling
                # Return only if non-trivial
                if base_tiling != 1.0 or detail_tiling != 1.0:
                    return {'base': base_tiling, 'detail': compound_detail}
        except (ValueError, IndexError):
            pass

    return None


def _add_uv_animation(node_tree, mapping_node, material_block, mat_type):
    """Add UV scroll/rotation animation driven by frame time.

    Reads UserParam2_Float4.z (scroll speed) and .w (rotation speed).
    Only active for animated_mock shader types — other shader types use
    UserParam2_Float4.z/w for non-animation purposes (detail bump, etc.).

    Returns:
        The animation Mapping node if created, else the original mapping_node.
    """
    # UV animation is specific to animated_mock variants
    if mat_type not in ("animated_mock", "dyn_animated_mock"):
        return mapping_node
    param = material_block.params.get("UserParam2_Float4", "")
    if not param:
        return mapping_node

    try:
        parts = [float(x) for x in param.strip('() ').split()]
    except (ValueError, IndexError):
        return mapping_node

    if len(parts) < 4:
        return mapping_node

    scroll_speed = parts[2]
    rotate_speed = parts[3]

    if scroll_speed == 0.0 and rotate_speed == 0.0:
        return mapping_node

    # ── Time node driven by current frame ──
    time_node = node_tree.nodes.new(type='ShaderNodeValue')
    time_node.name = "UV_Time"
    time_node.label = "UV Time"
    time_node.outputs[0].default_value = 0.0
    time_node.location = (mapping_node.location[0] - 300,
                          mapping_node.location[1] - 180)
    try:
        fcurve = time_node.outputs[0].driver_add('default_value')
        fcurve.driver.expression = 'frame / 24'
    except Exception:
        pass

    # ── Animation Mapping node: chain after static mapping ──
    anim_map = node_tree.nodes.new(type='ShaderNodeMapping')
    anim_map.name = "UV_Anim"
    anim_map.label = "UV Animation"
    anim_map.vector_type = 'TEXTURE'
    anim_map.location = (mapping_node.location[0] + 200,
                         mapping_node.location[1])
    # Preserve static tiling (scale already applied on first mapping)
    anim_map.inputs['Scale'].default_value = (1.0, 1.0, 1.0)
    # Feed static mapping output → animation mapping input
    node_tree.links.new(mapping_node.outputs['Vector'],
                        anim_map.inputs['Vector'])

    base_x = mapping_node.location[0]
    base_y = mapping_node.location[1] - 180
    offset_y = 0

    if scroll_speed != 0.0:
        mul = node_tree.nodes.new(type='ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.label = f"Scroll {scroll_speed:.2f}/s"
        mul.location = (base_x, base_y + offset_y)
        mul.inputs[1].default_value = scroll_speed
        node_tree.links.new(time_node.outputs[0], mul.inputs[0])

        comb = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        comb.label = "UV Scroll"
        comb.location = (base_x + 140, base_y + offset_y)
        comb.inputs[0].default_value = 0.0
        comb.inputs[2].default_value = 0.0
        node_tree.links.new(mul.outputs[0], comb.inputs[1])

        node_tree.links.new(comb.outputs['Vector'],
                            anim_map.inputs['Location'])
        offset_y -= 160

    if rotate_speed != 0.0:
        mul = node_tree.nodes.new(type='ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.label = f"Rot {rotate_speed:.2f} rad/s"
        mul.location = (base_x, base_y + offset_y)
        mul.inputs[1].default_value = rotate_speed
        node_tree.links.new(time_node.outputs[0], mul.inputs[0])

        comb = node_tree.nodes.new(type='ShaderNodeCombineXYZ')
        comb.label = "UV Rotate"
        comb.location = (base_x + 140, base_y + offset_y)
        comb.inputs[0].default_value = 0.0
        comb.inputs[1].default_value = 0.0
        node_tree.links.new(mul.outputs[0], comb.inputs[2])

        node_tree.links.new(comb.outputs['Vector'],
                            anim_map.inputs['Rotation'])

    return anim_map


def _add_param_annotations(node_tree, material_block, mat_type):
    """Add a Frame node with UserParam documentation.

    Parses MDF UserParam values and pins flags, generates human-readable
    annotations describing UV animation, transparency mode, tiling, etc.
    """
    lines = [f"MDF: {mat_type}"]
    params = material_block.params
    pins = material_block.pins

    # ── animated_mock UV animation ──
    if mat_type in ("animated_mock", "dyn_animated_mock"):
        up2 = params.get("UserParam2_Float4", "")
        up4 = params.get("UserParam4_Float4", "")
        up0 = params.get("UserParam0_Float4", "")
        try:
            p2 = [float(x) for x in up2.strip('() ').split()]
            if len(p2) >= 4:
                if p2[0] != 0 or p2[1] != 0:
                    lines.append(f"UV Static Offset: ({p2[0]:.3f}, {p2[1]:.3f})")
                if p2[2] != 0:
                    lines.append(f"UV Scroll Y: {p2[2]:.3f}/s")
                if p2[3] != 0:
                    lines.append(f"UV Rotate: {p2[3]:.3f} rad/s")
        except (ValueError, IndexError):
            pass
        try:
            p4 = [float(x) for x in up4.strip('() ').split()]
            if len(p4) >= 4:
                nonzero = any(v != 0 for v in p4)
                if nonzero:
                    lines.append(f"UV Anim Offset: ({p4[0]:.3f},{p4[1]:.3f},{p4[2]:.3f},{p4[3]:.3f})")
        except (ValueError, IndexError):
            pass
        try:
            p0 = [float(x) for x in up0.strip('() ').split()]
            if len(p0) >= 2:
                lines.append(f"Glow Intensity: {p0[0]:.3f}")
        except (ValueError, IndexError):
            pass

    # ── object_norm detail tiling ──
    if mat_type in ("object_norm", "dyn_object_norm"):
        up2 = params.get("UserParam2_Float4", "")
        up3 = params.get("UserParam3_Float4", "")
        try:
            p2 = [float(x) for x in up2.strip('() ').split()]
            if len(p2) >= 2 and (p2[0] != 1.0 or p2[1] != 1.0):
                lines.append(f"UV Tiling: ({p2[0]:.2f}, {p2[1]:.2f})")
        except (ValueError, IndexError):
            pass
        try:
            p3 = [float(x) for x in up3.strip('() ').split()]
            if len(p3) >= 4:
                if p3[2] != 0 or p3[3] != 0:
                    lines.append(f"UV Scroll: ({p3[2]:.3f}, {p3[3]:.3f})/s")
        except (ValueError, IndexError):
            pass

    # ── sky UV animation ──
    if mat_type in ("sky", "skybackground"):
        up0 = params.get("UserParam0_Float4", "")
        up2 = params.get("UserParam2_Float4", "")
        try:
            p0 = [float(x) for x in up0.strip('() ').split()]
            if len(p0) >= 4:
                if p0[0] != 0:
                    lines.append(f"UV Rotate: {p0[0]:.3f} rad/s")
                if p0[1] != 0:
                    lines.append(f"UV Scroll X: {p0[1]:.3f}/s")
        except (ValueError, IndexError):
            pass
        try:
            p2 = [float(x) for x in up2.strip('() ').split()]
            if len(p2) >= 2:
                if p2[0] != 0:
                    lines.append(f"UV Scroll Y: {p2[0]:.3f}/s")
                if p2[1] != 0:
                    lines.append(f"Layer2 Scroll X: {p2[1]:.3f}/s")
        except (ValueError, IndexError):
            pass

    # ── Pins flags ──
    pin_descs = []
    if pins.get("User0") == 1: pin_descs.append("AlphaTest")
    if pins.get("User1") == 1:
        if mat_type in ("animated_mock", "dyn_animated_mock"):
            u1_map = {0: "BlendAlpha", 1: "Additive", 2: "CodeAlpha",
                      3: "CodeTransp", 4: "AlphaFromDiffuse"}
            pin_descs.append(f"Blend={u1_map.get(pins['User1'], str(pins['User1']))}")
        else:
            pin_descs.append("Glow")
    if pins.get("User2") == 1:
        if mat_type in ("animated_mock", "dyn_animated_mock"):
            pin_descs.append("CullNone")
        elif mat_type in ("object_norm", "dyn_object_norm"):
            pin_descs.append("BumpDetail")
        elif mat_type in ("sky",):
            pin_descs.append("ColorMap")
        elif mat_type in ("ship_hull",):
            pin_descs.append("Dyeing")
    if pins.get("User3") == 1:
        if mat_type in ("object_norm", "dyn_object_norm"):
            pin_descs.append("AlbedoDetail")
    if pins.get("User4") == 1: pin_descs.append("UniformSpecular")
    if pins.get("Type") == 5: pin_descs.append("PDO")
    if pins.get("Type") == 1: pin_descs.append("ExtraMasks")

    if pin_descs:
        lines.append("Pins: " + ", ".join(pin_descs))

    # Skip if nothing to annotate
    if len(lines) <= 1:
        return

    # Create Frame node
    frame = node_tree.nodes.new(type='NodeFrame')
    frame.label = "\n".join(lines)
    frame.name = "MDF_Params"
    # Shrink frame by default (minimize visual clutter)
    frame.shrink = True
    # Position the frame below all other nodes
    frame.location = (-720, -400)


def _add_tweak_nodes(node_tree, bsdf):
    """Insert Value→Multiply coefficient nodes before key BSDF inputs.

    Allows users to easily tweak transparency, roughness, metallic, and
    emission strength directly in the Blender Shader Editor.
    Each chain: user_tweak → Multiply → BSDF socket.
    """
    tweaks = [
        ('Alpha', 1.0, (-580, -540)),
        ('Roughness', 1.0, (-580, -600)),
        ('Metallic', 0.0, (-580, -660)),
        ('Emission Strength', 1.0, (-580, -720)),
    ]

    for socket_name, default_val, loc in tweaks:
        socket = bsdf.inputs.get(socket_name)
        if socket is None:
            continue

        # Only insert tweak nodes when something IS connected.
        # Never override Blender defaults for unconnected sockets
        # (Emission Strength=0.0, Roughness=0.5, Metallic=0.0, Alpha=1.0).
        existing = [l for l in bsdf.id_data.links if l.to_socket == socket]
        if not existing:
            continue

        # Existing link → insert Multiply node in between
        src_socket = existing[0].from_socket
        bsdf.id_data.links.remove(existing[0])

        # Value node for user tweaking
        val_node = bsdf.id_data.nodes.new(type='ShaderNodeValue')
        val_node.location = (loc[0] - 180, loc[1])
        val_node.label = socket_name
        val_node.outputs['Value'].default_value = default_val

        # Multiply node
        mul_node = bsdf.id_data.nodes.new(type='ShaderNodeMath')
        mul_node.operation = 'MULTIPLY'
        mul_node.location = loc
        mul_node.label = f"{socket_name}×"

        # Reconnect: src → Multiply.A, Value → Multiply.B, Multiply → BSDF
        bsdf.id_data.links.new(src_socket, mul_node.inputs[0])
        bsdf.id_data.links.new(val_node.outputs['Value'], mul_node.inputs[1])
        bsdf.id_data.links.new(mul_node.outputs['Value'], socket)


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

    # ── Glass material (dyn_glass) — parameter-driven, no samplers ──
    mat_type = material_block.shader_type
    if mat_type == "dyn_glass":
        # UserParam0_Float4: (R, G, B) — glass tint color
        if "UserParam0_Float4" in material_block.params:
            parts = _parse_float4(material_block.params["UserParam0_Float4"])
            if len(parts) >= 3:
                bsdf.inputs['Base Color'].default_value = (parts[0], parts[1], parts[2], 1.0)

        # UserParam0_Float: (alpha, ?, ?, ?) — first component = opacity
        alpha = 0.5
        if "UserParam0_Float" in material_block.params:
            parts = _parse_float4(material_block.params["UserParam0_Float"])
            if len(parts) >= 1:
                alpha = parts[0]

        bsdf.inputs['Alpha'].default_value = alpha
        bsdf.inputs['Transmission Weight'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.1

        # UserParam1_Float4: (ior, fresnel_x, fresnel_y) — Fresnel params
        if "UserParam1_Float4" in material_block.params:
            parts = _parse_float4(material_block.params["UserParam1_Float4"])
            if len(parts) >= 2:
                # Use fresnel power to adjust roughness
                fresnel_strength = parts[1] if parts[1] > 0 else 0.1
                bsdf.inputs['Roughness'].default_value = max(0.0, min(1.0, 1.0 - fresnel_strength))

        mat.blend_method = 'BLEND'
        mat.shadow_method = 'HASHED'
        mat.use_screen_refraction = True
        return mat

    # ── UV Tiling: base (diffuse) + detail (bump/albedo) ──
    tiling = _extract_uv_tiling(material_block, mat_type)
    base_tiling = tiling['base'] if tiling else 1.0
    detail_tiling = tiling['detail'] if tiling else 1.0
    mapping_node = _create_mapping_node(node_tree,
                                        location=(-700, 200),
                                        scale_xy=(base_tiling, base_tiling))
    # Detail textures (DetailSampler, UserSampler1) use separate tiling
    # object.fx L187: detailUV = baseUV * detail_tiling → compound factor
    detail_mapping = None
    if detail_tiling != 1.0:
        detail_mapping = _create_mapping_node(node_tree,
                                              location=(-700, 260),
                                              scale_xy=(detail_tiling, detail_tiling))
    # object_norm_blend: ColormapSampler uses separate tiling from UserParam3_Float4.y
    # object.fx L323: secondUv = i.uv0.xy * UserParam3_Float4.y
    cm_blend_mapping = None
    if mat_type in ("object_norm_blend", "dyn_object_norm_blend"):
        cm_tiling = 1.0
        up3 = material_block.params.get("UserParam3_Float4")
        if up3:
            try:
                parts = [float(x) for x in up3.strip('() ').split()]
                if len(parts) >= 2 and parts[1] != 1.0:
                    cm_tiling = parts[1]
            except (ValueError, IndexError):
                pass
        if cm_tiling != 1.0:
            cm_blend_mapping = _create_mapping_node(node_tree,
                                                    location=(-700, 320),
                                                    scale_xy=(cm_tiling, cm_tiling))

    # ── UV animation: add frame-driven scroll/rotate for animated_mock types ──
    mapping_node = _add_uv_animation(node_tree, mapping_node, material_block, mat_type)
     
    # ── Lightmap UV mapping ──
    # Always create the lightmap node chain. The core material binds a shared
    # 1×1 white neutral image so UV coords don't matter (any coord → white).
    # Use default TexCoord (uv_map_name=None) to avoid ShaderNodeUVMap
    # referencing a potentially non-existent "lightmap" UV layer, which can
    # cause GPU shader compilation failure in Blender 5.0.
    # Scene-specific _pdo textures are applied via create_lightmap_variant().
    lightmap_mapping = _create_mapping_node(node_tree,
                                            location=(-700, -80),
                                            scale_xy=(1.0, 1.0),
                                            uv_map_name=None)
    # Label the TexCoord feeding the lightmap so create_lightmap_variant()
    # can upgrade it to UVMap("lightmap") for real _pdo textures.
    for link in node_tree.links:
        if link.to_node == lightmap_mapping and link.to_socket == lightmap_mapping.inputs['Vector']:
            if link.from_node.type == 'TEX_COORD':
                link.from_node.label = "LightmapUV"
            break
    # Store real lightmap path for post-import variant creation (may be None)
    _real_lightmap_path = texture_map.get("LightmapSampler")

    # ── animated_mock: ColormapSampler uses UV2 (Tex1), DiffuseSampler uses UV1 (Tex0) ──
    # animated_mock.fx: o.uv0.xy=v.Tex0 (base), o.uv0.zw=v.Tex1 (cm)
    mat_type = material_block.shader_type
    has_cm = "ColormapSampler" in texture_map and texture_map["ColormapSampler"] is not None
    cm_uv2_mapping = None
    if mat_type in ("animated_mock", "dyn_animated_mock") and has_cm:
        cm_uv2_mapping = _create_mapping_node(node_tree,
                                              location=(-700, -160),
                                              scale_xy=(1.0, 1.0),
                                              uv_map_name="FX")

    x_offset = -400
    y_offset = 300
    spacing_y = -280

    ao_outputs = []
    lightmap_output = None
    diffuse_source = None  # for AO multiplication linking
    colormap_source = None  # for ColormapSampler RGB mixing (gate_mask02)
    colormap_shader_type = None  # shader type for cm mixing logic
    detail_bump_tex = None  # DetailSampler texture node for post-loop normal mixing
    detail_bump_strength = 1.0
    detail_albedo_tex = None  # UserSampler1 texture node for post-loop albedo mixing
    nm_out_node = None  # Normal Map output node for detail normal blending
    spec_alpha_gloss_out = None  # _sc Alpha → roughness (fallback when _msk absent)

    for sampler_name, texture_path in texture_map.items():
        if texture_path is None:
            continue

        # LightmapSampler is handled after the loop with a neutral white image.
        # The real _pdo path is stored in _real_lightmap_path for variant creation.
        if sampler_name == "LightmapSampler":
            continue

        suffix = shader_presets.get_sampler_suffix(sampler_name)
        colorspace = shader_presets.get_colorspace(suffix) if suffix else 'sRGB'

        # RGBA 颜色贴图使用 CHANNEL_PACKED 模式
        _rgba_samplers = {"DiffuseSampler", "ColormapSampler",
                          "Diffuse2Sampler", "SpecularColorSampler",
                          "AmbOcclSampler"}
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
        # animated_mock: ColormapSampler → UV2 (Tex1 in shader)
        elif sampler_name == "ColormapSampler" and cm_uv2_mapping:
            node_tree.links.new(cm_uv2_mapping.outputs['Vector'],
                               tex_node.inputs['Vector'])
        # object_norm_blend: ColormapSampler → separate tiling (UserParam3_Float4.y)
        elif sampler_name == "ColormapSampler" and cm_blend_mapping:
            node_tree.links.new(cm_blend_mapping.outputs['Vector'],
                               tex_node.inputs['Vector'])
        # Detail textures → separate detail tiling (object.fx L187)
        elif sampler_name in ("DetailSampler", "UserSampler1") and detail_mapping:
            node_tree.links.new(detail_mapping.outputs['Vector'],
                               tex_node.inputs['Vector'])
        else:
            node_tree.links.new(mapping_node.outputs['Vector'],
                               tex_node.inputs['Vector'])

        # ── Normal sampler → DXT5nm decode → Normal Map + AO ──
        if sampler_name == "NormalSampler":
            nm_out, nm_ao = _build_dxt5nm_normal(node_tree, tex_node, (x_offset, y_offset))
            node_tree.links.new(nm_out.outputs['Normal'], bsdf.inputs['Normal'])
            # R channel from _nm = AO (FetchBumpOccl.z)
            # object.fx L549-551: bumpOccl.z is only used in BL2_DETAIL/PD_OCCL paths.
            # object.fx L422-428: general path uses _msk G instead (masks.g).
            # These are MUTUALLY EXCLUSIVE — don't chain both together.
            # Skip _nm AO if _msk (AmbOcclSampler) is present (general path).
            has_msk = "AmbOcclSampler" in texture_map and texture_map["AmbOcclSampler"] is not None
            if not has_msk:
                ao_outputs.append(nm_ao)
            nm_out_node = nm_out  # store for detail normal post-loop blending

        # ── Detail normal ──
        elif sampler_name == "DetailSampler":
            # object.fx L530-533 (BUMP_DETAIL):
            #   normalTS.xy += detailNormal.xy; normalTS = normalize(normalTS)
            # Note: BUMP_DETAIL uses simple additive blending (strength=1.0).
            #       BL2_DETAIL (blend types) uses partial derivative blending
            #       with UserParam4_Float4.z/w scale factors (object.fx L521-522).
            # Store for post-loop mixing with the main Normal Map output.
            if complexity == 'FULL':
                detail_bump_tex = tex_node
                detail_bump_strength = 1.0
                # UserParam4_Float4.z is detail-bump factor ONLY in BL2_DETAIL (blend types)
                # object.fx L521: detailNormal = lerp(0, detailNormal, UserParam4_Float4.z)
                if mat_type in ("object_norm_blend", "dyn_object_norm_blend"):
                    param = material_block.params.get("UserParam4_Float4")
                    if param:
                        try:
                            parts = [float(x) for x in param.strip('() ').split()]
                            if len(parts) >= 3:
                                detail_bump_strength = parts[2]
                        except (ValueError, IndexError):
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
            # B channel → Glossiness → nonlinear → Roughness
            # object.fx L427: glossFactor = masks.b
            # object.fx L683: specPower = exp2(9 * glossFactor + 2)  (Blinn-Phong)
            # GGX approximation: roughness = 1 - gloss² (better than linear invert)
            gloss_sq = node_tree.nodes.new(type='ShaderNodeMath')
            gloss_sq.operation = 'MULTIPLY'
            gloss_sq.location = (x_offset + 440, y_offset - 60)
            gloss_sq.label = "Gloss²"
            node_tree.links.new(gloss_out, gloss_sq.inputs[0])
            node_tree.links.new(gloss_out, gloss_sq.inputs[1])
            
            gloss_inv = _create_invert(node_tree, (x_offset + 600, y_offset - 60), "Gloss→Rough")
            node_tree.links.new(gloss_sq.outputs['Value'], gloss_inv.inputs['Color'])
            
            # ── Clamp roughness to [0.03, 0.97] ──
            # Prevents extreme values while preserving dynamic range
            clamp_min = node_tree.nodes.new(type='ShaderNodeMath')
            clamp_min.operation = 'MAXIMUM'
            clamp_min.location = (x_offset + 760, y_offset - 60)
            clamp_min.label = "Rough>0.03"
            clamp_min.inputs[1].default_value = 0.03
            node_tree.links.new(gloss_inv.outputs['Color'], clamp_min.inputs[0])

            clamp_max = node_tree.nodes.new(type='ShaderNodeMath')
            clamp_max.operation = 'MINIMUM'
            clamp_max.location = (x_offset + 920, y_offset - 60)
            clamp_max.label = "Rough<0.97"
            clamp_max.inputs[1].default_value = 0.97
            node_tree.links.new(clamp_min.outputs['Value'], clamp_max.inputs[0])

            node_tree.links.new(clamp_max.outputs['Value'], bsdf.inputs['Roughness'])
            # R channel → Height/Parallax (unused in default path, left for manual use)

        # ── Diffuse → Base Color (with per-type alpha and emission handling) ──
        elif sampler_name == "DiffuseSampler":
            diffuse_source = tex_node
            mat_type = material_block.shader_type

            # Determine how to route diffuse color and alpha based on material type
            if mat_type == "skybackground":
                # Building billboard impostors (fed_station_01.dds):
                #   - Alpha channel has building silhouette cutouts → connect directly
                #   - Also has NormalSampler for fake 3D (handled by NormalSampler branch)
                node_tree.links.new(tex_node.outputs['Alpha'],
                                   bsdf.inputs['Alpha'])
                base_color_src = tex_node.outputs['Color']

            elif mat_type in ("sky", "planets"):
                # Planet atmosphere (ceres_aura.dds):
                #   - Alpha channel is white (no cutout data)
                #   - sky.fx: color.rgb *= color.a * MAX_RGBS_RANGE
                #   - User request: use color luminance as alpha (bright→opaque, dark→fade)
                #   - Creates atmospheric glow fade effect
                # sky.fx: color.rgb *= color.a * MAX_RGBS_RANGE (alpha = 1.0 → color * 4)
                # Still multiply by alpha for general correctness
                alpha_mul = _create_mix_node(node_tree, (x_offset + 240, y_offset - 60),
                                             blend_type='MULTIPLY', label="Alpha*Color")
                node_tree.links.new(tex_node.outputs['Color'], alpha_mul.inputs['A'])
                node_tree.links.new(tex_node.outputs['Alpha'], alpha_mul.inputs['B'])
                base_color_src = alpha_mul.outputs['Result']

                # Convert color luminance → BSDF Alpha for atmosphere fade
                lum_to_alpha = node_tree.nodes.new(type='ShaderNodeRGBToBW')
                lum_to_alpha.location = (x_offset + 240, y_offset - 120)
                lum_to_alpha.label = "Lum→Alpha"
                node_tree.links.new(tex_node.outputs['Color'], lum_to_alpha.inputs['Color'])
                node_tree.links.new(lum_to_alpha.outputs['Val'], bsdf.inputs['Alpha'])
            else:
                base_color_src = tex_node.outputs['Color']
                # ── Transparent materials: Diffuse alpha → BSDF Alpha ──
                # Covers two sources of transparency:
                #   a) Explicit transparent shader types (glass, fresnel, decals, etc.)
                #   b) AlphaTest pin (User0=1): used by trees/vegetation for leaf
                #      cutouts — game-side alpha-test becomes Blender alpha clip.
                if (shader_presets.is_transparent_material(mat_type)
                    or material_block.pins.get("User0") == 1):
                    node_tree.links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])

            node_tree.links.new(base_color_src, bsdf.inputs['Base Color'])

            # ── Self-illumination: Diffuse → Emission (all sky types without _glow) ──
            if mat_type in ("sky", "skybackground", "planets") \
               and "Diffuse2Sampler" not in texture_map:
                node_tree.links.new(base_color_src, bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = 1.0

            # ── animated_mock without ColormapSampler (inner_glow etc) ──
            # No gate_mask02 → transparency from Diffuse luminance + additive emission
            if mat_type in ("animated_mock", "dyn_animated_mock") \
               and "ColormapSampler" not in texture_map:
                # RGB → BW → Alpha (bright = more opaque/visible)
                glow_lum = node_tree.nodes.new(type='ShaderNodeRGBToBW')
                glow_lum.location = (x_offset + 240, y_offset - 120)
                glow_lum.label = "Glow→Alpha"
                node_tree.links.new(tex_node.outputs['Color'], glow_lum.inputs['Color'])
                node_tree.links.new(glow_lum.outputs['Val'], bsdf.inputs['Alpha'])
                # Diffuse → Emission (additive glow)
                node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = 1.0
                # Set Roughness=0 for emissive surfaces
                bsdf.inputs['Roughness'].default_value = 0.3

            # ── animated_mock WITH ColormapSampler (gate_scroll + gate_mask02) ──
            # gate_scroll is a glowing scrolling texture → connect to Emission
            if mat_type in ("animated_mock", "dyn_animated_mock") \
               and "ColormapSampler" in texture_map:
                node_tree.links.new(tex_node.outputs['Color'], bsdf.inputs['Emission Color'])
                bsdf.inputs['Emission Strength'].default_value = 1.0
                bsdf.inputs['Roughness'].default_value = 0.3

        # ── Glow → Emission ──
        elif sampler_name == "Diffuse2Sampler":
            # object.fx L856-869: glowLum = SiGetLuminance(glow.rgb) * UserParam2_Float4.w + 1.0
            # Extract luminance before feeding to Emission for better match
            glow_lum = node_tree.nodes.new(type='ShaderNodeRGBToBW')
            glow_lum.location = (x_offset + 200, y_offset)
            glow_lum.label = "Glow Lum"
            node_tree.links.new(tex_node.outputs['Color'], glow_lum.inputs['Color'])
            
            # Apply UserParam2_Float4.w as glow intensity modifier
            up2 = material_block.params.get("UserParam2_Float4", "")
            glow_intensity = 1.0
            if up2:
                try:
                    parts = [float(x) for x in up2.strip('() ').split()]
                    if len(parts) >= 4:
                        # object.fx L865: glowLum *= UserParam2_Float4.w + 1.0
                        glow_intensity = parts[3] + 1.0
                except (ValueError, IndexError):
                    pass
            
            # Multiply luminance by intensity, then multiply back with original color
            glow_mul_lum = node_tree.nodes.new(type='ShaderNodeMath')
            glow_mul_lum.operation = 'MULTIPLY'
            glow_mul_lum.location = (x_offset + 360, y_offset)
            glow_mul_lum.label = "Glow×Intensity"
            glow_mul_lum.inputs[1].default_value = glow_intensity
            node_tree.links.new(glow_lum.outputs['Val'], glow_mul_lum.inputs[0])
            
            glow_mul_color = node_tree.nodes.new(type='ShaderNodeMix')
            glow_mul_color.data_type = 'RGBA'
            glow_mul_color.blend_type = 'MULTIPLY'
            glow_mul_color.location = (x_offset + 520, y_offset)
            glow_mul_color.label = "Glow×Color"
            glow_mul_color.inputs['Factor'].default_value = 1.0
            node_tree.links.new(tex_node.outputs['Color'], glow_mul_color.inputs['A'])
            node_tree.links.new(glow_mul_lum.outputs['Value'], glow_mul_color.inputs['B'])
            
            node_tree.links.new(glow_mul_color.outputs['Result'],
                               bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 1.0

        # ── Specular ──
        elif sampler_name == "SpecularColorSampler":
            # object.fx L389-397: specColor.rgb from SpecularColorSampler RGB
            # Connect to Specular Tint (color-tinted specular), not Specular IOR Level
            node_tree.links.new(tex_node.outputs['Color'],
                               bsdf.inputs['Specular Tint'])
            # object.fx L416: glossFactor = specColorTex.a (sc Alpha = glossiness)
            # Extract Alpha → invert → use as roughness fallback when _msk not present
            spec_gloss_inv = _create_invert(node_tree, (x_offset + 200, y_offset - 80), "SC Gloss→Rough")
            node_tree.links.new(tex_node.outputs['Alpha'], spec_gloss_inv.inputs['Color'])
            spec_alpha_gloss_out = spec_gloss_inv.outputs['Color']

        # ── UserSampler1 → Detail Albedo (ALBEDO_DETAIL) ──
        # object.fx L344-345:
        #   albedo *= tex2D(UserSampler1, detailUv) * 2;
        # Store for post-loop multiplication into Base Color.
        elif sampler_name == "UserSampler1":
            if complexity == 'FULL':
                detail_albedo_tex = tex_node

        # ── Colormap ──
        elif sampler_name == "ColormapSampler":
            # animated_mock.fx: albedo.a = cm.a (alpha from ColormapSampler)
            # But gate_mask02.dds alpha is often pure white; in that case use
            # RGB luminance as fallback (shader: albedo.rgb *= cm.rgb, luminance≈opacity)
            if shader_presets.is_transparent_material(material_block.shader_type):
                # RGB → BW luminance as alpha fallback
                cm_lum = node_tree.nodes.new(type='ShaderNodeRGBToBW')
                cm_lum.location = (x_offset + 240, y_offset - 30)
                cm_lum.label = "CM Luminance"
                node_tree.links.new(tex_node.outputs['Color'], cm_lum.inputs['Color'])
                # Mix: prefer alpha, fallback to luminance (user can adjust factor)
                cm_alpha_mix = _create_mix_node(node_tree, (x_offset + 400, y_offset - 30),
                                                blend_type='MIX', label="CM Alpha|Lum")
                cm_alpha_mix.inputs['Factor'].default_value = 1.0  # default: use alpha
                node_tree.links.new(tex_node.outputs['Alpha'], cm_alpha_mix.inputs['A'])
                node_tree.links.new(cm_lum.outputs['Val'], cm_alpha_mix.inputs['B'])
                node_tree.links.new(cm_alpha_mix.outputs['Result'], bsdf.inputs['Alpha'])
            # Store for RGB multiplication with Diffuse color (post-loop processing)
            # animated_mock.fx: albedo.rgb *= cm.rgb (gate_scroll × gate_mask02 RGB)
            colormap_source = tex_node
            colormap_shader_type = material_block.shader_type

        y_offset += spacing_y

    # ── Post-loop: Neutral lightmap (always present) ──
    # The core material always has a lightmap node chain with a shared 1×1 white
    # neutral image. This ensures consistent node group structure for all materials
    # while the lightmap AO multiply (×1.0) has no visual effect.
    # Scene-specific _pdo textures replace this via create_lightmap_variant().
    neutral_img = _get_neutral_lightmap()
    lm_tex_node = node_tree.nodes.new(type='ShaderNodeTexImage')
    lm_tex_node.location = (x_offset, y_offset)
    lm_tex_node.image = neutral_img
    lm_tex_node.label = "Lightmap (neutral)"
    # NOTE: Do NOT set color_space on the node — the Image already has
    # Non-Color in _get_neutral_lightmap(). Node-level override conflicts
    # with Blender 5.0's GPU shader compilation (causes pink materials).
    node_tree.links.new(lightmap_mapping.outputs['Vector'],
                        lm_tex_node.inputs['Vector'])
    lightmap_output = _build_ao_channel_extract(node_tree, lm_tex_node,
                                                (x_offset, y_offset))
    y_offset += spacing_y

    # ── Post-loop: Detail Albedo multiplication (ALBEDO_DETAIL, pins User3=1) ──
    # object.fx L344-345: albedo *= tex2D(UserSampler1, detailUv) * 2
    if complexity == 'FULL' and detail_albedo_tex and diffuse_source:
        bsdf_base = bsdf.inputs['Base Color']
        existing_links = [l for l in node_tree.links if l.to_socket == bsdf_base]
        if existing_links:
            base_src = existing_links[0].from_socket
            node_tree.links.remove(existing_links[0])
            
            # Multiply detail albedo × 2 (shader: albedo *= detailAlbedo * 2)
            detail_mul = _create_mix_node(node_tree, (200, y_offset - 80),
                                          blend_type='MULTIPLY', label="DetailAlbedo×2")
            node_tree.links.new(base_src, detail_mul.inputs['A'])
            node_tree.links.new(detail_albedo_tex.outputs['Color'], detail_mul.inputs['B'])
            
            # Multiply by 2
            factor_two = node_tree.nodes.new(type='ShaderNodeMath')
            factor_two.operation = 'MULTIPLY'
            factor_two.inputs[0].default_value = 2.0
            factor_two.location = (400, y_offset - 80)
            factor_two.label = "×2"
            node_tree.links.new(detail_mul.outputs['Result'], factor_two.inputs[1])
            
            # Clamp to prevent overshoot
            clamp = node_tree.nodes.new(type='ShaderNodeClamp')
            clamp.location = (540, y_offset - 80)
            clamp.label = "Clamp"
            clamp.inputs['Min'].default_value = 0.0
            clamp.inputs['Max'].default_value = 10.0
            node_tree.links.new(factor_two.outputs['Value'], clamp.inputs['Value'])
            
            node_tree.links.new(clamp.outputs['Result'], bsdf.inputs['Base Color'])
            # Update diffuse_source for downstream AO linking
            diffuse_source = None  # already connected to BSDF
            y_offset -= 100

    # ── Post-loop: Detail Normal blending (BUMP_DETAIL, pins User2=1) ──
    # object.fx L530-533:
    #   detailNormal = FetchBump(DetailSampler, detailUv);
    #   normalTS.xy += detailNormal.xy;
    #   normalTS = normalize(normalTS);
    if complexity == 'FULL' and detail_bump_tex and nm_out_node:
        # Disconnect existing Normal Map → BSDF link
        existing_nm_links = [l for l in node_tree.links
                             if l.from_node == nm_out_node
                             and l.to_socket == bsdf.inputs['Normal']]
        for l in existing_nm_links:
            node_tree.links.remove(l)
        
        # Create Bump node for detail normal (reads from DetailSampler texture)
        # NOTE: The shader does direct XY addition of decoded normals:
        #   detailNormal = FetchBump(DetailSampler, detailUv); // bump.wy * 2 - 1
        #   normalTS.xy += detailNormal.xy; normalTS = normalize(normalTS);
        # The Bump node converts height→normals instead, which is an approximation.
        # For exact match, DetailSampler would need a separate DXT5nm decode + Normal Map.
        detail_bump = _create_bump_node(node_tree, (200, y_offset - 80),
                                        label="Detail Bump",
                                        strength=detail_bump_strength)
        node_tree.links.new(detail_bump_tex.outputs['Color'],
                           detail_bump.inputs['Height'])
        
        # Vector Math: Add main normal + detail bump normal
        vm_add = _create_vector_math_node(node_tree, (400, y_offset - 80),
                                          operation='ADD', label="Normal Add")
        node_tree.links.new(nm_out_node.outputs['Normal'], vm_add.inputs[0])
        node_tree.links.new(detail_bump.outputs['Normal'], vm_add.inputs[1])
        
        # Vector Math: Normalize
        vm_norm = _create_vector_math_node(node_tree, (560, y_offset - 80),
                                           operation='NORMALIZE', label="Normalize")
        node_tree.links.new(vm_add.outputs['Vector'], vm_norm.inputs[0])
        
        # Connect to BSDF Normal
        node_tree.links.new(vm_norm.outputs['Vector'], bsdf.inputs['Normal'])
        y_offset -= 120

    # ── Post-loop: _sc Alpha → Roughness fallback ──
    # object.fx L416: glossFactor = specColorTex.a  (when _sc texture present)
    # If _msk wasn't processed (no roughness link exists), fall back to _sc Alpha.
    if spec_alpha_gloss_out:
        existing_roughness = [l for l in node_tree.links
                              if l.to_socket == bsdf.inputs['Roughness']]
        if not existing_roughness:
            node_tree.links.new(spec_alpha_gloss_out, bsdf.inputs['Roughness'])

    # ── Post-loop: Uniform Specular Color (pins User4=1 / SPEC) ──
    # object.fx L393-394: specColor.rgb = UserParam0_Float4.rgb
    # object.fx L401-403: #ifndef SPEC → specColor = 0 (disabled without SPEC macro)
    # Only activate when: (a) no SpecularColorSampler texture was used
    #                    (b) pins User4=1 (UNIFORM_SPECULAR_COLOR / SPEC enabled)
    has_spec_tex = "SpecularColorSampler" in texture_map and texture_map["SpecularColorSampler"] is not None
    has_spec_pin = material_block.pins.get(4, 0) == 1 if hasattr(material_block, 'pins') and material_block.pins else False
    if not has_spec_tex and has_spec_pin:
        param = material_block.params.get("UserParam0_Float4")
        if param:
            try:
                parts = [float(x) for x in param.strip('() ').split()]
                if len(parts) >= 3:
                    spec_rgb = parts[:3]
                    # Only apply if non-trivial (not (0,0,0) or (1,1,1))
                    if spec_rgb != [0.0, 0.0, 0.0] and spec_rgb != [1.0, 1.0, 1.0]:
                        # Create RGB node with the specular color
                        spec_node = node_tree.nodes.new(type='ShaderNodeRGB')
                        spec_node.location = (-300, y_offset - 80)
                        spec_node.label = "Spec Color"
                        spec_node.outputs['Color'].default_value = (
                            spec_rgb[0], spec_rgb[1], spec_rgb[2], 1.0
                        )
                        node_tree.links.new(spec_node.outputs['Color'],
                                           bsdf.inputs['Specular Tint'])
                        y_offset -= 60
            except (ValueError, IndexError):
                pass

    # ── AO/Lightmap blending (FULL mode) ──
    # AO sources (multiplied with Base Color in order):
    #   1. _nm R channel (FetchBumpOccl.z) — primary static AO
    #   2. _msk G channel (masks.g) — texture-based AO/detail occlusion
    #   3. _pdo R channel (pdoTex.x) — precomputed lightmap AO (UV2)
    # Glossiness from _msk B is inverted → Roughness (connected above).
    if complexity == 'FULL' and (ao_outputs or lightmap_output or colormap_source):
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

            # ── Colormap RGB blending (shader-type dependent) ──
            # object_norm_blend: object.fx L360 — lerp(albedo, cm.rgb, blendFactor)
            #   blendFactor depends on vertex intensity, cm Alpha, brightness, contrast
            # animated_mock:     animated_mock.fx — albedo.rgb *= cm.rgb (multiply)
            if colormap_source:
                if colormap_shader_type in ("object_norm_blend", "dyn_object_norm_blend"):
                    # Lerp blend: Diffuse ← → Colormap (like shader object.fx L360)
                    # blendFactor = saturate((vertIntensity + (brightness-1+cmAlpha)*vertIntensity - 0.5)*(contrast+1)+0.5)
                    # Simplified: use brightness (UserParam2_Float4.y) to drive blend
                    # Default: 0.3 (70% Diffuse, 30% Colormap) — "Diffuse为主，Colormap为辅"
                    blend_factor = 0.3
                    if material_block.params.get("UserParam2_Float4"):
                        try:
                            parts = [float(x) for x in material_block.params["UserParam2_Float4"].strip('() ').split()]
                            if len(parts) >= 2:
                                brightness = max(0.0, min(2.0, parts[1]))
                                blend_factor = max(0.1, min(0.9, brightness * 0.4))
                        except (ValueError, IndexError):
                            pass
                    cm_mix = _create_mix_node(node_tree, (mix_x, mix_y),
                                              blend_type='MIX', label="CM Blend",
                                              factor=blend_factor)
                else:
                    # Multiply blend: albedo.rgb *= cm.rgb (animated_mock, sky, etc.)
                    cm_mix = _create_mix_node(node_tree, (mix_x, mix_y),
                                              blend_type='MULTIPLY', label="CM×Diff")
                node_tree.links.new(prev_output, cm_mix.inputs['A'])
                node_tree.links.new(colormap_source.outputs['Color'], cm_mix.inputs['B'])
                prev_output = cm_mix.outputs['Result']
                mix_y -= 80

            for ao_out in ao_outputs:
                ao_mix = _create_mix_node(node_tree, (mix_x, mix_y),
                                          blend_type='MULTIPLY', label="AO Mix")
                node_tree.links.new(prev_output, ao_mix.inputs['A'])
                node_tree.links.new(ao_out, ao_mix.inputs['B'])
                prev_output = ao_mix.outputs['Result']
                mix_y -= 80

            if lightmap_output:
                # Lightmap mix: lerp(BaseColor, BaseColor * Lightmap, strength)
                # object.fx L629: globalOcclusion = pdoTex.x (cosine-weighted AO)
                # Simple multiply makes everything too dark in Blender (no env lighting)
                # Use mix with strength factor instead for user control
                lm_mul = _create_mix_node(node_tree, (mix_x + 200, mix_y),
                                          blend_type='MULTIPLY', label="LM Mul")
                node_tree.links.new(prev_output, lm_mul.inputs['A'])
                node_tree.links.new(lightmap_output, lm_mul.inputs['B'])

                lm_mix = _create_mix_node(node_tree, (mix_x + 400, mix_y),
                                          blend_type='MIX', label="LM Mix",
                                          factor=0.3)  # default strength: 30% (prevents over-darkening)
                node_tree.links.new(prev_output, lm_mix.inputs['A'])
                node_tree.links.new(lm_mul.outputs['Result'], lm_mix.inputs['B'])
                prev_output = lm_mix.outputs['Result']

            node_tree.links.new(prev_output, bsdf_base)

    # ── Material type-specific defaults ──
    mat_type = material_block.shader_type

    if mat_type == "dyn_glass":
        bsdf.inputs['Transmission Weight'].default_value = 1.0
        bsdf.inputs['Roughness'].default_value = 0.05
        bsdf.inputs['IOR'].default_value = 1.45

    elif mat_type in ("dyn_fresnel", "fresnel"):
        # fresnel.fx UserParam layout:
        #   UserParam0_Float4 = diffuse tiling/offset
        #   UserParam1_Float4 = mask tiling/offset
        #   UserParam2_Float4 = fresnelColor / transparency (L13)
        #   UserParam3_Float4 = color / gloss (L15)
        #   UserParam4_Float4 = dir/min/power/intensity (L17)
        # Apply the key parameters that affect visual appearance:
        if "UserParam2_Float4" in material_block.params:
            parts = _parse_float4(material_block.params["UserParam2_Float4"])
            if len(parts) >= 4:
                bsdf.inputs['Base Color'].default_value = (parts[0], parts[1], parts[2], 1.0)
                bsdf.inputs['Alpha'].default_value = parts[3]
        if "UserParam3_Float4" in material_block.params:
            parts = _parse_float4(material_block.params["UserParam3_Float4"])
            if len(parts) >= 4:
                bsdf.inputs['Specular Tint'].default_value = (parts[0], parts[1], parts[2], 1.0)
                bsdf.inputs['Roughness'].default_value = max(0.03, min(0.97, 1.0 - parts[3]))
        bsdf.inputs['Transmission Weight'].default_value = 0.3
        mat.blend_method = 'BLEND'
        if hasattr(mat, 'shadow_method'):
            mat.shadow_method = 'NONE'

    elif mat_type in ("sky", "skybackground"):
        # Sky materials should be emission-only
        bsdf.inputs['Emission Strength'].default_value = 1.0

    # ── UserParam annotations (Frame node with parameter documentation) ──
    _add_param_annotations(node_tree, material_block, mat_type)

    # ── Tweak nodes: add multiplier coefficients for key BSDF inputs ──
    _add_tweak_nodes(node_tree, bsdf)

    # ── Transparent material blend mode ──
    if shader_presets.is_transparent_material(mat_type):
        mat.blend_method = 'BLEND'
        if hasattr(mat, 'shadow_method'):
            mat.shadow_method = 'HASHED'
        # Glass gets full transmission
        if mat_type == "dyn_glass":
            if hasattr(mat, 'shadow_method'):
                mat.shadow_method = 'NONE'
    elif material_block.pins.get("User0") == 1:
        # AlphaTest pin (game-side): trees, grass, vegetation with leaf
        # cutout textures. Use CLIP mode (hard on/off at threshold) to
        # match the game's alpha-test behavior.
        mat.blend_method = 'CLIP'
        if hasattr(mat, 'alpha_threshold'):
            mat.alpha_threshold = 0.5
        if hasattr(mat, 'shadow_method'):
            mat.shadow_method = 'CLIP'

    return mat


# ──────────────────────────────────────────────────────────────
# Lightmap Variant — scene-specific _pdo override
# ──────────────────────────────────────────────────────────────

def create_lightmap_variant(core_material, lightmap_texture_path, variant_suffix="lm"):
    """Create a lightmap variant of a core material by replacing the
    neutral white lightmap image with an actual scene-specific _pdo.

    The core material (built by build_material_from_mdf) always has a
    neutral 1×1 white lightmap node. This function:
      1. Makes a full copy of the core material (new datablock + node tree)
      2. Finds the lightmap Image Texture node (labeled "Lightmap (neutral)")
      3. Replaces its image with the scene's _pdo texture
    
    The object can then be assigned this variant instead of the core material,
    while all other objects sharing the same core textures continue to use
    the original (neutral) material.

    Args:
        core_material: bpy.types.Material — the shared core material.
        lightmap_texture_path: str — full path to the scene's _pdo texture.
        variant_suffix: str — suffix for the variant material name.

    Returns:
        bpy.types.Material or None — the variant material, or None on failure.
    """
    if not lightmap_texture_path or not os.path.isfile(lightmap_texture_path):
        return None

    # Check if this exact variant already exists
    lm_basename = os.path.splitext(os.path.basename(lightmap_texture_path))[0]
    variant_name = "{}_lm_{}".format(core_material.name, lm_basename)
    if len(variant_name) > 63:
        variant_name = variant_name[:63]

    existing = bpy.data.materials.get(variant_name)
    if existing:
        return existing

    try:
        # Full copy (material + node tree)
        variant = core_material.copy()
        variant.name = variant_name

        # Load the lightmap texture (may fail in Blender 5.0 for some DDS formats)
        lm_img = _get_or_create_image(lightmap_texture_path,
                                      name_hint=lm_basename,
                                      colorspace='Non-Color',
                                      alpha_mode='STRAIGHT')
        if lm_img is None:
            bpy.data.materials.remove(variant)
            return None

        # Find and replace the neutral lightmap image in the node tree
        node_tree = variant.node_tree
        lm_tex_node = None
        for node in node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.label == "Lightmap (neutral)":
                node.image = lm_img
                node.label = "Lightmap ({})".format(lm_basename)
                lm_tex_node = node
                break

        # Switch lightmap UV from default TexCoord to UVMap("lightmap")
        # for correct lightmap sampling on models that have UV2 data.
        for node in node_tree.nodes:
            if node.type == 'TEX_COORD' and node.label == "LightmapUV":
                uv_map = node_tree.nodes.new(type='ShaderNodeUVMap')
                uv_map.uv_map = "lightmap"
                uv_map.location = node.location
                # Rewire all outgoing connections from TexCoord → UVMap
                for link in list(node_tree.links):
                    if link.from_node == node:
                        node_tree.links.new(uv_map.outputs['UV'],
                                            link.to_socket)
                node_tree.nodes.remove(node)
                break

        return variant
    except Exception as e:
        # Blender 5.0 may fail on material.copy() or image assignment
        # for certain material configurations. Fail gracefully.
        import sys
        print("[MSH Pro] Lightmap variant failed for {}: {}".format(
            core_material.name, str(e)), file=sys.stderr)
        # Clean up partial variant if created
        if 'variant' in locals() and variant:
            try:
                bpy.data.materials.remove(variant)
            except Exception:
                pass
        return None


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
                      material_block_index=None):
    """Get the material block for a specific MSH piece.

    Lookup order:
      1. MSH header material_block_index (embedded in .mdl-msh file) → authoritative
      2. 1:1 index match (for in-range indices)
      3. Modulo spread (for out-of-range map tiles)

    For ship models (is_map=False): exact 1:1 mapping, LODs ≤ block count.
    For map tiles (is_map=True): MSH count >> MDF block count.
      - MSH header block index takes priority (authoritative source)
      - In-range indices: matched 1:1 (best effort)
      - Out-of-range: spread via modulo hash

    Args:
        mdf_blocks: List of MaterialBlock (original order from MDF file).
        msh_index: Integer index extracted from filename (e.g. 0 for msh000).
        is_map: True if this is a map-level import (many MSH, few MDF blocks).
        material_block_index: Optional int from MSH header[0x00].
            If valid (0 <= idx < len(mdf_blocks)), used as authoritative source.

    Returns:
        (MaterialBlock or None, is_fallback: bool)
        is_fallback: True when block was assigned by heuristic, not exact match.
    """
    if not mdf_blocks:
        return None, False

    # ── Strategy 1: MSH header material_block_index (authoritative) ──
    if material_block_index is not None and 0 <= material_block_index < len(mdf_blocks):
        return mdf_blocks[material_block_index], False

    # ── Strategy 2: 1:1 index match ──
    if 0 <= msh_index < len(mdf_blocks):
        return mdf_blocks[msh_index], False

    # ── Strategy 3: Modulo spread (map only) ──
    if is_map and len(mdf_blocks) > 0:
        return mdf_blocks[msh_index % len(mdf_blocks)], True
    
    return mdf_blocks[0], True
