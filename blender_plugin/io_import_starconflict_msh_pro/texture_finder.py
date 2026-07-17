# ============================================================================
# Texture Finder — Multi-directory texture search engine
# ============================================================================
"""Search for texture files across multiple directories based on MDF sampler paths.

The engine uses a three-tier progressive matching strategy:

  Tier 1 — Exact path concatenation:
    Directly join search_dir + sampler_path + extension. This covers the
    ideal case where the user preserved the original directory structure.

  Tier 2 — Suffix-progressive matching:
    Strip leading directory segments from sampler_path one at a time and
    walk search_dirs for matching path suffixes. Handles reorganized or
    flattened directory structures while still preferring structural matches.

  Tier 3 — Basename fallback with similarity scoring:
    Match by basename only. When multiple candidates exist, score them by
    path suffix similarity to the original MDF sampler_path and pick the best.

Key features:
  - Multiple search directories (recursive)
  - Multiple file extensions (.dds, .png, .tga)
  - Path normalization (MDF uses backslashes, filesystem may use either)
  - Result caching for performance
  - No false matches when same basename exists in multiple directories
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
    """Build an in-memory index: basename → list of candidate full paths.

    Unlike the previous version which stored only one path per basename
    ("first found wins"), this version stores ALL candidates so that
    similarity scoring can choose the best match later.

    Args:
        search_dirs: List of directory paths to search (order preserved).
        extensions: List of extensions to match (e.g. ['.dds', '.png']).

    Returns:
        dict: {basename_lower: [full_path, ...]}
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
                    full_path = os.path.join(root, fname)
                    if key not in index:
                        index[key] = []
                    # Avoid exact duplicates (same path appearing via different
                    # search_dirs or symlinks)
                    if full_path not in index[key]:
                        index[key].append(full_path)
    return index


# Global cache: preserves search_dir order via tuple
_dir_index_cache = {}


def get_or_build_index(search_dirs, extensions):
    """Get a cached file index or build a new one.

    Uses tuple of normalized dirs (order-preserving) + sorted extensions
    as cache key so directory priority is maintained.
    """
    dirs_tuple = tuple(_normalize_path(d) for d in search_dirs)
    cache_key = (dirs_tuple, tuple(sorted(extensions)))
    if cache_key not in _dir_index_cache:
        _dir_index_cache.clear()  # keep only latest
        _dir_index_cache[cache_key] = _build_file_index(search_dirs, extensions)
    return _dir_index_cache[cache_key]


# ──────────────────────────────────────────────────────────────
# Path similarity scoring
# ──────────────────────────────────────────────────────────────

def _score_path_similarity(mdf_path, candidate_full_path, search_dirs):
    """Score how well a candidate file path matches the MDF sampler path.

    Algorithm:
      1. Strip the search_dir prefix from the candidate to get a relative path.
      2. Split both the MDF path and candidate relative path into segments.
      3. Compare segments from the END (suffix matching), counting consecutive
         matches. Earlier directory mismatches are ignored.
      4. Additional bonus: if the MDF path is a suffix substring of the
         candidate relative path (e.g. ".../textures/asteroid_hole01_d.dds"
         contains the suffix "textures/asteroid_hole01_d"), score is higher.

    Returns:
        int: Similarity score (higher = better match). 0 = no structural match.
    """
    mdf_norm = _normalize_path(mdf_path)
    mdf_segments = [s.lower() for s in mdf_norm.split('/') if s]

    # Determine relative path of candidate
    candidate_norm = _normalize_path(candidate_full_path)
    # Strip extension for comparison
    candidate_noext = os.path.splitext(candidate_norm)[0]

    # Try stripping each search_dir prefix to get the relative path
    best_score = 0
    for sd in search_dirs:
        sd_norm = _normalize_path(sd)
        if candidate_noext.startswith(sd_norm + '/'):
            rel = candidate_noext[len(sd_norm) + 1:]
        elif candidate_noext.startswith(sd_norm):
            rel = candidate_noext[len(sd_norm):].lstrip('/')
        else:
            # Candidate not under this search_dir — use basename only
            rel = os.path.basename(candidate_noext)

        cand_segments = [s.lower() for s in rel.split('/') if s]

        # ── Suffix match count (from the end) ──
        suffix_match = 0
        m = len(mdf_segments)
        c = len(cand_segments)
        for i in range(1, min(m, c) + 1):
            if mdf_segments[-i] == cand_segments[-i]:
                suffix_match += 1
            else:
                break

        # ── Substring bonus: MDF suffix appears as substring in candidate ──
        substring_bonus = 0
        mdf_suffix = '/'.join(mdf_segments[-2:]) if len(mdf_segments) >= 2 else mdf_segments[-1]
        if mdf_suffix in '/'.join(cand_segments):
            substring_bonus = 10

        score = suffix_match * 100 + substring_bonus
        # Tiebreaker: when suffix-match is shallow (≤2 segments), slightly
        # prefer candidates closer to the search_dir root. This biases toward
        # "canonical" paths (e.g. textures/ vs models/energy_geiser/) when
        # only the basename matched.
        if suffix_match <= 2:
            score -= len(cand_segments) * 0.5
        if score > best_score:
            best_score = score

    return best_score


def _try_exact_path(sampler_path, search_dirs, extensions):
    """Tier 1: Exact path concatenation.

    Directly join search_dir + sampler_path + extension and check existence.
    This is O(1) per directory and handles the best-case scenario where
    the user preserved the original directory structure.

    Returns:
        str or None: Full path if found.
    """
    normalized = _normalize_path(sampler_path)
    for search_dir in search_dirs:
        for ext in extensions:
            full = os.path.join(search_dir, normalized + ext)
            full_norm = os.path.normpath(full)
            if os.path.isfile(full_norm):
                return full_norm
    return None


def _try_suffix_progressive(sampler_path, search_dirs, extensions):
    """Tier 2: Suffix-progressive matching.

    Strip leading directory segments from sampler_path one at a time,
    then search for path suffixes in search_dirs via os.walk.
    When multiple candidates are found for a suffix, the one with the
    highest similarity score is returned.

    Example:
        sampler_path = "mapskit/maps/textures/asteroid_hole01_d"
        suffixes tried (from most specific to least):
          0 strip: "mapskit/maps/textures/asteroid_hole01_d" (tier 1 already)
          1 strip: "maps/textures/asteroid_hole01_d"
          2 strip: "textures/asteroid_hole01_d"
          3 strip: "asteroid_hole01_d" → falls through to tier 3

    This handles scenarios where:
      - Intermediate directories were renamed or merged
      - User organized textures into a different folder hierarchy
      - Only the deepest directory names were preserved

    Returns:
        str or None: Best matching full path, or None if no suffix matched.
    """
    normalized = _normalize_path(sampler_path)

    # Build suffix list: progressively strip leading segments
    segments = [s for s in normalized.split('/') if s]
    if len(segments) <= 1:
        return None  # single segment → skip to tier 3

    # Try suffixes from specific to general (strip 1..n-1 leading segments)
    best_candidate = None
    best_score = -1.0

    for strip_count in range(1, len(segments)):
        suffix_segments = segments[strip_count:]
        suffix = '/'.join(suffix_segments)

        # Walk search_dirs looking for path suffix match
        for search_dir in search_dirs:
            if not os.path.isdir(search_dir):
                continue
            for root, dirs, filenames in os.walk(search_dir):
                for fname in filenames:
                    name, ext = os.path.splitext(fname)
                    if ext.lower() not in extensions:
                        continue
                    full_path = os.path.join(root, fname)
                    # Check if the full path ends with this suffix + extension
                    full_norm = _normalize_path(full_path)
                    suffix_with_ext = suffix + ext.lower()
                    if full_norm.endswith(suffix_with_ext) or full_norm.endswith(suffix):
                        # Found a suffix match — score it
                        score = _score_path_similarity(
                            sampler_path, full_path, search_dirs
                        )
                        # Bonus for longer suffix (more specific match)
                        score += strip_count * 5
                        if score > best_score:
                            best_score = score
                            best_candidate = full_path

    return best_candidate


def _try_basename_fallback(sampler_path, search_dirs, extensions):
    """Tier 3: Basename fallback with similarity scoring.

    Last-resort matching that only uses the filename (no directory info).
    When multiple candidates share the same basename, the one with the
    highest path similarity score is returned.

    This is the most expensive tier because it builds the index, but it
    handles the worst-case scenario where textures are dumped into a flat
    or arbitrarily-named directory structure.

    Returns:
        str or None: Best matching full path, or None.
    """
    normalized = _normalize_path(sampler_path)
    basename = os.path.basename(normalized)
    key = basename.lower()

    file_index = get_or_build_index(search_dirs, extensions)
    candidates = file_index.get(key, [])

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    # Multiple candidates — pick the best by similarity score
    best = None
    best_score = -1.0
    for cand in candidates:
        score = _score_path_similarity(sampler_path, cand, search_dirs)
        if score > best_score:
            best_score = score
            best = cand

    return best


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def find_texture_by_path(sampler_path, search_dirs, extensions=None):
    """Find a texture file using the sampler path from an MDF.

    Three-tier progressive matching (tried in order):

      Tier 1 — Exact path concatenation:
        Directly join search_dir + sampler_path + extension.
        Fastest (O(1) per dir), handles preserved directory structure.

      Tier 2 — Suffix-progressive matching:
        Strip leading segments and search for path suffixes.
        Handles reorganized/flattened directory structures.

      Tier 3 — Basename fallback with similarity scoring:
        Match by filename only. When multiple candidates exist,
        score by path similarity to choose the best match.
        Handles worst-case (all textures in a flat directory).

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

    # ── Tier 1: Exact path concatenation ──
    result = _try_exact_path(sampler_path, search_dirs, extensions)
    if result is not None:
        return result

    # ── Tier 2: Suffix-progressive matching ──
    result = _try_suffix_progressive(sampler_path, search_dirs, extensions)
    if result is not None:
        return result

    # ── Tier 3: Basename fallback with similarity scoring ──
    return _try_basename_fallback(sampler_path, search_dirs, extensions)


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
