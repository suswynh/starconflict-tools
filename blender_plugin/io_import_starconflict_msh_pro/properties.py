# ============================================================================
# Custom Properties — Scene-level settings for the MSH Pro importer
# ============================================================================
"""Blender PropertyGroup definitions for storing per-scene import settings."""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
    CollectionProperty,
)


class SC_TextureSearchPath(bpy.types.PropertyGroup):
    """A single texture search path entry."""
    path: StringProperty(
        name="Path",
        description="Directory to search for texture files",
        subtype='DIR_PATH',
        default="",
    )


class SC_MSHProSettings(bpy.types.PropertyGroup):
    """Scene-level settings for the Star Conflict MSH Pro importer."""

    # ── Material settings ──
    auto_link_materials: BoolProperty(
        name="Auto-Link Materials",
        description="Automatically find MDF files and create materials after import",
        default=True,
    )

    # ── Texture search settings ──
    texture_search_paths: CollectionProperty(
        name="Texture Search Paths",
        type=SC_TextureSearchPath,
        description="Directories to search for texture files",
    )

    active_search_path_index: IntProperty(
        name="Active Path Index",
        default=0,
        min=0,
    )

    texture_extensions: StringProperty(
        name="Texture Extensions",
        description="Comma-separated list of texture extensions to try (in priority order)",
        default=".dds,.png,.tga",
    )

    # ── MDF search settings ──
    mdf_search_paths: CollectionProperty(
        name="MDF Search Paths",
        type=SC_TextureSearchPath,
        description="Additional directories to search for .mdf files",
    )

    active_mdf_path_index: IntProperty(
        name="Active MDF Path Index",
        default=0,
        min=0,
    )

    # ── Shader settings ──
    create_shader_nodes: BoolProperty(
        name="Create Shader Nodes",
        description="Build full PBR node network (disable for simple Principled BSDF + textures only)",
        default=True,
    )

    shader_complexity: EnumProperty(
        name="Shader Complexity",
        description="Level of detail for shader node reconstruction",
        items=[
            ('FULL', "Full PBR Network",
             "Complete Principled BSDF with all texture channels, Normal Map, AO mixing"),
            ('SIMPLE', "Simple Textures Only",
             "Just connect textures to Principled BSDF without extra node groups"),
        ],
        default='FULL',
    )

    # ── Material naming ──
    material_name_template: StringProperty(
        name="Material Name Template",
        description="Template for material naming. Use {asset}, {type}, {index}",
        default="{asset}_{type}",
    )


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

def register():
    bpy.utils.register_class(SC_TextureSearchPath)
    bpy.utils.register_class(SC_MSHProSettings)
    bpy.types.Scene.sc_msh_pro = bpy.props.PointerProperty(type=SC_MSHProSettings)


def unregister():
    del bpy.types.Scene.sc_msh_pro
    bpy.utils.unregister_class(SC_MSHProSettings)
    bpy.utils.unregister_class(SC_TextureSearchPath)
