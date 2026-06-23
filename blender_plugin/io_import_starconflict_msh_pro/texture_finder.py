# ============================================================================
# Texture Finder — Multi-directory texture search engine
# ============================================================================
"""Search for texture files across multiple directories based on MDF sampler paths.

The engine handles:
  - Multiple search directories (recursive or flat)
  - Multiple file extensions (.dds, .png, .tga)
  - Path normalization (MDF uses backslashes, filesystem may use either)
  - Result caching for performance
  - Partial path matching (trying subdirectory structure)
"""

import os
import re
from functools import lru_cache


# Max cache size to prevent memory issues with large projects
_MAX_CACHE_SIZE = 4096


def _normalize_path(path):
    """Normalize path separators to forward slashes for consistent comparison."""
    return path.replace('\\', '/')


def _get_search_extensions(ext_string):
    """Parse comma-separated extension string into a list.

    Args:
        ext_string: e.g. ".dds,.png,.tga"

    Returns:
        list[str]: e.g. [".dds", ".png", ".tga"]
    """
    exts = []
    for ext in ext_string.split(','):
        ext = ext.strip()
        if ext and not ext.startswith('.'):
            ext = '.' + ext
        if ext:
            exts.append(ext.lower())
    return exts


def _build_file_index(search_dirs, extensions):
    """Build an in-memory index of all texture files in search directories.

    Returns a dict mapping lowercase basename (without extension) to full path.

    Args:
        search_dirs: List of directory paths to search.
        extensions: List of extensions to match (e.g. ['.dds', '.png']).

    Returns:
        dict: {basename_lower: full_path}
    """
    index = {}
    for search_dir in search_dirs:
        if not os.path.isdir(search_dir):
            continue
        for root, dirs, filenames in os.walk(search_dir):
            for fname in filenames:
                name, ext = os.path.splitext(fname)
                if ext.lower() in extensions:
                    key = name.lower()
                    # First found wins (search_dirs are priority-ordered)
                    if key not in index:
                        index[key] = os.path.join(root, fname)
    return index


# Global cache: {frozenset(search_dirs): file_index}
_dir_index_cache = {}


def get_or_build_index(search_dirs, extensions):
    """Get a cached file index or build a new one.

    Uses frozenset of normalized search dirs as cache key.
    """
    norm_dirs = frozenset(_normalize_path(d) for d in search_dirs)
    cache_key = (norm_dirs, tuple(sorted(extensions)))
    if cache_key not in _dir_index_cache:
        _dir_index_cache.clear()  # keep only latest
        _dir_index_cache[cache_key] = _build_file_index(search_dirs, extensions)
    return _dir_index_cache[cache_key]


def find_texture_by_path(sampler_path, search_dirs, extensions=None):
    """Find a texture file using the sampler path from an MDF.

    Strategies (tried in order):
      1. Direct basename match: extract filename from sampler path,
         search in file index.
      2. Subdirectory match: try the sampler path relative to each
         search dir (preserving directory structure).
      3. Fallback: try common path variations.

    Args:
        sampler_path: The path string from MDF sampler reference
                      (e.g. "models\\weapons\\plasma_gun\\plasma_gun_d").
        search_dirs: List of directory paths to search.
        extensions: List of extensions to try. Defaults to ['.dds', '.png', '.tga'].

    Returns:
        str or None: Full path to the texture file, or None if not found.
    """
    if extensions is None:
        extensions = ['.dds', '.png', '.tga']

    normalized = _normalize_path(sampler_path)
    basename = os.path.basename(normalized)

    # Strategy 1: Build index and lookup by basename
    file_index = get_or_build_index(search_dirs, extensions)
    key = basename.lower()
    if key in file_index:
        return file_index[key]

    # Strategy 2: Try the relative path under each search dir
    # sampler_path might be like "models/weapons/plasma_gun/plasma_gun_d"
    rel_path = normalized
    for search_dir in search_dirs:
        for ext in extensions:
            full = os.path.join(search_dir, rel_path + ext)
            full_norm = os.path.normpath(full)
            if os.path.isfile(full_norm):
                return full_norm

    # Strategy 3: Try without extension (some tools output .dds without ext)
    for search_dir in search_dirs:
        full = os.path.join(search_dir, rel_path)
        if os.path.isfile(full):
            return full

    return None


def find_textures_for_material(material_block, search_dirs, extensions=None):
    """Find all texture files referenced by a MaterialBlock.

    Args:
        material_block: MaterialBlock from mdf_parser.
        search_dirs: List of directory paths.
        extensions: List of extensions to try.

    Returns:
        dict: {sampler_name: full_texture_path_or_None}
    """
    result = {}
    for sampler_name, sampler_path in material_block.samplers.items():
        result[sampler_name] = find_texture_by_path(
            sampler_path, search_dirs, extensions
        )
    return result


def clear_cache():
    """Clear the file index cache (call when search paths change)."""
    _dir_index_cache.clear()
