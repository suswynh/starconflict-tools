# ============================================================================
# Material Registry — 运行时材质注册表
# ============================================================================
"""基于贴图指纹的全局材质注册表。

核心职责:
  1. 材质 ID 生成（基于 shader_type + 贴图指纹）
  2. 材质查找与复用（跨模型、跨导入批次）
  3. 材质创建委托给 material_builder
  4. 降级处理（默认库查不到时）

与 MaterialLibrary 的关系:
  - MaterialLibrary: 静态数据（预生成 JSON）
  - MaterialRegistry: 运行时状态（Blender session 内）
  - Registry 优先查 Library，找不到则降级
"""

import os
import hashlib
import bpy

from . import shader_presets


# ============================================================================
# 贴图后缀正则（与 material_library.py 保持一致）
# ============================================================================

import re

_TEXTURE_SUFFIXES = [
    "_d", "_nm", "_sc", "_pdo", "_s1", "_s2", "_s3", "_s4", "_s5",
    "_glow", "_msk", "_s1out", "_remap", "_noise", "_trail", "_beam",
    "_mask", "_clean", "_a", "_b", "_c", "_dmg", "_detail"
]
_TEXTURE_SUFFIX_RE = re.compile(
    r'(' + '|'.join(re.escape(s) for s in sorted(_TEXTURE_SUFFIXES, key=len, reverse=True)) + r')$'
)


# ============================================================================
# Material Registry
# ============================================================================

class MaterialRegistry:
    """全局材质注册表。

    用法:
        registry = MaterialRegistry(library)

        # 从 MDF block 获取或创建材质
        mat = registry.get_or_create(block, texture_map)

        # 从库中按模型名获取材质
        materials = registry.get_materials_for_model("r1_h_t1")

        # 获取统计
        print(registry.stats())
    """

    def __init__(self, library=None, unpack_root=None):
        """
        Args:
            library: MaterialLibrary 实例（可选）
            unpack_root: 用户指定的解包根目录（可选）
        """
        self._library = library
        self._unpack_root = unpack_root

        # 运行时缓存: {mat_id: bpy.types.Material}
        self._cache = {}

        # 反向索引: {(shader_type, fingerprint): mat_id}
        # 用于从 MDF block 快速查找
        self._fingerprint_index = {}

        # 统计
        self._hit_count = 0
        self._miss_count = 0
        self._created_count = 0

    # ── 核心 API ────────────────────────────────────────────

    def get_or_create(self, block, texture_map, complexity='FULL'):
        """获取或创建材质。

        查找顺序:
          1. 指纹索引（当前 session 内已创建）
          2. 按贴图 basename 在 Blender 全局材质中查找（跨 session）
          3. 创建新材质

        Args:
            block: MaterialBlock from mdf_parser
            texture_map: {sampler_name: texture_path}
            complexity: 'FULL' or 'SIMPLE'

        Returns:
            bpy.types.Material
        """
        fingerprint, aliased_shader = self._compute_fingerprint(block)
        mat_id = f"SC_{aliased_shader}_{fingerprint}"

        # 1. 运行时缓存命中
        if mat_id in self._cache:
            mat = self._cache[mat_id]
            if mat and mat.name in bpy.data.materials:
                self._hit_count += 1
                return mat
            # 缓存中的材质已被删除，清除
            del self._cache[mat_id]

        # 2. 按名称在 Blender 全局材质中查找（跨 session 复用）
        existing = bpy.data.materials.get(mat_id)
        if existing:
            self._cache[mat_id] = existing
            self._hit_count += 1
            return existing

        # 3. 创建新材质
        from . import material_builder
        mat = material_builder.build_material_from_mdf(
            block, texture_map,
            name=mat_id,
            complexity=complexity
        )

        self._cache[mat_id] = mat
        self._fingerprint_index[(aliased_shader, fingerprint)] = mat_id
        self._miss_count += 1
        self._created_count += 1
        return mat

    def get_materials_for_model(self, basename, skin="default", texture_map_builder=None):
        """通过库反查模型对应的材质列表。

        适用场景: 用户只有 MSH 文件，没有 MDF 文件。

        Args:
            basename: 模型基础名（如 "r1_h_t1"）
            skin: skin 名称
            texture_map_builder: 可选，用于为库中的 sampler 路径查找实际贴图

        Returns:
            list[bpy.types.Material]: 材质列表
        """
        if not self._library:
            return []

        model = self._library.get_model(basename)
        if not model:
            # 模糊匹配
            fuzzy = self._library.find_model_by_basename_fuzzy(basename)
            if fuzzy:
                model = self._library.get_model(fuzzy)

        if not model:
            return []

        skin_data = model.skins.get(skin, model.skins.get("default", {}))
        mat_ids = skin_data.get("materials", [])

        materials = []
        for mat_id in mat_ids:
            # 检查运行时缓存
            if mat_id in self._cache:
                materials.append(self._cache[mat_id])
                continue

            # 检查 Blender 全局
            mat = bpy.data.materials.get(mat_id)
            if mat:
                self._cache[mat_id] = mat
                materials.append(mat)
                continue

            # 从库数据创建
            mat_def = self._library.get_material(mat_id)
            if mat_def and texture_map_builder:
                # 使用库中的材质定义创建
                mat = self._create_from_library_def(mat_def, texture_map_builder)
                if mat:
                    self._cache[mat_id] = mat
                    materials.append(mat)
            else:
                materials.append(None)  # 无法创建，保留 None 占位

        return materials

    def _create_from_library_def(self, mat_def, texture_map_builder):
        """从库中的 MaterialDef 创建 Blender 材质。

        Args:
            mat_def: MaterialDef 对象
            texture_map_builder: 用于查找贴图的函数 fn(sampler_path) → full_texture_path
        """
        from . import mdf_parser
        from . import material_builder

        # 构建临时 MaterialBlock
        block = mdf_parser.MaterialBlock(
            shader_type=mat_def.shader_type,
            samplers=mat_def.samplers,
            params=mat_def.params,
            pins=mat_def.pins
        )

        # 构建 texture_map
        texture_map = {}
        for sampler_name, rel_path in mat_def.samplers.items():
            texture_map[sampler_name] = texture_map_builder(rel_path)

        mat = material_builder.build_material_from_mdf(
            block, texture_map,
            name=mat_def.mat_id,
            complexity='FULL'
        )
        return mat

    # ── 查询 ────────────────────────────────────────────────

    def find_mat_id(self, block):
        """查找 block 对应的材质 ID（不创建）。

        Returns:
            str or None
        """
        fingerprint, aliased_shader = self._compute_fingerprint(block)
        mat_id = f"SC_{aliased_shader}_{fingerprint}"
        if mat_id in self._cache:
            return mat_id
        if bpy.data.materials.get(mat_id):
            return mat_id
        return None

    def clear(self):
        """清除运行时缓存（不删除 Blender 材质）。"""
        self._cache.clear()
        self._fingerprint_index.clear()

    # ── 统计 ────────────────────────────────────────────────

    def stats(self):
        return {
            "cache_size": len(self._cache),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "created_count": self._created_count,
            "library_materials": self._library.material_count if self._library else 0,
            "library_models": self._library.model_count if self._library else 0,
            "unpack_root": self._unpack_root
        }

    # ── 指纹计算 ────────────────────────────────────────────

    def _compute_fingerprint(self, block):
        """计算材质的贴图指纹（MD5 前8位）。

        指纹基于:
          - shader_type（经别名规范化）
          - 所有 sampler 引用的贴图基底名（去后缀、排序）
          - UserParam2_Float4（UV tiling）

        注意: LightmapSampler 不参与指纹计算，以允许不同场景/上下文
        使用相同核心贴图集的对象共享基础材质；lightmap 通过 variant 机制
        在赋值阶段单独处理（参见 material_builder.create_lightmap_variant）。

        Returns:
            (fingerprint_8chars, aliased_shader_type)
        """
        # ── Shader type 别名规范化 ──
        aliased = shader_presets.SHADER_TYPE_ALIASES.get(
            block.shader_type, block.shader_type
        )

        texture_basenames = set()
        for sampler_name, path in block.samplers.items():
            # LightmapSampler 不参与指纹——lightmap 是场景级外部因素，
            # 不应阻止核心贴图集相同的材质共享。
            if sampler_name == "LightmapSampler":
                continue
            basename = os.path.basename(path)
            clean = _TEXTURE_SUFFIX_RE.sub('', basename)
            texture_basenames.add(clean)

        # 也包含 params 中的关键参数（UV tiling 等）
        param_key = ""
        if "UserParam2_Float4" in block.params:
            param_key = f"|uv={block.params['UserParam2_Float4']}"

        key = f"{aliased}|{'|'.join(sorted(texture_basenames))}{param_key}"
        return hashlib.md5(key.encode('utf-8')).hexdigest()[:8], aliased

    # ── 属性 ────────────────────────────────────────────────

    @property
    def library(self):
        return self._library

    @library.setter
    def library(self, value):
        self._library = value

    @property
    def unpack_root(self):
        return self._unpack_root

    @unpack_root.setter
    def unpack_root(self, value):
        self._unpack_root = value
        if self._library and value:
            # 尝试从解包目录加载/校验库
            pass
