# ============================================================================
# Def Resolver — Extract Def→Model mappings from decompiled Lua sources
# ============================================================================
"""Resolve Star Conflict Def entity names to model paths.

Uses gamedata_decompiled/def/objects/*.lua (plain text, no bytecode) to
build an exact Def→Model mapping by parsing Lua table definitions:

    Def.SomeEntity = {
        model = "path/to/model",
        ...
    }

When decompiled sources are unavailable, falls back to file-system search
in the unpack root, matching MSH file basenames against Def name segments.

Usage:
    resolver = DefResolver()
    resolver.build_map(decompiled_dir="/path/to/gamedata_decompiled/def/objects",
                        unpack_root="/path/to/unpack")
    model_path = resolver.resolve("VitalPoint_Beacon1_RC")
"""

import os
import re
import glob
from typing import Optional, List


# ============================================================================
# Regex for decompiled Lua parsing
# ============================================================================

# Match "Def.SomeName = {" — captures the Def name
_RE_DEF_HEADER = re.compile(r'^Def\.(\w+)\s*=\s*\{')

# Match model = "path" — captures model path
_RE_MODEL = re.compile(r'^\s*model\s*=\s*"([^"]*)"')

# Match inherit = "ParentName" — captures parent Def name
_RE_INHERIT = re.compile(r'^\s*inherit\s*=\s*"([^"]*)"')

# Match gameplay_idx = <number> — captures the index value
_RE_GAMEPLAY_IDX = re.compile(r'^\s*gameplay_idx\s*=\s*(\d+)')

# Suffixes to strip during resolve() fallback
_RESOLVE_SUFFIXES = ['_rc', '_king', '_ss', '_tdm', '_pve', '_pvp',
                      '_king_easy', '_king_hard', '_king_normal',
                      '_group1', '_group2', '_group3', '_group4']


# ============================================================================
# Def Resolver
# ============================================================================

class DefResolver:
    """Resolver that maps Def entity names to model paths.

    Uses decompiled Lua text (preferred) or file-system search to build
    the mapping. The mapping is a dict: {lowercase_def_name: model_path}.
    """

    def __init__(self):
        """Initialise an empty DefResolver."""
        self._mapping: dict = {}            # {lowercase_def_name: model_path}
        self._inherit_map: dict = {}        # {lowercase_def_name: lowercase_parent_name}
        self._child_map: dict = {}          # {lowercase_parent_name: [lowercase_child_names]}
        self._gameplay_idx_map: dict = {}   # {lowercase_def_name: gameplay_idx}
        self._parent_gp_children: dict = {} # {lowercase_parent: {gameplay_idx: (child_def, model_path)}}
        self._def_segments: dict = {}       # {segment: [full_def_names]} for fuzzy search
        self._unpack_root: str = ""
        self._msh_index: dict = {}          # {keyword: [(path, basename)]}
        self._msh_index_built: bool = False

    # ------------------------------------------------------------------
    # Map building — decompiled Lua (primary)
    # ------------------------------------------------------------------

    def build_map(self, gamedata_def_dir: str,
                  decompiled_dir: str = "",
                  unpack_root: str = "") -> int:
        """Build Def→Model mapping from Lua definition files.

        Priority:
          1. gamedata_decompiled/def/objects/*.lua (plain text, exact parsing)
          2. Pre-index MSH files for fast file-system fallback lookup
          3. Fallback: file-system search in unpack_root

        Args:
            gamedata_def_dir: Path to gamedata/def/objects/ (legacy, unused).
            decompiled_dir: Path to gamedata_decompiled/def/objects/ (preferred).
            unpack_root: Root directory for file-system fallback search.

        Returns:
            Number of Def→Model mappings built.
        """
        self._unpack_root = unpack_root
        count = 0

        # ── Strategy 1: decompiled Lua text ──
        if decompiled_dir and os.path.isdir(decompiled_dir):
            count = self._build_from_decompiled(decompiled_dir)
            print(f"[DefResolver] Decompiled Lua: {count} Def→Model mappings built")
            if count == 0:
                print(f"[DefResolver] WARNING: 0 mappings from decompiled Lua (dir={decompiled_dir})")

        # ── Strategy 2: pre-index MSH files for fast lookup ──
        if unpack_root and os.path.isdir(unpack_root):
            self._build_msh_index(unpack_root)

        return count

    def _build_msh_index(self, unpack_root: str):
        """Pre-index .mdl-msh* files for fast keyword lookup.

        Stores both the directory path and the MSH basename (before .mdl-msh)
        so that scoring can match against actual filenames, not just directories.
        """
        if self._msh_index_built:
            return

        msh_files = []
        for search_dir in ['models', 'mapskit']:
            d = os.path.join(unpack_root, search_dir)
            if os.path.isdir(d):
                msh_files.extend(glob.glob(os.path.join(d, '**/*.mdl-msh*'), recursive=True))

        for mf in msh_files:
            basename = os.path.basename(mf)
            base = basename.split('.mdl-msh')[0].lower()

            # Relative directory path (model_path for _find_msh_files)
            dir_path = os.path.dirname(mf)
            try:
                rel = os.path.relpath(dir_path, unpack_root).replace('\\', '/')
            except ValueError:
                rel = dir_path

            # Index by each underscore-separated segment from the MSH basename
            for seg in base.split('_'):
                if len(seg) >= 2:
                    if seg not in self._msh_index:
                        self._msh_index[seg] = []
                    # Store (path, basename) so scoring can use basename
                    entry = (rel, base)
                    if entry not in self._msh_index[seg]:
                        self._msh_index[seg].append(entry)

        self._msh_index_built = True
        if msh_files:
            print(f"[DefResolver] Indexed {len(msh_files)} MSH files for fast lookup")

    def _build_from_decompiled(self, decompiled_dir: str) -> int:
        """Parse decompiled .lua files for Def→Model mappings.

        Parses Lua table blocks:
            Def.EntityName = {
                model = "path/to/model",
                ...
            }

        Tracks brace depth to correctly associate model properties with
        their enclosing Def blocks. This avoids the proximity-guessing
        problems of the old bytecode-based approach.

        Also captures inherit = "ParentName" relationships and resolves
        the inheritance chain so that Def entries without an explicit
        model inherit from their parent Def's model.
        """
        # First pass: collect raw mappings + inherit relationships
        count = 0
        raw_inherit = {}  # {lower_def: lower_parent}
        inherit_defs = set()  # defs that have inherit (regardless of model)
        lua_files = sorted(glob.glob(os.path.join(decompiled_dir, "*.lua")))

        for fpath in lua_files:
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
            except OSError:
                continue

            current_def = None
            brace_depth = 0
            in_def_block = False
            current_has_model = False
            current_gameplay_idx = None

            for line in lines:
                # Count braces on this line
                open_braces = line.count('{')
                close_braces = line.count('}')
                brace_depth += open_braces - close_braces

                # Clamp negative depth to 0 to prevent accumulation errors
                if brace_depth < 0:
                    brace_depth = 0

                # Check for Def header
                if not in_def_block:
                    m = _RE_DEF_HEADER.match(line.strip())
                    if m:
                        current_def = m.group(1)
                        in_def_block = True
                        current_has_model = False
                        current_gameplay_idx = None
                        if brace_depth <= 0:
                            in_def_block = False
                            current_def = None
                    continue

                # Inside a Def block — look for model property
                if in_def_block and current_def:
                    m = _RE_MODEL.match(line.strip())
                    if m:
                        model_path = m.group(1)
                        key = current_def.lower()
                        self._mapping[key] = model_path
                        count += 1
                        current_has_model = True
                        self._index_segments(current_def, model_path)
                    else:
                        # Check for inherit property
                        im = _RE_INHERIT.match(line.strip())
                        if im:
                            parent = im.group(1)
                            raw_inherit[current_def.lower()] = parent.lower()
                            inherit_defs.add(current_def.lower())
                        else:
                            # Check for gameplay_idx
                            gm = _RE_GAMEPLAY_IDX.match(line.strip())
                            if gm:
                                current_gameplay_idx = int(gm.group(1))
                                self._gameplay_idx_map[current_def.lower()] = current_gameplay_idx

                # Check if block ended
                if in_def_block and brace_depth <= 0:
                    in_def_block = False
                    current_def = None
                    current_gameplay_idx = None

        # ── Second pass: resolve inheritance chain ──
        # For defs that have inherit but NO explicit model,
        # walk up the chain to find a model from an ancestor.
        resolved_count = 0
        for child_key in sorted(inherit_defs, key=len, reverse=True):
            if child_key in self._mapping:
                continue  # Already has explicit model
            chain = [child_key]
            parent = raw_inherit.get(child_key)
            while parent and parent not in self._mapping:
                if parent in chain:
                    break  # Circular inheritance
                chain.append(parent)
                parent = raw_inherit.get(parent)
            if parent and parent in self._mapping:
                self._mapping[child_key] = self._mapping[parent]
                resolved_count += 1

        # ── Build child_map for downward inheritance ──
        for child_key, parent_key in raw_inherit.items():
            if parent_key not in self._child_map:
                self._child_map[parent_key] = []
            self._child_map[parent_key].append(child_key)

        # ── Build inherit_map (direct parent lookup) ──
        self._inherit_map = raw_inherit

        # ── Build parent → gameplay_idx children mapping ──
        # For parents whose children have gameplay_idx and (optionally)
        # different models, store {gameplay_idx: (child_name, model_path)}.
        gp_count = 0
        for child_key, parent_key in raw_inherit.items():
            gp = self._gameplay_idx_map.get(child_key)
            if gp is None:
                continue
            if parent_key not in self._parent_gp_children:
                self._parent_gp_children[parent_key] = {}
            model = self._mapping.get(child_key, self._mapping.get(parent_key, ""))
            self._parent_gp_children[parent_key][gp] = (child_key, model)
            gp_count += 1

        print(f"[DefResolver] Decompiled Lua: {count} direct + {resolved_count} inherited "
              f"Def→Model mappings built"
              f"{f', {gp_count} gameplay_idx children' if gp_count > 0 else ''}")
        return count + resolved_count

    def _index_segments(self, def_name: str, model_path: str):
        """Index a Def name by its underscore-separated segments.

        For fuzzy fallback: if exact match fails, we can search the index
        for Def names containing certain keywords.
        """
        segments = def_name.lower().split('_')
        for seg in segments:
            if len(seg) >= 3:
                if seg not in self._def_segments:
                    self._def_segments[seg] = []
                self._def_segments[seg].append(def_name)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, def_type: str,
                unpack_root: str = "",
                scene_level_dir: str = "") -> Optional[str]:
        """Resolve a Def entity name to a model path.

        Resolution strategies (tried in order):
          1. Exact case-insensitive match from decompiled mapping,
             with downward inheritance check (children override parent).
          2. Strip known suffixes (_RC, _King, etc.) and retry.
          3. Strip trailing digit sequences.
          4. Segment-based fuzzy lookup (via pre-built index).
          5. File-system search: glob for .mdl-msh* matching Def name segments.

        Downward inheritance: when a base Def (e.g. ClanShip_BaseGen) has
        its own explicit model but also has children with DIFFERENT models,
        the children's model is preferred when a clear majority exists.
        """
        if not def_type:
            return None

        # ── Strategy 1: exact match ──
        key = def_type.lower()
        path = self._mapping.get(key)
        if path:
            return path

        # ── Strategy 1b: downward inheritance for abstract defs ──
        # If the requested Def is NOT in the mapping but its children are,
        # use the first child's model.
        children = self._child_map.get(key, [])
        if children:
            # Collect unique child models
            child_models = {}
            for child_key in sorted(children):
                child_path = self._mapping.get(child_key)
                if child_path:
                    child_models[child_path] = child_models.get(child_path, 0) + 1
            if len(child_models) == 1:
                # All children share the same model → use it
                return next(iter(child_models))
            elif child_models:
                # Multiple models → use the most common one
                best_model = max(child_models, key=child_models.get)
                best_count = child_models[best_model]
                total = sum(child_models.values())
                if best_count > total / 2:
                    return best_model
                # If tied, first child's model wins
                first_child = sorted(children)[0]
                return self._mapping.get(first_child)

        # ── Strategy 2: strip known suffixes ──
        for suffix in sorted(_RESOLVE_SUFFIXES, key=len, reverse=True):
            if key.endswith(suffix):
                stripped = key[:-len(suffix)]
                path = self._mapping.get(stripped)
                if path:
                    return path
                # Also strip trailing digit after suffix
                stripped2 = stripped.rstrip('0123456789')
                if stripped2 != stripped:
                    path = self._mapping.get(stripped2)
                    if path:
                        return path

        # ── Strategy 3: strip trailing digits ──
        stripped_digits = key.rstrip('0123456789')
        if stripped_digits != key:
            path = self._mapping.get(stripped_digits)
            if path:
                return path

        # ── Strategy 4: segment-based fuzzy lookup ──
        # Search the pre-built segment index for def names containing
        # unique keywords from the query. Require at least 2 matching
        # segments for confidence.
        segments = key.split('_')
        candidates = {}
        for seg in segments:
            if len(seg) >= 3 and seg in self._def_segments:
                for def_name in self._def_segments[seg]:
                    candidates[def_name] = candidates.get(def_name, 0) + 1

        # Only return if exactly ONE candidate matches 2+ segments
        best = None
        for def_name, score in candidates.items():
            if score >= 2:
                if best is not None:
                    return None  # ambiguous — multiple candidates
                best = def_name

        if best:
            path = self._mapping.get(best.lower())
            if path:
                return path

        # ── Strategy 5: file-system glob search ──
        # Search for .mdl-msh* files whose basename contains Def name segments.
        # This is O(n) but user accepts the performance cost.
        root = unpack_root or self._unpack_root
        if root and os.path.isdir(root):
            path = self._filesystem_search(def_type, root, scene_level_dir)
            if path:
                return path

        return None

    def _filesystem_search(self, def_type: str, unpack_root: str,
                           scene_level_dir: str = "") -> Optional[str]:
        """Search the filesystem for MSH files matching a Def name.

        Uses the pre-built MSH index for fast lookup (O(segments * index_size)).
        Falls back to glob for targeted scene-level search.
        """
        segments = def_type.lower().split('_')
        if not segments:
            return None

        # ── Use pre-built MSH index ──
        if self._msh_index:
            # Collect all candidate (path, basename) entries that match any segment
            scored = {}  # {path: (score, basename)}
            for seg in segments:
                if len(seg) < 2:
                    continue
                if seg in self._msh_index:
                    for path, base in self._msh_index[seg]:
                        # Score: number of Def segments found in the MSH BASENAME
                        s = sum(1 for s in segments if s in base)
                        if path not in scored or s > scored[path][0]:
                            scored[path] = (s, base)

            # Require at least 2 matching segments in the basename for confidence
            if scored:
                best_score = max(v[0] for v in scored.values())
                if best_score >= 2:
                    for path, (score, base) in scored.items():
                        if score == best_score:
                            return path

            # Try composite segment matching (last 2-3 segments joined)
            for n in [2, 3]:
                if len(segments) >= n:
                    tail = '_'.join(segments[-n:])
                    if tail in self._msh_index and self._msh_index[tail]:
                        return self._msh_index[tail][0]

        # ── Targeted scene-level search ──
        if scene_level_dir and os.path.isdir(scene_level_dir):
            pattern = os.path.join(scene_level_dir, "**/*.mdl-msh*")
            msh_files = glob.glob(pattern, recursive=True)
            if msh_files:
                tail = '_'.join(segments[-2:])
                for mf in msh_files:
                    basename = os.path.basename(mf)
                    base = basename.split('.mdl-msh')[0].lower()
                    if tail in base:
                        return self._extract_model_path(mf, unpack_root)

        # ── Last resort: glob search in models/ ──
        models_dir = os.path.join(unpack_root, 'models')
        if os.path.isdir(models_dir):
            for seg in reversed(segments):
                if len(seg) < 3:
                    continue
                pattern = os.path.join(models_dir, '**', seg, '*.mdl-msh*')
                msh_files = glob.glob(pattern, recursive=True)
                if msh_files:
                    return self._extract_model_path(msh_files[0], unpack_root)

        return None

    # ------------------------------------------------------------------
    # Gameplay index resolution
    # ------------------------------------------------------------------

    def has_gameplay_idx_children(self, parent_def: str) -> bool:
        """Check whether a parent Def has children with gameplay_idx."""
        return parent_def.lower() in self._parent_gp_children

    def resolve_child_by_index(self, parent_def: str, index: int) -> Optional[str]:
        """Resolve a parent Def to a child's model path via gameplay_idx.

        When scene.xml entities use a base Def (e.g. ClanShip_BaseGen) but
        the entity name encodes a sub-type slot (e.g. main_1 → gameplay_idx 0),
        this method maps the index to the correct child's model.

        Args:
            parent_def: The base Def name from scene.xml.
            index: Zero-based gameplay index (e.g. from main_N → N-1).

        Returns:
            Model path for the matching child, or None if no match.
        """
        children = self._parent_gp_children.get(parent_def.lower())
        if not children:
            return None
        result = children.get(index)
        if result:
            child_name, model_path = result
            return model_path
        return None

    def _extract_model_path(self, msh_filepath: str, unpack_root: str) -> str:
        """Extract the model directory path (for _find_msh_files lookup).

        Given a full .mdl-msh* path, return the parent directory relative
        to unpack_root, which is what _find_msh_files expects as model_path.
        """
        dir_path = os.path.dirname(msh_filepath)
        try:
            rel = os.path.relpath(dir_path, unpack_root)
            return rel.replace('\\', '/')
        except ValueError:
            return dir_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def mapping_count(self) -> int:
        return len(self._mapping)

    def get_mapping_info(self) -> dict:
        """Return statistics about the mapping."""
        return {
            "total": len(self._mapping),
            "segments": len(self._def_segments),
        }
