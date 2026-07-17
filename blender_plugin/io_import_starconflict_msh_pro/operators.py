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

    auto_place: BoolProperty(
        name="Auto-Place from scene.xml",
        description="If a scene.xml exists in levels/, automatically place "
                    "imported models at their scene-specified world positions",
        default=True,
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

        # ── Scene.xml position lookup (auto-place) ──
        entity_positions = {}  # {model_basename: (pos_tuple, rot_tuple)}
        if self.auto_place and unpack_root and os.path.isdir(unpack_root):
            try:
                from . import scene_xml_parser as sxp
                # Search for scene.xml: levels/<area>/<map>/scene.xml
                levels_dir = os.path.join(unpack_root, "levels")
                if os.path.isdir(levels_dir):
                    for root, dirs, files in os.walk(levels_dir):
                        if "scene.xml" in files:
                            scene_path = os.path.join(root, "scene.xml")
                            try:
                                scene = sxp.parse_scene_xml(scene_path)
                                for entity in scene.model_entities:
                                    # Normalize model path to basename
                                    model_base = os.path.basename(
                                        entity.model_path.replace('\\', '/')
                                    )
                                    if model_base:
                                        entity_positions[model_base] = (
                                            entity.pos, entity.rot
                                        )
                            except Exception:
                                pass
                if entity_positions:
                    print(f"  [MSH Pro] Batch: Loaded {len(entity_positions)} "
                          f"entity positions from scene.xml")
            except Exception as e:
                print(f"  [MSH Pro] Batch: scene.xml lookup skipped ({e})")

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
                smooth_angle=self.smooth_angle if self.auto_smooth else 0.0,
            )
            if obj:
                imported += 1

                # ── Auto-place from scene.xml ──
                if entity_positions:
                    fname_noext = os.path.splitext(fname)[0]
                    # Strip .mdl-msh suffix variants
                    import re
                    fname_base = re.sub(r'\.mdl-msh\d+$', '', fname_noext)
                    if fname_base in entity_positions:
                        pos, rot = entity_positions[fname_base]
                        hx, hy, hz = pos
                        qx, qy, qz, qw = rot
                        # Hammer Y-up world → Blender Z-up world: (hx, hz, hy)
                        obj.location = (hx, hz, hy)
                        if (qx, qy, qz, qw) != (0, 0, 0, 1):
                            obj.rotation_mode = 'QUATERNION'
                            obj.rotation_quaternion = (qw, qx, qz, qy)

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
# Import Scene XML — Level Assembly Operator
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_import_scene_xml(Operator, ImportHelper):
    """Import a Star Conflict level from scene.xml (one-click assembly)"""
    bl_idname = "import_scene.starconflict_scene_xml"
    bl_label = "Import Star Conflict Level (scene.xml)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".xml"

    filter_glob: StringProperty(
        default="*.xml",
        options={'HIDDEN'},
    )

    unpack_root: StringProperty(
        name="Unpack Root",
        description="Star Conflict unpack root directory (e.g. /path/to/unpack/output)",
        default="",
        subtype='DIR_PATH',
    )

    scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.001, max=1000.0,
    )

    up_axis: EnumProperty(
        name="Up Axis",
        items=[
            ('Z_UP_TO_Y_UP', "Z-up → Y-up", "Convert from Z-up to Y-up"),
            ('Y_UP_TO_Z_UP', "Y-up → Z-up", "Convert from Hammer Y-up to Blender Z-up"),
            ('NONE', "No Rotation", "Keep original vertex data"),
        ],
        default='Z_UP_TO_Y_UP',
    )

    import_static: BoolProperty(
        name="Import Static Scene",
        description="Also import map.mdl-msh* static scene geometry",
        default=True,
    )

    import_decals: BoolProperty(
        name="Import Decals (Experimental)",
        description="Import decals from decals.dat. "
                    "EXPERIMENTAL: decals require manual editing after import",
        default=True,
    )

    import_lights: BoolProperty(
        name="Import Lights (Experimental)",
        description="Import Lights_ entities as Blender light objects. "
                    "EXPERIMENTAL: light orientation may need manual correction",
        default=False,
    )

    tex_extensions: StringProperty(
        name="Texture Extensions",
        description="Comma-separated extensions (priority order)",
        default=".dds,.png,.tga",
    )

    @classmethod
    def _get_prefs(cls, context):
        """Get addon preferences, safely."""
        try:
            addon = context.preferences.addons.get(__package__.split('.')[0])
            return addon.preferences if addon else None
        except Exception:
            return None

    def invoke(self, context, event):
        """Auto-fill unpack_root from preferences."""
        prefs = self._get_prefs(context)
        if prefs and not self.unpack_root:
            self.unpack_root = getattr(prefs, 'unpack_root_default', '') or ''
        return super().invoke(context, event)

    def execute(self, context):
        from . import level_assembler
        from . import material_registry as mat_reg
        from . import material_library as mat_lib

        prefs = self._get_prefs(context)

        # Texture search dirs
        tex_dirs = []
        tex_ext = self.tex_extensions if hasattr(self, 'tex_extensions') else ".dds,.png,.tga"
        if prefs:
            for item in prefs.default_tex_paths:
                if item.path and os.path.isdir(item.path):
                    tex_dirs.append(item.path)
            tex_ext = prefs.tex_extensions

        # MDF search dirs
        mdf_dirs = []
        if prefs:
            for item in prefs.default_mdf_paths:
                if item.path and os.path.isdir(item.path):
                    mdf_dirs.append(item.path)

        # Unpack root
        unpack_root = self.unpack_root
        if not unpack_root and prefs:
            unpack_root = getattr(prefs, 'default_unpack_root', '')

        if not unpack_root or not os.path.isdir(unpack_root):
            self.report({'ERROR'}, "Unpack root not set. Configure in preferences or operator options.")
            return {'CANCELLED'}

        # Setup material library + registry
        library = None
        registry = None
        try:
            library_path = os.path.join(unpack_root, "material_library.json")
            if os.path.isfile(library_path):
                library = mat_lib.MaterialLibrary(library_path=library_path)
            else:
                library = mat_lib.MaterialLibrary()
            registry = mat_reg.MaterialRegistry(library=library, unpack_root=unpack_root)
        except Exception:
            registry = mat_reg.MaterialRegistry(unpack_root=unpack_root)

        # Run assembly with progress
        context.workspace.status_text_set("Star Conflict — Importing level, please wait...")
        self.report({'INFO'}, f"Assembling level from: {self.filepath}")
        print(f"\n{'='*60}")
        print(f"  Star Conflict — 正在导入关卡场景，请耐心等待...")
        print(f"  {self.filepath}")
        print(f"{'='*60}\n")

        def _progress(current, total, message=""):
            pct = int((current / total) * 100) if total > 0 else 0
            context.workspace.status_text_set(
                f"Star Conflict: {message} ({current}/{total})"
            )
            self.report({'INFO'}, f"Star Conflict: {message} ({current}/{total})")

        result = level_assembler.assemble_level(
            scene_xml_path=self.filepath,
            unpack_root=unpack_root,
            context=context,
            registry=registry,
            library=library,
            tex_search_dirs=tex_dirs,
            mdf_search_dirs=mdf_dirs,
            tex_extensions=tex_ext,
            import_decals=getattr(self, 'import_decals', True),
            import_lights=getattr(self, 'import_lights', False),
            scale=self.scale,
            up_axis=self.up_axis,
            import_static_scene=self.import_static,
            progress_callback=_progress,
        )

        if "error" in result:
            self.report({'ERROR'}, result["error"])
            return {'CANCELLED'}

        summary = (
            f"Level '{result['level_name']}': "
            f"{result['imported_count']} entities imported, "
            f"{result['static_scene_count']} static meshes"
        )
        if result['error_count'] > 0:
            summary += f", {result['error_count']} errors"
            for err in result['errors'][:5]:
                print(f"  [LevelAssembler Error] {err}")

        self.report({'INFO'}, summary)
        print(f"[LevelAssembler] {summary} (elapsed: {result['elapsed']:.1f}s)")
        context.workspace.status_text_set(None)
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "unpack_root")
        layout.prop(self, "scale")
        layout.prop(self, "up_axis")
        layout.prop(self, "import_static")
        layout.prop(self, "import_decals")
        layout.prop(self, "import_lights")


# ──────────────────────────────────────────────────────────────
# Level Area Import — discover and import complete level area
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_import_level_area(Operator):
    """Import a complete Star Conflict level area (all variants + static scenes)

    Select the area folder (e.g. levels/dreadnoughtbattle/allidium/)
    and this operator will discover all scene variants, static scenes,
    and orphan models, then let you choose what to import.
    """
    bl_idname = "import_scene.starconflict_level_area"
    bl_label = "Import Star Conflict Level Area"
    bl_options = {'REGISTER', 'UNDO'}

    directory: StringProperty(
        name="Area Folder",
        description="Select the level area folder containing scene variants",
        subtype='DIR_PATH',
    )

    unpack_root: StringProperty(
        name="Unpack Root",
        description="Star Conflict unpack root directory",
        default="",
        subtype='DIR_PATH',
    )

    scale: FloatProperty(
        name="Scale",
        default=1.0,
        min=0.001, max=1000.0,
    )

    @classmethod
    def _get_prefs(cls, context):
        try:
            addon = context.preferences.addons.get(__package__.split('.')[0])
            return addon.preferences if addon else None
        except Exception:
            return None

    def invoke(self, context, event):
        prefs = self._get_prefs(context)
        if prefs and not self.unpack_root:
            self.unpack_root = getattr(prefs, 'unpack_root_default', '') or ''
        return context.window_manager.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "unpack_root")
        layout.prop(self, "directory")
        layout.prop(self, "scale")

    def execute(self, context):
        from . import level_assembler
        from . import level_area_dialog

        area_path = self.directory
        if not area_path or not os.path.isdir(area_path):
            self.report({'ERROR'}, "Please select a valid area folder")
            return {'CANCELLED'}

        unpack_root = self.unpack_root
        prefs = self._get_prefs(context)
        if not unpack_root and prefs:
            unpack_root = getattr(prefs, 'unpack_root_default', '') or ''

        if not unpack_root or not os.path.isdir(unpack_root):
            self.report({'ERROR'}, "Unpack root not set")
            return {'CANCELLED'}

        # Gather texture/MDF search paths
        tex_dirs = []
        mdf_dirs = []
        tex_ext = ".dds,.png,.tga"
        if prefs:
            for item in prefs.default_tex_paths:
                if item.path and os.path.isdir(item.path):
                    tex_dirs.append(item.path)
            tex_ext = prefs.tex_extensions or tex_ext
            for item in prefs.default_mdf_paths:
                if item.path and os.path.isdir(item.path):
                    mdf_dirs.append(item.path)

        # ── Discovery ──
        context.workspace.status_text_set("Star Conflict — Scanning level area...")
        self.report({'INFO'}, f"Scanning level area: {area_path}")
        print(f"\n[LevelArea] Scanning: {area_path}")

        results = level_assembler.discover_level_area(area_path, unpack_root)
        if "error" in results:
            self.report({'ERROR'}, results["error"])
            return {'CANCELLED'}

        # Print discovery summary
        area_name = results["area_name"]
        variants = results.get("scene_variants", [])
        statics = results.get("static_scenes", [])
        orphans = results.get("orphan_models", [])

        print(f"[LevelArea] Area: {area_name}")
        print(f"  Scene variants: {len(variants)}")
        for sv in variants:
            inh = f" ↗ {', '.join(sv['inherits_from'])}" if sv.get('inherits_from') else ""
            print(f"    - {sv['name']}{inh} ({sv['entity_count']} entities)")
        print(f"  Static scenes: {len(statics)}")
        for ss in statics:
            shared = " [SHARED]" if ss.get("shared") else ""
            print(f"    - {os.path.basename(ss['path'])}{shared} ({ss['msh_count']} models)")
        print(f"  Orphan models: {len(orphans)}")
        for om in orphans:
            print(f"    - {om['name']} ({om['msh_count']} meshes)")

        # ── Show confirm dialog ──
        level_area_dialog.set_discovery_results(
            results=results,
            unpack_root=unpack_root,
            scale=self.scale,
            tex_extensions=tex_ext,
            tex_search_dirs=tex_dirs,
            mdf_search_dirs=mdf_dirs,
            import_decals=True,
            import_lights=False,
        )
        bpy.ops.sc_pro.import_level_area_confirm('INVOKE_DEFAULT')
        context.workspace.status_text_set(None)
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

_CLASSES = [
    SC_PRO_OT_import_msh,
    SC_PRO_OT_import_msh_batch,
    SC_PRO_OT_import_scene_xml,
    SC_PRO_OT_import_level_area,
    SC_PRO_OT_refresh_materials,
    SC_PRO_OT_clear_tex_cache,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
