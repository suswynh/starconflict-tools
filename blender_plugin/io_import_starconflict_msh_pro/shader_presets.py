# ============================================================================
# Shader Presets — Material Type to Sampler Mapping & Node Network Templates
# ============================================================================
"""Define mappings from Hammer Engine material types to texture sampler suffixes
and Blender Principled BSDF node connections.

Each preset describes:
  - Which sampler types a material type expects
  - Which texture suffix corresponds to each sampler
  - How to connect textures to Principled BSDF inputs
  - Color space for each texture type
"""

# ──────────────────────────────────────────────────────────────
# Sampler → Texture Suffix Mapping (canonical)
# ──────────────────────────────────────────────────────────────

SAMPLER_TO_SUFFIX = {
    "DiffuseSampler":         "_d",
    "Diffuse2Sampler":        "_glow",
    "NormalSampler":          "_nm",
    "SpecularColorSampler":   "_sc",
    "ColormapSampler":        "_s1",
    "LightmapSampler":        "_pdo",
    "AmbOcclSampler":         "_msk",
    "DetailSampler":          "_nm",  # detail normal reuses normal texture
    "EnvSampler":             None,   # cubemap — no suffix mapping
    "ReflectionsSampler":     None,   # cubemap — no suffix mapping
    "UserSampler1":           None,   # custom — no suffix mapping
}

# ──────────────────────────────────────────────────────────────
# Texture Color Space: sRGB vs Non-Color
# ──────────────────────────────────────────────────────────────

TEXTURE_COLORSPACE = {
    "_d":    "sRGB",
    "_nm":   "Non-Color",
    "_sc":   "sRGB",
    "_s1":   "sRGB",
    "_glow": "sRGB",
    "_pdo":  "Non-Color",
    "_msk":  "Non-Color",
}

# ──────────────────────────────────────────────────────────────
# Sampler → Principled BSDF Input Mapping
# ──────────────────────────────────────────────────────────────

SAMPLER_TO_BSDF_INPUT = {
    "DiffuseSampler":         "Base Color",
    "NormalSampler":          "Normal",          # via Normal Map node
    "SpecularColorSampler":   "Specular IOR Level",
    "Diffuse2Sampler":        "Emission Color",
    "LightmapSampler":        None,              # multiply with Base Color via Mix
    "AmbOcclSampler":         None,              # multiply with Base Color via Mix
    "ColormapSampler":        None,              # blend/dye — user-defined
    "DetailSampler":          None,              # detail normal — advanced
}

# ──────────────────────────────────────────────────────────────
# Material Type → Expected Samplers
# ──────────────────────────────────────────────────────────────

MATERIAL_SAMPLERS = {
    # ── Ship / Weapon hull ──
    "ship_hull": [
        "DiffuseSampler",
        "NormalSampler",
        "SpecularColorSampler",
        "Diffuse2Sampler",
        "LightmapSampler",
        "ColormapSampler",
    ],

    # ── Decals ──
    "ship_decals": [
        "DiffuseSampler",
        "NormalSampler",
        "LightmapSampler",
    ],
    "ship_static_decals": [
        "DiffuseSampler",
        "NormalSampler",
        "LightmapSampler",
    ],

    # ── Static objects ──
    "object": [
        "DiffuseSampler",
    ],
    "object_norm": [
        "DiffuseSampler",
        "NormalSampler",
    ],
    "object_norm_blend": [
        "DiffuseSampler",
        "NormalSampler",
        "ColormapSampler",
    ],

    # ── Dynamic objects ──
    "dyn_object": [
        "DiffuseSampler",
        "AmbOcclSampler",
    ],
    "dyn_object_norm": [
        "DiffuseSampler",
        "NormalSampler",
        "SpecularColorSampler",
        "AmbOcclSampler",
        "DetailSampler",
    ],
    "dyn_object_norm_blend": [
        "DiffuseSampler",
        "NormalSampler",
        "SpecularColorSampler",
        "ColormapSampler",
    ],

    # ── Animated mock ──
    "dyn_animated_mock": [
        "DiffuseSampler",
        "ColormapSampler",
    ],
    "animated_mock": [
        "DiffuseSampler",
        "ColormapSampler",
    ],

    # ── Glass ──
    "dyn_glass": [
        # glass uses parameters, not textures
    ],

    # ── Fresnel ──
    "dyn_fresnel": [
        "DiffuseSampler",
    ],
    "fresnel": [
        "DiffuseSampler",
    ],

    # ── Drone ──
    "dyn_drone": [
        "DiffuseSampler",
    ],

    # ── Blank objects ──
    "dyn_blank_object": [],
    "blank_object": [],

    # ── Sky ──
    "sky": [
        "DiffuseSampler",
        "ColormapSampler",
    ],
    "skybackground": [
        "DiffuseSampler",
    ],

    # ── Planets / Grass ──
    "planets": [
        "DiffuseSampler",
    ],
    "grassbase": [
        "DiffuseSampler",
    ],
}


def get_sampler_suffix(sampler_name):
    """Get the texture suffix for a sampler type."""
    return SAMPLER_TO_SUFFIX.get(sampler_name)


def get_colorspace(suffix):
    """Get the color space for a texture suffix."""
    return TEXTURE_COLORSPACE.get(suffix, "sRGB")


def get_bsdf_input(sampler_name):
    """Get the Principled BSDF input socket name for a sampler."""
    return SAMPLER_TO_BSDF_INPUT.get(sampler_name)


def get_expected_samplers(material_type):
    """Get the list of sampler types expected for a material type."""
    return MATERIAL_SAMPLERS.get(material_type, [])


def is_normal_map_sampler(sampler_name):
    """Check if a sampler is a normal map."""
    return sampler_name in ("NormalSampler", "DetailSampler")


def is_non_color_sampler(sampler_name):
    """Check if a sampler's texture should use Non-Color space."""
    suffix = get_sampler_suffix(sampler_name)
    if suffix:
        return get_colorspace(suffix) == "Non-Color"
    return False


# ──────────────────────────────────────────────────────────────
# Transparent / Alpha-blended material types
# ──────────────────────────────────────────────────────────────

# shader_type values that require Alpha Blend in Blender.
# Evidence from .fx shader analysis and .mmp preset names:
#   dyn_glass       → glass with Transmission
#   dyn_fresnel     → fresnel-based semi-transparency
#   fresnel         → fresnel effect (alpha)
#   spaceship_shield → clip-based alpha, fresnel shield
#   *_decals        → decal overlays need alpha
#   flares          → additive alpha glow
#   laserbeam/flatbeam → beam effects
#   scanner         → scanning overlay
#   refraction      → fixed alpha=0.165
#   dyn_animated_mock / animated_mock → gate_scroll and shield scroll effects
TRANSPARENT_MATERIAL_TYPES = frozenset({
    "dyn_glass",
    "dyn_fresnel",
    "fresnel",
    "spaceship_shield",
    "decals",
    "ship_decals",
    "ship_static_decals",
    "flares",
    "laserbeam",
    "flatbeam",
    "scanner",
    "dyn_animated_mock",
    "animated_mock",
    "dyn_drone",
})


def is_transparent_material(shader_type):
    """Check if a shader_type requires alpha blending."""
    return shader_type in TRANSPARENT_MATERIAL_TYPES
