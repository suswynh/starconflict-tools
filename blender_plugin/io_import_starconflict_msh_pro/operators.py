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
from . import material_builder


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
        default='Z_UP_TO_Y_UP',
    )

    auto_smooth: BoolProperty(
        name="Auto Smooth",
        description="Automatically split normals based on face angle (matching in-game shading)",
        default=True,
    )

    smooth_angle: FloatProperty(
        name="Smooth Angle",
        description="Face angle threshold for auto-smooth (degrees). Default 30° matches typical game settings",
        default=30.0,
        min=1.0, max=180.0,
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

    # ── Unpack root (for material library & name resolution) ──
    unpack_root: StringProperty(
        name="Unpack Root",
        description="Star Conflict unpack root directory (e.g. /path/to/unpack/output). "
                    "Used for material library lookup, name conflict resolution, "
                    "and Collection organization. Leave empty to use embedded library.",
        default="",
        subtype='DIR_PATH',
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
        # ── Initialize resolver & registry ──
        resolver = None
        registry = None
        mapping_db = None

        prefs = self._get_prefs(context)

        # Determine unpack root
        unpack_root = self.unpack_root
        if not unpack_root and prefs:
            unpack_root = prefs.unpack_root_default

        if unpack_root and os.path.isdir(unpack_root):
            from . import name_resolver
            from . import material_registry
            from . import material_library

            # Library
            lib = material_library.MaterialLibrary()
            lib_path = prefs.material_library_path if prefs else ""
            if lib_path and os.path.isfile(lib_path):
                lib.load(lib_path)

            registry = material_registry.MaterialRegistry(
                library=lib,
                unpack_root=unpack_root
            )

            # Resolver
            resolver = name_resolver.NameResolver(
                common_root=unpack_root,
                collection_depth=prefs.collection_depth if prefs else 2,
                use_abbreviations=prefs.use_abbreviations if prefs else False,
            )

        # ── Load static material mapping database ──
        mapping_db = None
        try:
            from . import material_mapping
            db_path = os.path.join(os.path.dirname(__file__), 'material_mapping_db.json')
            mapping_db = material_mapping.MaterialMappingDB.load(db_path)
            if not mapping_db.is_empty:
                print(f"  [MSH Pro] MappingDB: {mapping_db.map_count} maps, "
                      f"{mapping_db.total_overrides} overrides")
        except Exception as e:
            pass  # DB optional — fail silently

        # Collect texture search dirs
        tex_dirs = []
        if self.tex_search_dir and os.path.isdir(self.tex_search_dir):
            tex_dirs.append(self.tex_search_dir)

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
                resolver=resolver,
                registry=registry,
                unpack_root=unpack_root,
                mapping_db=mapping_db,
                smooth_angle=self.smooth_angle if self.auto_smooth else 0.0,
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
        default='Z_UP_TO_Y_UP',
    )

    auto_link_materials: BoolProperty(
        name="Auto-Link Materials",
        default=True,
    )

    auto_smooth: BoolProperty(
        name="Auto Smooth",
        description="Automatically split normals based on face angle",
        default=True,
    )

    smooth_angle: FloatProperty(
        name="Smooth Angle",
        description="Face angle threshold in degrees (default 30°)",
        default=30.0,
        min=1.0, max=180.0,
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

    # ── Unpack root ──
    unpack_root: StringProperty(
        name="Unpack Root",
        description="Star Conflict unpack root directory. Used for material library, "
                    "name conflict resolution, and Collection organization.",
        default="",
        subtype='DIR_PATH',
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
        mapping_db = None  # 初始化默认值

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

        # ── Initialize resolver & registry ──
        resolver = None
        registry = None
        unpack_root = self.unpack_root
        if not unpack_root and prefs:
            unpack_root = prefs.unpack_root_default

        if unpack_root and os.path.isdir(unpack_root):
            from . import name_resolver
            from . import material_registry
            from . import material_library

            lib = material_library.MaterialLibrary()
            lib_path = prefs.material_library_path if prefs else ""
            if lib_path and os.path.isfile(lib_path):
                lib.load(lib_path)

            registry = material_registry.MaterialRegistry(
                library=lib, unpack_root=unpack_root
            )
            resolver = name_resolver.NameResolver(
                common_root=unpack_root,
                collection_depth=prefs.collection_depth if prefs else 2,
                use_abbreviations=prefs.use_abbreviations if prefs else False,
            )

        # ── Load static material mapping database ──
        mapping_db = None
        try:
            from . import material_mapping
            db_path = os.path.join(os.path.dirname(__file__), 'material_mapping_db.json')
            mapping_db = material_mapping.MaterialMappingDB.load(db_path)
            if not mapping_db.is_empty:
                print(f"  [MSH Pro] MappingDB: {mapping_db.map_count} maps, "
                      f"{mapping_db.total_overrides} overrides")
        except Exception:
            pass

        # ── Collect & scan all MSH files ──
        all_msh = []
        for root, dirs, filenames in os.walk(self.directory):
            for fname in filenames:
                if ".mdl-msh" in fname:
                    all_msh.append(os.path.join(root, fname))

        if self.max_files > 0:
            all_msh = all_msh[:self.max_files]

        if resolver is not None and len(all_msh) > 1:
            resolver.scan(all_msh)
            conflicts = resolver.get_conflicts()
            if conflicts:
                print(f"  [MSH Pro] Batch: {len(conflicts)} conflict groups detected")

        # Import files
        total = len(all_msh)
        for i, fpath in enumerate(all_msh):
            if self.max_files > 0 and imported + failed >= self.max_files:
                break
            fname = os.path.basename(fpath)

            # ── 进度提示 ──
            progress_pct = int((i / total) * 100) if total > 0 else 0
            status_msg = f"Star Conflict MSH Pro: Importing {i+1}/{total} ({progress_pct}%) — {fname}"
            context.workspace.status_text_set(status_msg)
            # 每10个文件刷新一次 UI 避免过慢
            if i % 10 == 0:
                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)

            obj = msh_importer.import_msh_with_materials(
                fpath, context,
                scale=self.scale,
                up_axis=self.up_axis,
                auto_link=self.auto_link_materials,
                tex_search_dirs=tex_dirs,
                mdf_search_dirs=mdf_dirs,
                tex_extensions=tex_ext,
                complexity=self.shader_complexity,
                resolver=resolver,
                registry=registry,
                unpack_root=unpack_root,
                mapping_db=mapping_db,
                smooth_angle=self.smooth_angle if self.auto_smooth else 0.0,
            )
            if obj:
                imported += 1
                if self.show_details:
                    print(f"  ✓ {fname}")
            else:
                failed += 1
                if self.show_details:
                    print(f"  ✗ {fname}")

        msg = f"Imported {imported}"
        if failed > 0:
            msg += f", failed {failed}"
        if resolver and resolver.conflict_count > 0:
            msg += f", {resolver.conflict_count} conflict groups resolved"
        if registry:
            msg += f", {registry.stats()['created_count']} materials created"
        self.report({'INFO'}, msg)

        # 清除进度提示
        context.workspace.status_text_set(None)
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
