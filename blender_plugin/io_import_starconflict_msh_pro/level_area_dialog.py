# ============================================================================
# Level Area Import Dialog — Discovery results UI with checkboxes
# ============================================================================
"""Show discovered level area components and let the user select what to import.

Flow:
  1. SC_PRO_OT_import_level_area picks the area folder → runs discovery
  2. Results are stored in this module's _discovery_cache
  3. SC_PRO_OT_import_level_area_confirm shows the dialog
  4. User checks/unchecks components → imports selected
"""

import os
import bpy
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy.types import Operator, PropertyGroup


# ──────────────────────────────────────────────────────────────
# Discovery cache (module-level, shared between operators)
# ──────────────────────────────────────────────────────────────

_discovery_cache = {
    "results": None,
    "unpack_root": "",
    "scale": 1.0,
    "tex_extensions": ".dds,.png,.tga",
    "tex_search_dirs": None,
    "mdf_search_dirs": None,
    "import_decals": True,
    "import_lights": False,
}


def set_discovery_results(results, unpack_root="", scale=1.0,
                           tex_extensions=".dds,.png,.tga",
                           tex_search_dirs=None, mdf_search_dirs=None,
                           import_decals=True, import_lights=False):
    """Store discovery results for the confirm dialog."""
    _discovery_cache["results"] = results
    _discovery_cache["unpack_root"] = unpack_root
    _discovery_cache["scale"] = scale
    _discovery_cache["tex_extensions"] = tex_extensions
    _discovery_cache["tex_search_dirs"] = tex_search_dirs or []
    _discovery_cache["mdf_search_dirs"] = mdf_search_dirs or []
    _discovery_cache["import_decals"] = import_decals
    _discovery_cache["import_lights"] = import_lights


def get_discovery_results():
    """Get stored discovery results."""
    return _discovery_cache["results"]


# ──────────────────────────────────────────────────────────────
# Property group for a single importable item
# ──────────────────────────────────────────────────────────────

class LevelAreaItem(PropertyGroup):
    """A single component in the import list."""
    item_id: StringProperty(name="ID")
    label: StringProperty(name="Label")
    item_type: StringProperty(name="Type")  # 'static', 'variant', 'orphan'
    detail: StringProperty(name="Detail")
    data: StringProperty(name="Data")  # JSON-serialized extra info
    selected: BoolProperty(name="Selected", default=True)


# ──────────────────────────────────────────────────────────────
# Confirm dialog operator
# ──────────────────────────────────────────────────────────────

class SC_PRO_OT_import_level_area_confirm(Operator):
    """Select components to import from the discovered level area"""
    bl_idname = "sc_pro.import_level_area_confirm"
    bl_label = "Import Level Area"
    bl_options = {'REGISTER', 'UNDO'}

    items: CollectionProperty(type=LevelAreaItem)

    def _populate_items(self, results):
        """Fill the items collection from discovery results."""
        self.items.clear()
        import json

        # ── Static scenes ──
        for ss in results.get("static_scenes", []):
            item = self.items.add()
            ss_name = os.path.basename(ss["path"])
            shared_tag = " [SHARED]" if ss.get("shared") else ""
            item.item_id = f"static:{ss['path']}"
            item.label = f"Static Scene: {ss_name}{shared_tag}"
            item.item_type = "static"
            item.detail = f"{ss['msh_count']} models"
            item.data = json.dumps(ss)
            item.selected = True

        # ── Scene variants ──
        for sv in results.get("scene_variants", []):
            item = self.items.add()
            inh = f" ↗ {', '.join(sv['inherits_from'])}" if sv.get("inherits_from") else ""
            item.item_id = f"variant:{sv['path']}"
            item.label = f"Scene: {sv['name']}{inh}"
            item.item_type = "variant"
            item.detail = f"{sv['entity_count']} entities"
            item.data = json.dumps(sv)
            item.selected = True

        # ── Orphan models ──
        for om in results.get("orphan_models", []):
            item = self.items.add()
            item.item_id = f"orphan:{om['path']}"
            item.label = f"Orphan Model: {om['name']} (no entity transform)"
            item.item_type = "orphan"
            item.detail = f"{om['msh_count']} sub-meshes"
            item.data = json.dumps(om)
            item.selected = False  # Default off for orphans

    def invoke(self, context, event):
        results = _discovery_cache.get("results")
        if not results:
            self.report({'ERROR'}, "No discovery results. Run area scan first.")
            return {'CANCELLED'}

        self._populate_items(results)

        area_name = results.get("area_name", "Unknown")
        static_count = len(results.get("static_scenes", []))
        variant_count = len(results.get("scene_variants", []))
        orphan_count = len(results.get("orphan_models", []))

        total = static_count + variant_count + orphan_count
        self._title = (
            f"Level Area: {area_name}  "
            f"({variant_count} scenes, {static_count} static, {orphan_count} orphan)"
        )

        return context.window_manager.invoke_props_dialog(self, width=650)

    def draw(self, context):
        layout = self.layout

        # Header
        if hasattr(self, '_title'):
            layout.label(text=self._title, icon='WORLD_DATA')

        # Sections
        sections = {
            "static": ("Static Scenes", 'MESH_DATA'),
            "variant": ("Scene Variants", 'SCENE_DATA'),
            "orphan": ("Orphan Models (no transform)", 'QUESTION'),
        }

        for item_type, (section_label, icon) in sections.items():
            type_items = [i for i in self.items if i.item_type == item_type]
            if not type_items:
                continue

            box = layout.box()
            row = box.row()
            row.label(text=section_label, icon=icon)

            for item in type_items:
                sub = box.row()
                sub.prop(item, "selected", text="")
                col = sub.column()
                col.label(text=item.label)
                col.label(text=item.detail, icon='DOT')

        # Summary
        selected_count = sum(1 for i in self.items if i.selected)
        layout.separator()
        layout.label(
            text=f"Will import {selected_count} of {len(self.items)} components"
        )

    def execute(self, context):
        results = _discovery_cache.get("results")
        if not results:
            return {'CANCELLED'}

        import json
        from . import level_assembler
        from . import material_registry as mat_reg
        from . import material_library as mat_lib

        unpack_root = _discovery_cache.get("unpack_root", "")
        scale = _discovery_cache.get("scale", 1.0)
        tex_ext = _discovery_cache.get("tex_extensions", ".dds,.png,.tga")
        tex_dirs = _discovery_cache.get("tex_search_dirs") or []
        mdf_dirs = _discovery_cache.get("mdf_search_dirs") or []
        import_decals = _discovery_cache.get("import_decals", True)
        import_lights = _discovery_cache.get("import_lights", False)

        # ── Create shared MaterialRegistry for fingerprint-based naming ──
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

        imported = 0
        errors = []

        # ── Status bar hint ──
        context.workspace.status_text_set(
            "Star Conflict — Importing level area, please wait..."
        )

        # ── Create shared static collection once ──
        static_coll = None
        area_name = results.get("area_name", "unknown")
        has_static = any(
            i.selected and i.item_type == "static" for i in self.items
        )
        if has_static:
            static_coll_name = f"StaticScene_{area_name}"
            static_coll = bpy.data.collections.get(static_coll_name)
            if static_coll is None:
                static_coll = bpy.data.collections.new(static_coll_name)
                context.scene.collection.children.link(static_coll)

        # ── Import selected components ──
        for item in self.items:
            if not item.selected:
                continue

            data = json.loads(item.data)

            if item.item_type == "variant":
                variant_name = data["name"]
                context.workspace.status_text_set(
                    f"Star Conflict — Importing variant: {variant_name}..."
                )
                print(f"\n[LevelArea] Importing scene variant: {variant_name}")

                # ── Create variant collection ──
                variant_coll = bpy.data.collections.get(variant_name)
                if variant_coll is None:
                    variant_coll = bpy.data.collections.new(variant_name)
                    context.scene.collection.children.link(variant_coll)

                # ── Snapshot scene root children before import ──
                before_children = {c.name for c in context.scene.collection.children}

                # Import scene variant — do NOT pass entity_collection;
                # let NameResolver build its own collection tree under scene root.
                scene_path = data["path"]
                if not os.path.isfile(scene_path):
                    errors.append(f"Scene not found: {scene_path}")
                    continue

                result = level_assembler.assemble_level(
                    scene_xml_path=scene_path,
                    unpack_root=unpack_root,
                    context=context,
                    registry=registry,
                    library=None,
                    tex_search_dirs=tex_dirs,
                    mdf_search_dirs=mdf_dirs,
                    tex_extensions=tex_ext,
                    scale=scale,
                    up_axis='Z_UP_TO_Y_UP',
                    import_static_scene=False,  # Static imported separately
                    import_decals=import_decals,
                    import_lights=import_lights,
                )
                if "error" in result:
                    errors.append(f"{variant_name}: {result['error']}")
                else:
                    imported += result.get("imported_count", 0)

                # ── Post-process: move new top-level collections to variant ──
                after_children = {c.name for c in context.scene.collection.children}
                new_tops = after_children - before_children - {variant_name}
                for name in new_tops:
                    coll = bpy.data.collections.get(name)
                    if coll:
                        context.scene.collection.children.unlink(coll)
                        variant_coll.children.link(coll)

            elif item.item_type == "static":
                static_path = data["path"]
                if not os.path.isdir(static_path):
                    errors.append(f"Static dir not found: {static_path}")
                    continue

                ss_name = os.path.basename(static_path)
                context.workspace.status_text_set(
                    f"Star Conflict — Importing static scene: {ss_name}..."
                )
                print(f"\n[LevelArea] Importing static scene: {ss_name}")

                msh_files = sorted([
                    f for f in level_assembler.glob.glob(
                        os.path.join(static_path, "**/*.mdl-msh*"), recursive=True)
                ])

                # ── Create NameResolver so static models get collection hierarchy ──
                from . import name_resolver
                resolver = name_resolver.NameResolver(
                    common_root=unpack_root,
                    collection_depth=-1,  # Full hierarchy
                )
                if len(msh_files) > 1:
                    resolver.scan(msh_files)

                # ── Snapshot scene root children before import ──
                before_children = {c.name for c in context.scene.collection.children}

                for msh_path in msh_files:
                    try:
                        obj = level_assembler.msh_importer.import_msh_with_materials(
                            filepath=msh_path,
                            context=context,
                            scale=scale,
                            up_axis='Z_UP_TO_Y_UP',
                            auto_link=True,
                            tex_search_dirs=tex_dirs,
                            mdf_search_dirs=mdf_dirs + [os.path.dirname(msh_path)],
                            tex_extensions=tex_ext,
                            complexity='FULL',
                            resolver=resolver,
                            registry=registry,
                            unpack_root=unpack_root,
                        )
                        if obj:
                            imported += 1
                    except Exception as exc:
                        errors.append(f"{os.path.basename(msh_path)}: {exc}")

                # ── Post-process: move new top-level collections to static ──
                if static_coll is not None:
                    after_children = {c.name for c in context.scene.collection.children}
                    new_tops = after_children - before_children
                    for name in new_tops:
                        coll = bpy.data.collections.get(name)
                        if coll:
                            context.scene.collection.children.unlink(coll)
                            static_coll.children.link(coll)

            elif item.item_type == "orphan":
                orphan_path = data["path"]
                orphan_name = data["name"]
                context.workspace.status_text_set(
                    f"Star Conflict — Importing orphan: {orphan_name}..."
                )
                print(f"\n[LevelArea] Importing orphan model: {orphan_name}")
                msh_files = sorted([
                    f for f in level_assembler.glob.glob(
                        os.path.join(orphan_path, "*.mdl-msh*"))
                ])
                # ── Create NameResolver for orphan hierarchy ──
                from . import name_resolver
                resolver = name_resolver.NameResolver(
                    common_root=unpack_root,
                    collection_depth=-1,
                )
                if len(msh_files) > 1:
                    resolver.scan(msh_files)
                for msh_path in msh_files:
                    try:
                        obj = level_assembler.msh_importer.import_msh_with_materials(
                            filepath=msh_path,
                            context=context,
                            scale=scale,
                            up_axis='Z_UP_TO_Y_UP',
                            auto_link=True,
                            tex_search_dirs=tex_dirs,
                            mdf_search_dirs=mdf_dirs + [os.path.dirname(msh_path)],
                            tex_extensions=tex_ext,
                            complexity='FULL',
                            resolver=resolver,
                            registry=registry,
                            unpack_root=unpack_root,
                        )
                        if obj:
                            imported += 1
                    except Exception as exc:
                        errors.append(f"{os.path.basename(msh_path)}: {exc}")

        # ── Report ──
        msg = f"Level Area import: {imported} objects"
        if errors:
            msg += f", {len(errors)} errors"
        self.report({'INFO'}, msg)

        if errors:
            print(f"[LevelArea] Errors:")
            for e in errors:
                print(f"  - {e}")

        print(f"\n[LevelArea] Done. Imported {imported} objects total.")
        context.workspace.status_text_set(None)
        return {'FINISHED'}


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

classes = [
    LevelAreaItem,
    SC_PRO_OT_import_level_area_confirm,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
