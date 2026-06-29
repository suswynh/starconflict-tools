# ============================================================================
# Name Resolver — 重名冲突检测、前缀生成、Collection 组织
# ============================================================================
"""处理 MSH 导入时的命名冲突和 Blender 对象组织。

核心功能:
  1. 冲突检测：扫描待导入文件，找出同名 basename
  2. 前缀生成：为冲突文件从路径层级生成唯一前缀
  3. 名称截断：处理 Blender 63 字符对象名限制
  4. Collection 组织：按路径层级创建 Blender Collection

命名规则:
  - 无冲突 → 保留原始名
  - 有冲突 → 从路径中逐层添加目录名前缀，直到唯一
  - 超 63 字符 → 智能截断（优先保留文件名末尾 LOD 编号）
"""

import os
import re
from collections import defaultdict


# ============================================================================
# 常量
# ============================================================================

BLENDER_NAME_MAX = 63           # Blender 对象名最大长度
SAFE_NAME_MAX = 60              # 留 3 字符余量
LOD_SUFFIX_PATTERN = re.compile(r'(msh\d+)$', re.IGNORECASE)

# 跳过这些目录名（资源分类目录，不是组织单元）
SKIP_DIRS = {
    "models", "mapskit", "maps", "levels", "textures",
    "materials", "scripts", "gamedata", "ships", "objects",
    "weapons", "output", "scunpack", "data", "src",
}

# 可选简写映射（用户可配置，默认关闭）
DEFAULT_ABBREVIATIONS = {
    "empire":            "emp",
    "federation":        "fed",
    "jericho":           "jer",
    "precursor":         "prec",
    "dreadnoughtbattle": "dnbattle",
    "dreadnought":       "dred",
    "experimental":      "exp",
    "clanbigship":       "cbs",
    "allidium":          "ald",
    "pirate":            "prt",
}


# ============================================================================
# Name Resolver
# ============================================================================

class NameResolver:
    """MSH 文件命名冲突解析器。

    用法:
        resolver = NameResolver(common_root="/path/to/unpack/output")

        # Batch 模式：扫描全部文件
        resolver.scan(file_paths)

        # 对每个文件获取最终名称和 Collection 路径
        name = resolver.resolve_name(file_path)
        coll_path = resolver.get_collection_path(file_path)

        # 单文件模式：固定 N 层前缀
        name = resolver.resolve_single(file_path, prefix_depth=1)
    """

    def __init__(self, common_root=None, collection_depth=2,
                 use_abbreviations=False, abbreviations=None,
                 skip_dirs=None):
        """
        Args:
            common_root: 用户指定的根目录（用于计算相对路径）
            collection_depth: 建 Collection 的层级数（默认2）
            use_abbreviations: 是否启用简写
            abbreviations: 自定义简写映射（dict）
            skip_dirs: 跳过的目录名集合
        """
        self.common_root = common_root or ""
        self.collection_depth = collection_depth
        self.use_abbreviations = use_abbreviations
        self.abbreviations = abbreviations or DEFAULT_ABBREVIATIONS
        self.skip_dirs = skip_dirs or SKIP_DIRS

        # 扫描结果
        self._conflict_map = {}       # {basename: [full_path, ...]}
        self._resolved_names = {}     # {full_path: resolved_name}
        self._collection_paths = {}   # {full_path: [coll_name, ...]}
        self._all_paths = []

    # ── 扫描 ────────────────────────────────────────────────

    def scan(self, file_paths):
        """扫描所有待导入文件，检测冲突。

        Args:
            file_paths: list[str] 所有 MSH 文件路径
        """
        self._all_paths = list(file_paths)
        self._conflict_map.clear()
        self._resolved_names.clear()
        self._collection_paths.clear()

        # 提取 basename 分组
        by_basename = defaultdict(list)
        for fpath in file_paths:
            basename = self._extract_base_name(fpath)
            by_basename[basename].append(fpath)

        # 仅保留有冲突的（出现次数 > 1）
        for basename, paths in by_basename.items():
            if len(paths) > 1:
                self._conflict_map[basename] = paths

        # 为所有文件预计算解析名和 Collection 路径
        for fpath in file_paths:
            self._resolved_names[fpath] = self._resolve_name_internal(fpath)
            self._collection_paths[fpath] = self._build_collection_path(fpath)

    # ── 名称解析 ────────────────────────────────────────────

    def resolve_name(self, file_path):
        """获取文件的最终对象名。

        Args:
            file_path: MSH 文件完整路径

        Returns:
            str: Blender 对象名
        """
        if file_path in self._resolved_names:
            return self._resolved_names[file_path]
        return self._resolve_name_internal(file_path)

    def resolve_single(self, file_path, prefix_depth=1):
        """单文件导入模式：固定 N 层前缀。

        Args:
            file_path: MSH 文件完整路径
            prefix_depth: 添加几层目录前缀（默认1）

        Returns:
            str: Blender 对象名
        """
        dir_parts = self._get_relative_dir_parts(file_path)
        base_name = self._make_clean_name(file_path)

        # 取最近 prefix_depth 层有意义目录名
        meaningful = [p for p in dir_parts if p.lower() not in self.skip_dirs]
        prefix = meaningful[-prefix_depth:] if len(meaningful) >= prefix_depth else meaningful

        if prefix:
            return self._truncate_name("_".join(prefix + [base_name]))
        return base_name

    def _resolve_name_internal(self, file_path):
        """内部：计算解析名。"""
        base_name = self._make_clean_name(file_path)
        basename = self._extract_base_name(file_path)

        # 无冲突 → 直接返回（不改名）
        if basename not in self._conflict_map:
            return base_name

        # 有冲突 → 先检查 base_name（含 LOD 编号）是否已唯一
        # 例: r3_h_altair_000 vs r3_h_altair_001 本身已不同，无需前缀
        conflict_paths = self._conflict_map[basename]
        if self._is_unique_name_in_group(base_name, file_path, conflict_paths):
            return self._truncate_name(base_name)

        # 仍需前缀 → 从最近层开始，逐层添加目录前缀直到唯一
        dir_parts = self._get_relative_dir_parts(file_path)
        meaningful = [p for p in dir_parts if p.lower() not in self.skip_dirs]

        # 安全检查：meaningful 为空的边界情况
        if not meaningful:
            # 无有意义目录 → 用路径 hash 兜底
            import hashlib
            dir_hash = hashlib.md5(file_path.encode()).hexdigest()[:6]
            return self._truncate_name(f"x{dir_hash}_{base_name}")

        for depth in range(1, len(meaningful) + 1):
            prefix = meaningful[-depth:]
            candidate = self._build_candidate_name(prefix, base_name)

            # 检查在此冲突组中是否唯一
            if self._is_unique_in_group(candidate, file_path, conflict_paths, depth, meaningful):
                return self._truncate_name(candidate)

        # 极端情况：即使全部层级也不够 → 加目录 hash
        import hashlib
        dir_hash = hashlib.md5(file_path.encode()).hexdigest()[:4]
        return self._truncate_name(f"{meaningful[-1]}_{dir_hash}_{base_name}")

    def _build_candidate_name(self, prefix_parts, base_name):
        """构建候选名，避免前缀与文件名中的内容重复。

        例: 目录 jer + 文件名 jer_bs_beacon_000 → 不添加 jer 前缀
            目录 jer + 文件名 bs_beacon_000 → jer_bs_beacon_000
        """
        # 检查 base_name 是否已经以某个 prefix 开头
        for part in reversed(prefix_parts):
            if base_name.lower().startswith(part.lower() + '_'):
                # 文件名已有此前缀，跳过
                continue
            base_name = f"{part}_{base_name}"
        return base_name

    def _is_unique_name_in_group(self, name, my_path, conflict_paths):
        """检查 clean name（含 LOD 编号）在冲突组内是否唯一。

        用于避免对同目录 LOD 变体添加无谓目录前缀:
          r3_h_altair_000 vs r3_h_altair_001 → 已唯一，无需 r3_h_altair → 不加 h_ 前缀

        Args:
            name: 当前文件的 clean name（来自 _make_clean_name）
            my_path: 当前文件路径
            conflict_paths: 同 basename 的全部文件路径

        Returns:
            bool: True 如果 name 在组内唯一
        """
        for other_path in conflict_paths:
            if other_path == my_path:
                continue
            other_name = self._make_clean_name(other_path)
            if other_name.lower() == name.lower():
                return False
        return True

    def _is_unique_in_group(self, candidate, my_path, conflict_paths, depth, my_meaningful):
        """检查候选名在冲突组内是否唯一。"""
        for other_path in conflict_paths:
            if other_path == my_path:
                continue
            other_parts = [p for p in self._get_relative_dir_parts(other_path)
                          if p.lower() not in self.skip_dirs]
            other_prefix = other_parts[-depth:] if len(other_parts) >= depth else other_parts
            other_base = self._make_clean_name(other_path)
            other_candidate = "_".join(other_prefix + [other_base])
            if other_candidate.lower() == candidate.lower():
                return False
        return True

    # ── Collection ──────────────────────────────────────────

    def get_collection_path(self, file_path):
        """获取文件的 Collection 层级路径。

        Returns:
            list[str]: Collection 名列表（从根到叶），如 ["dreadnoughtbattle", "empire"]
        """
        if file_path in self._collection_paths:
            return self._collection_paths[file_path]
        return self._build_collection_path(file_path)

    def _build_collection_path(self, file_path):
        """构建 Collection 路径。

        collection_depth 语义:
          -  -1: 使用全部目录层级（完整镜像文件夹树，不跳过任何目录）
          -   0: 不使用 Collection（返回空列表）
          - N>0: 使用最近 N 层有意义目录（应用 skip_dirs，向后兼容）
        """
        if self.collection_depth == 0:
            return []

        dir_parts = self._get_relative_dir_parts(file_path)

        if self.collection_depth == -1:
            # 全层级模式：使用全部目录，不跳过任何层级
            coll_names = list(dir_parts)
        else:
            # 限定深度：跳过分类目录后取最近 N 层
            meaningful = [p for p in dir_parts if p.lower() not in self.skip_dirs]
            if len(meaningful) >= self.collection_depth:
                coll_names = meaningful[-self.collection_depth:]
            else:
                coll_names = list(meaningful)

        # 应用简写（如启用）
        if self.use_abbreviations:
            coll_names = [self.abbreviations.get(n, n) for n in coll_names]

        return coll_names

    # Blender 自动重命名正则: "name.001", "name.002" ...
    _AUTO_RENAME_PATTERN = re.compile(r'^(.+)\.(\d{3})$')

    def create_collections(self, coll_path, parent=None):
        """在 Blender 中创建 Collection 层级。

        按父级查找已存在的子 Collection：同名且同父级 → 复用；
        同名不同父级 → 创建新的（自动 .001 后缀区分）。

        修复了 Blender 自动重命名后的查找失败问题:
          - 当 "637" 已存在于别处，bpy.data.collections.new("637") 会被
            Blender 自动重命名为 "637.001"。
          - 后续导入同一路径时，不仅匹配精确名 "637"，也匹配
            "637.001"、"637.002" 等自动重命名变体。

        Args:
            coll_path: list[str] Collection 名列表
            parent: 父 Collection（None 则从场景根开始）

        Returns:
            bpy.types.Collection: 最深层 Collection
        """
        import bpy

        if not coll_path:
            return parent or bpy.context.scene.collection

        current = None
        for coll_name in coll_path:
            coll_name = self._safe_collection_name(coll_name)

            # 在当前父级的子 Collection 中查找同名（含自动重命名变体）
            existing = None
            children = parent.children if parent else bpy.context.scene.collection.children
            for child in children:
                if child.name == coll_name:
                    existing = child
                    break
                # 匹配 Blender 自动重命名: "name" → "name.001", "name.002" ...
                m = self._AUTO_RENAME_PATTERN.match(child.name)
                if m and m.group(1) == coll_name:
                    existing = child
                    break

            if existing:
                current = existing
            else:
                current = bpy.data.collections.new(coll_name)
                if parent:
                    parent.children.link(current)
                else:
                    bpy.context.scene.collection.children.link(current)

            parent = current

        return current or bpy.context.scene.collection

    # ── 名称工具 ────────────────────────────────────────────

    def _extract_base_name(self, file_path):
        """从路径提取用于冲突检测的 basename。

        例: "r1_h_t1.mdl-msh000" → "r1_h_t1"
        例: "dreadnoughtbattle_01.mdl-msh000" → "dreadnoughtbattle_01"
        """
        fname = os.path.basename(file_path)
        # 去掉 .mdl-mshXXX 后缀
        m = re.search(r'(.+)\.mdl-msh\d+', fname)
        if m:
            return m.group(1)
        return os.path.splitext(fname)[0]

    def _make_clean_name(self, file_path):
        """生成干净的 Blender 对象名。

        例: "r1_h_t1.mdl-msh000" → "r1_h_t1_000"
        例: "dreadnoughtbattle_01.mdl-msh005" → "dreadnoughtbattle_01_005"
        """
        fname = os.path.basename(file_path)
        # 替换 .mdl-msh → _
        name = re.sub(r'\.mdl-msh', '_', fname)
        # 去掉多余的特殊字符
        name = name.replace(" ", "_")
        return name[:SAFE_NAME_MAX]

    def _get_relative_dir_parts(self, file_path):
        """获取相对于 common_root 的目录层级。

        Returns:
            list[str]: 目录名列表（从根到叶）
        """
        if self.common_root and file_path.lower().startswith(self.common_root.lower()):
            rel = os.path.relpath(os.path.dirname(file_path), self.common_root)
        else:
            rel = os.path.dirname(file_path)

        if rel == '.':
            return []
        return [p for p in rel.replace('\\', '/').split('/') if p]

    def _truncate_name(self, name):
        """截断过长的名称。

        策略:
          1. ≤ 60 字符 → 直接返回
          2. > 60 字符 → 保留文件名末尾（LOD 编号重要），从前面截断
          3. 若仍超 → 使用简写（如启用）
        """
        if len(name) <= SAFE_NAME_MAX:
            return name

        # 尝试保留 LOD 后缀
        lod_match = LOD_SUFFIX_PATTERN.search(name)
        if lod_match:
            lod = lod_match.group(1)
            prefix = name[:lod_match.start()].rstrip('_')
            avail = SAFE_NAME_MAX - len(lod) - 1  # -1 for _
            if avail > 8:
                return prefix[:avail] + "_" + lod

        # 无 LOD 或前缀太短 → 直接截断
        return name[:SAFE_NAME_MAX]

    def _safe_collection_name(self, name):
        """确保 Collection 名在 Blender 限制内。"""
        return name[:SAFE_NAME_MAX]

    # ── 属性 ────────────────────────────────────────────────

    @property
    def conflict_count(self):
        return len(self._conflict_map)

    @property
    def total_files(self):
        return len(self._all_paths)

    def get_conflicts(self):
        """获取所有冲突组的摘要。

        Returns:
            dict: {basename: count} 仅冲突的
        """
        return {k: len(v) for k, v in self._conflict_map.items()}


# ============================================================================
# 便捷函数
# ============================================================================

def extract_msh_lod_index(filename):
    """从 MSH 文件名提取 LOD 索引。

    例: "bigship_empire_02.mdl-msh005" → 5
    """
    m = re.search(r'msh(\d+)', filename, re.IGNORECASE)
    return int(m.group(1)) if m else 0


def extract_msh_base_name(filename):
    """提取基础名（去掉 .mdl-mshXXX）。

    例: "r1_h_t1.mdl-msh000" → "r1_h_t1"
    """
    m = re.search(r'(.+)\.mdl-msh\d+', filename, re.IGNORECASE)
    return m.group(1) if m else os.path.splitext(filename)[0]
