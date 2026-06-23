# ============================================================================
# MDF Material Definition File Parser
# ============================================================================
"""Parse Hammer Engine .mdf material definition files.

MDF format is a C-like text structure:
    material <shader_type>
    {
        SamplerType "relative\path\to\texture"
        UserParamN_Float4 ( x y z w )
        InfluenceBones N
        pins { ... }
    }

Each file may contain multiple material blocks.
"""

import re
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MaterialBlock:
    """A single material definition from an MDF file."""
    shader_type: str
    samplers: dict = field(default_factory=dict)     # {"DiffuseSampler": "path"}
    params: dict = field(default_factory=dict)        # {"UserParam2_Float4": "(1,1,0,0)"}
    pins: dict = field(default_factory=dict)           # {"User1": 1}
    influence_bones: Optional[int] = None


# Regex patterns
_RE_MATERIAL = re.compile(r'^\s*material\s+(\w+)', re.IGNORECASE)
_RE_SAMPLER = re.compile(r'^\s*(\w+Sampler)\s+"([^"]*)"', re.IGNORECASE)
_RE_PARAM = re.compile(r'^\s*(UserParam\d+_(?:Float4?|Int))\s+(\([^)]*\))', re.IGNORECASE)
_RE_PIN = re.compile(r'^\s*(\w+)\s+(-?\d+(?:\.\d+)?)', re.IGNORECASE)
_RE_INFLUENCE = re.compile(r'^\s*InfluenceBones\s+(\d+)', re.IGNORECASE)
_RE_BLOCK_OPEN = re.compile(r'\{')
_RE_BLOCK_CLOSE = re.compile(r'\}')


def _strip_comment(line):
    """Remove // comments from a line."""
    idx = line.find('//')
    if idx >= 0:
        return line[:idx]
    return line


def parse_mdf(filepath):
    """Parse an MDF file and return a list of MaterialBlock objects.

    Args:
        filepath: Path to the .mdf file.

    Returns:
        list[MaterialBlock]: Parsed material definitions.

    Raises:
        FileNotFoundError: If filepath does not exist.
        ValueError: If the file has malformed syntax.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"MDF file not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    blocks = []
    current_block = None
    in_pins = False
    brace_depth = 0

    for raw_line in lines:
        line = _strip_comment(raw_line).strip()
        if not line:
            continue

        # Check for opening brace
        if '{' in line:
            brace_depth += line.count('{')
            if current_block is None:
                # This brace belongs to the material block
                pass
            elif not in_pins and 'pins' in line.lower():
                in_pins = True
            continue

        # Check for closing brace
        if '}' in line:
            brace_depth -= line.count('}')
            if in_pins and brace_depth <= 1:
                in_pins = False
            if brace_depth <= 0 and current_block is not None:
                blocks.append(current_block)
                current_block = None
                brace_depth = 0
            continue

        # Try to match a new material block
        mat_match = _RE_MATERIAL.match(line)
        if mat_match:
            current_block = MaterialBlock(shader_type=mat_match.group(1))
            brace_depth = 0
            in_pins = False
            continue

        if current_block is None:
            continue

        # Inside a material block

        # InfluenceBones
        inf_match = _RE_INFLUENCE.match(line)
        if inf_match:
            current_block.influence_bones = int(inf_match.group(1))
            continue

        # Inside pins section
        if in_pins:
            pin_match = _RE_PIN.match(line)
            if pin_match:
                current_block.pins[pin_match.group(1)] = float(pin_match.group(2))
            continue

        # Sampler
        samp_match = _RE_SAMPLER.match(line)
        if samp_match:
            current_block.samplers[samp_match.group(1)] = samp_match.group(2)
            continue

        # Parameter
        param_match = _RE_PARAM.match(line)
        if param_match:
            current_block.params[param_match.group(1)] = param_match.group(2)
            continue

        # Check for 'pins' keyword alone
        if line.strip().lower() == 'pins':
            continue

    # If file ended with unclosed block, still add it
    if current_block is not None:
        blocks.append(current_block)

    return blocks


def extract_texture_basename(sampler_path):
    """Extract the texture base name from a sampler path.

    Removes the directory prefix and returns just the filename portion.
    e.g. "models\\weapons\\plasma_gun\\plasma_gun_d" -> "plasma_gun_d"

    Args:
        sampler_path: The path string from the sampler reference.

    Returns:
        str: The base filename without extension.
    """
    normalized = sampler_path.replace('\\', '/')
    return os.path.basename(normalized)


def extract_asset_basename(mdf_path):
    """Extract the asset base name from an MDF file path.

    If the MDF name contains '_modN', strips that suffix to get the
    shared texture base name.
    e.g. "plasma_gun_mod1.mdf" -> "plasma_gun"

    Args:
        mdf_path: Path to the .mdf file.

    Returns:
        str: The asset base name used for texture lookup.
    """
    name = os.path.splitext(os.path.basename(mdf_path))[0]
    # Strip _mod<N> suffix if present
    mod_match = re.match(r'^(.+)_mod\d+$', name)
    if mod_match:
        return mod_match.group(1)
    return name
