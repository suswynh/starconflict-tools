# Star Conflict MSH Importer Pro — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender，**并自动根据 .mdf 材质定义文件创建材质和链接贴图**。

**区别于基础版**：基础版 (`io_import_starconflict_msh`) 仅导入网格，Pro 版增加了完整的材质管线。

> **v2.1** (2026-06) — 修复前向轴：MSH 前向 -Z→+Z，默认坐标系改为 Z-up→Y-up。导入即标准姿势。

**兼容版本**：Blender 4.2 LTS、Blender 5.0+

---

## 功能

| 功能 | 基础版 | Pro 版 |
|------|:---:|:---:|
| MSH 网格导入 | ✅ | ✅ |
| UV 坐标导入 | ✅ | ✅ |
| 批量目录导入 | ✅ | ✅ |
| 坐标系转换 | ✅ | ✅ |
| **MDF 材质解析** | ❌ | ✅ |
| **自动贴图搜索与链接** | ❌ | ✅ |
| **Principled BSDF 节点网络** | ❌ | ✅ |
| **按材质类型还原着色器** | ❌ | ✅ |
| **AO/Lightmap 混合** | ❌ | ✅ |
| **偏好设置面板** | ❌ | ✅ |
| **工具侧边栏** | ❌ | ✅ |

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

指向已转换的纹理目录。本项目转换产物位于：

```
D:\starconflict upcak\scunpack\tex_universe_check\
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
D:\starconflict upcak\scunpack\output\
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

| VBytes | 用途 |
|--------|------|
| 20 | 基础网格 |
| 24 | 扩展网格 |
| 28 | 场景物体 |
| 32 | 中型网格 |
| 36 | 大型网格 |
| 40 | 角色模型 |
| 44 | 装饰模型 |

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

### 贴图后缀映射

| MDF Sampler | 后缀 | Blender 节点 | 颜色空间 |
|------------|------|-------------|---------|
| DiffuseSampler | `_d` | Base Color | sRGB |
| NormalSampler | `_nm` | Normal Map (DX→GL fix) | Non-Color |
| SpecularColorSampler | `_sc` | Specular | sRGB |
| ColormapSampler | `_s1` | (染色遮罩) | sRGB |
| Diffuse2Sampler | `_glow` | Emission | sRGB |
| LightmapSampler | `_pdo` | AO混合 (R通道) | Non-Color |
| AmbOcclSampler | `_msk` | AO混合 (R通道) | Non-Color |

### 透明材质类型

以下 shader 类型自动设置 Alpha Blend：

`dyn_glass` `dyn_fresnel` `fresnel` `spaceship_shield` `decals` `ship_decals` `ship_static_decals` `flares` `laserbeam` `flatbeam` `scanner` `dyn_animated_mock` `animated_mock` `dyn_drone`

---

## 文件结构

```
io_import_starconflict_msh_pro/
├── __init__.py           # 插件入口 + bl_info + register/unregister
├── msh_parser.py         # MSH 二进制格式解析
├── msh_importer.py       # Blender 网格构建 + 导入编排
├── mdf_parser.py         # MDF 材质定义文件解析
├── texture_finder.py     # 多目录贴图搜索引擎
├── shader_presets.py     # 材质类型→Sampler映射 + 节点网络预设
├── material_builder.py   # Blender 材质/节点创建
├── properties.py         # Scene 级自定义属性
├── preferences.py        # AddonPreferences 全局设置
├── operators.py          # 导入操作符 + 工具操作符
└── panels.py             # UI 面板（导入菜单 + 侧边栏）
```

---

## 工作流

```
用户导入 MSH 文件
    │
    ▼
┌──────────────────┐
│ MSH 解析         │ → 顶点、UV、面索引
│ (msh_parser.py)  │
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
│ MDF 解析         │ → MaterialBlock 列表
│ (mdf_parser.py)  │
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
│ 材质构建         │ → Blender Material + 节点网络
│ (material_builder)│
└──────┬───────────┘
       │
       ▼
   ✅ 完成：网格 + UV + 材质 + 贴图
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
  + D:\starconflict upcak\scunpack\tex_universe_check

MDF Search Paths:
  + D:\starconflict upcak\scunpack\output

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
