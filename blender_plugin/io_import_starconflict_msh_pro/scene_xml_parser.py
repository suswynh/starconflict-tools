# ============================================================================
# Scene XML Parser — Star Conflict level description file parser
# ============================================================================
"""Parse Star Conflict levels/*/scene.xml files.

Extracts:
  - Entity instances with world-space transforms (Pos + Rot quaternion)
  - External Model references (cross-directory model paths)
  - Inheritance chain (sub-scene references)

Coordinate system notes:
  - Hammer Engine: Y-up
  - Blender: Z-up
  - Transform conversion handled by level_assembler, not here.
    Parser returns raw data as-is from XML.

Quaternion format:
  - XML: "x y z w" (string)
  - Blender: (w, x, y, z) tuple
"""

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class EntityInstance:
    """A single entity instance from scene.xml."""
    name: str                    # Entity Name attribute
    def_type: str                # Def attribute (e.g. "ModelEntity")
    pos: Tuple[float, float, float]  # World position (x, y, z)
    rot: Tuple[float, float, float, float]  # Quaternion (x, y, z, w) from XML
    model_path: str = ""         # Model="..." attribute (empty if no model)
    extra_attrs: dict = field(default_factory=dict)  # All other XML attributes

    @property
    def has_model(self) -> bool:
        """Whether this entity references an external model file."""
        return bool(self.model_path)

    @property
    def blender_quaternion(self) -> Tuple[float, float, float, float]:
        """Return quaternion in Blender format (w, x, y, z)."""
        x, y, z, w = self.rot
        return (w, x, y, z)


@dataclass
class SceneXML:
    """Parsed scene.xml content."""
    filepath: str                         # Absolute path to the scene.xml
    env_settings: dict = field(default_factory=dict)
    inheritance: List[str] = field(default_factory=list)  # Sub-scene paths (relative)
    entities: List[EntityInstance] = field(default_factory=list)

    @property
    def model_entities(self) -> List[EntityInstance]:
        """Return only entities that reference external models."""
        return [e for e in self.entities if e.has_model]


# ============================================================================
# Parser
# ============================================================================

def parse_scene_xml(filepath: str) -> SceneXML:
    """Parse a Star Conflict levels/*/scene.xml file.

    Args:
        filepath: Absolute path to scene.xml.

    Returns:
        SceneXML with parsed entities, inheritance, and env settings.

    Raises:
        FileNotFoundError: If filepath does not exist.
        ET.ParseError: If XML is malformed.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"scene.xml not found: {filepath}")

    tree = ET.parse(filepath)
    root = tree.getroot()

    scene = SceneXML(filepath=os.path.abspath(filepath))

    # ── EnvSettings ──
    env_node = root.find("EnvSettings")
    if env_node is not None:
        scene.env_settings = dict(env_node.attrib)

    # ── Inheritance chain ──
    inheritance_node = root.find("Inheritance")
    if inheritance_node is not None:
        for child in inheritance_node.findall("Scene"):
            sub_path = child.get("Name", "")
            if sub_path:
                scene.inheritance.append(sub_path)

    # ── EntityContainer ──
    container = root.find("EntityContainer")
    if container is None:
        return scene

    for entity_node in container.findall("Entity"):
        name = entity_node.get("Name", "")
        def_type = entity_node.get("Def", "")

        # Parse position
        pos_str = entity_node.get("Pos", "0 0 0")
        pos_parts = pos_str.strip().split()
        pos = (
            float(pos_parts[0]) if len(pos_parts) > 0 else 0.0,
            float(pos_parts[1]) if len(pos_parts) > 1 else 0.0,
            float(pos_parts[2]) if len(pos_parts) > 2 else 0.0,
        )

        # Parse rotation quaternion (default: identity)
        rot_str = entity_node.get("Rot", "0 0 0 1")
        rot_parts = rot_str.strip().split()
        rot = (
            float(rot_parts[0]) if len(rot_parts) > 0 else 0.0,
            float(rot_parts[1]) if len(rot_parts) > 1 else 0.0,
            float(rot_parts[2]) if len(rot_parts) > 2 else 0.0,
            float(rot_parts[3]) if len(rot_parts) > 3 else 1.0,
        )

        # Model reference (optional)
        model_path = entity_node.get("Model", "")

        # Extra attributes (everything else)
        extra = {}
        for key, val in entity_node.attrib.items():
            if key not in ("Name", "Def", "Pos", "Rot", "Model"):
                extra[key] = val

        entity = EntityInstance(
            name=name,
            def_type=def_type,
            pos=pos,
            rot=rot,
            model_path=model_path,
            extra_attrs=extra,
        )
        scene.entities.append(entity)

    return scene


# ============================================================================
# Utility: resolve inheritance chain
# ============================================================================

def resolve_inheritance_chain(scene: SceneXML, unpack_root: str,
                               max_depth: int = 5) -> List[SceneXML]:
    """Recursively resolve the inheritance chain of a scene.xml.

    Args:
        scene: The root scene (already parsed).
        unpack_root: Unpack root directory (e.g. /path/to/unpack/output).
        max_depth: Maximum recursion depth (safety limit).

    Returns:
        List of SceneXML in order: [root, child_1, child_2, ...]
    """
    chain = [scene]
    seen = {os.path.normpath(scene.filepath)}

    for sub_path in scene.inheritance:
        if len(chain) >= max_depth:
            break

        # sub_path is relative to unpack_root
        full_path = os.path.join(unpack_root, sub_path)
        full_path = os.path.normpath(full_path)

        if full_path in seen:
            continue
        seen.add(full_path)

        if os.path.isfile(full_path):
            child_scene = parse_scene_xml(full_path)
            chain.append(child_scene)

            # Recurse into child inheritance
            for sub in child_scene.inheritance:
                if sub not in scene.inheritance:
                    scene.inheritance.append(sub)
                    child_path = os.path.join(unpack_root, sub)
                    child_path = os.path.normpath(child_path)
                    if child_path not in seen:
                        seen.add(child_path)
                        if os.path.isfile(child_path):
                            chain.append(parse_scene_xml(child_path))

    return chain


def collect_all_model_entities(scene: SceneXML, unpack_root: str,
                                max_depth: int = 5) -> List[EntityInstance]:
    """Collect all ModelEntity instances from a scene and its inheritance chain.

    Args:
        scene: Root scene.
        unpack_root: Unpack root directory.
        max_depth: Max inheritance depth.

    Returns:
        Flat list of all EntityInstance objects that have Model references.
    """
    chain = resolve_inheritance_chain(scene, unpack_root, max_depth)
    entities = []
    for s in chain:
        entities.extend(s.model_entities)
    return entities
