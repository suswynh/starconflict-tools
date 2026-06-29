# ============================================================================
# Material Mapping Database — 静态 MSH→MDF block 映射覆盖表
# ============================================================================
"""提供 MSH piece index → MDF material block index 的静态覆盖映射。

核心设计:
  - 稀疏覆盖表: 只存储与默认行为不同的映射
  - MDF 指纹: SHA1(map.mdf) 确保映射与 MDF 版本匹配
  - 置信度: verified > high > medium > low
  - 只读查询: 导入时使用，不修改数据库

用法:
    db = MaterialMappingDB.load("material_mapping_db.json")
    override = db.get_override(mdf_path, msh_index=55)
    if override:
        block_idx, confidence = override
"""

import os
import json
import hashlib
from typing import Optional, Tuple, Dict, Any

# 数据库版本
SCHEMA_VERSION = "1.0.0"

# 置信度级别
CONFIDENCE_LEVELS = {"verified": 4, "high": 3, "medium": 2, "low": 1}


def _sha1_file(filepath: str) -> str:
    """计算文件的 SHA1 指纹 (前16字符，足够区分)"""
    if not os.path.isfile(filepath):
        return ""
    h = hashlib.sha1()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()[:16]


class MaterialMappingDB:
    """静态 MSH→MDF 材质映射数据库。

    Attributes:
        _data: 完整的 JSON 数据
        _fingerprint_index: {mdf_fingerprint: map_entry} 快速索引
    """

    def __init__(self):
        self._data: Dict[str, Any] = {
            "version": SCHEMA_VERSION,
            "maps": {}
        }
        self._fingerprint_index: Dict[str, dict] = {}
        self._build_index()

    # ── 加载 / 保存 ────────────────────────────────────────

    @classmethod
    def load(cls, filepath: str) -> "MaterialMappingDB":
        """从 JSON 文件加载数据库。

        文件不存在 → 返回空数据库 (不报错)。
        JSON 格式错误 → 打印警告，返回空数据库。
        """
        db = cls()
        if not os.path.isfile(filepath):
            return db

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"  [MappingDB] 警告: 无法加载 {filepath}: {e}")
            return db

        # 版本检查
        if data.get("version", "") != SCHEMA_VERSION:
            print(f"  [MappingDB] 警告: 版本不匹配 "
                  f"(DB={data.get('version')}, code={SCHEMA_VERSION})，使用空库")

        db._data = data
        db._build_index()
        return db

    def save(self, filepath: str) -> bool:
        """保存数据库到 JSON 文件。"""
        try:
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"  [MappingDB] 保存失败: {e}")
            return False

    # ── 索引 ────────────────────────────────────────────────

    def _build_index(self):
        """构建 mdf_fingerprint → map_entry 快速索引"""
        self._fingerprint_index.clear()
        for fingerprint, map_entry in self._data.get("maps", {}).items():
            self._fingerprint_index[fingerprint] = map_entry

    # ── 查询 API ────────────────────────────────────────────

    def get_override(
        self, mdf_path: str, msh_index: int
    ) -> Optional[Tuple[int, str]]:
        """查询指定 MSH piece 的材质 block 覆盖。

        Args:
            mdf_path: map.mdf 文件的完整路径
            msh_index: MSH 文件序号 (如 55 对应 map.mdl-msh055)

        Returns:
            (block_index: int, confidence: str) 如果存在覆盖
            None 如果无覆盖 (使用默认行为)
        """
        fingerprint = _sha1_file(mdf_path)
        if not fingerprint:
            return None

        map_entry = self._fingerprint_index.get(fingerprint)
        if not map_entry:
            return None

        overrides = map_entry.get("overrides", {})
        override = overrides.get(str(msh_index))
        if not override:
            return None

        block = override.get("block")
        confidence = override.get("confidence", "low")
        if block is None:
            return None

        return (int(block), str(confidence))

    def get_chunk_groups(
        self, mdf_path: str
    ) -> Optional[Dict[str, list]]:
        """获取 chunk → block 组映射 (用于无覆盖时的分组回退)。

        Returns:
            {chunk_index: [block_indices]} 或 None
        """
        fingerprint = _sha1_file(mdf_path)
        if not fingerprint:
            return None

        map_entry = self._fingerprint_index.get(fingerprint)
        if not map_entry:
            return None

        groups = map_entry.get("chunk_groups")
        if not groups:
            return None
        # 转换 string key → int
        return {int(k): v for k, v in groups.items()}

    def get_map_meta(self, mdf_path: str) -> Optional[dict]:
        """获取地图的元数据 (mdf_blocks, default_strategy 等)。"""
        fingerprint = _sha1_file(mdf_path)
        if not fingerprint:
            return None
        return self._fingerprint_index.get(fingerprint)

    # ── 校验 API ────────────────────────────────────────────

    def validate_block(
        self, mdf_path: str, block_index: int, mdf_block_count: int
    ) -> Tuple[bool, Optional[str]]:
        """校验 block_index 是否在有效范围内。

        Returns:
            (is_valid: bool, error_message: str or None)
        """
        meta = self.get_map_meta(mdf_path)
        expected = meta.get("mdf_blocks", mdf_block_count) if meta else mdf_block_count

        if block_index < 0:
            return False, f"block index {block_index} < 0"
        if block_index >= expected:
            return False, (
                f"block index {block_index} >= MDF blocks ({expected})"
            )
        return True, None

    # ── 管理 API (供标注工具使用) ────────────────────────────

    def add_override(
        self, mdf_path: str, msh_index: int, block_index: int,
        confidence: str = "medium", source: str = "heuristic",
        note: str = ""
    ):
        """添加或更新一条覆盖映射。"""
        fingerprint = _sha1_file(mdf_path)
        if not fingerprint:
            raise ValueError(f"MDF file not readable: {mdf_path}")

        if "maps" not in self._data:
            self._data["maps"] = {}

        if fingerprint not in self._data["maps"]:
            self._data["maps"][fingerprint] = {
                "label": os.path.basename(os.path.dirname(mdf_path)),
                "mdf_file": os.path.basename(mdf_path),
                "mdf_blocks": 0,
                "overrides": {},
            }
            self._fingerprint_index[fingerprint] = self._data["maps"][fingerprint]

        entry = self._data["maps"][fingerprint]
        if "overrides" not in entry:
            entry["overrides"] = {}

        entry["overrides"][str(msh_index)] = {
            "block": block_index,
            "confidence": confidence,
            "source": source,
            "note": note,
        }

    def remove_override(self, mdf_path: str, msh_index: int):
        """删除一条覆盖映射 (回退默认行为)。"""
        fingerprint = _sha1_file(mdf_path)
        if not fingerprint:
            return
        entry = self._data.get("maps", {}).get(fingerprint, {})
        overrides = entry.get("overrides", {})
        overrides.pop(str(msh_index), None)

    # ── 属性 ────────────────────────────────────────────────

    @property
    def map_count(self) -> int:
        return len(self._data.get("maps", {}))

    @property
    def total_overrides(self) -> int:
        return sum(
            len(entry.get("overrides", {}))
            for entry in self._data.get("maps", {}).values()
        )

    @property
    def is_empty(self) -> bool:
        return self.total_overrides == 0
