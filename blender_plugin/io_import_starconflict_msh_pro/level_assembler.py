# ============================================================================
# Level Assembler — Scene entity import and placement
# ============================================================================
"""Resolve Model references from scene.xml and import+place models in Blender.

Core workflow:
  1. Parse scene.xml via scene_xml_parser
  2. Resolve Model paths to actual .mdl-msh* files under unpack_root
  3. Import each model and place at its scene-specified transform
  4. Organize into Blender Collections

Model path resolution:
  scene.xml references models as paths like:
    "mapskit\maps\dreadnoughtbattle\allidium\allidium_yard\allidium_glass_01"
    "models\objects\trees\tree_01"

  Resolution strategy (tried in order):
    a) <model_path>.mdl-msh000 (model as a directory with .mdl-msh files inside)
    b) <parent_of_model_path>\<basename>.mdl-msh000 (model base name in parent dir)
    c) Recursive search in unpack_root for matching basename
"""

import os
import glob
import time
import math
import re
import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

from . import scene_xml_parser
from . import msh_importer
from . import texture_finder
from . import material_registry
from . import material_library
from . import name_resolver
from . import def_resolver
from . import decal_parser


# ============================================================================
# Model path resolution
# ============================================================================

def _find_msh_files(model_rel_path: str, unpack_root: str) -> list:
    """Find all .mdl-msh* files for a model reference.

    Args:
        model_rel_path: Relative path from scene.xml Model attribute,
                        e.g. "models\objects\trees\tree_01"
        unpack_root: Unpack root directory.

    Returns:
        List of absolute paths to .mdl-msh* files, sorted by LOD index.
    """
    model_rel_path = model_rel_path.replace('\\', '/')

    # Strategy A: model_rel_path is a directory containing .mdl-msh* files
    dir_path = os.path.join(unpack_root, model_rel_path)
    if os.path.isdir(dir_path):
        msh_files = glob.glob(os.path.join(dir_path, "*.mdl-msh*"))
        if msh_files:
            return sorted(msh_files)

    # Strategy B: model_rel_path is a base name; its parent dir has
    #             <basename>.mdl-msh* files
    parent_dir = os.path.dirname(os.path.join(unpack_root, model_rel_path))
    basename = os.path.basename(model_rel_path)
    if os.path.isdir(parent_dir):
        msh_files = glob.glob(os.path.join(parent_dir, f"{basename}.mdl-msh*"))
        if msh_files:
            return sorted(msh_files)

    # Strategy C: fallback — recursive search in unpack_root
    #             (slow, only used if A and B both fail)
    search_pattern = os.path.join(unpack_root, "**", f"{basename}.mdl-msh*")
    msh_files = glob.glob(search_pattern, recursive=True)
    if msh_files:
        return sorted(msh_files)

    return []


# ============================================================================
# Entity import
# ============================================================================

def import_entity(entity: scene_xml_parser.EntityInstance,
                  unpack_root: str,
                  context,
                  registry=None,
                  resolver=None,
                  collection=None,
                  tex_search_dirs=None,
                  mdf_search_dirs=None,
                  tex_extensions=".dds,.png,.tga",
                  scale=1.0,
                  up_axis='Y_UP_TO_Z_UP') -> list:
    """Import all MSH files for a single entity and place at its transform.

    Args:
        entity: Parsed EntityInstance with pos/rot/model_path.
        unpack_root: Unpack root directory.
        context: Blender context.
        registry: MaterialRegistry instance (optional).
        resolver: NameResolver instance (optional).
        collection: Target Blender Collection.
        tex_search_dirs: Texture search directories.
        mdf_search_dirs: MDF search directories.
        tex_extensions: Texture extensions string.
        scale: Global scale factor.
        up_axis: Coordinate system conversion.

    Returns:
        List of imported Blender objects.
    """
    if not entity.has_model:
        return []

    msh_files = _find_msh_files(entity.model_path, unpack_root)
    if not msh_files:
        print(f"[LevelAssembler] No MSH files found for: {entity.model_path}")
        return []

    imported = []
    for msh_path in msh_files:
        # Determine MDF search dirs — include the model's own directory
        msh_dir = os.path.dirname(msh_path)
        all_mdf_dirs = list(mdf_search_dirs) if mdf_search_dirs else []
        if msh_dir not in all_mdf_dirs:
            all_mdf_dirs.insert(0, msh_dir)

        # Also add sibling/parent directories for MDF lookup
        parent_dir = os.path.dirname(msh_dir)
        if parent_dir not in all_mdf_dirs:
            all_mdf_dirs.append(parent_dir)

        obj = msh_importer.import_msh_with_materials(
            filepath=msh_path,
            context=context,
            scale=scale,
            up_axis='NONE',  # No object rotation — we bake Y→Z into vertices
            auto_link=True,
            tex_search_dirs=tex_search_dirs,
            mdf_search_dirs=all_mdf_dirs,
            tex_extensions=tex_extensions,
            complexity='FULL',
            resolver=resolver,
            registry=registry,
            unpack_root=unpack_root,
        )

        if obj is None:
            continue

        # ── Bake Y-up → Z-up into mesh vertices ──
        # build_mesh already does Z-flip: (x, y, z_hammer) → (x, y, -z_hammer)
        # Apply +90° X to convert: (x, y, -z) → (x, z, y)  = Blender Z-up
        # This allows entity rotation to be set directly without up_rot conflicts.
        rot_bake = Matrix.Rotation(math.radians(90), 4, 'X')
        obj.data.transform(rot_bake)

        # ── Apply entity transform ──
        # Hammer Y-up world pos (hx, hy, hz) → Blender Z-up world pos (hx, hz, hy)
        hx, hy, hz = entity.pos
        obj.location = (hx, hz, hy)

        # Rotation: XML quaternion (x, y, z, w) → Blender (w, -x, -z, -y)
        # Coordinate pipeline: MSH(Y-up,-Z fwd) → Z-flip(+Z fwd) → RotX(90°) bake
        # M = [[1,0,0],[0,0,1],[0,1,0]] conjugation: all rotation axes sign-flipped
        # Hammer RotX(θ)→Blender RotX(-θ), RotY(θ)→RotZ(-θ), RotZ(θ)→RotY(-θ)
        # Hence: q_blender = (qw, -qx, -qz, -qy) — all vector components negated
        if entity.rot != (0, 0, 0, 1):
            qx, qy, qz, qw = entity.rot
            # Normalize to unit length
            mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
            if mag > 1e-10:
                qx, qy, qz, qw = qx/mag, qy/mag, qz/mag, qw/mag
            obj.rotation_mode = 'QUATERNION'
            obj.rotation_quaternion = (qw, -qx, -qz, -qy)

        # ── Apply entity extra_attrs scale ──
        # env_scale from Effect entities: single float → uniform scale
        env_scale_val = entity.extra_attrs.get('env_scale', '')
        if env_scale_val:
            try:
                s = float(env_scale_val)
                obj.scale = (s, s, s)
            except (ValueError, TypeError):
                pass

        # Scale (capital S) from extra_attrs: single float or 3-value vector
        scale_val = entity.extra_attrs.get('Scale', '')
        if scale_val:
            try:
                parts = scale_val.strip().split()
                if len(parts) == 1:
                    s = float(parts[0])
                    obj.scale = (s, s, s)
                elif len(parts) == 3:
                    obj.scale = (float(parts[0]), float(parts[1]), float(parts[2]))
            except (ValueError, TypeError):
                pass

        # ── Collection linking ──
        if collection is not None:
            # Remove from default collections and add to target
            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            collection.objects.link(obj)

        obj.name = f"{entity.name}_{os.path.basename(msh_path).replace('.mdl-msh', '_msh')}"
        if len(obj.name) > 63:
            obj.name = obj.name[:63]

        imported.append(obj)

    return imported


# ============================================================================
# Environment settings → Blender World
# ============================================================================

def _apply_env_settings(env_settings: dict, unpack_root: str, tex_search_dirs: list = None):
    """Apply scene EnvSettings to Blender World environment and 3D View.

    Reads additionalColorRemap texture path, resolves it to a file,
    and sets up the Blender World shader with an Environment Texture node.
    Also sets 3D View clip distance from battlefieldRadius / levelPhysLimitRadius.

    Args:
        env_settings: Dict parsed from <EnvSettings> XML element.
        unpack_root: Star Conflict unpack root directory.
        tex_search_dirs: Additional texture search directories.
    """
    if not env_settings:
        return

    if tex_search_dirs is None:
        tex_search_dirs = []

    # ── Resolve environment texture ──
    color_remap = env_settings.get('additionalColorRemap', '').replace('\\', '/')
    texture_path = None

    if color_remap:
        candidates = []

        # Try relative to unpack_root
        base = os.path.join(unpack_root, color_remap)
        for ext in ('.dds', '.png', '.tga'):
            p = base + ext
            if os.path.isfile(p):
                candidates.append(p)

        # Try tex_search_dirs
        if not candidates:
            for d in tex_search_dirs:
                p_base = os.path.join(d, color_remap)
                for ext in ('.dds', '.png', '.tga'):
                    p = p_base + ext
                    if os.path.isfile(p):
                        candidates.append(p)
                        break
                if candidates:
                    break

        if candidates:
            texture_path = candidates[0]
            print(f"[EnvSettings] Found environment texture: {texture_path}")
        else:
            print(f"[EnvSettings] Environment texture not found: {color_remap}")

    # ── Setup Blender World ──
    world_name = env_settings.get('Name', 'World')
    world = bpy.data.worlds.get(world_name)
    if world is None:
        world = bpy.data.worlds.new(world_name)
    bpy.context.scene.world = world
    world.use_nodes = True
    node_tree = world.node_tree

    # Clear existing nodes
    node_tree.nodes.clear()

    if texture_path:
        # Create nodes: TexCoord → Mapping → Environment Texture → Background → World Output
        tex_coord = node_tree.nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-600, 0)

        # Y-up → Z-up conversion: rotate +90° around X to transform
        # Blender Z-up Generated coords into Hammer Y-up cubemap lookups
        mapping = node_tree.nodes.new('ShaderNodeMapping')
        mapping.location = (-500, 0)
        mapping.vector_type = 'POINT'
        mapping.inputs['Rotation'].default_value = (1.5708, 0.0, 0.0)

        env_tex = node_tree.nodes.new('ShaderNodeTexEnvironment')
        env_tex.location = (-300, 0)
        env_tex.image = bpy.data.images.load(texture_path)

        background = node_tree.nodes.new('ShaderNodeBackground')
        background.location = (-100, 0)

        world_output = node_tree.nodes.new('ShaderNodeOutputWorld')
        world_output.location = (200, 0)

        # Connect nodes
        node_tree.links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
        node_tree.links.new(mapping.outputs['Vector'], env_tex.inputs['Vector'])
        node_tree.links.new(env_tex.outputs['Color'], background.inputs['Color'])
        node_tree.links.new(background.outputs['Background'], world_output.inputs['Surface'])

        print(f"[EnvSettings] World shader configured with: {os.path.basename(texture_path)}")
    else:
        # Fallback: simple background node
        background = node_tree.nodes.new('ShaderNodeBackground')
        background.location = (-100, 0)
        # Use a neutral gray
        background.inputs['Color'].default_value = (0.05, 0.05, 0.08, 1.0)

        world_output = node_tree.nodes.new('ShaderNodeOutputWorld')
        world_output.location = (200, 0)

        node_tree.links.new(background.outputs['Background'], world_output.inputs['Surface'])

    # ── Set 3D View clip distance ──
    clip_end = None
    battlefield_radius = env_settings.get('battlefieldRadius', '')
    phys_limit_radius = env_settings.get('levelPhysLimitRadius', '')

    if phys_limit_radius:
        try:
            clip_end = float(phys_limit_radius)
        except (ValueError, TypeError):
            pass

    if clip_end is None and battlefield_radius:
        try:
            clip_end = float(battlefield_radius)
        except (ValueError, TypeError):
            pass

    if clip_end is not None:
        # Set film transparent
        bpy.context.scene.render.film_transparent = True

        # Set clip_end for all 3D View areas
        screen = bpy.context.screen
        if screen:
            for area in screen.areas:
                if area.type == 'VIEW_3D':
                    for space in area.spaces:
                        if space.type == 'VIEW_3D':
                            space.clip_end = clip_end * 100

        print(f"[EnvSettings] 3D View clip_end set to {clip_end} (film_transparent=True)")

    # ── Log summary ──
    applied = []
    if texture_path:
        applied.append(f"texture={color_remap}")
    if clip_end is not None:
        applied.append(f"clip_end={clip_end}")
    if applied:
        print(f"[EnvSettings] Applied: {', '.join(applied)}")


# ============================================================================
# Level assembly
# ============================================================================


def _make_decal_plane_mesh(texture_name, material_defs):
    """Create a plane mesh with UVs baked to the decal's UV window.

    Geometry: 1×1 XY-plane (bmesh.ops.create_grid), face normal = +Z.

    UV coordinate pipeline:
      1. Parse UV window from gamedata/decals.dat
         DirectX convention: (u, v_dx, w, h) — V=0 at top
      2. Convert to OpenGL:  v_gl = 1 - v_dx - h  (V=0 at bottom)
      3. Map plane coordinates to UV window:
           Y → U (model Y maps to texture U)
           X → V (model X maps to texture V)
      4. ×0.5 contraction toward UV shell centroid:
           cx + 0.5*(u - cx), cy + 0.5*(v - cy)
           Prevents edge bleed into adjacent decal tiles on atlas.

    0.5 factor (experimentally verified):
      Decal atlas textures pack multiple decals tightly in a grid.
      Shrinking UV by 0.5 around the shell centroid prevents the plane
      edge from sampling texels belonging to neighboring decals.
      Consistent with the 0.5 model scale factor — both arise from the
      relationship between Hammer's decal unit system and the 1×1 plane.

    Args:
        texture_name: Decal texture name (e.g. "empire_signs20yellow")
        material_defs: Dict from decal_parser.parse_decals_material()

    Returns:
        bpy.types.Mesh with UVs cropped, or None.
    """
    try:
        bm = bmesh.new()
        uv_layer = bm.loops.layers.uv.new("UVMap")
        bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.0)

        # Compute UV window from gamedata/decals.dat
        defn = material_defs.get(texture_name.lower()) if texture_name else None
        if defn and defn.uv and defn.uv != (0, 0, 1, 1):
            u, v_dx, w, h = defn.uv
            # DirectX (V=0 at top) → OpenGL (V=0 at bottom): v_gl = 1 - v_dx - h
            min_u = max(0.0, min(1.0, u))
            max_u = max(0.0, min(1.0, u + w))
            min_v = max(0.0, min(1.0, 1.0 - v_dx - h))
            max_v = max(0.0, min(1.0, 1.0 - v_dx))
        else:
            min_u, max_u = 0.0, 1.0
            min_v, max_v = 0.0, 1.0

        # Explicit UV: Y→U, X→V, then ×0.5 shrink toward centroid
        cx = (min_u + max_u) * 0.5
        cy = (min_v + max_v) * 0.5
        for face in bm.faces:
            for loop in face.loops:
                x, y, z = loop.vert.co
                u_val = min_u + (y + 0.5) * (max_u - min_u)
                v_val = min_v + (x + 0.5) * (max_v - min_v)
                # ×0.5 contraction: prevents edge bleed on decal atlas
                loop[uv_layer].uv = (
                    cx + 0.5 * (u_val - cx),
                    cy + 0.5 * (v_val - cy),
                )

        mesh_name = f"DecalPlane_{texture_name}" if texture_name else "DecalPlane"
        if len(mesh_name) > 63:
            mesh_name = mesh_name[:63]
        mesh = bpy.data.meshes.new(mesh_name)
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        return mesh
    except Exception as exc:
        print(f"[LevelAssembler] Failed to create decal plane mesh: {exc}")
        return None


def _build_decal_material(texture_name, material_defs, tex_search_dirs, extensions):
    """Create a Blender material for a decal with auto-linked diffuse texture.

    Args:
        texture_name: Decal texture name (e.g. "empire_signs04yellow")
        material_defs: Dict from decal_parser.parse_decals_material()
        tex_search_dirs: List of texture search root directories
        extensions: List of file extensions (e.g. ['.dds', '.png', '.tga'])

    Returns:
        bpy.types.Material or None.
    """
    defn = material_defs.get(texture_name.lower())

    # ── Resolve texture file ──
    texture_path = None
    if defn and defn.diffuse:
        diffuse = defn.diffuse.replace('\\', '/')
        basename = os.path.splitext(os.path.basename(diffuse))[0]
        for search_dir in (tex_search_dirs or []):
            # Try exact relative path
            for ext in extensions:
                candidate = os.path.join(search_dir, diffuse + ext)
                if os.path.isfile(candidate):
                    texture_path = candidate
                    break
            if texture_path:
                break
            # Try basename under search_dir (recursive, depth-limited)
            for root, dirs, files in os.walk(search_dir):
                for ext in extensions:
                    target = basename + ext
                    if target in files:
                        texture_path = os.path.join(root, target)
                        break
                if texture_path:
                    break
                depth = root.replace(search_dir, '').count(os.sep)
                if depth > 4:
                    dirs.clear()
            if texture_path:
                break

    # ── Create material ──
    mat_name = f"Decal_{texture_name}"
    if len(mat_name) > 63:
        mat_name = mat_name[:63]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    mat.blend_method = 'BLEND'
    mat.shadow_method = 'NONE'

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)

    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if texture_path and os.path.isfile(texture_path):
        img = bpy.data.images.load(texture_path)
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.location = (-300, 0)
        tex_node.image = img

        # UVs already baked into mesh — simple UV → Texture setup
        tex_coord = nodes.new('ShaderNodeTexCoord')
        tex_coord.location = (-500, 0)
        links.new(tex_coord.outputs['UV'], tex_node.inputs['Vector'])

        links.new(tex_node.outputs['Color'], bsdf.inputs['Base Color'])
        # Alpha → transparency (decals are translucent)
        links.new(tex_node.outputs['Alpha'], bsdf.inputs['Alpha'])
        # Glow/blend mode → emission
        if defn and defn.blend and 'glow' in defn.blend.lower():
            links.new(tex_node.outputs['Color'], bsdf.inputs['Emission Color'])
            bsdf.inputs['Emission Strength'].default_value = 0.5
    else:
        # Missing texture — visible fallback
        bsdf.inputs['Base Color'].default_value = (1.0, 0.0, 1.0, 1.0)

    return mat


def assemble_level(scene_xml_path: str,
                   unpack_root: str,
                   context,
                   registry=None,
                   library=None,
                   tex_search_dirs=None,
                   mdf_search_dirs=None,
                   tex_extensions=".dds,.png,.tga",
                   scale=1.0,
                     up_axis='Y_UP_TO_Z_UP',
                     import_static_scene=True,
                     import_decals=True,
                     import_lights=True,
                     progress_callback=None,
                     entity_collection=None,
                     static_collection=None) -> dict:
    """Assemble a complete Star Conflict level from scene.xml.

    This is the main entry point for "one-click level assembly".

    Args:
        scene_xml_path: Path to levels/*/scene.xml.
        unpack_root: Star Conflict unpack root directory.
        context: Blender context.
        registry: MaterialRegistry (optional).
        library: MaterialLibrary (optional).
        tex_search_dirs: Texture search directories.
        mdf_search_dirs: MDF search directories.
        tex_extensions: Texture extensions.
        scale: Global scale.
        up_axis: Coordinate system conversion.
        import_static_scene: Whether to also import map.mdl-msh* static scene.
        progress_callback: fn(current, total, message).
        entity_collection: Optional Blender Collection for entity objects.
        static_collection: Optional Blender Collection for static scene objects.

    Returns:
        dict with stats: {entity_count, imported_count, errors, ...}
    """
    start_time = time.time()
    imported_count = 0

    # ── 1. Parse scene.xml ──
    if not os.path.isfile(scene_xml_path):
        return {"error": f"scene.xml not found: {scene_xml_path}"}

    scene = scene_xml_parser.parse_scene_xml(scene_xml_path)

    # ── 2. Resolve inheritance chain ──
    all_entities = scene_xml_parser.collect_all_model_entities(
        scene, unpack_root
    )

    if progress_callback:
        progress_callback(0, len(all_entities), f"Found {len(all_entities)} model entities")

    # ── Load Def→Model resolver for fallback ──
    def_map = def_resolver.DefResolver()
    mapped_count = 0
    try:
        # Prefer decompiled Lua text for exact parsing
        decompiled_dir = os.path.join(unpack_root, 'gamedata_decompiled', 'def', 'objects')
        mapped_count = def_map.build_map(
            gamedata_def_dir="",
            decompiled_dir=decompiled_dir,
            unpack_root=unpack_root,
        )
    except Exception as e:
        print(f"[LevelAssembler] ERROR building Def map: {e}")
        import traceback; traceback.print_exc()
    if mapped_count > 0:
        print(f"[LevelAssembler] Loaded {mapped_count} Def→Model mappings")
    else:
        print(f"[LevelAssembler] No Def→Model mappings found — using file-system search")

    # ── 3. Pre-resolve all MSH files for NameResolver scanning ──
    all_msh_paths = []
    entity_msh_map = {}  # {model_path: (entity, [msh_paths])}

    for entity in all_entities:
        if not entity.has_model:
            continue
        msh_files = _find_msh_files(entity.model_path, unpack_root)
        if msh_files:
            all_msh_paths.extend(msh_files)
            entity_msh_map[entity.model_path] = (entity, msh_files)

    # ── Def-based entities (no Model= attribute) — always processed ──
    # Previously guarded by 'if not entity_msh_map:', which caused Def entities
    # to be silently skipped when ANY Model= entity existed in the scene chain.
    # Now Def entities are always resolved alongside Model-based ones.
    all_scene_entities = []
    chain = scene_xml_parser.resolve_inheritance_chain(scene, unpack_root, max_depth=5)
    for s in chain:
        all_scene_entities.extend(s.entities)

    for entity in all_scene_entities:
        if entity.has_model:
            continue
        if not entity.def_type:
            continue
        if entity.def_type.startswith(('Logic_', 'Sound_', 'Helpers_', 'Camera',
                                        'Path', 'Effects_')):
            continue

        # ── Lights entities → create Blender light objects ──
        if import_lights and entity.def_type.startswith('Lights_'):
            light_data = None
            light_name = entity.name
            light_pos = (entity.pos[0], entity.pos[2], entity.pos[1])  # Hammer Y-up → Blender Z-up

            if 'PointLight' in entity.def_type:
                light_data = bpy.data.lights.new(name=light_name, type='POINT')
                rad = entity.extra_attrs.get('rad', '60')
                color = entity.extra_attrs.get('color', '0xFFFFFFFF')
                try:
                    light_data.energy = float(rad) * 10  # approximate
                    # Parse hex color: 0xAARRGGBB or 0xRRGGBBAA
                    c = color.replace('0x', '').replace('0X', '')
                    if len(c) == 8:
                        light_data.color = (int(c[2:4], 16) / 255, int(c[4:6], 16) / 255, int(c[6:8], 16) / 255)
                    elif len(c) == 6:
                        light_data.color = (int(c[0:2], 16) / 255, int(c[2:4], 16) / 255, int(c[4:6], 16) / 255)
                except Exception:
                    pass
            elif 'Beam' in entity.def_type:
                light_data = bpy.data.lights.new(name=light_name, type='SPOT')
                width = entity.extra_attrs.get('width', '3')
                try:
                    light_data.energy = float(width) * 50
                    base_color = entity.extra_attrs.get('base_color', '0x15FF2828')
                    c = base_color.replace('0x', '').replace('0X', '')
                    if len(c) >= 6:
                        light_data.color = (int(c[2:4], 16) / 255, int(c[4:6], 16) / 255, int(c[6:8], 16) / 255)
                except Exception:
                    pass
            else:
                light_data = bpy.data.lights.new(name=light_name, type='POINT')

            if light_data:
                light_obj = bpy.data.objects.new(name=light_name, object_data=light_data)
                light_obj.location = light_pos
                # Apply rotation (same M-conjugated formula as model entities)
                if entity.rot != (0, 0, 0, 1):
                    qx, qy, qz, qw = entity.rot
                    light_obj.rotation_mode = 'QUATERNION'
                    light_obj.rotation_quaternion = (qw, -qx, -qz, -qy)

                # Flip direction for beam-type lights (SPOT)
                if 'Beam' in entity.def_type:
                    flip = Quaternion((0.0, 1.0, 0.0), math.radians(180))
                    light_obj.rotation_quaternion = flip @ light_obj.rotation_quaternion

                # Link to Lights collection
                lights_coll = bpy.data.collections.get('Lights（Experimental - need user to edit）')
                if lights_coll is None:
                    lights_coll = bpy.data.collections.new('Lights（Experimental - need user to edit）')
                    context.scene.collection.children.link(lights_coll)
                lights_coll.objects.link(light_obj)
                imported_count += 1
            continue

        # ── Gameplay index resolution: main_N → gameplay_idx (N-1) ──
        # When a base Def (e.g. ClanShip_BaseGen) has sub-types with different
        # models and gameplay_idx values, the entity name "main_<N>_team_..." 
        # encodes which sub-type to use. Map N→index and resolve to child model.
        gp_name_match = re.match(r'^main_(\d+)_', entity.name)
        if gp_name_match:
            gp_index = int(gp_name_match.group(1)) - 1
            if def_map.has_gameplay_idx_children(entity.def_type):
                gp_model = def_map.resolve_child_by_index(entity.def_type, gp_index)
                if gp_model:
                    msh_files = _find_msh_files(gp_model, unpack_root)
                    if msh_files:
                        fake_path = f"gpdef://{entity.def_type}/{entity.name}"
                        entity.model_path = fake_path
                        all_msh_paths.extend(msh_files)
                        entity_msh_map[fake_path] = (entity, msh_files)
                        all_entities.append(entity)
                        continue

        def_name = entity.def_type.lower()
        # Try mapskit/maps/<level>/<map>/<def_name>
        rel_parts = os.path.relpath(scene_xml_path, unpack_root).replace('\\', '/').split('/')
        if len(rel_parts) >= 3:
            msh_files = _find_msh_files(
                f"mapskit/maps/{rel_parts[1]}/{rel_parts[2]}/{def_name}",
                unpack_root)
            if msh_files:
                fake_path = f"def://{entity.def_type}/{entity.name}"
                entity.model_path = fake_path
                all_msh_paths.extend(msh_files)
                entity_msh_map[fake_path] = (entity, msh_files)
                # Also add to all_entities for the import loop
                all_entities.append(entity)
                continue

        # Try models/objects/<def_name>
        msh_files = _find_msh_files(f"models/objects/{def_name}", unpack_root)
        if msh_files:
            fake_path = f"def://{entity.def_type}/{entity.name}"
            entity.model_path = fake_path
            all_msh_paths.extend(msh_files)
            entity_msh_map[fake_path] = (entity, msh_files)
            all_entities.append(entity)
            continue

        # Third fallback: try DefResolver mapping (decompiled Lua + filesystem)
        model_path = def_map.resolve(entity.def_type, unpack_root=unpack_root,
                                      scene_level_dir=os.path.dirname(scene_xml_path))
        if model_path:
            msh_files = _find_msh_files(model_path, unpack_root)
            if msh_files:
                fake_path = f"def://{entity.def_type}/{entity.name}"
                entity.model_path = fake_path
                all_msh_paths.extend(msh_files)
                entity_msh_map[fake_path] = (entity, msh_files)
                if entity not in all_entities:
                    all_entities.append(entity)
                continue

    # Static scene MSH files — resolve the corresponding mapskit directory.
    #
    # Hammer Engine uses two conventions for level→mapskit mapping:
    #
    #   Convention A (variant-specific):
    #     levels/X/Y/variant/scene.xml  →  mapskit/maps/X/Y/variant/
    #     Example: allidium_yard → mapskit/…/allidium/allidium_yard/  (206 MSH)
    #
    #   Convention B (faction-shared):
    #     levels/X/Y/variant_01/scene.xml → mapskit/maps/X/Y/  (parent dir)
    #     Example: empire_dreadnoughtbattle_01~03 → mapskit/…/empire/  (1151 MSH)
    #
    # Resolution strategy (tried in order):
    #   1. Try variant-specific  (rel_parts[3])
    #   2. Try faction-level parent (rel_parts[2]) — when multiple variants
    #      share a single mapskit directory (empire/federation/jericho).
    static_msh_paths = []
    if import_static_scene:
        rel_parts = os.path.relpath(scene_xml_path, unpack_root).replace('\\', '/').split('/')
        static_dir = None
        if len(rel_parts) >= 4 and rel_parts[0] == 'levels':
            # Strategy 1: variant-specific (Convention A)
            candidate = os.path.join(unpack_root, 'mapskit', 'maps',
                                     rel_parts[1], rel_parts[2], rel_parts[3])
            if os.path.isdir(candidate):
                static_dir = candidate
            else:
                # Strategy 2: faction-level fallback (Convention B)
                # Used when multiple variants share one mapskit directory,
                # e.g. empire_dreadnoughtbattle_01~03 → mapskit/…/empire/
                fallback = os.path.join(unpack_root, 'mapskit', 'maps',
                                        rel_parts[1], rel_parts[2])
                if os.path.isdir(fallback):
                    static_dir = fallback
        elif len(rel_parts) == 3 and rel_parts[0] == 'levels':
            static_dir = os.path.join(unpack_root, 'mapskit', 'maps',
                                      rel_parts[1], rel_parts[2])
        if static_dir and os.path.isdir(static_dir):
            static_msh_paths = sorted(glob.glob(os.path.join(static_dir, "**/*.mdl-msh*"), recursive=True))
            all_msh_paths.extend(static_msh_paths)

    # ── Dedup: remove static scene MSH files that overlap with entity MSH ──
    # Entity imports carry scene.xml Pos/Rot transforms — keep those, skip raw static.
    entity_basenames = set()
    for model_path, (entity, msh_files) in entity_msh_map.items():
        for mf in msh_files:
            entity_basenames.add(os.path.basename(mf))
    dedup_count = 0
    if entity_basenames:
        new_static = []
        for sp in static_msh_paths:
            if os.path.basename(sp) in entity_basenames:
                # Remove from all_msh_paths as well
                if sp in all_msh_paths:
                    all_msh_paths.remove(sp)
                dedup_count += 1
            else:
                new_static.append(sp)
        static_msh_paths[:] = new_static
    if dedup_count > 0:
        print(f"[LevelAssembler] Dedup: {dedup_count} static MSH files skipped "
              f"(already covered by entity imports with transforms)")

    # ── 4. Setup name resolver (same as batch import) ──
    resolver = name_resolver.NameResolver(
        common_root=unpack_root,
        collection_depth=-1,  # Full hierarchy
    )

    if len(all_msh_paths) > 1:
        resolver.scan(all_msh_paths)
        conflicts = resolver.get_conflicts()
        if conflicts:
            print(f"  [LevelAssembler] {len(conflicts)} conflict groups detected")

    if progress_callback:
        progress_callback(0, len(all_entities),
                          f"Found {len(all_entities)} entities, {len(all_msh_paths)} MSH files")

    # ── 5. Validate entity data before import ──
    # Detect potential data merge issues: entities with same def_type
    # that have identical pos+rot (should never happen for distinct entities).
    entity_groups = {}  # {def_type: [(name, pos, rot)]}
    for entity in all_entities:
        if not entity.has_model:
            continue
        key = entity.def_type.lower()
        if key not in entity_groups:
            entity_groups[key] = []
        entity_groups[key].append((entity.name, entity.pos, entity.rot))

    merge_warnings = 0
    for def_type, items in entity_groups.items():
        if len(items) <= 1:
            continue
        # Check for identical transforms
        seen = {}
        for name, pos, rot in items:
            sig = (round(pos[0], 3), round(pos[1], 3), round(pos[2], 3),
                   round(rot[0], 3), round(rot[1], 3), round(rot[2], 3), round(rot[3], 3))
            if sig in seen:
                merge_warnings += 1
                if merge_warnings <= 5:
                    print(f"[LevelAssembler] WARNING: {def_type} entities "
                          f"'{seen[sig]}' and '{name}' have identical pos+rot "
                          f"— possible data merge!")
            else:
                seen[sig] = name
    if merge_warnings > 0:
        print(f"[LevelAssembler] Total {merge_warnings} possible data merge(s) detected")
    else:
        print(f"[LevelAssembler] No data merge issues detected ({len(entity_groups)} unique Def types)")

    # ── 6. Import all model entities ──
    error_count = 0
    errors = []

    for i, entity in enumerate(all_entities):
        if not entity.has_model or entity.model_path not in entity_msh_map:
            continue

        _, msh_files = entity_msh_map[entity.model_path]
        if progress_callback:
            progress_callback(i + 1, len(all_entities),
                              f"Importing: {entity.name}")

        try:
            for msh_path in msh_files:
                msh_dir = os.path.dirname(msh_path)
                all_mdf = list(mdf_search_dirs) if mdf_search_dirs else []
                if msh_dir not in all_mdf:
                    all_mdf.insert(0, msh_dir)
                parent_dir = os.path.dirname(msh_dir)
                if parent_dir not in all_mdf:
                    all_mdf.append(parent_dir)

                obj = msh_importer.import_msh_with_materials(
                    filepath=msh_path,
                    context=context,
                    scale=scale,
                    up_axis='NONE',  # No object rotation — bake Y→Z into vertices
                    auto_link=True,
                    tex_search_dirs=tex_search_dirs,
                    mdf_search_dirs=all_mdf,
                    tex_extensions=tex_extensions,
                    complexity='FULL',
                    resolver=resolver,
                    registry=registry,
                    unpack_root=unpack_root,
                )
                if obj:
                    # Bake Y-up → Z-up into mesh vertices
                    rot_bake = Matrix.Rotation(math.radians(90), 4, 'X')
                    obj.data.transform(rot_bake)

                    # Apply entity transform
                    hx, hy, hz = entity.pos
                    obj.location = (hx, hz, hy)

                    # Rotation: XML quaternion (x, y, z, w) → Blender (w, -x, -z, -y)
                    # M = [[1,0,0],[0,0,1],[0,1,0]] conjugation negates all rotation axes.
                    # Hammer RotX(θ)→RotX(-θ), RotY(θ)→RotZ(-θ), RotZ(θ)→RotY(-θ)
                    if entity.rot != (0, 0, 0, 1):
                        qx, qy, qz, qw = entity.rot
                        # Normalize to unit length — decompiled XML data may have
                        # accumulated floating-point drift that Blender rejects.
                        mag = math.sqrt(qx*qx + qy*qy + qz*qz + qw*qw)
                        if mag > 1e-10:
                            qx, qy, qz, qw = qx/mag, qy/mag, qz/mag, qw/mag
                        obj.rotation_mode = 'QUATERNION'
                        obj.rotation_quaternion = (qw, -qx, -qz, -qy)
                        # Debug: log entity rotations for verification
                        if imported_count < 20:
                            print(f"  [Rot] {entity.name}: XML=({qx:.4f},{qy:.4f},{qz:.4f},{qw:.4f}) "
                                  f"→ Blender=({qw:.4f},{-qx:.4f},{-qz:.4f},{-qy:.4f})")

                    imported_count += 1

                    # ── Link to entity collection ──
                    if entity_collection is not None:
                        for coll in obj.users_collection:
                            coll.objects.unlink(obj)
                        entity_collection.objects.link(obj)

        except Exception as exc:
            error_count += 1
            errors.append(f"{entity.name}: {exc}")

    # ── 6. Import static scene from map.mdl-msh* ──
    static_count = 0
    for msh_path in static_msh_paths:
        msh_dir = os.path.dirname(msh_path)
        all_mdf = list(mdf_search_dirs) if mdf_search_dirs else []
        if msh_dir not in all_mdf:
            all_mdf.insert(0, msh_dir)

        obj = msh_importer.import_msh_with_materials(
            filepath=msh_path,
            context=context,
            scale=scale,
            up_axis=up_axis,
            auto_link=True,
            tex_search_dirs=tex_search_dirs,
            mdf_search_dirs=all_mdf,
            tex_extensions=tex_extensions,
            complexity='FULL',
            resolver=resolver,
            registry=registry,
            unpack_root=unpack_root,
        )
        if obj:
            static_count += 1
            # ── Link to static collection ──
            if static_collection is not None:
                for coll in obj.users_collection:
                    coll.objects.unlink(obj)
                static_collection.objects.link(obj)

    # ── 7. Apply environment settings ──
    try:
        _apply_env_settings(scene.env_settings, unpack_root, tex_search_dirs)
    except Exception as exc:
        print(f"[LevelAssembler] Failed to apply env settings: {exc}")

    # ── 8. Import decals ──
    decal_count = 0
    scene_dir = os.path.dirname(scene_xml_path)
    decals_path = os.path.join(scene_dir, 'decals.dat')
    if import_decals and os.path.isfile(decals_path):
        try:
            decals = decal_parser.parse_decals(decals_path)
            if decals:
                # ── Parse gamedata/decals.dat material definitions ──
                material_defs = {}
                gamedata_decals = os.path.join(unpack_root, "gamedata", "decals.dat")
                if os.path.isfile(gamedata_decals):
                    material_defs = decal_parser.parse_decals_material(gamedata_decals)

                # ── Per-texture mesh cache: tex_name → mesh ──
                tex_meshes = {}
                # ── Material cache: tex_name → material ──
                mat_cache = {}
                exts = [e.strip() for e in tex_extensions.split(',') if e.strip()]

                # ── Decals collection ──
                decals_coll = bpy.data.collections.get('Decals（need user to edit）')
                if decals_coll is None:
                    decals_coll = bpy.data.collections.new('Decals（need user to edit）')
                    context.scene.collection.children.link(decals_coll)

                # ── Coordinate change matrix ──
                M = Matrix((
                    (1, 0, 0),
                    (0, 0, 1),
                    (0, 1, 0),
                ))

                for i, decal in enumerate(decals):
                    obj_name = (f"Decal_{decal.texture}_{i}"
                                if decal.texture else f"Decal_{i}")
                    if len(obj_name) > 63:
                        obj_name = obj_name[:63]

                    # ── Per-texture mesh with UVs baked to decal's UV window ──
                    tex_key = decal.texture.lower() if decal.texture else "_empty_"
                    if tex_key not in tex_meshes:
                        tex_mesh = _make_decal_plane_mesh(
                            decal.texture, material_defs)
                        tex_meshes[tex_key] = tex_mesh
                    base_mesh = tex_meshes.get(tex_key)

                    if base_mesh:
                        obj = bpy.data.objects.new(obj_name, base_mesh)
                    else:
                        obj = bpy.data.objects.new(obj_name, None)
                        obj.empty_display_type = 'PLAIN_AXES'

                    # ── Apply material (cached per texture) ──
                    if base_mesh and decal.texture:
                        if tex_key not in mat_cache:
                            mat_cache[tex_key] = _build_decal_material(
                                decal.texture, material_defs,
                                tex_search_dirs, exts)
                        mat = mat_cache.get(tex_key)
                        if mat:
                            obj.data.materials.clear()
                            obj.data.materials.append(mat)

                    # ── Position ──
                    hx, hy, hz = decal.pos
                    obj.location = M @ Vector((hx, hy, hz))

                    # ── Rotation: direction-driven alignment + twist ──
                    # ═══════════════════════════════════════════════════════
                    # ── Rotation: normal-aligned + world-up texture ──
                    # ═══════════════════════════════════════════════════════
                    #
                    # Derived from decals.dat binary format analysis:
                    #
                    #   direction (dx,dy,dz) = surface normal in Hammer Y-up
                    #   rotation  (qx,qy,qz) = ALWAYS (0,1,0) in Hammer
                    #     → qw=0 confirms this is a direction vector, not a
                    #       quaternion. In Hammer, decal texture-up is
                    #       fixed to world-up (+Y_ham → +Z_bl after M).
                    #       The field is redundant — we ignore it.
                    #
                    # Plane mesh (bmesh.ops.create_grid, size=1.0):
                    #   normal = +Z, texture-U = +Y (Y→U), texture-V = +X
                    #
                    # Conversion:
                    #   1. N_bl = M·(dx,dy,dz) = (dx, dz, dy)  [Hammer→Blender]
                    #   2. q_align = (+Z).rotation_difference(N_bl)
                    #   3. World-up(+Z_bl) projected onto N_bl's plane
                    #   4. q_tex = rotate plane's +Y → world-up projection
                    #   5. final = q_align @ q_tex
                    #
                    # Old formula (v2.5.4, now removed):
                    #   Used hacky axis-swap + delta_q(70.5°) hand-fit.
                    #   Replaced by direct geometric construction.
                    # ═══════════════════════════════════════════════════════
                    dx, dy, dz = decal.direction
                    N_bl = Vector((dx, dy, dz))  # direction as-is (no M — geometric vector)

                    obj.rotation_mode = 'QUATERNION'

                    if N_bl.length > 1e-10:
                        N_bl.normalize()

                        # Align plane normal +Z → N_bl
                        q_align = Vector((0, 0, 1)).rotation_difference(N_bl)

                        # Project world-up (+Z) onto plane ⟂ N_bl
                        world_up = Vector((0, 0, 1))
                        up_proj = world_up - N_bl * N_bl.dot(world_up)
                        if up_proj.length > 1e-10:
                            up_proj.normalize()
                            Y_after = q_align @ Vector((0, 1, 0))
                            # Deterministic axis-angle (cross product fixes sign)
                            dot = Y_after.dot(up_proj)
                            if abs(dot) < 1.0 - 1e-10:
                                angle = math.acos(max(-1.0, min(1.0, dot)))
                                axis = Y_after.cross(up_proj).normalized()
                                q_tex = Quaternion(axis, angle)
                            else:
                                q_tex = Quaternion()
                        else:
                            q_tex = Quaternion()

                        obj.rotation_quaternion = q_align @ q_tex

                        if i < 20:
                            a_deg = math.degrees(2 * math.acos(
                                max(-1.0, min(1.0, abs(q_align.w)))))
                            t_deg = math.degrees(2 * math.acos(
                                max(-1.0, min(1.0, abs(q_tex.w)))))
                            r = decal.rot
                            print(f"  [{i}] {decal.texture} "
                                  f"dir=({dx:.2f},{dy:.2f},{dz:.2f}) "
                                  f"r=({r[0]:.2f},{r[1]:.2f},{r[2]:.2f}) "
                                  f"→N=({N_bl.x:.2f},{N_bl.y:.2f},{N_bl.z:.2f}) "
                                  f"a={a_deg:.0f}° t={t_deg:.0f}°")
                    else:
                        obj.rotation_quaternion = Quaternion((1, 0, 0, 0))

                    # ═══════════════════════════════════════════════════════
                    # ── Scale: 0.5 × original (M-converted: sx,sz,sy) ──
                    # ═══════════════════════════════════════════════════════
                    #
                    # 0.5 factor (determined experimentally):
                    #   - Plane mesh is 1×1 (bmesh.ops.create_grid(size=1.0))
                    #   - Hammer scale units appear to be 2× the plane mesh
                    #     effective size, so 0.5 maps them correctly.
                    #   - This applies to both model scale and UV shell
                    #     (see _make_decal_plane_mesh UV ×0.5 contraction).
                    #   - Verified on actual level data.
                    # ═══════════════════════════════════════════════════════
                    obj.scale = 0.5 * (M @ Vector(decal.scale))

                    # Link to Decals collection
                    for coll in obj.users_collection:
                        coll.objects.unlink(obj)
                    decals_coll.objects.link(obj)
                    decal_count += 1

                if decal_count > 0:
                    print(f"[LevelAssembler] Imported {decal_count} decals "
                          f"({len(tex_meshes)} unique textures)")
        except Exception as exc:
            print(f"[LevelAssembler] Failed to import decals: {exc}")

    elapsed = time.time() - start_time

    # Compute level name from path
    rel_parts = os.path.relpath(scene_xml_path, unpack_root).replace('\\', '/').split('/')
    level_display = '/'.join(rel_parts[1:3]) if len(rel_parts) >= 3 else os.path.basename(scene_xml_path)

    return {
        "level_name": level_display,
        "entity_count": len(all_entities),
        "imported_count": imported_count,
        "static_scene_count": static_count,
        "decal_count": decal_count,
        "error_count": error_count,
        "errors": errors,
        "elapsed": elapsed,
        "inheritance_chain": [s.filepath for s in
                              scene_xml_parser.resolve_inheritance_chain(scene, unpack_root)],
    }


# ============================================================================
# Level Area Discovery — scan area folder for all components
# ============================================================================

def discover_level_area(area_path: str, unpack_root: str) -> dict:
    """Discover all importable components in a level area folder.

    Scans the area directory and its mapskit counterpart to find:
      - Static scenes (mapskit directories, Convention A or B)
      - Scene variants (scene.xml files in subdirectories)
      - Orphan models (in mapskit but no entity reference)

    Args:
        area_path: Absolute path to the area folder
                   (e.g. .../levels/dreadnoughtbattle/allidium/).
        unpack_root: Star Conflict unpack root directory.

    Returns:
        dict: {
            "area_name": str,
            "area_path": str,
            "static_scenes": [{path, msh_count, shared}],
            "scene_variants": [{name, path, entity_count, inherits_from}],
            "orphan_models": [{name, path, msh_count}],
        }
    """
    import xml.etree.ElementTree as ET

    area_path = os.path.normpath(area_path)
    area_name = os.path.basename(area_path)

    # ── Compute relative path from unpack_root ──
    try:
        rel_area = os.path.relpath(area_path, unpack_root).replace('\\', '/')
    except ValueError:
        return {"error": f"Area path is not under unpack_root: {area_path}"}

    rel_parts = rel_area.split('/')

    # ── 1. Discover scene variants ──
    scene_variants = []
    if os.path.isdir(area_path):
        for entry in sorted(os.listdir(area_path)):
            sub_path = os.path.join(area_path, entry)
            scene_xml = os.path.join(sub_path, "scene.xml")
            if os.path.isfile(scene_xml):
                # Count entities
                entity_count = 0
                inherits_from = []
                try:
                    tree = ET.parse(scene_xml)
                    root = tree.getroot()
                    container = root.find("EntityContainer")
                    if container is not None:
                        entity_count = len(container.findall("Entity"))
                    inh_node = root.find("Inheritance")
                    if inh_node is not None:
                        for child in inh_node.findall("Scene"):
                            inh_name = child.get("Name", "")
                            if inh_name:
                                # Extract just the variant name
                                inh_base = os.path.basename(os.path.dirname(
                                    inh_name.replace('\\', '/')))
                                inherits_from.append(inh_base)
                except Exception:
                    pass

                scene_variants.append({
                    "name": entry,
                    "path": scene_xml,
                    "entity_count": entity_count,
                    "inherits_from": inherits_from,
                })

    # ── 2. Discover static scenes ──
    static_scenes = []
    if len(rel_parts) >= 3 and rel_parts[0] == 'levels':
        # Convention A: variant-specific
        for variant in scene_variants:
            candidate = os.path.join(unpack_root, 'mapskit', 'maps',
                                     rel_parts[1], rel_parts[2], variant['name'])
            if os.path.isdir(candidate):
                msh_count = _count_msh_files(candidate)
                if msh_count > 0:
                    # Check if already in list
                    already = any(s['path'] == candidate for s in static_scenes)
                    if not already:
                        static_scenes.append({
                            "path": candidate,
                            "msh_count": msh_count,
                            "shared": False,
                            "variant_name": variant['name'],
                        })

        # Convention B: faction-shared (parent directory)
        fallback = os.path.join(unpack_root, 'mapskit', 'maps',
                                rel_parts[1], rel_parts[2])
        if os.path.isdir(fallback):
            msh_count = _count_msh_files(fallback)
            if msh_count > 0:
                # Only add if not already covered by Convention A
                already_covered = any(
                    os.path.commonpath([s['path'], fallback]) == fallback
                    for s in static_scenes
                )
                if not already_covered:
                    static_scenes.append({
                        "path": fallback,
                        "msh_count": msh_count,
                        "shared": len(scene_variants) > 1,
                        "variant_name": None,
                    })

    # ── 3. Discover orphan models ──
    orphan_models = []
    for ss in static_scenes:
        ss_dir = ss['path']
        # Models in /models/ subdirectory
        models_dir = os.path.join(ss_dir, 'models')
        if os.path.isdir(models_dir):
            for entry in sorted(os.listdir(models_dir)):
                entry_path = os.path.join(models_dir, entry)
                if os.path.isdir(entry_path):
                    msh_count = len(glob.glob(os.path.join(
                        entry_path, "*.mdl-msh*")))
                    if msh_count > 0:
                        # Check if any scene variant references this model
                        entity_covered = False
                        for variant in scene_variants:
                            if variant['name'] == entry:
                                entity_covered = True
                                break
                        if not entity_covered:
                            orphan_models.append({
                                "name": entry,
                                "path": entry_path,
                                "msh_count": msh_count,
                            })
                elif entry.endswith('.mdl-msh0') or '.mdl-msh' in entry:
                    # Single-file orphan model
                    orphan_models.append({
                        "name": os.path.splitext(
                            os.path.splitext(entry)[0])[0].replace('.mdl-msh', ''),
                        "path": entry_path,
                        "msh_count": 1,
                    })

    # Deduplicate orphan models
    seen = set()
    unique_orphans = []
    for om in orphan_models:
        if om['name'] not in seen:
            seen.add(om['name'])
            unique_orphans.append(om)

    return {
        "area_name": area_name,
        "area_path": area_path,
        "static_scenes": static_scenes,
        "scene_variants": scene_variants,
        "orphan_models": unique_orphans,
    }


def _count_msh_files(directory: str) -> int:
    """Count .mdl-msh* files recursively in a directory."""
    return len(glob.glob(os.path.join(directory, "**/*.mdl-msh*"), recursive=True))
