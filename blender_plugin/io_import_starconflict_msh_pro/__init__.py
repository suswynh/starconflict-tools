# ============================================================================
# Star Conflict MSH Importer Pro for Blender
# ============================================================================
# Import Hammer Engine .mdl-mshXXX static mesh files into Blender
# WITH automatic material creation and texture linking from .mdf definitions.
#
# Supports: Blender 4.2 LTS, Blender 5.0+, Python 3.11+
#
# This is the PRO version — extends the base importer with:
#   - MDF material definition parsing
#   - Multi-directory texture search
#   - Principled BSDF node network construction
#   - Per-material-type shader presets
#   - UI sidebar panel with material management tools
#
# Installation:
#   1. Copy this entire folder to Blender's addons directory:
#      %APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\
#   2. Enable in Edit > Preferences > Add-ons:
#      "Star Conflict MSH Importer Pro"
#
# Usage:
#   File > Import > Star Conflict MSH Pro (.mdl-msh*)
#   File > Import > Star Conflict MSH Pro Batch (directory)
#   3D View > Sidebar > Star Conflict > MSH Pro
# ============================================================================

bl_info = {
    "name": "Star Conflict MSH Importer Pro",
    "author": "SUSWYNH",
    "version": (2, 5, 4),
    "blender": (4, 2, 0),
    "location": "File > Import, 3D View > Sidebar > Star Conflict",
    "description": (
        "Import Star Conflict Hammer Engine .mdl-mshXXX mesh files "
        "with automatic MDF material parsing and texture linking. "
        "Builds Principled BSDF node networks from game shader definitions."
    ),
    "category": "Import-Export",
    "support": "COMMUNITY",
}

# ──────────────────────────────────────────────────────────────
# Sub-module imports
# ──────────────────────────────────────────────────────────────

import bpy

from . import msh_parser
from . import mdf_parser
from . import texture_finder
from . import shader_presets
from . import material_builder
from . import msh_importer
from . import scene_xml_parser
from . import level_assembler
from . import properties
from . import preferences
from . import operators
from . import panels
from . import level_area_dialog

# ──────────────────────────────────────────────────────────────
# Registration order (critical):
#   1. Properties    — data structures first
#   2. Preferences   — addon preferences
#   3. Operators     — actions
#   4. Panels        — UI last
# ──────────────────────────────────────────────────────────────

_MODULES = [
    properties,
    preferences,
    operators,
    level_area_dialog,
    panels,
]


# ──────────────────────────────────────────────────────────────
# Menu registration — File → Import (Blender 4.2+)
# Only scene_xml needs explicit registration; ImportHelper
# auto-registers operators with import_scene.* bl_idname.
# ──────────────────────────────────────────────────────────────

def _menu_import_scene_xml(self, context):
    self.layout.operator("import_scene.starconflict_scene_xml",
                          text="Star Conflict Level (scene.xml)")


def _menu_import_level_area(self, context):
    self.layout.operator("import_scene.starconflict_level_area",
                          text="Star Conflict Level Area (folder)")


def register():
    """Register all classes and menu items."""
    for mod in _MODULES:
        if hasattr(mod, 'register'):
            mod.register()

    bpy.types.TOPBAR_MT_file_import.append(_menu_import_scene_xml)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import_level_area)


def unregister():
    """Unregister in reverse order (LIFO)."""
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import_level_area)
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import_scene_xml)

    for mod in reversed(_MODULES):
        if hasattr(mod, 'unregister'):
            mod.unregister()
