# ============================================================================
# Star Conflict MSH Importer for Blender
# ============================================================================
# Import Hammer Engine .mdl-mshXXX static mesh files into Blender.
# Supports: Blender 4.2 LTS, Blender 5.0+, Python 3.11+
#
# Installation:
#   1. Copy this entire folder to Blender's addons directory:
#      %APPDATA%\Blender Foundation\Blender\<version>\scripts\addons\
#   2. Enable in Edit > Preferences > Add-ons: "Star Conflict MSH Importer"
#
# Usage:
#   File > Import > Star Conflict MSH (.mdl-msh*)
#   File > Import > Star Conflict MSH Batch (directory)
# ============================================================================

bl_info = {
    "name": "Star Conflict MSH Importer",
    "author": "Sisyphus",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "File > Import",
    "description": "Import Star Conflict Hammer Engine .mdl-mshXXX mesh files",
    "category": "Import-Export",
    "support": "COMMUNITY",
}

import os
import struct
import math
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


# ============================================================================
# MSH Format Parser
# ============================================================================

def get_uv_offset(vbytes, flag):
    """Calculate UV1 byte offset within vertex structure.
    
    For VBytes=44 flag=0x16, UV1 is at offset 20 (not 24).
    """
    if vbytes == 20:
        return 12
    elif vbytes == 24:
        return 16
    elif vbytes == 28:
        if flag == 0xE or flag == 5:
            return 16
        elif flag == 0x11:
            return 20
        return 16
    elif vbytes == 32:
        return 20
    elif vbytes == 36:
        return 20
    elif vbytes == 40:
        return 24
    elif vbytes == 44:
        return 20   # Fixed: was 24, UV1 starts at offset 20 for flag=0x16
    return -1


def get_uv2_info(vbytes, flag):
    """Get UV2 (lightmap) byte offset and format within vertex structure.
    
    Returns (offset, format) or None if no UV2 space.
    format: 'float2' or 'uint16_unorm'
    """
    if vbytes < 36:
        return None
    
    if vbytes == 36:
        return (28, 'uint16_unorm')  # Fixed: was 'float2', but UV2 is uint16 UNORM
    
    if vbytes == 40:
        if flag == 0x1C or flag == 0x10:
            return (32, 'uint16_unorm')
        elif flag == 0x13:
            return (32, 'float2')
        return (32, 'float2')
    
    if vbytes == 44:
        return (28, 'uint16_unorm')
    
    return None


def parse_msh(data):
    """
    Parse .mdl-mshXXX binary data.

    File layout (little-endian):
      [0x00] uint32 version      (0/1/2/3)
      [0x04] uint32 flag         (affects UV offset)
      [0x08] uint32 VBytes       (vertex stride: 20/24/28/32/36/40/44)
      [0x0C] uint32 VCount       (vertex count)
      [0x10] uint32 FCount       (index count, triangles*3)
      [0x14~0x43]                (reserved)
      [0x44]                     vertex data (VCount * VBytes)
      [0x44 + VCount*VBytes]     index data (FCount * uint16)

    Note: MSH format does NOT contain vertex colors. The extra bytes
    beyond position+UV in VBytes=40/44 are bone indices/weights and
    possibly compressed normals/tangents.

    Returns (positions, uvs, uvs2, indices) or raises ValueError.
    positions: list of (x,y,z) tuples
    uvs:       list of (u,v) tuples, same length as positions (UV1 / diffuse)
    uvs2:      list of (u,v) tuples or None (UV2 / lightmap)
    indices:   list of int (triangle list, every 3 = 1 triangle)
    """
    if len(data) < 0x44 + 12:
        raise ValueError("File too small")

    version = struct.unpack_from("<I", data, 0x00)[0]
    flag    = struct.unpack_from("<I", data, 0x04)[0]
    vbytes  = struct.unpack_from("<I", data, 0x08)[0]
    vcount  = struct.unpack_from("<I", data, 0x0C)[0]
    fcount  = struct.unpack_from("<I", data, 0x10)[0]

    # Validation
    if version > 200:
        raise ValueError(f"Bad version: {version}")
    if vbytes < 20 or vbytes > 48:
        raise ValueError(f"Unsupported VBytes: {vbytes}")
    if vcount < 1 or vcount > 500000:
        raise ValueError(f"Bad VCount: {vcount}")
    if fcount < 3 or fcount > 1000000:
        raise ValueError(f"Bad FCount: {fcount}")

    expected = 0x44 + vcount * vbytes + fcount * 2
    if abs(expected - len(data)) > 100:
        raise ValueError(f"Size mismatch: expected {expected}, got {len(data)}")

    uv_off = get_uv_offset(vbytes, flag)
    uv2_info = get_uv2_info(vbytes, flag)

    # Parse vertices
    vert_base = 0x44
    positions = []
    uvs = []
    uvs2 = [] if uv2_info else None
    for i in range(vcount):
        off = vert_base + i * vbytes
        px, py, pz = struct.unpack_from("<fff", data, off)
        positions.append((px, py, pz))

        # UV1 (diffuse/color)
        if uv_off >= 0:
            u, v = struct.unpack_from("<ff", data, off + uv_off)
            uvs.append((u, 1.0 - v))  # flip V
        else:
            uvs.append((0.0, 0.0))
        
        # UV2 (lightmap)
        if uv2_info:
            uv2_off, uv2_fmt = uv2_info
            if uv2_fmt == 'float2':
                u2, v2 = struct.unpack_from("<ff", data, off + uv2_off)
                uvs2.append((u2, 1.0 - v2))
            elif uv2_fmt == 'uint16_unorm':
                u2_raw = struct.unpack_from("<H", data, off + uv2_off)[0]
                v2_raw = struct.unpack_from("<H", data, off + uv2_off + 2)[0]
                u2 = u2_raw / 32767.0
                v2 = 1.0 - (v2_raw / 32767.0)
                uvs2.append((u2, v2))

    # Parse indices (uint16 triangle list)
    idx_base = vert_base + vcount * vbytes
    indices = list(struct.unpack_from(f"<{fcount}H", data, idx_base))

    return positions, uvs, uvs2, indices


# ============================================================================
# Blender Mesh Builder
# ============================================================================

def build_mesh(name, positions, uvs, indices, uvs2=None):
    """
    Create a Blender mesh from parsed MSH data.

    Returns a bpy.types.Mesh ready to be linked to an Object.
    """
    # Build face list (every 3 indices = 1 triangle)
    # X 轴取反已同步翻转卷绕方向（与 Noesis v1.1 修复一致）
    faces = []
    for i in range(0, len(indices) - 2, 3):
        faces.append((indices[i], indices[i+1], indices[i+2]))

    # 修复前向轴：MSH 前向 -Z → +Z（与 Noesis v1.2 一致）
    positions = [(x, y, -z) for x, y, z in positions]

    # Create mesh
    mesh = bpy.data.meshes.new(name=name)
    mesh.from_pydata(positions, [], faces)

    # Create UV1 layer (named "map1" to match FBX/Noesis convention)
    if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
        uv_layer = mesh.uv_layers.new(name="map1")
        # Blender stores UVs per-loop (per-face-vertex)
        # Since we have per-vertex UVs, map each face corner to its vertex UV
        loop_idx = 0
        for face in faces:
            for vert_idx in face:
                if vert_idx < len(uvs):
                    uv_layer.data[loop_idx].uv = uvs[vert_idx]
                loop_idx += 1

    # Create UV2 layer (lightmap, "lightmap")
    if uvs2 and any(u != 0.0 or v != 0.0 for u, v in uvs2):
        uv2_layer = mesh.uv_layers.new(name="lightmap")
        loop_idx = 0
        for face in faces:
            for vert_idx in face:
                if vert_idx < len(uvs2):
                    uv2_layer.data[loop_idx].uv = uvs2[vert_idx]
                loop_idx += 1

    mesh.validate()
    mesh.update()

    return mesh


def _apply_up_axis(obj, up_axis):
    """Apply coordinate system rotation to a Blender object."""
    if up_axis == 'NONE':
        return

    from mathutils import Matrix, Euler

    if up_axis == 'Y_UP_TO_Z_UP':
        # Convert Y-up (many game engines) to Blender Z-up
        obj.rotation_euler = Euler((math.radians(-90), 0, 0), 'XYZ')

    elif up_axis == 'Z_UP_TO_Y_UP':
        obj.rotation_euler = Euler((math.radians(90), 0, 0), 'XYZ')

    elif up_axis == 'NOESIS_COMPAT':
        # Match Noesis preview: setAngOfs "0 290 130"
        # Noesis order may differ; this is the raw angle offset
        obj.rotation_euler = Euler((
            math.radians(0),
            math.radians(290),
            math.radians(130),
        ), 'XYZ')

    elif up_axis == 'AUTO_FLIP_YZ':
        # Directly swap Y and Z in mesh data
        mesh = obj.data
        for v in mesh.vertices:
            v.co = (v.co.x, v.co.z, -v.co.y)


# ============================================================================
# Import Operator (Single/Multiple Files)
# ============================================================================

class SC_OT_import_msh(Operator, ImportHelper):
    """Import Star Conflict MSH model files"""
    bl_idname = "import_scene.starconflict_msh"
    bl_label = "Import Star Conflict MSH (.mdl-msh*)"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".mdl-msh*"

    filter_glob: StringProperty(
        default="*.mdl-msh*",
        options={'HIDDEN'},
    )

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN'},
    )

    directory: StringProperty(subtype='DIR_PATH')

    # Import options
    join_lod: BoolProperty(
        name="Join LOD Models",
        description="Group multiple LOD levels into a single collection",
        default=True,
    )
    scale: FloatProperty(
        name="Scale",
        description="Scale factor applied to imported meshes",
        default=1.0,
        min=0.001, max=1000.0,
    )

    up_axis: EnumProperty(
        name="Up Axis",
        description="Coordinate system conversion (Blender uses Z-up)",
        items=[
            ('Y_UP_TO_Z_UP', "Y-up → Z-up", "Convert from Y-up (common game engines) to Blender Z-up (rotate X -90)"),
            ('NONE', "No Rotation", "Keep original vertex data as-is"),
            ('Z_UP_TO_Y_UP', "Z-up → Y-up", "Convert from Z-up to Y-up (rotate X 90)"),
            ('NOESIS_COMPAT', "Noesis Compat", "Match Noesis preview orientation (~0, 290, 130)"),
            ('AUTO_FLIP_YZ', "Auto (Flip Y/Z)", "Swap Y and Z coordinates"),
        ],
        default='Z_UP_TO_Y_UP',
    )

    auto_smooth: BoolProperty(
        name="Auto Smooth",
        description="Automatically split normals by face angle (matching in-game shading)",
        default=True,
    )

    smooth_angle: FloatProperty(
        name="Smooth Angle",
        description="Face angle threshold in degrees (default 30°)",
        default=30.0,
        min=1.0, max=180.0,
    )

    def execute(self, context):
        if not self.files:
            # Single file from filepath
            return self._import_file(self.filepath, context)
        return self._import_files(context)

    def _import_files(self, context):
        """Import multiple selected files."""
        imported = 0
        failed = 0

        for f in self.files:
            filepath = os.path.join(self.directory, f.name)
            result = self._import_one(filepath, context)
            if result:
                imported += 1
            else:
                failed += 1

        if self.join_lod and imported > 1:
            # Group by base name into collections
            basename = None
            for f in self.files:
                bn = self._extract_base_name(f.name)
                if basename is None:
                    basename = bn
                elif bn != basename:
                    basename = None
                    break
            if basename:
                self._group_into_collection(basename, context)

        if failed > 0:
            self.report({'WARNING'}, f"Imported {imported}, failed {failed}")
        else:
            self.report({'INFO'}, f"Imported {imported} models")
        return {'FINISHED'}

    def _group_into_collection(self, base_name, context):
        """Create a collection and move matching objects into it."""
        coll = bpy.data.collections.new(base_name)
        context.scene.collection.children.link(coll)
        for obj in context.selected_objects:
            # Move obj to new collection
            for c in obj.users_collection:
                c.objects.unlink(obj)
            coll.objects.link(obj)

    def _import_file(self, filepath, context):
        """Import from filepath (when using file browser single select)."""
        result = self._import_one(filepath, context)
        if result:
            self.report({'INFO'}, f"Imported: {os.path.basename(filepath)}")
        else:
            self.report({'ERROR'}, f"Failed: {os.path.basename(filepath)}")
        return {'FINISHED'}

    def _import_one(self, filepath, context):
        """Import a single MSH file into the current Blender scene."""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()
            positions, uvs, uvs2, indices = parse_msh(data)

            name = self._clean_name(os.path.basename(filepath))
            mesh = build_mesh(name, positions, uvs, indices, uvs2)

            # Auto-smooth for matching in-game normal splitting
            if self.auto_smooth and self.smooth_angle > 0.0:
                mesh.use_auto_smooth = True
                mesh.auto_smooth_angle = math.radians(self.smooth_angle)

            # Compute tangents for normal mapping (must be after auto_smooth)
            if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
                try:
                    mesh.calc_tangents(uvmap="map1")
                except Exception:
                    pass

            obj = bpy.data.objects.new(name=name, object_data=mesh)

            # Apply coordinate system rotation
            _apply_up_axis(obj, self.up_axis)

            # Apply scale
            if self.scale != 1.0:
                obj.scale = (self.scale, self.scale, self.scale)

            # Link to current collection
            collection = context.collection or context.scene.collection
            collection.objects.link(obj)

            # Select and make active
            obj.select_set(True)
            context.view_layer.objects.active = obj

            return True

        except ValueError as e:
            print(f"MSH parse error [{filepath}]: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error [{filepath}]: {e}")
            return False

    @staticmethod
    def _extract_base_name(filename):
        """Extract base name from .mdl-mshXXX: plasma_gun.mdl-msh000 -> plasma_gun"""
        dot = filename.rfind(".mdl-msh")
        if dot >= 0:
            return filename[:dot]
        return os.path.splitext(filename)[0]

    @staticmethod
    def _clean_name(filename):
        """Convert MSH filename to a clean Blender object name."""
        # plasma_gun.mdl-msh000 -> plasma_gun_000
        name = filename
        name = name.replace(".mdl-msh", "_msh")
        # Remove characters Blender doesn't like
        name = name.replace(" ", "_")
        # Truncate to Blender's 63 char name limit
        if len(name) > 63:
            name = name[:63]
        return name


# ============================================================================
# Batch Import Operator (Directory)
# ============================================================================

class SC_OT_import_msh_batch(Operator, ImportHelper):
    """Batch import all Star Conflict MSH files from a directory"""
    bl_idname = "import_scene.starconflict_msh_batch"
    bl_label = "Import Star Conflict MSH Batch (directory)"
    bl_options = {'REGISTER', 'UNDO'}

    # Override: use directory selection instead of file
    filename_ext = ""
    use_filter_folder = True

    filter_glob: StringProperty(
        default="",
        options={'HIDDEN'},
    )

    directory: StringProperty(subtype='DIR_PATH')

    files: CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'},
    )

    show_details: BoolProperty(
        name="Show Details",
        description="Print per-file progress to console",
        default=False,
    )

    scale: FloatProperty(        name="Scale",
        default=1.0,
        min=0.001, max=1000.0,
    )
    max_files: IntProperty(
        name="Max Files",
        description="Maximum number of files to import (0 = no limit)",
        default=0,
        min=0,
    )

    up_axis: EnumProperty(
        name="Up Axis",
        description="Coordinate system conversion",
        items=[
            ('Y_UP_TO_Z_UP', "Y-up → Z-up", "Convert from Y-up to Blender Z-up (rotate X -90)"),
            ('NONE', "No Rotation", "Keep original vertex data as-is"),
            ('Z_UP_TO_Y_UP', "Z-up → Y-up", "Convert from Z-up to Y-up (rotate X 90)"),
            ('NOESIS_COMPAT', "Noesis Compat", "Match Noesis preview orientation"),
            ('AUTO_FLIP_YZ', "Auto (Flip Y/Z)", "Swap Y and Z coordinates"),
        ],
        default='Z_UP_TO_Y_UP',
    )

    auto_smooth: BoolProperty(
        name="Auto Smooth",
        description="Automatically split normals by face angle",
        default=True,
    )

    smooth_angle: FloatProperty(
        name="Smooth Angle",
        description="Face angle threshold in degrees (default 30°)",
        default=30.0,
        min=1.0, max=180.0,
    )

    def execute(self, context):
        return self._batch_import(context)

    def _batch_import(self, context):
        """Recursively scan directory and import all .mdl-msh* files."""
        imported = 0
        failed = 0
        skipped = 0

        for root, dirs, filenames in os.walk(self.directory):
            for fname in filenames:
                if ".mdl-msh" not in fname:
                    continue
                if self.max_files > 0 and imported + failed >= self.max_files:
                    break

                filepath = os.path.join(root, fname)

                try:
                    # Skip if already in scene (by name)
                    obj_name = SC_OT_import_msh._clean_name(fname)
                    if obj_name in bpy.data.objects:
                        skipped += 1
                        if self.show_details:
                            print(f"  SKIP: {fname} (already in scene)")
                        continue

                    with open(filepath, 'rb') as f:
                        data = f.read()
                    positions, uvs, uvs2, indices = parse_msh(data)

                    mesh = build_mesh(obj_name, positions, uvs, indices, uvs2)

                    # Auto-smooth
                    if self.auto_smooth and self.smooth_angle > 0.0:
                        mesh.use_auto_smooth = True
                        mesh.auto_smooth_angle = math.radians(self.smooth_angle)

                    # Compute tangents (must be after auto_smooth)
                    if uvs and any(u != 0.0 or v != 0.0 for u, v in uvs):
                        try:
                            mesh.calc_tangents(uvmap="map1")
                        except Exception:
                            pass

                    obj = bpy.data.objects.new(name=obj_name, object_data=mesh)

                    if self.scale != 1.0:
                        obj.scale = (self.scale, self.scale, self.scale)

                    # Apply coordinate system rotation
                    _apply_up_axis(obj, self.up_axis)

                    collection = context.collection or context.scene.collection
                    collection.objects.link(obj)

                    if imported == 0:
                        # Select first imported object
                        obj.select_set(True)
                        context.view_layer.objects.active = obj

                    imported += 1
                    if self.show_details:
                        print(f"  OK: {fname}")

                except ValueError:
                    failed += 1
                    if self.show_details:
                        print(f"  FAIL: {fname} (unsupported format)")
                except Exception as e:
                    failed += 1
                    if self.show_details:
                        print(f"  FAIL: {fname} ({e})")

            if self.max_files > 0 and imported + failed >= self.max_files:
                break

        self.report(
            {'INFO'},
            f"Batch import: {imported} ok, {failed} failed, {skipped} skipped"
        )
        print(f"Star Conflict MSH Batch: {imported} imported, {failed} failed, {skipped} skipped")
        return {'FINISHED'}


# ============================================================================
# Registration
# ============================================================================

def menu_func_import(self, context):
    self.layout.operator(SC_OT_import_msh.bl_idname,
                         text="Star Conflict MSH (.mdl-msh*)")
    self.layout.operator(SC_OT_import_msh_batch.bl_idname,
                         text="Star Conflict MSH Batch (directory)")

CLASSES = [
    SC_OT_import_msh,
    SC_OT_import_msh_batch,
]

def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
