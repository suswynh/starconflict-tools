# ============================================================================
# Panels — UI panels for Star Conflict MSH Pro
# ============================================================================
"""Sidebar panels and menus for the MSH Pro importer."""

import bpy
from bpy.types import Panel, Menu


# ──────────────────────────────────────────────────────────────
# Import Menu Item
# ──────────────────────────────────────────────────────────────

def menu_func_import(self, context):
    """Add import menu entries."""
    self.layout.operator(
        "import_scene.starconflict_msh_pro",
        text="Star Conflict MSH Pro (.mdl-msh*)"
    )
    self.layout.operator(
        "import_scene.starconflict_msh_pro_batch",
        text="Star Conflict MSH Pro Batch (directory)"
    )


# ──────────────────────────────────────────────────────────────
# Sidebar Panel — 3D View
# ──────────────────────────────────────────────────────────────

class SC_PRO_PT_main(Panel):
    """Star Conflict MSH Pro tools panel in 3D View sidebar."""
    bl_label = "Star Conflict MSH Pro"
    bl_idname = "SC_PRO_PT_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Star Conflict"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout

        # ── Import section ──
        box = layout.box()
        box.label(text="Import", icon='IMPORT')
        box.operator("import_scene.starconflict_msh_pro", text="Import MSH File", icon='FILE_NEW')
        box.operator("import_scene.starconflict_msh_pro_batch", text="Batch Import Directory", icon='FILE_FOLDER')

        # ── Material section ──
        box = layout.box()
        box.label(text="Materials", icon='MATERIAL')
        box.operator("sc_pro.refresh_materials", text="Refresh Materials", icon='FILE_REFRESH')

        # ── Cache section ──
        box = layout.box()
        box.label(text="Cache", icon='CACHE')
        box.operator("sc_pro.clear_tex_cache", text="Clear Texture Cache", icon='X')

        # ── Settings summary ──
        prefs = self._get_prefs(context)
        if prefs:
            box = layout.box()
            box.label(text="Settings", icon='PREFERENCES')
            box.label(text=f"Extensions: {prefs.tex_extensions}")
            tex_count = len(prefs.default_tex_paths)
            mdf_count = len(prefs.default_mdf_paths)
            box.label(text=f"Texture paths: {tex_count}  |  MDF paths: {mdf_count}")

    @staticmethod
    def _get_prefs(context):
        try:
            return context.preferences.addons[__package__.split('.')[0]].preferences
        except (KeyError, AttributeError):
            return None


# ──────────────────────────────────────────────────────────────
# Material Info Panel
# ──────────────────────────────────────────────────────────────

class SC_PRO_PT_material_info(Panel):
    """Show material info for the active object."""
    bl_label = "Material Info"
    bl_idname = "SC_PRO_PT_material_info"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Star Conflict"
    bl_parent_id = "SC_PRO_PT_main"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH' and obj.material_slots

    def draw(self, context):
        layout = self.layout
        obj = context.active_object

        for idx, slot in enumerate(obj.material_slots):
            mat = slot.material
            if mat is None:
                continue
            row = layout.row()
            row.label(text=f"[{idx}] {mat.name}", icon='MATERIAL')

            if mat.use_nodes:
                tex_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
                for tn in tex_nodes:
                    if tn.image:
                        sub = layout.row()
                        sub.label(text=f"    └ {tn.image.name}", icon='TEXTURE')
                        sub.enabled = False


# ──────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────

_CLASSES = [
    SC_PRO_PT_main,
    SC_PRO_PT_material_info,
]


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)
