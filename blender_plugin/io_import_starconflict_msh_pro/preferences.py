# ============================================================================
# Addon Preferences — User-configurable global settings
# ============================================================================
"""Blender AddonPreferences for Star Conflict MSH Pro importer.

Provides:
  - Default texture search paths
  - Default MDF search paths
  - Texture extension priority
  - Shader complexity default
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
)


class SC_ProTextureSearchPath(bpy.types.PropertyGroup):
    """A single texture search path entry in preferences."""
    path: StringProperty(
        name="Path",
        description="Directory to search for texture files",
        subtype='DIR_PATH',
        default="",
    )


class SC_ProPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__.split('.')[0] if '.' in __package__ else __package__

    # ── Texture search paths ──
    default_tex_paths: CollectionProperty(
        name="Default Texture Search Paths",
        type=SC_ProTextureSearchPath,
        description="Default directories to search for texture files",
    )

    active_tex_path_index: IntProperty(
        name="Active Texture Path Index",
        default=0,
        min=0,
    )

    # ── MDF search paths ──
    default_mdf_paths: CollectionProperty(
        name="Default MDF Search Paths",
        type=SC_ProTextureSearchPath,
        description="Additional directories to search for .mdf files",
    )

    active_mdf_path_index: IntProperty(
        name="Active MDF Path Index",
        default=0,
        min=0,
    )

    # ── Texture settings ──
    tex_extensions: StringProperty(
        name="Texture Extensions",
        description="Comma-separated texture extensions in priority order",
        default=".dds,.png,.tga",
    )

    # ── Shader settings ──
    shader_complexity_default: EnumProperty(
        name="Default Shader Complexity",
        description="Default shader node complexity for new imports",
        items=[
            ('FULL', "Full PBR Network", "Complete node network with all channels"),
            ('SIMPLE', "Simple Textures", "Direct Principled BSDF connections"),
        ],
        default='FULL',
    )

    # ── Material settings ──
    auto_link_default: BoolProperty(
        name="Auto-Link by Default",
        description="Enable auto material linking for new imports",
        default=True,
    )

    def draw(self, context):
        layout = self.layout

        # ── Texture Search Paths ──
        box = layout.box()
        box.label(text="Default Texture Search Paths", icon='FILE_FOLDER')
        row = box.row()
        row.template_list(
            "SC_UL_ProTexPathList", "",
            self, "default_tex_paths",
            self, "active_tex_path_index",
            rows=3,
        )
        col = row.column(align=True)
        col.operator("sc_pro.add_tex_path", icon='ADD', text="")
        col.operator("sc_pro.remove_tex_path", icon='REMOVE', text="")

        # ── MDF Search Paths ──
        box = layout.box()
        box.label(text="Default MDF Search Paths", icon='FILE_FOLDER')
        row = box.row()
        row.template_list(
            "SC_UL_ProMDFPathList", "",
            self, "default_mdf_paths",
            self, "active_mdf_path_index",
            rows=3,
        )
        col = row.column(align=True)
        col.operator("sc_pro.add_mdf_path", icon='ADD', text="")
        col.operator("sc_pro.remove_mdf_path", icon='REMOVE', text="")

        # ── Texture Settings ──
        box = layout.box()
        box.label(text="Texture Settings", icon='TEXTURE')
        box.prop(self, "tex_extensions")

        # ── Defaults ──
        box = layout.box()
        box.label(text="Import Defaults", icon='PREFERENCES')
        box.prop(self, "shader_complexity_default")
        box.prop(self, "auto_link_default")


# ──────────────────────────────────────────────────────────────
# UI List classes (needed for template_list)
# ──────────────────────────────────────────────────────────────

class SC_UL_ProTexPathList(bpy.types.UIList):
    """UI List for texture search paths."""
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "path", text="", emboss=False, icon='FILE_FOLDER')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_FOLDER')


class SC_UL_ProMDFPathList(bpy.types.UIList):
    """UI List for MDF search paths."""
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "path", text="", emboss=False, icon='FILE_FOLDER')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='FILE_FOLDER')


# ──────────────────────────────────────────────────────────────
# Operators for managing search paths
# ──────────────────────────────────────────────────────────────

class SC_OT_AddTexPath(bpy.types.Operator):
    """Add a texture search path"""
    bl_idname = "sc_pro.add_tex_path"
    bl_label = "Add Texture Path"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        prefs.default_tex_paths.add()
        prefs.active_tex_path_index = len(prefs.default_tex_paths) - 1
        return {'FINISHED'}


class SC_OT_RemoveTexPath(bpy.types.Operator):
    """Remove the selected texture search path"""
    bl_idname = "sc_pro.remove_tex_path"
    bl_label = "Remove Texture Path"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        idx = prefs.active_tex_path_index
        if 0 <= idx < len(prefs.default_tex_paths):
            prefs.default_tex_paths.remove(idx)
            prefs.active_tex_path_index = min(idx, len(prefs.default_tex_paths) - 1)
        return {'FINISHED'}


class SC_OT_AddMDFPath(bpy.types.Operator):
    """Add an MDF search path"""
    bl_idname = "sc_pro.add_mdf_path"
    bl_label = "Add MDF Path"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        prefs.default_mdf_paths.add()
        prefs.active_mdf_path_index = len(prefs.default_mdf_paths) - 1
        return {'FINISHED'}


class SC_OT_RemoveMDFPath(bpy.types.Operator):
    """Remove the selected MDF search path"""
    bl_idname = "sc_pro.remove_mdf_path"
    bl_label = "Remove MDF Path"
    bl_options = {'INTERNAL'}

    def execute(self, context):
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        idx = prefs.active_mdf_path_index
        if 0 <= idx < len(prefs.default_mdf_paths):
            prefs.default_mdf_paths.remove(idx)
            prefs.active_mdf_path_index = min(idx, len(prefs.default_mdf_paths) - 1)
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

_CLASSES = [
    SC_ProTextureSearchPath,
    SC_ProPreferences,
    SC_UL_ProTexPathList,
    SC_UL_ProMDFPathList,
    SC_OT_AddTexPath,
    SC_OT_RemoveTexPath,
    SC_OT_AddMDFPath,
    SC_OT_RemoveMDFPath,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
