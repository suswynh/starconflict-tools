# Star Conflict MSH Importer Pro — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender，**并自动根据 .mdf 材质定义文件创建材质和链接贴图**。

**区别于基础版**：基础版 (`io_import_starconflict_msh`) 仅导入网格，Pro 版增加了完整的材质管线。

> **v2.2** (2026-06) — 材质静态映射库、UV2 Lightmap、Collection 全层级树、LOD 命名修复。
> **v2.1** (2026-06) — 修复前向轴：MSH 前向 -Z→+Z，默认坐标系改为 Z-up→Y-up。

**兼容版本**：Blender 4.2 LTS、Blender 5.0+

---

## 功能

| 功能 | 基础版 | Pro 版 |
|------|:---:|:---:|
| MSH 网格导入 | ✅ | ✅ |
| UV 坐标导入 (diffuse) | ✅ | ✅ |
| **UV2 Lightmap 导入** | ❌ | ✅ |
| 批量目录导入 | ✅ | ✅ |
| 坐标系转换 | ✅ | ✅ |
| **MDF 材质解析** | ❌ | ✅ |
| **自动贴图搜索与链接** | ❌ | ✅ |
| **Principled BSDF 节点网络** | ❌ | ✅ |
| **按材质类型还原着色器** | ❌ | ✅ |
| **AO/Lightmap 混合** | ❌ | ✅ |
| **Collection 层级自动组织** | ❌ | ✅ |
| **模型命名冲突检测与重命名** | ❌ | ✅ |
| **材质静态库 (去重复用)** | ❌ | ✅ |
| **Map 材质映射覆盖表** | ❌ | ✅ |
| **偏好设置面板** | ❌ | ✅ |
| **工具侧边栏** | ❌ | ✅ |

---

## 新增功能 (v2.2)

### UV2 Lightmap

MSH 文件包含第二套 UV (lightmap)。插件自动导入为 `lightmap` UV 层。顶点格式 `VBytes=36/40/44` 时自动检测 `uint16_unorm` 或 `float2` 编码。

### Collection 自动组织

导入时自动按文件夹目录层级创建 Blender Collection 树。`collection_depth` 设置：
- **-1 (全层级)**：完整镜像文件夹树，不跳过任何目录（推荐）
- **N > 0**：仅使用最近 N 层有意义目录
- **0**：不创建 Collection

重名子文件夹自动使用 Blender 命名规则 (`.001`, `.002`)。

### 模型命名冲突检测

批量导入时自动检测同名模型，从路径层级生成前缀以区分。同目录 LOD 变体（`_000`, `_001`）不会触发额外前缀。

### 材质静态库与注册表

- `MaterialLibrary`: 预生成的 JSON 材质定义库，支持按模型名反查材质
- `MaterialRegistry`: 运行时去重复用，基于贴图指纹 (MD5) 生成唯一材质名 `SC_{shader}_{hash[:8]}`
- 同一贴图组合跨批次、跨 session 自动复用

### Map 材质映射覆盖表

Map 场景下 MSH 数量远超 MDF block 数量，1:1 索引映射不适用。插件使用 modulo 分散 + 静态映射覆盖表：

1. `material_references/` 下每个地图一对 CSV + JSON 模板
2. CSV 为明码材质参照表（block → shader → 贴图名）
3. JSON 为 overrides 模板，人工校验后粘贴到 `material_mapping_db.json`
4. 导入时优先查库，日志标记 `[DB:verified]` / `[fallback]`

---

## 安装

### 方法 1：ZIP 安装（推荐）

1. 将 `io_import_starconflict_msh_pro` 文件夹打包为 `.zip`
2. Blender → Edit → Preferences → Add-ons → 右上角 ▼ → **Install from Disk...**
3. 选择刚才的 `.zip` 文件
4. 搜索 "Star Conflict MSH Importer Pro"，勾选启用

> ⚠️ 不要与基础版 `io_import_starconflict_msh` 放在同一个 zip 中，两者是独立插件。

### 方法 2：手动复制

将文件夹复制到 Blender addons 目录：

```
# Windows (Blender 4.2)
%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons\

# Windows (Blender 5.0)
%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\
```

---

## 使用

### 1. 配置搜索路径

安装后，在 Preferences 中设置贴图和 MDF 的搜索目录。

**Edit → Preferences → Add-ons → Star Conflict MSH Importer Pro → 展开**

#### 贴图搜索路径（Texture Search Paths）

指向已转换的纹理目录。以本项目为例，转换产物位于：

```
<unpack_root>/tex_universe_check/
```

该目录结构：
```
tex_universe_check/
├── models/
│   └── weapons/
│       └── plasma_gun/
│           ├── plasma_gun_d.dds    ← 漫反射 (diffuse)
│           ├── plasma_gun_nm.dds   ← 法线贴图 (normal map)
│           ├── plasma_gun_s.dds    ← 高光 (specular)
│           └── plasma_gun_e.dds    ← 自发光 (emissive)
├── mapskit/
│   └── backgrounds/
│       └── ...
└── levels/
    └── ...
```

**支持子文件夹搜索（递归）**：只需指定顶层目录（如 `tex_universe_check`），插件会自动递归搜索所有子文件夹中的贴图文件。无需逐个添加子目录。

#### MDF 搜索路径（MDF Search Paths）

MDF 材质定义文件与 MSH 模型文件位于同一目录树中：

```
<unpack_root>/output/
```

目录结构示例：
```
output/
├── models/
│   └── weapons/
│       ├── plasma_gun.mdf              ← MDF 材质定义
│       ├── plasma_gun.mdl-msh000       ← LOD0 模型
│       ├── plasma_gun.mdl-msh001       ← LOD1 模型
│       └── ...
├── mapskit/
│   └── backgrounds/
│       └── ...
└── levels/
    └── ...
```

**自动查找规则**：
1. **同目录匹配**：先在 MSH 文件所在目录查找同名 `.mdf` 文件（如 `plasma_gun.mdl-msh000` → `plasma_gun.mdf`）
2. **递归搜索**：若同目录未找到，则递归搜索 MDF Search Paths 中所有的子文件夹

> 💡 **提示**：如果 MSH 和 MDF 文件位于同一目录树（如本例中均在 `scunpack\output\` 下），只需将 MDF Search Path 指向 `output` 目录查看即可。插件会自动扫描 MSH 文件所在目录，通常无需额外配置 MDF 搜索路径。

#### 贴图扩展名（Texture Extensions）

默认 `.dds,.png,.tga`，按优先级排列。`tex_targem_py.py` / `batch_tex_all.py` 转换产物为 `.dds`，无需修改。

### 2. 导入模型

**File → Import → Star Conflict MSH Pro (.mdl-msh\*)**

| 选项 | 说明 |
|------|------|
| Scale | 缩放系数（默认 1.0） |
| Up Axis | 坐标系转换（默认 Y-up→Z-up） |
| **Auto-Link Materials** | 自动查找 MDF 并创建材质（默认开启） |
| Texture Path 1-3 | 本次导入的额外贴图搜索目录 |
| MDF Search Path | 额外的 MDF 搜索目录 |
| Texture Extensions | 贴图扩展名（默认 `.dds,.png,.tga`） |
| **Shader Nodes** | Full（完整 PBR 节点网络）/ Simple（仅贴图直连） |

#### 导入流程

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│ .mdl-mshXXX     │ →   │ MSH Parser   │ →   │ Blender Mesh        │
│ (模型文件)      │     │ (顶点+UV+面) │     │ (位置+UV+三角面)    │
└─────────────────┘     └──────────────┘     └──────────┬──────────┘
                                                        │
┌─────────────────┐     ┌──────────────┐               │
│ .mdf            │ →   │ MDF Parser   │ →   ┌─────────▼──────────┐
│ (材质定义)      │     │ (材质块+贴图)│     │ Material Builder    │
└─────────────────┘     └──────────────┘     │ (Principled BSDF)   │
                                             └──────────┬──────────┘
                                                        │
┌─────────────────┐     ┌──────────────┐               │
│ .dds / .png     │ ←   │ Texture      │ ←────────────┘
│ (纹理文件)      │     │ Finder       │   递归搜索 tex_universe_check
└─────────────────┘     │ (递归搜索)   │
                        └──────────────┘
```

### 2a. 批量导入

**File → Import → Star Conflict MSH Pro Batch (directory)**

选择包含 `.mdl-msh*` 文件的目录，递归导入所有模型。适用于一次性导入整个武器库或场景集。

### 3. 材质管理

导入后可在 **3D View → Sidebar (N键) → Star Conflict** 面板中：

- **Import MSH File**：再次导入
- **Batch Import Directory**：批量导入
- **Refresh Materials**：清除并重新扫描材质
- **Clear Texture Cache**：清除贴图索引缓存

---

## 支持格式

### MSH 网格格式

| VBytes | 用途 | UV1 | UV2(Lightmap) |
|--------|------|:---:|:---:|
| 20 | 基础网格 | ✅ | ❌ |
| 24 | 扩展网格 | ✅ | ❌ |
| 28 | 场景物体 | ✅ | ❌ |
| 32 | 中型网格 (bigship/map) | ✅ | ✅ (v2.2新增) |
| 36 | 大型网格 | ✅ | ✅ |
| 40 | 角色模型 | ✅ | ✅ |
| 44 | 装饰模型 | ✅ | ✅ |
| 48 | 扩展格式 | ✅ | ✅ |

### MDF 材质类型（21 种）

| 类型 | 用途 | 贴图通道数 |
|------|------|:---:|
| `ship_hull` | 飞船/武器主体 | 6 |
| `ship_decals` | 动态贴花 | 3 |
| `ship_static_decals` | 静态贴花 | 3 |
| `dyn_object` | 动态物体 | 2 |
| `dyn_object_norm` | 动态物体+法线 | 5 |
| `dyn_animated_mock` | 动态动画 | 2 |
| `dyn_glass` | 玻璃 | 0 |
| `dyn_fresnel` | 菲涅尔 | 1 |
| `dyn_drone` | 无人机 | 1 |
| `dyn_blank_object` | 空白动态 | 0 |
| `object` / `object_norm` | 静态物体 | 1-2 |
| `sky` / `skybackground` | 天空 | 1-2 |
| 其他 | `fresnel`, `planets`, `grassbase` 等 | 0-1 |

| 贴图后缀 | 对应的 Sampler | Blender 节点连接 | 颜色空间 | 通道说明 |
|---------|---------------|-----------------|---------|---------|
| `_d` | DiffuseSampler | Base Color | sRGB | RGB=漫反射颜色 |
| `_nm` | NormalSampler | Normal (DX→GL) + AO | Non-Color | **DXT5nm**: R=**AO** (FetchBumpOccl.z), G=NormalY, A=NormalX |
| `_sc` | SpecularColorSampler | Specular IOR Level | sRGB | RGB=高光颜色, A=Gloss(部分模式) |
| `_msk_sc` | SpecularColorSampler | Specular IOR Level | sRGB | bigship/map命名变体, 同_sc |
| **`_msk`** | AmbOcclSampler | **G→AO** / **B→Gloss→Roughness** | Non-Color | 详见下方 [PBR Mask通道拆解](#pbr-mask通道拆解_msk) |
| `_s1` | ColormapSampler | (染色遮罩) | sRGB | RGB=染色颜色, A=混合权重 |
| `_glow` | Diffuse2Sampler | Emission Color | sRGB | RGB=自发光颜色 |
| `_pdo` | LightmapSampler | AO混合 (**R通道**, UV2) | Non-Color | R=余弦加权AO (object.fx L629), G=PDO方向Y, Z=方向, W=强度 |

### UV 通道说明

| UV 通道 | 名称 | 用途 |
|--------|------|------|
| UV1 | `map1` | 漫反射/法线/高光等通用贴图 (所有模型) |
| UV2 | `lightmap` | 预计算光照贴图 `_pdo` (VBytes≥32 的模型) |

> **UV2 支持范围**：VBytes=32/36/40/44/48 的模型自动解析 lightmap UV2 通道。VBytes=28 的模型因顶点格式不含 UV2 空间，lightmap 使用 UV1 采样 (PD_OCCL Type=0 模式)。

### PBR Mask通道拆解 (_msk)

> ⚠️ **v2.3 重大修正**：通道映射已通过着色器源码 `object.fx` 第422-428行验证，废弃此前错误的ORM假设。

Star Conflict 使用 **Specular-Gloss** 工作流（Blinn-Phong 高光模型，`specPower = exp2(9*gloss+2)`），`_msk` 贴图通道含义如下：

| 通道 | PBR 参数 | 值域 | 说明 |
|------|---------|------|------|
| **R** (红) | Height (Parallax) | 0=平, 1=最大高度 | 仅在 PARALLAX 模式用于视差高度偏移；默认模式下不使用 |
| **G** (绿) | **AO / Occlusion** | 0=遮蔽, 1=开放 | 纹理级环境光遮蔽，与 Base Color 相乘。`object.fx L428`: `texOcclusion = masks.g` |
| **B** (蓝) | **Glossiness** | 0=粗糙, 1=光滑 | 高光锐度，转换为 Blender Roughness = 1-Gloss。`object.fx L427`: `glossFactor = masks.b` |

**已验证案例** — `fed_plates01_msk.dds` (1024×1024 DXT1):
- R: 全黑 (avg=0) → 无视差高度
- G: 亮绿 (avg=209-251) → AO≈0.82-0.98 (大部分区域无遮蔽)
- B: 暗蓝 (avg=32-55) → Gloss≈0.12-0.22 → Roughness≈0.78-0.88 (粗糙板材)

### _msk 双用途总结（着色器源码验证）

| 着色器模式 | `_msk` 用途 | 触发条件 |
|----------|-----------|---------|
| **默认模式** | R=未使用, **G=AO**, **B=Gloss** | 大多数材质 |
| `PARALLAX` | **R=高度偏移**, G/B=同上 | 视差贴图启用时 |
| `BL2_DETAIL` | **RGB=细节反射率** (用于 albedo 混合) | 混合细节模式 |
| `SHIP_DECAL` | **G=AO** (单通道) | 舰船贴花 |

### _nm 法线贴图的 AO

法线贴图 `_nm` (DXT5nm) 的 R 通道也包含 AO 数据：
- `FetchBumpOccl(NormalSampler, uv).z` = R 通道 AO
- 在 `BL2_DETAIL` 或 `PD_OCCL` 模式下，法线贴图 AO **会覆盖** `_msk` 的 G 通道 AO (`object.fx L550`)
- 插件同时提取两处 AO 并全部与 Base Color 相乘

### 透明材质类型

以下 shader 类型自动设置 Alpha Blend：

`dyn_glass` `dyn_fresnel` `fresnel` `spaceship_shield` `decals` `ship_decals` `ship_static_decals` `flares` `laserbeam` `flatbeam` `scanner` `dyn_animated_mock` `animated_mock` `dyn_drone`

---

## 文件结构

```
io_import_starconflict_msh_pro/
├── __init__.py              # 插件入口 + bl_info + register/unregister
├── msh_parser.py            # MSH 二进制格式解析 (含 UV2 lightmap)
├── msh_importer.py          # Blender 网格构建 + 导入编排
├── mdf_parser.py            # MDF 材质定义文件解析
├── texture_finder.py        # 多目录贴图搜索引擎
├── shader_presets.py        # 材质类型→Sampler映射 + 节点网络预设
├── material_builder.py      # Blender 材质/节点创建 + MSH→MDF 映射
├── material_library.py      # 预生成静态材质库 (加载/校验/查询)
├── material_registry.py     # 运行时材质注册表 (去重复用)
├── material_mapping.py      # 静态 MSH→MDF 映射覆盖表
├── material_mapping_db.json # 映射覆盖数据 (初始为空)
├── name_resolver.py         # 命名冲突检测 + Collection 层级生成
├── properties.py            # Scene 级自定义属性
├── preferences.py           # AddonPreferences 全局设置
├── operators.py             # 导入操作符 + 工具操作符
├── panels.py                # UI 面板（导入菜单 + 侧边栏）
└── material_references/     # 各地图材质参照表 (CSV + JSON模板)
```

---

## 工作流

```
用户导入 MSH 文件
    │
    ▼
┌──────────────────┐
│ MSH 解析         │ → 顶点、UV1、UV2(lightmap)、面索引
│ (msh_parser.py)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 命名解析         │ → 冲突检测 + Collection 路径
│ (name_resolver)  │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ MDF 查找         │ → <基础名>.mdf
│ (msh_importer.py)│
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Block 映射       │ → DB覆盖 > 1:1索引 > modulo回退
│ (material_builder)│
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 贴图搜索         │ → sampler→文件路径映射
│ (texture_finder) │
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 材质创建         │ → Registry去重 → Blender Material
│ (material_registry)│
└──────┬───────────┘
       │
       ▼
   ✅ 完成：网格 + UV1/UV2 + Collection + 材质 + 贴图
```

---

## 关于 LOD 模型

**Star Conflict 没有统一的 LOD 编号规则**，不同模型/阵营使用不同约定：

### 实测数据

| 模型 | 命名 | 角色 | 总顶点量 | 证据（文件大小） |
|------|------|:--:|------|------|
| **联邦无畏舰** | `bigship_fed` | LOD0 | ~2.3MB | msh000(1260KB)+msh001(287KB)+msh002(730KB) |
| | `bigship_fed_2` | LOD1 | ~0.5MB | 约为 LOD0 的 22% |
| **帝国无畏舰** | `bigship_empire_01` | LOD0 | ~1.2MB | 19 个子网格，最大 msh011(395KB) |
| | `bigship_empire_02` | LOD0 | ~1.5MB | 12 个子网格，最大 msh000(763KB) — 船体另一部件 |
| **Jericho 无畏舰** | `bigship_jer_03_{back,front}` | LOD0 | ~4.6MB | 两部件拼接，msh007(1099KB) |
| | `bigship_jer` | LOD1 | ~2.7MB | msh002(1957KB) — 约为 LOD0 的 59% |
| | `bigship_jer_2` | LOD2 | ~0.5MB | 约为 LOD0 的 11% |
| **普通飞船** | `物体_01/02/03` | LOD1/2/3 | 递减 | 命名后缀递增 = 精度递减 |
| **武器/炮塔** | `物体_mod1~4` | 变体 | 相近 | 装备升级，非 LOD |

### 已知问题

- **Jericho 无畏舰不同 LOD 长度不一致**：`bigship_jer_2`(LOD2) 和 `bigship_jer`(LOD1) 比 `bigship_jer_03`(LOD0) 短一截 — 低精度 LOD 简化了延展结构（天线、炮管等）
- **旋转值不统一**：不同 LOD 可能有不同的坐标原点或导出变换，需要手动对齐
- **命名无统一规律**：`_01/_02` 在帝国是两部件、在 Jericho 可能是 LOD 编号，需逐模型确认

### 建议

导入时注意区分：查看 MDF 文件对应的 MSH 数量和多部件关系（如 `_03_back` + `_03_front`），低精度 LOD 通常文件名不含 `_03` 等大数字、且文件明显更小。

---

## 已知限制

| 限制 | 说明 |
|------|------|
| 材质槽-面映射 | MSH 不含材质-面映射，按序号 MDF块↔MSH编号分配 |
| DDS 兼容性 | 部分 RGBA DDS 可能需要 Honeyview/GIMP 查看 |
| Shader 还原 | 当前为手动预设映射，非 .fx 自动解析 |
| Cubemap | EnvSampler / ReflectionsSampler 暂未实现 |

---

## 与基础版共存

基础版 (`io_import_starconflict_msh`) 和 Pro 版可以**同时安装**：

- 基础版：File → Import → Star Conflict MSH (.mdl-msh\*)
- Pro 版：File → Import → Star Conflict MSH Pro (.mdl-msh\*)

两者互不冲突。

---

## 常见问题排查

### 贴图未找到（材质显示紫色/粉色）

**原因**：Texture Finder 在搜索路径中未找到匹配的贴图文件。

**排查步骤**：
1. 确认贴图已转换：检查 `scunpack\tex_universe_check\` 目录是否存在
2. 确认搜索路径正确：Preferences → Texture Search Paths 是否包含 `tex_universe_check`
3. 清除缓存重试：3D View → Sidebar → Star Conflict → **Clear Texture Cache**，再重新导入
4. 检查贴图扩展名：Preferences → Texture Extensions，确认 `.dds` 在列表中

> 💡 Texture Finder 使用 **递归搜索**（`os.walk`），只需指定顶层目录即可覆盖所有子文件夹。

### MDF 未找到（无材质创建）

**原因**：`find_mdf_for_msh` 未找到 MSH 对应的 MDF 文件。

**查找逻辑**：
1. 先在 MSH 文件**所在目录**查找 `<basename>.mdf`
2. 再**递归搜索** MDF Search Paths 中所有子文件夹

**常见场景**：
- MSH 和 MDF 在同一目录 → 无需配置，自动匹配
- MSH 和 MDF 在不同目录 → 在 Preferences 中添加 MDF 所在顶层目录
- 示例：MSH 在 `scunpack\output\models\weapons\`，MDF 也在同一目录 → 自动找到

### 搜索路径配置示例

以下配置覆盖本项目完整资源：

```
Preferences → Star Conflict MSH Importer Pro

Texture Search Paths:
  + <unpack_root>/tex_universe_check

MDF Search Paths:
  + <unpack_root>/output

Texture Extensions: .dds,.png,.tga
Auto-Link by Default: ☑
Default Shader Complexity: Full PBR Network
```

### 子文件夹搜索机制

| 搜索项 | 方法 | 说明 |
|--------|------|------|
| **贴图** | `os.walk()` 全量递归 | 扫描搜索路径下所有子目录，按 basename 匹配 |
| **MDF** | `os.walk()` 全量递归 | 扫描搜索路径下所有子目录，按文件名匹配 |

> ⚠️ 首次导入时会构建贴图索引（~11,628 个 DDS 文件），可能需要 5-10 秒。
> 索引会被缓存，后续导入直接使用缓存，速度极快。切换搜索路径后需手动清除缓存。
