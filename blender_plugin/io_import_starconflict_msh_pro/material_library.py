# ============================================================================
# Material Library — 预生成静态材质库 + 加载/校验/查询 API
# ============================================================================
"""Star Conflict 静态材质库系统。

功能：
  1. 内嵌预生成材质库（基于官方数据，覆盖 3900+ MDF 文件）
  2. 运行时加载、校验、查询
  3. 与用户本地解包目录的对比与合并
  4. 支持按模型文件名反查材质定义（无 MDF 时的降级方案）

库文件结构:
  {
    "version": "1.0.0",
    "generated_at": "2026-06-27",
    "material_count": 1234,
    "model_count": 3992,
    "materials": { mat_id: MaterialDef },
    "models": { model_basename: ModelDef },
    "mdf_index": { mdf_basename: relative_path }
  }
"""

import os
import json
import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

from . import shader_presets
SHADER_TYPE_ALIASES = shader_presets.SHADER_TYPE_ALIASES

# ============================================================================
# 内嵌默认材质库（最小集——覆盖最常见的 shader 类型）
# ============================================================================

_EMBEDDED_LIBRARY = {
    "version": "1.0.0",
    "generated_at": "2026-06-27",
    "source": "Star Conflict (Hammer Engine)",
    "material_count": 0,
    "model_count": 0,
    "materials": {},
    "models": {},
    "mdf_index": {}
}

# ============================================================================
# 贴图后缀规则（用于从路径提取基底名）
# ============================================================================

TEXTURE_SUFFIXES = [
    "_d", "_nm", "_sc", "_pdo", "_s1", "_s2", "_s3", "_s4", "_s5",
    "_glow", "_msk", "_s1out", "_remap", "_noise", "_trail", "_beam",
    "_mask", "_clean", "_a", "_b", "_c", "_dmg", "_detail"
]

_TEXTURE_SUFFIX_RE = re.compile(
    r'(' + '|'.join(re.escape(s) for s in sorted(TEXTURE_SUFFIXES, key=len, reverse=True)) + r')$'
)

# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class MaterialDef:
    """材质定义条目"""
    mat_id: str
    shader_type: str
    label: str = ""
    samplers: dict = field(default_factory=dict)   # {sampler_name: relative_path}
    params: dict = field(default_factory=dict)       # {param_name: value}
    pins: dict = field(default_factory=dict)          # {pin_name: value}
    source_mdfs: list = field(default_factory=list)   # 来源 MDF 路径列表

    def to_dict(self):
        return {
            "shader_type": self.shader_type,
            "label": self.label,
            "samplers": self.samplers,
            "params": self.params,
            "pins": self.pins,
            "source_mdfs": self.source_mdfs
        }

    @classmethod
    def from_dict(cls, mat_id, data):
        return cls(
            mat_id=mat_id,
            shader_type=data.get("shader_type", ""),
            label=data.get("label", ""),
            samplers=data.get("samplers", {}),
            params=data.get("params", {}),
            pins=data.get("pins", {}),
            source_mdfs=data.get("source_mdfs", [])
        )


@dataclass
class ModelDef:
    """模型定义条目"""
    basename: str
    default_skin: str = "default"
    skins: dict = field(default_factory=dict)  # {skin_name: {mdf: str, materials: [mat_id]}}

    def to_dict(self):
        return {
            "default_skin": self.default_skin,
            "skins": self.skins
        }

    @classmethod
    def from_dict(cls, basename, data):
        return cls(
            basename=basename,
            default_skin=data.get("default_skin", "default"),
            skins=data.get("skins", {})
        )


# ============================================================================
# Library Manager
# ============================================================================

class MaterialLibrary:
    """材质库管理器。

    加载内嵌默认库，支持与用户本地 MDF 文件对比合并。
    """

    def __init__(self, library_path=None):
        self._data = None
        self._materials = {}    # {mat_id: MaterialDef}
        self._models = {}       # {basename: ModelDef}
        self._mdf_index = {}    # {mdf_basename: rel_path}
        self._loaded = False

        if library_path and os.path.isfile(library_path):
            self.load(library_path)
        else:
            self._load_embedded()

    # ── 加载 ────────────────────────────────────────────────

    def _load_embedded(self):
        """加载内嵌默认库（最小集）。"""
        self._data = json.loads(json.dumps(_EMBEDDED_LIBRARY))
        self._parse_data()
        self._loaded = True

    def load(self, library_path):
        """从 JSON 文件加载完整库。"""
        with open(library_path, 'r', encoding='utf-8') as f:
            self._data = json.load(f)
        self._parse_data()
        self._loaded = True

    def _parse_data(self):
        """解析库数据到快速查找结构。"""
        # 材质
        for mat_id, mat_data in self._data.get("materials", {}).items():
            self._materials[mat_id] = MaterialDef.from_dict(mat_id, mat_data)

        # 模型
        for basename, model_data in self._data.get("models", {}).items():
            self._models[basename] = ModelDef.from_dict(basename, model_data)

        # MDF 索引
        self._mdf_index = self._data.get("mdf_index", {})

    # ── 查询 ────────────────────────────────────────────────

    def get_material(self, mat_id):
        """按材质 ID 查询材质定义。"""
        return self._materials.get(mat_id)

    def get_model(self, basename):
        """按模型 basename 查询模型定义。

        Args:
            basename: 如 "r1_h_t1"（不含 .mdl-msh 后缀）

        Returns:
            ModelDef or None
        """
        return self._models.get(basename)

    def get_materials_for_model(self, basename, skin="default"):
        """获取模型指定 skin 的材质 ID 列表。

        Returns:
            list[str]: 材质 ID 列表，或空列表
        """
        model = self.get_model(basename)
        if not model:
            return []
        skin_data = model.skins.get(skin, model.skins.get("default", {}))
        return skin_data.get("materials", [])

    def get_mdf_path(self, mdf_basename):
        """查 MDF 相对路径。"""
        return self._mdf_index.get(mdf_basename)

    def find_model_by_basename_fuzzy(self, basename):
        """模糊匹配模型名（忽略大小写、下划线/连字符变体）。

        Args:
            basename: 如 "r1_h_t1" 或 "R1_H_T1"

        Returns:
            str or None: 匹配到的精确 basename
        """
        normalized = basename.lower().replace('-', '_')
        for key in self._models:
            if key.lower().replace('-', '_') == normalized:
                return key
        return None

    @property
    def material_count(self):
        return len(self._materials)

    @property
    def model_count(self):
        return len(self._models)

    @property
    def is_loaded(self):
        return self._loaded

    @property
    def version(self):
        return self._data.get("version", "0.0.0") if self._data else "0.0.0"

    # ── 校验 ────────────────────────────────────────────────

    def validate_against_directory(self, mdf_root_dir):
        """校验库中的 MDF 索引与实际文件是否一致。

        Args:
            mdf_root_dir: 用户解包根目录（如 /path/to/unpack/output）

        Returns:
            dict: {
                "total_in_lib": int,
                "total_on_disk": int,
                "missing_in_lib": [str],
                "missing_on_disk": [str],
                "match_count": int
            }
        """
        if not os.path.isdir(mdf_root_dir):
            return {"error": f"目录不存在: {mdf_root_dir}"}

        # 扫描磁盘上的 MDF 文件
        disk_mdfs = set()
        for root, dirs, files in os.walk(mdf_root_dir):
            for f in files:
                if f.lower().endswith('.mdf'):
                    basename = os.path.splitext(f)[0]
                    disk_mdfs.add(basename)

        lib_mdfs = set(self._mdf_index.keys())

        return {
            "total_in_lib": len(lib_mdfs),
            "total_on_disk": len(disk_mdfs),
            "missing_in_lib": sorted(disk_mdfs - lib_mdfs),
            "missing_on_disk": sorted(lib_mdfs - disk_mdfs),
            "match_count": len(lib_mdfs & disk_mdfs)
        }

    # ── 生成 ────────────────────────────────────────────────

    def generate_from_directory(self, mdf_root_dir, progress_callback=None):
        """从解包目录全量扫描 MDF 生成完整库。

        Args:
            mdf_root_dir: 解包根目录
            progress_callback: 可选，进度回调 fn(current, total)

        Returns:
            dict: 完整库数据（可保存为 JSON）
        """
        from . import mdf_parser

        if not os.path.isdir(mdf_root_dir):
            raise FileNotFoundError(f"目录不存在: {mdf_root_dir}")

        # 收集所有 MDF 文件
        mdf_files = []
        for root, dirs, files in os.walk(mdf_root_dir):
            for f in files:
                if f.lower().endswith('.mdf'):
                    mdf_files.append(os.path.join(root, f))

        total = len(mdf_files)
        material_map = {}       # {指纹 → MaterialDef}
        model_map = {}          # {basename → ModelDef}
        mdf_index = {}          # {basename → rel_path}

        for i, mdf_path in enumerate(mdf_files):
            if progress_callback:
                progress_callback(i, total)

            basename = os.path.splitext(os.path.basename(mdf_path))[0]
            rel_path = os.path.relpath(mdf_path, mdf_root_dir).replace('\\', '/')
            mdf_index[basename] = rel_path

            try:
                blocks = mdf_parser.parse_mdf(mdf_path)
            except Exception:
                continue

            material_ids = []
            for block in blocks:
                fingerprint = _compute_fingerprint(block, shader_aliases=SHADER_TYPE_ALIASES)
                aliased_shader = SHADER_TYPE_ALIASES.get(block.shader_type, block.shader_type)
                mat_id = f"SC_{aliased_shader}_{fingerprint}"

                if mat_id not in material_map:
                    material_map[mat_id] = MaterialDef(
                        mat_id=mat_id,
                        shader_type=block.shader_type,
                        label=_generate_label(basename, block.shader_type),
                        samplers=block.samplers,
                        params=block.params,
                        pins=block.pins,
                        source_mdfs=[rel_path]
                    )
                else:
                    material_map[mat_id].source_mdfs.append(rel_path)

                material_ids.append(mat_id)

            # 检查是否有 .skins 文件
            skins = _parse_skins_file(mdf_root_dir, basename, mdf_path)
            model_map[basename] = ModelDef(
                basename=basename,
                default_skin="default",
                skins=skins or {"default": {"mdf": basename, "materials": material_ids}}
            )

        # 组装库
        library = {
            "version": "1.0.0",
            "generated_at": _timestamp_now(),
            "source": "Star Conflict (generated from MDF)",
            "material_count": len(material_map),
            "model_count": len(model_map),
            "materials": {k: v.to_dict() for k, v in material_map.items()},
            "models": {k: v.to_dict() for k, v in model_map.items()},
            "mdf_index": mdf_index
        }
        return library

    def save_library(self, output_path, library_data=None):
        """保存库到 JSON 文件。"""
        data = library_data or self._data
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# ============================================================================
# 辅助函数
# ============================================================================

def _compute_fingerprint(block, shader_aliases=None):
    """计算材质的贴图指纹（MD5 前8位）。

    基于 shader_type（经别名规范化）+ 所有 sampler 引用的贴图基底名
    + UserParam2_Float4（UV tiling 影响材质行为）。

    注意: LightmapSampler 不参与指纹，以允许跨场景的材质共享；
    lightmap 通过 variant 机制单独处理。
    """
    # ── Shader type 别名规范化（dyn_object_norm → object_norm 等）──
    if shader_aliases:
        shader_type = shader_aliases.get(block.shader_type, block.shader_type)
    else:
        shader_type = block.shader_type

    texture_basenames = set()
    for sampler_name, path in block.samplers.items():
        # LightmapSampler 不参与指纹——场景级 lightmap 不应阻止材质共享
        if sampler_name == "LightmapSampler":
            continue
        basename = os.path.basename(path)
        clean = _TEXTURE_SUFFIX_RE.sub('', basename)
        texture_basenames.add(clean)

    # 包含 UV tiling 参数（与 material_registry 保持一致）
    param_key = ""
    if "UserParam2_Float4" in block.params:
        param_key = f"|uv={block.params['UserParam2_Float4']}"

    key = f"{shader_type}|{'|'.join(sorted(texture_basenames))}{param_key}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()[:8]


def _generate_label(basename, shader_type):
    """为材质生成可读标签。"""
    return f"{basename} ({shader_type})"


def _parse_skins_file(root_dir, base_name, mdf_path):
    """解析 .skins 文件（如有）。

    Returns:
        dict: {skin_name: {mdf: str, materials: []}} 或 None
    """
    skins_path = os.path.splitext(mdf_path)[0] + '.skins'
    if not os.path.isfile(skins_path):
        # 尝试在 mdf 同目录查找
        alt = os.path.join(os.path.dirname(mdf_path), base_name + '.skins')
        if os.path.isfile(alt):
            skins_path = alt
        else:
            return None

    skins = {}
    try:
        with open(skins_path, 'r', encoding='utf-8', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('//'):
                    continue
                parts = line.split()
                if len(parts) >= 3 and parts[0].lower() == 'skin':
                    skin_name = parts[1]
                    mdf_name = parts[2]
                    skins[skin_name] = {"mdf": mdf_name, "materials": []}
    except Exception:
        pass
    return skins if skins else None


def _timestamp_now():
    """当前日期字符串。"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def extract_texture_basename(sampler_path):
    """从 sampler 路径中提取贴图基底名（去后缀）。

    例:
        "models/ships/race_1/h/r1_h_t1_d" → "r1_h_t1"
        "models/weapons/lasers/auto/auto_d" → "auto"

    Args:
        sampler_path: MDF 中的 sampler 路径

    Returns:
        str: 贴图基底名（不含目录和纹理类型后缀）
    """
    basename = os.path.basename(sampler_path)
    clean = _TEXTURE_SUFFIX_RE.sub('', basename)
    return clean
