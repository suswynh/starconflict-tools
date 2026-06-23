# ============================================================================
# Operators — Import and utility operators
# ============================================================================
"""Blender operators for Star Conflict MSH Pro importer.

Provides:
  - SC_PRO_OT_import_msh — Single/multi file import with material linking
  - SC_PRO_OT_import_msh_batch — Batch directory import
  - SC_PRO_OT_refresh_materials — Refresh materials on selected objects
  - SC_PRO_OT_link_textures — Re-link textures for selected objects
"""

import os
import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    CollectionProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
)
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

from . import msh_importer
from . import texture_finder


# ──────────────────────────────────────────────────────────────
# Single/Multi File Import
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_import_msh(Operator, ImportHelper):
    """Import Star Conflict MSH with material linking"""
    bl_idname = "import_scene.starconflict_msh_pro"
    bl_label = "Import Star Conflict MSH Pro (.mdl-msh*)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".mdl-msh*"

    filter_glob: StringProperty(
        default="*.mdl-msh*",
        options={'HIDDEN'},
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    # ── Geometry settings ──
    scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.001, max=1000.0,
    )

    up_axis: EnumProperty(
        name="Up Axis",
        items=[
            ('Y_UP_TO_Z_UP', "Y-up → Z-up", "Convert from Y-up to Blender Z-up"),
            ('NONE', "No Rotation", "Keep original vertex data"),
            ('Z_UP_TO_Y_UP', "Z-up → Y-up", "Convert from Z-up to Y-up"),
            ('NOESIS_COMPAT', "Noesis Compat", "Match Noesis preview"),
            ('AUTO_FLIP_YZ', "Auto (Flip Y/Z)", "Swap Y and Z coordinates"),
        ],
        default='Y_UP_TO_Z_UP',
    )

    # ── Material settings ──
    auto_link_materials: BoolProperty(
        name="Auto-Link Materials",
        description="Automatically find MDF and create/link materials after import",
        default=True,
    )

    # ── Texture search ──
    tex_search_dir: StringProperty(
        name="Texture Dir",
        description="Additional texture search directory (paste path; set defaults in Preferences)",
        default="",
    )

    tex_extensions: StringProperty(
        name="Texture Extensions",
        description="Comma-separated extensions (priority order)",
        default=".dds,.png,.tga",
    )

    # ── MDF search ──
    mdf_search_dir: StringProperty(
        name="MDF Dir",
        description="Additional directory to search for .mdf files (paste path; set defaults in Preferences)",
        default="",
    )

    # ── Shader ──
    shader_complexity: EnumProperty(
        name="Shader Nodes",
        items=[
            ('FULL', "Full PBR Network", "Complete node network with AO, normal map"),
            ('SIMPLE', "Simple Textures", "Direct Principled BSDF connections only"),
        ],
        default='FULL',
    )

    def execute(self, context):
        # Collect texture search dirs
        tex_dirs = []
        if self.tex_search_dir and os.path.isdir(self.tex_search_dir):
            tex_dirs.append(self.tex_search_dir)

        # Also include paths from preferences
        prefs = self._get_prefs(context)
        if prefs:
            for item in prefs.default_tex_paths:
                if item.path and os.path.isdir(item.path):
                    tex_dirs.append(item.path)
            if not self.tex_extensions or self.tex_extensions == ".dds,.png,.tga":
                self.tex_extensions = prefs.tex_extensions

        # Collect MDF search dirs
        mdf_dirs = []
        if self.mdf_search_dir and os.path.isdir(self.mdf_search_dir):
            mdf_dirs.append(self.mdf_search_dir)
        if prefs:
            for item in prefs.default_mdf_paths:
                if item.path and os.path.isdir(item.path):
                    mdf_dirs.append(item.path)

        # Import each file
        basedir = os.path.dirname(self.filepath)
        files_to_import = self._get_file_list(basedir)

        imported = 0
        for fname in files_to_import:
            fpath = os.path.join(basedir, fname.name)
            obj = msh_importer.import_msh_with_materials(
                fpath, context,
                scale=self.scale,
                up_axis=self.up_axis,
                auto_link=self.auto_link_materials,
                tex_search_dirs=tex_dirs,
                mdf_search_dirs=mdf_dirs,
                tex_extensions=self.tex_extensions,
                complexity=self.shader_complexity,
            )
            if obj:
                imported += 1

        if imported > 0:
            self.report({'INFO'}, f"Imported {imported} MSH file(s) with materials")
        else:
            self.report({'WARNING'}, "No files imported")

        return {'FINISHED'}

    def _get_file_list(self, basedir):
        """Get list of files to import."""
        if self.files and len(self.files) > 0:
            return list(self.files)
        # Single file mode
        class FakeEntry:
            pass
        entry = FakeEntry()
        entry.name = os.path.basename(self.filepath)
        return [entry]

    @staticmethod
    def _get_prefs(context):
        """Get addon preferences."""
        try:
            addon_name = __package__.split('.')[0]
            return context.preferences.addons[addon_name].preferences
        except (KeyError, AttributeError):
            return None


# ──────────────────────────────────────────────────────────────
# Batch Directory Import
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_import_msh_batch(Operator, ImportHelper):
    """Batch import all Star Conflict MSH files from a directory"""
    bl_idname = "import_scene.starconflict_msh_pro_batch"
    bl_label = "Import Star Conflict MSH Pro Batch (directory)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ""
    use_filter_folder = True

    filter_glob: StringProperty(default="", options={'HIDDEN'})
    directory: StringProperty(subtype='DIR_PATH')

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    scale: FloatProperty(name="Scale", default=1.0, min=0.001, max=1000.0)
    max_files: IntProperty(name="Max Files", default=0, min=0)

    up_axis: EnumProperty(
        name="Up Axis",
        items=[
            ('Y_UP_TO_Z_UP', "Y-up → Z-up", ""),
            ('NONE', "No Rotation", ""),
            ('Z_UP_TO_Y_UP', "Z-up → Y-up", ""),
            ('NOESIS_COMPAT', "Noesis Compat", ""),
            ('AUTO_FLIP_YZ', "Auto (Flip Y/Z)", ""),
        ],
        default='Y_UP_TO_Z_UP',
    )

    auto_link_materials: BoolProperty(
        name="Auto-Link Materials",
        default=True,
    )

    show_details: BoolProperty(
        name="Show Details",
        default=False,
    )

    # ── Texture & MDF search (same as single-file import) ──
    tex_search_dir: StringProperty(
        name="Texture Dir",
        description="Additional texture search directory (paste path; set defaults in Preferences)",
        default="",
    )

    tex_extensions: StringProperty(
        name="Texture Extensions",
        description="Comma-separated extensions (priority order)",
        default=".dds,.png,.tga",
    )

    mdf_search_dir: StringProperty(
        name="MDF Dir",
        description="Additional directory to search for .mdf files",
        default="",
    )

    shader_complexity: EnumProperty(
        name="Shader Nodes",
        items=[
            ('FULL', "Full PBR Network", ""),
            ('SIMPLE', "Simple Textures", ""),
        ],
        default='FULL',
    )

    def execute(self, context):
        return self._batch_import(context)

    def _batch_import(self, context):
        imported = 0
        failed = 0

        # Get search paths: operator fields first, then preferences
        tex_dirs = []
        if self.tex_search_dir and os.path.isdir(self.tex_search_dir):
            tex_dirs.append(self.tex_search_dir)
        mdf_dirs = []
        if self.mdf_search_dir and os.path.isdir(self.mdf_search_dir):
            mdf_dirs.append(self.mdf_search_dir)

        prefs = SC_PRO_OT_import_msh._get_prefs(context)
        tex_ext = self.tex_extensions
        if prefs:
            for item in prefs.default_tex_paths:
                if item.path and os.path.isdir(item.path):
                    tex_dirs.append(item.path)
            if tex_ext == ".dds,.png,.tga":
                tex_ext = prefs.tex_extensions or tex_ext
            for item in prefs.default_mdf_paths:
                if item.path and os.path.isdir(item.path):
                    mdf_dirs.append(item.path)

        for root, dirs, filenames in os.walk(self.directory):
            for fname in filenames:
                if ".mdl-msh" not in fname:
                    continue
                if self.max_files > 0 and imported + failed >= self.max_files:
                    break

                fpath = os.path.join(root, fname)
                obj = msh_importer.import_msh_with_materials(
                    fpath, context,
                    scale=self.scale,
                    up_axis=self.up_axis,
                    auto_link=self.auto_link_materials,
                    tex_search_dirs=tex_dirs,
                    mdf_search_dirs=mdf_dirs,
                    tex_extensions=tex_ext,
                    complexity=self.shader_complexity,
                )
                if obj:
                    imported += 1
                    if self.show_details:
                        print(f"  ✓ {fname}")
                else:
                    failed += 1
                    if self.show_details:
                        print(f"  ✗ {fname}")

            if self.max_files > 0 and imported + failed >= self.max_files:
                break

        self.report({'INFO'}, f"Imported {imported}, failed {failed}")
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Refresh Materials Operator
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_refresh_materials(Operator):
    """Re-scan MDF and re-link materials on selected objects"""
    bl_idname = "sc_pro.refresh_materials"
    bl_label = "Refresh Materials (Re-scan MDF)"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.selected_objects is not None

    def execute(self, context):
        prefs = SC_PRO_OT_import_msh._get_prefs(context)
        tex_dirs = []
        mdf_dirs = []
        tex_ext = ".dds,.png,.tga"
        if prefs:
            for item in prefs.default_tex_paths:
                if item.path and os.path.isdir(item.path):
                    tex_dirs.append(item.path)
            tex_ext = prefs.tex_extensions
            for item in prefs.default_mdf_paths:
                if item.path and os.path.isdir(item.path):
                    mdf_dirs.append(item.path)

        updated = 0
        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue
            # Clear existing materials
            obj.data.materials.clear()
            # Re-import materials
            # (This is a simplified version — in production, we'd want
            #  to store the original MSH path on the object)
            updated += 1

        self.report({'INFO'}, f"Cleared materials on {updated} object(s)")
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Clear Texture Cache Operator
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_clear_tex_cache(Operator):
    """Clear the texture search index cache"""
    bl_idname = "sc_pro.clear_tex_cache"
    bl_label = "Clear Texture Cache"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        texture_finder.clear_cache()
        self.report({'INFO'}, "Texture search cache cleared")
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

_CLASSES = [
    SC_PRO_OT_import_msh,
    SC_PRO_OT_import_msh_batch,
    SC_PRO_OT_refresh_materials,
    SC_PRO_OT_clear_tex_cache,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
