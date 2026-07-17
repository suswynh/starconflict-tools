# Star Conflict MSH Importer Pro — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender，**并自动根据 .mdf 材质定义文件创建材质和链接贴图**。

**区别于基础版**：基础版 (`io_import_starconflict_msh`) 仅导入网格，Pro 版增加了完整的材质管线。

## 坐标转换管线 & 迭代历史

### 核心转换链

```
MSH(Y-up, -Z forward) → Z-flip → RotX(90°) bake → Blender Z-up
```

#### 4步完整推导

```
第1步 MSH原始数据
  └─ 坐标系: X=右, Y=上, Z=-前 (模型朝-Z方向)
  └─ 一个"正前方"的顶点: V_msh = (0, 0, -10)

第2步 Z-flip (build_mesh 中)
  └─ positions = [(x, y, -z) for x, y, z in positions]
  └─ V_zflip = (0, 0, 10) → +Z 变成前方
  └─ 修复前向轴: MSH 前向 -Z → +Z (与 Noesis v1.2 一致)

第3步 RotX(90°) 烘焙到网格数据
  └─ 矩阵: (x, y, z) → (x, -z, y)
  └─ V_bake = (0, -10, 0) → 模型在 Blender 中朝 -Y (后方)
  └─ 结果坐标系: X=右, Y=后, Z=上
  └─ ⚠️ 此步骤是数学必然——Y-up→Z-up 转换必然导致默认朝 -Y

第4步 Entity 旋转 (XML → Blender)
   └─ XML 存为 "x y z w" → entity.rot = (qx, qy, qz, qw)
   └─ 坐标变换矩阵 M = [[1,0,0],[0,0,1],[0,1,0]] 共轭下所有旋转轴取反
   └─ 公式: obj.rotation_quaternion = (qw, -qx, -qz, -qy)
   └─ 原因: M 是反射矩阵(det=-1)，共轭变换 M·R·M⁻¹ 将 RotX/Y/Z(θ) 全部映射为 RotX/Y/Z(-θ)
```

#### 公式推导细节

```
M = [[1,0,0],[0,0,1],[0,1,0]]  坐标变换: Hammer → Blender

M 共轭作用于旋转矩阵 R:
  M · RotX(θ) · M⁻¹ = RotX(-θ)     X轴旋转取反
  M · RotY(θ) · M⁻¹ = RotZ(-θ)     Y轴→Z轴, 取反
  M · RotZ(θ) · M⁻¹ = RotY(-θ)     Z轴→Y轴, 取反

四元数转换 (Hammer qx,qy,qz,qw → Blender w,x,y,z):
  qw 保持不变
  qx → -qx  (X轴取反)
  qy → -qz  (Y→Z轴, 取反)
  qz → -qy  (Z→Y轴, 取反)

最终公式: (qw, -qx, -qz, -qy)

验证: XML Rot="0.707 0 0 0.707" (RotX(90°) Hammer)
     → (0.707, -0.707, 0, 0) = RotX(-90°) Blender ✓
```

### 迭代修复记录

#### v2.5.2 (2026-07) — 旋转公式修正 (第二轮)

| 修复 | 文件 | 说明 |
|------|------|------|
| 旋转公式 `→ (qw,-qx,-qz,-qy)` | `level_assembler.py` ×4 | M共轭变换全部向量分量取反，修正所有轴旋转方向 |
| Lights/Decals 旋转同步修复 | `level_assembler.py` | 统一使用 M 共轭公式 |

#### v2.5.3 (2026-07) — 旋转公式修正 (第三轮·最终)

基于精确数学推导：坐标变换矩阵 `M = [[1,0,0],[0,0,1],[0,1,0]]` (det=-1，反射) 的共轭变换将对**所有三个轴的旋转取反**。因此之前只取反 qy（Z分量）或完全不取反的方案都只能覆盖部分情况。

**正确公式**: `obj.rotation_quaternion = (qw, -qx, -qz, -qy)`

##### 各版本公式验证

| 版本 | 公式 | RotX(90°)→RotX(-90°) | RotY(90°)→RotZ(-90°) | RotZ(90°)→RotY(-90°) |
|------|------|:---:|:---:|:---:|
| v2.4 | `(qw,qx,qz,qy)` | ✗ | ✗ | ✗ |
| v2.5.1 | `(qw,qx,qz,-qy)` | ✗ | ✓ | ✗ |
| v2.5.2 | `(qw,qx,qz,qy)` | ✗ | ✗ | ✗ |
| **v2.5.3** | `(qw,-qx,-qz,-qy)` | ✓ | ✓ | ✓ |

#### v2.5.4 (2026-07) — ClanShip_BaseGen 子类型解析

Dreadnoughtbattle 关卡中 `Def="ClanShip_BaseGen"` 实体使用抽象基类引用，实际子类型
由 Lua 定义中的 `gameplay_idx` 和实体命名约定 `main_<N>_team_*` 共同决定。

##### 问题

`def_resolver.resolve()` 对 `ClanShip_BaseGen` 精确命中直接返回 generator 模型，
从不检查子类型（ShieldGeneratorA / TurretPowerB / TicketTowerC）的不同 model。

| Entity Name | gameplay_idx | 子类型 | 正确模型 | 修复前 |
|-------------|:---:|------|------|:--:|
| main_1_team1_1 | 0 | ShieldGeneratorA | generator | ✅ (巧合) |
| main_2_team1_1 | 1 | TurretPowerB | cooler | ❌ |
| main_3_team1_1 | 2 | TicketTowerC | control_cab | ❌ |

##### 修复

| 修改 | 文件 | 说明 |
|------|------|------|
| 解析 `gameplay_idx = <N>` | `def_resolver.py` | 新增 `_RE_GAMEPLAY_IDX` 正则 + `_parent_gp_children` 映射 |
| 新增 `resolve_child_by_index()` | `def_resolver.py` | 按 index 查询子类型 model 路径 |
| `main_N` 命名约定匹配 | `level_assembler.py` | `main_1`→idx=0, `main_2`→idx=1, `main_3`→idx=2 |
| 容错回退 | `level_assembler.py` | 不匹配/无子类型/index越界时静默回退到原有策略 |

##### 工作原理

```
entity.Name = "main_2_team1_1", Def = "ClanShip_BaseGen"
  → re.match(r'^main_(\d+)_', name) → N=2 → index=1
  → def_map.resolve_child_by_index("ClanShip_BaseGen", 1)
  → _parent_gp_children["clanship_basegen"][1] = ("clanship_turretpowerb", "mapskit/.../cooler_imp")
  → 返回 cooler 模型路径 ✓
```

#### v2.5.5 (2026-07-11) — 角色模型 UV1 偏移修正

VBytes=40/32 多种 flag 的顶点布局中 UV1 偏移量修正：

| 修复 | (VBytes, flag) | 旧偏移 | 新偏移 | 影响模型 |
|------|---------------|--------|--------|----------|
| skinned character | (40, 0x10) | 24 | **16** | fed_mercenary_man |
| static character | (40, 0x13) | 24 | **20** | loader, reptile_01 |
| mixed mesh | (32, 0x0F) | 20 | **16** | fed_mercenary_tool |

根因：VBytes=40 的 skinned 和 static 角色使用不同顶点布局（sentinel 7FFF0000 位置不同），
原统一返回偏移 24 导致读取全零数据，UV 显示为单点/单线。

##### 各 flag 顶点布局对比

```
flag=0x10 (skinned): [0]Pos(12)|[12]Data(4)|[16]UV1(8)|[24]Sentinel|[28]Data(4)|[32]UV2(4)
flag=0x13 (static):  [0]Pos(12)|[12]Data(8)|[20]UV1(8)|[28]Data(4)|[32]UV2(8)
flag=0x0F (mixed):   [0]Pos(12)|[12]Data(4)|[16]UV1(8)|[24]Sentinel|[28]Data(4)
```

#### v2.5 (2026-07-06) — 环境设置/Decals/Def映射

环境设置应用（World HDRI/Mapping/clip）、Lights实体→Blender灯光、decals.dat解析导入、Def实体映射引擎（LuaJIT字节码）、mapskit/models递归搜索、去重逻辑、tree透明修复、进度条优化。

#### v2.4 (2026-07) — 关卡一键组装

关卡一键组装 + 批量自动放置 + Glass材质。Shader Type 别名字典（dyn_*→静态归一化去重），scene.xml 关卡解析器（Entity 批量导入+自动世界坐标放置+Inheritance 继承链），批量导入支持自动 scene.xml 位置查找，dyn_glass 材质参数驱动渲染。

#### v2.3 (2026-07) — UV偏移修复

修复 VB=28 flag=0x0005 天空盒 UV 偏移：offset 16→20，修复 UV 解析为 (0,0)→(0,1) 单线问题。

#### v2.2 (2026-06) — 材质库/UV2/Collection

材质静态映射库、UV2 Lightmap、Collection 全层级树、LOD 命名修复。

#### v2.1 (2026-06) — 前向轴修复

修复前向轴：MSH 前向 -Z→+Z，默认坐标系改为 Z-up→Y-up。

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

### Map 材质映射（v3.0 更新）

Map 场景下 MSH 数量远超 MDF block 数量，材质映射由 **MSH 头部 `material_block_index`** 自动解决：

- `.mdl-msh` 文件头 `[0x00]` 的 uint32 即为材质 block 索引
- 每个 MSH 自动匹配正确的 MDF material block，无需手动校验
- 超出 MDF block 范围时 fallback 到 modulo 散布
- 导入日志 `[header]` 标记表示材质来自 MSH 头部

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

##### 透明材质遮罩贴图 (ColormapSampler)

部分半透明材质（如空气墙、护盾、传送门）额外使用 `ColormapSampler` 贴图，作用如下：

| 通道 | 作用 | 说明 |
|------|------|------|
| **RGB** | 颜色调制 | `albedo.rgb *= cm.rgb` — 与漫反射纹理相乘着色 |
| **A** | 透明度混合 | `albedo.a = cm.a` — 控制 Alpha Blending 透明度 |

> 示例: `gate_mask02.dds` 配合 `gate_scroll.dds` 用于空气墙效果
> - DiffuseSampler: `gate_scroll.dds`（基础发光卷轴图案）
> - ColormapSampler: `gate_mask02.dds`（RGB=色调遮罩, A=透明过渡）

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

## MSH 与 MDF 映射关系

每个 `.mdl-mshXXX` 子网格文件需要找到 MDF 中对应的 **material block** 才能获取材质定义。映射关系根据场景类型不同而有所区别。

### 飞船/武器模型（非 map 场景）

MSH 数量和 MDF block 数量通常一致或接近。映射策略：

```
MSH 文件名        →  MDF block
─────────────────────────────
plasma_gun.mdl-msh000  →  blocks[0]   (匹配 msh_index=0 或 MSH头部索引)
plasma_gun.mdl-msh001  →  blocks[1]   (匹配 msh_index=1 或 MSH头部索引)
plasma_gun.mdl-msh002  →  blocks[2]   (匹配 msh_index=2 或 MSH头部索引)
```

**查找优先级**：

| 优先级 | 策略 | 说明 |
|:---:|------|------|
| **1** | MSH 头部 `material_block_index` | `.mdl-msh` 文件头 `[0x00]` uint32，**authoritative（最高优先级）** |
| **2** | 1:1 索引匹配 | `msh_index == block_index`（范围内时直接对应） |
| **3** | Modulo 散布 | `blocks[msh_index % len(blocks)]`（超出范围时兜底） |

> LOD 模型的 block 数量可能与主模型不同——低精度 LOD 可能合并多个 material block。此时以 MSH 头部索引为准。

### 关卡 Map 场景（is_map=True）

Map 场景的 MSH 子网格数量（数十~数百个）远超 MDF block 数量（通常 10~50 个）。

MSH 头部 `[0x00]` 的 `material_block_index` 是关键突破点——**每个 MSH 文件都内嵌了正确的材质 block 索引**，使得 1:1 覆盖表不再必要：

```
例: pvp_omega/map.mdl-msh000~msh187 (188 个子网格) ←→ map.mdf (约 20 个 material block)

MSH 文件名            [0x00]  →  MDF block
────────────────────────────────────────
map.mdl-msh012  →     5       →  blocks[5]   ✓ (来自 MSH 头部)
map.mdl-msh055  →     2       →  blocks[2]   ✓ (来自 MSH 头部)
map.mdl-msh120  →     12      →  blocks[12]  ✓ (来自 MSH 头部)
```

**查找优先级**：

| 优先级 | 策略 | 说明 |
|:---:|------|------|
| **1** | MSH 头部 `material_block_index` | **authoritative**，每个 MSH 内嵌正确索引 |
| **2** | 1:1 索引匹配 | `msh_index < len(blocks)` 时直接对应 |
| **3** | **Modulo 散布** | `blocks[msh_index % len(blocks)]`，兜底 |

**效果**：
- Map 场景（如 pvp_omega，188 msh / 20 blocks）：**每个 msh 自动找到正确的材质**，无需手动校验
- 普通模型（武器/飞船 1~3 msh）：行为不变，block 索引与之前一致
- 导入日志标记 `[header]` 表示材质来源为 MSH 头部索引

> **v3.0 变更**：MSH 头部 `[0x00]` 原被误作 version 丢弃，现已修正为 `material_block_index`。静态映射覆盖表（`material_mapping_db.json` 和 `material_references/`）已移除。

---

## 文件格式详解

Star Conflict (Hammer Engine) 使用以下文件格式。Pro 版插件直接处理 `.mdl-msh` 和 `.mdf`，其他格式由 `mdl_tools/` 工具链支持。

### 模型与网格

| 文件 | 魔数/识别 | 内容 | 典型大小 | 工具 |
|------|----------|------|----------|------|
| **`.mdl-mshXXX`** | 小端序二进制 | 渲染网格：顶点位置、UV1/UV2、面索引、material_block_index | 0.1~16 MB | Pro 插件 |
| **`.mdl-hdr`** | 无魔数，80 字节固定 | 模型轴对齐包围盒 (AABB Min/Max)，用于视锥剔除和 LOD 切换 | 80 B | `mdl_hdr_parser.py` |
| **`.mdl-skl`** | 二进制 | 骨骼数据（骨骼名称、父子层级、绑定姿态矩阵） | 256 B~2 KB | 未实现 |
| **`.mdl-geo`** | 二进制 | 简化碰撞/LOD 代理网格（仅位置，无 UV/法线） | 0.5~150 KB | `mdl_geo_parser.py` |

**MSH VBytes 变体**（顶点字节步长，决定顶点格式）：

| VBytes | 用途 | UV1 | UV2 (Lightmap) |
|:---:|------|:---:|:---:|
| 20 | 基础网格 | ✅ | ❌ |
| 24 | 扩展网格 | ✅ | ❌ |
| 28 | 场景物体 | ✅ | ❌ |
| 32 | 中型网格（bigship/map） | ✅ | ✅ |
| 36 | 大型网格 | ✅ | ✅ |
| 40 | 角色模型 | ✅ | ✅ |
| 44 | 装饰模型 | ✅ | ✅ |
| 48 | 扩展格式 | ✅ | ✅ |

### 材质与贴图

| 文件 | 格式 | 内容 | 工具 |
|------|------|------|------|
| **`.mdf`** | 文本（类 C 语法） | 材质定义：`material <shader_type> { Sampler "path"; params; pins }` | `mdf_parser.py` |
| **`.tfh`** | 二进制 | Targem 纹理头：格式、尺寸、mip 链偏移表 | `tex_targem_py.py` |
| **`.tfd`** | 二进制 | Targem 纹理数据：DXT1/3/5/RGBA 压缩像素 | `tex_targem_py.py` |
| **`.dds`** | 标准 DDS | 转换后的纹理（`batch_tex_all.py` 输出） | Blender 内置 |

**MDF 材质块结构**：

```hlsl
material object_norm                     // shader_type — 对应 .mmp 预设
{
    DiffuseSampler "path\texture_d"      // 采样器 = 贴图通道
    NormalSampler "path\texture_nm"
    AmbOcclSampler "path\texture_msk"
    UserParam2_Float4 ( 1 1 0 0 )        // 浮点参数（含义由 pins 决定）
    pins                                 // 功能开关（编译时宏）
    {
        Type 5                           // Type=5 → PD_OCCL (PDO光照)
        User2 1                          // User2=1 → BUMP_DETAIL
        User3 1                          // User3=1 → ALBEDO_DETAIL
    }
}
```

#### Pins 控制位（功能开关）

每个 material block 的 `pins { ... }` 块控制着色器编译时宏开关。以下是从 `.mmp` 材质预设中提取的完整语义（按 material type 分组）：

**object / object_norm**：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `User0` | 1 | `ALPHA_TEST` — 启用 Alpha Test 裁剪 |
| `User1` | 1 | `GLOWING` — 启用自发光（Diffuse2Sampler → Emission） |
| `User2` | 1 | `BUMP_DETAIL` — 启用细节法线叠加（DetailSampler） |
| `User3` | 1 | `ALBEDO_DETAIL` — 启用细节漫反射混合（UserSampler1） |
| `User4` | 1 | `Uniform Specular` — 使用 UserParam0.rgb 作为统一高光色 |
| `User5` | 1 | `Sky Opacity Pass` — 天空不透明度通道 |
| `User6` | 1 | `Ice Material` — 冰材质模式 |
| `User8` | 1 | `Double Sided` — 双面渲染 |
| `Type` | 0 | 标准模式 |
| `Type` | 1 | `EXTRA_MASKS` — 第二套 UV 额外遮罩 |
| `Type` | 5 | `PD_OCCL` — PDO 预计算定向遮蔽（lightmap UV2） |

**ship_hull**：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `User0` | 1 | AlphaTest |
| `User1` | 1 | Glowing |
| `User2` | 1 | `DYEING` — 染色/涂装模式（armor pattern） |
| `User3` | 1 | Highlights — 高亮模式 |
| `User6` | 1 | Dissolving — 溶解效果 |
| `User6` | 4 | Engineer Shield — 工程师护盾 |
| `User8` | 1 | Crystal — 水晶材质 |

**animated_mock / dyn_animated_mock**（空气墙、护盾、传送门）：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `User1` | 0 | Blend Alpha（标准半透明） |
| `User1` | 1 | Additive（叠加混合） |
| `User1` | 2 | Code Driven Alpha（脚本控制透明度） |
| `User1` | 3 | Code Driven Transparency（脚本控制透明） |
| `User1` | 4 | Alpha from Diffuse（透明度来自漫反射 alpha 通道） |
| `User2` | 1 | Cull None（双面渲染，关闭背面剔除） |
| `User4` | 1 | Env — 启用环境立方体贴图 |
| `User6` | 1 | Appearance — 出现/消失动画效果 |
| `User7` | 1 | Sync Animation — 与 AnimatedEntity 同步（dyn_animated_mock） |
| `User8` | 1 | Fresnel — 菲涅尔效果 |

**sky**（天空层）：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `User0` | 0 | Base — 基础层 |
| `User0` | 1 | AlphaBlend — 透明度混合 |
| `User0` | 2 | Additive — 叠加混合（星云层最常用） |
| `User0` | 3 | Modulate — 调制混合 |
| `User1` | 1 | LAYER2 — 第二层纹理叠加 |
| `User2` | 1 | COLORMAP — 立方体贴图环境光 |
| `User3` | 1 | STATIC — 静态（不跟随相机旋转） |

**skybackground**（天空背景物体）：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `User0` | 0 | Base |
| `User0` | 1 | AlphaBlend |
| `User0` | 2 | Additive |
| `User0` | 3 | SOFT_DYN_LIT — 软动态光照 |
| `User1` | 1 | BUMP — 法线贴图 |
| `User2` | 1 | COLORMAP — 立方体贴图 |
| `User3` | 1 | GLOW — 自发光 |

**decals**（贴花）：

| Pin | 值 | 效果 |
|-----|:---:|------|
| `Type` | 0 | Alpha 混合 |
| `Type` | 5 | Alpha on PDO |
| `Type` | 6 | Alpha-Glow |
| `User0` | 0 | Flat（平贴） |
| `User0` | 1 | Bump（法线贴花） |
| `User0` | 2 | Parallax（视差贴花） |

#### UserParam 参数说明

MDF 中的 `UserParamN_Float4` 参数在不同材质类型下含义不同，由 pins 决定。以下是常见用法：

**object.fx**：

| 参数 | 上下文 | 含义 |
|------|--------|------|
| `UserParam0_Float4.rgb` | User4=1 (Uniform Specular) | 统一高光颜色 |
| `UserParam0_Float4.w` | 默认模式 | Gloss 因子（被 _msk.b 覆盖时忽略） |
| `UserParam0_Float4.x` | UNIFORM_ALBEDO | 统一不透明度 alpha |
| `UserParam1_Float4.rgb` | UNIFORM_ALBEDO | 统一漫反射颜色 |
| `UserParam2_Float4.xy` | 默认 | UV1 tiling (u, v)，值为 (1,1) 时无效 |
| `UserParam2_Float4.z` | DYN_LIT | 雾密度 (1 - fog) |
| `UserParam2_Float4.xy` | SHIP_HULL | UV tiling (u, v)，非 1 时启用 Mapping 节点 |
| `UserParam3_Float4.x` | BLEND | base UV tiling |
| `UserParam3_Float4.y` | BLEND | second UV tiling |
| `UserParam3_Float4.zw` | BL2_DETAIL | detail UV tiling (mat1, mat2) |
| `UserParam3_Float4.zw` | DYN_LIT | UV 滚动速度 (u speed, v speed) |
| `UserParam3_Float4.rgb` | ALBEDO_MULT | 漫反射颜色乘法因子 |
| `UserParam4_Float4.xy` | BL2_DETAIL | detail-albedo 混合因子 (mat1, mat2) |
| `UserParam4_Float4.zw` | BL2_DETAIL | detail-bump 混合因子 (mat1, mat2) |

**animated_mock.fx**（空气墙/护盾 UV 动画）：

| 参数 | 作用 |
|------|------|
| `UserParam0_Float4.x` | 发光强度倍增因子 |
| `UserParam0_Float4.y` | Fresnel 光泽度 (gloss) |
| `UserParam1_Float4` | 离散动画参数：`(1e6, 1, 1e6, 1)` 为典型值，控制 UV 跳帧 |
| `UserParam2_Float4.xy` | UV 静态偏移 (u, v) |
| `UserParam2_Float4.z` | UV Y 方向滚动速度（如 0.1 = 慢速向上滚动） |
| `UserParam2_Float4.w` | UV 旋转速度（弧度/秒） |
| `UserParam4_Float4` | UV 全局动画偏移 (xyzw 四通道) |
| `CodeParam0[0].x` | Code Driven Alpha — 脚本控制透明度 (0~1) |
| `CodeParam0[0].y` | Appearance time — 出现/消失动画时间 (0~1) |
| `CodeParam0[0].z` | Transparency factor — 透明因子 |
| `CodeParam0[0].w` | Anim time — 动画时间覆盖（非 GlobalTime） |
| `CodeParam0[1].xyz` | Scale — 缩放 (SCALING 模式) |

**sky.fx**：

| 参数 | 作用 |
|------|------|
| `UserParam0_Float4.x` | UV 旋转速度 (× GlobalTime.y × 2π) |
| `UserParam0_Float4.y` | UV X 方向滚动速度 |
| `UserParam0_Float4.z` | SIMPLE_FOG 雾混合因子 |
| `UserParam0_Float4.w` | GLOW 发光强度 (× detailLum × 32) |
| `UserParam1_Float4.x` | HIGH_RANGE_TEXTURE 亮度倍率 |
| `UserParam2_Float4.x` | UV Y 方向滚动速度 |
| `UserParam2_Float4.y` | LAYER2 UV X 方向滚动速度 |

### 物理与场景

| 文件 | 魔数 | 内容 | 工具 |
|------|------|------|------|
| **`.mdp`** | `TCF STATIC_PHYS` | TCF 碰撞物理网格（含嵌入 ASCII 材质标签如 `#NO_BONE#`、`Metal`） | `mdp_parser.py` |
| **`.sot`** | `OT02` | 场景对象表：每条 64 字节，含变换参数 + 8×uint8 标志 + 子索引层级 | `sot_parser.py` |
| **`.mdl-zon`** | Maya 形状名（ASCII 头） | 触发/杀伤区域（立方体、球体），含纹理路径和三角带顶点 | `mdl_zon_parser.py` |

### 场景与配置

| 文件 | 格式 | 内容 |
|------|------|------|
| `scene.xml` | XML | 关卡入口：EnvSettings（关卡名+环境设置名）、Entity 放置列表、出生点、信标 |
| `.map` | 文本（1行） | 地图资源指向：`mapskit\maps\{area}\{mapname}\map` |
| `envsetting.lua` | 二进制+Lua | 天空背景路径、太阳方向/颜色、雾效、粒子效果 |
| `.mmp` | 类 C 宏 | 材质预设：定义 shader_type 到 .fx 着色器 technique 的映射和 pins 语义 |
| `.fx` | HLSL | 着色器源码：顶点/像素着色器，含材质参数声明和渲染逻辑 |

### 典型关卡文件组合

以 `federation/pvp_omega` 为例，一个完整关卡涉及的文件：

```
output/
├── levels/federation/pvp_omega/
│   ├── scene.xml              ← 入口：关卡名、实体放置
│   ├── pvp_omega.map          ← 指向 mapskit/maps/.../map
│   └── decals.dat             ← 贴花数据（可选）
├── levels/envsettings/pvp_omega/
│   ├── envsetting.lua         ← 天空背景路径、光照参数
│   ├── irradiance*.tfh/tfd    ← IBL 辐照度
│   └── specularity*.tfh/tfd   ← IBL 镜面反射
├── mapskit/maps/federation/pvp_omega/
│   ├── map.mdf                ← 关卡材质（含 material sky 块）
│   ├── map.mdl-msh*           ← 关卡网格 (~188 个子网格)
│   ├── map.sot                ← 场景物体层级
│   ├── map.mdl-geo            ← 简化碰撞几何
│   ├── map.mdp                ← TCF 碰撞物理
│   └── lightmaps/             ← 预计算光照贴图
├── mapskit/backgrounds/       ← 天空贴图（多云、大气、地表等）
├── models/illumination/       ← 灯光模型
└── models/objects/constructor/decal/  ← 贴花模型
```

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
├── name_resolver.py         # 命名冲突检测 + Collection 层级生成
├── properties.py            # Scene 级自定义属性
├── preferences.py           # AddonPreferences 全局设置
├── operators.py             # 导入操作符 + 工具操作符
└── panels.py                # UI 面板（导入菜单 + 侧边栏）
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

### 贴图搜索机制 — 三层渐进匹配

`texture_finder.py` 使用三层递进策略，按精确度降级查找贴图：

```
MDF路径: mapskit\maps\textures\asteroid_hole01_d

Tier 1 — 精确路径拼接 (O(1) per dir)
  对每个搜索目录 × 每个扩展名:
    search_dir + sampler_path + ext → os.path.isfile
  例如: tex_universe_check/mapskit/maps/textures/asteroid_hole01_d.dds
  适用: 用户保留了原始目录结构（最常见情况）

Tier 2 — 后缀渐进匹配
  从 sampler_path 逐级剥离前导目录段:
    "maps/maps/textures/asteroid_hole01_d"
    "textures/asteroid_hole01_d"
    "asteroid_hole01_d"
  对每个后缀在搜索目录下 os.walk 匹配路径结尾，多候选时按相似度评分选最优。
  适用: 目录结构被重新组织或中间层级被打散

Tier 3 — basename 兜底 + 相似度评分
  仅用文件名匹配。当同一 basename 存在于多个目录时，按后缀相似度评分选择:
    - MDF路径 segments 与候选路径 segments 从末尾逐段比较
    - 每段匹配 +100 分，后2段作为子串出现 +10 分
    - ≤2 段匹配时，路径更浅的候选轻微优待
  适用: 所有贴图被塞在同一个扁平或任意命名的目录下
```

**相似度评分示例**：

| MDF 路径 | 候选路径（相对） | 匹配段数 | 分数 | 选中 |
|----------|-----------------|:---:|-----|:---:|
| `maps\maps\textures\asteroid_hole01_d` | `mapskit/maps/textures/asteroid_hole01_d` | 4 | 410 | ✅ |
| `maps\maps\textures\asteroid_hole01_d` | `mapskit/maps/models/energy_geiser/asteroid_hole01_d` | 1 | 97.5 | |
| `foo\bar\textures\asteroid_hole01_d` | `mapskit/maps/textures/asteroid_hole01_d` | 2 | 210 | ✅ |
| `foo\bar\asteroid_hole01_d` | `mapskit/maps/textures/asteroid_hole01_d` | 1 | 98.0 | ✅ |
| `foo\bar\asteroid_hole01_d` | `mapskit/maps/models/energy_geiser/asteroid_hole01_d` | 1 | 97.5 | |

> ⚠️ 首次导入时会构建贴图索引（~11,628 个 DDS 文件），可能需要 5-10 秒。
> 索引会被缓存，后续导入直接使用缓存，速度极快。切换搜索路径后需手动清除缓存。

---

## 完整关卡导入

导入一个完整的关卡场景（如 `pvp_omega`）时，`maps/` 目录下的模型仅是关卡主体（地形、建筑、大型残骸等）。以下三类资源分布在其他目录中，**批量导入时须一并导入**：

### 关卡资源分布（以 `federation/pvp_omega` 为例）

```
output/
│
├── mapskit/maps/{area}/{mapname}/          ← 关卡主体模型（地形、碰撞、建筑）
│   ├── map.mdl-msh*        # 关卡地形/建筑网格 (~N个子网格)
│   ├── map.mdf             # 关卡材质定义（含 material sky/skybackground 块）
│   ├── map.sot             # 场景物体层级树
│   ├── map.mdl-geo         # 关卡几何数据
│   ├── lightmaps/          # 预计算光照贴图
│   │   └── station_*.tfh/tfd
│   └── models/             # 关卡本地子模型（可选）
│
├── mapskit/backgrounds/                   ← 天空背景贴图
│   ├── misc/               # 通用背景元素
│   │   ├── temperate_surface_det.tfh/tfd  # 地表
│   │   ├── mainlands_cm.tfh/tfd          # 大陆立方体贴图
│   │   ├── clouds_*.tfh/tfd              # 云层（diffuse/cubemap/normal）
│   │   └── ...
│   ├── open_world/federation/            # 阵营专属背景
│   │   ├── atmosphere.tfh/tfd            # 大气层
│   │   ├── fed_*.mdl-msh*               # 背景3D模型（加勒比、前线、流明）
│   │   └── ...
│   ├── textures/           # 背景公共贴图
│   │   ├── fed_station_0*.tfh/tfd       # 联邦空间站
│   │   ├── stars*.tfh/tfd               # 星空贴图
│   │   ├── asteroids_*.tfh/tfd          # 小行星
│   │   └── freespacestars_cm.tfh/tfd    # 星空立方体贴图
│   └── area3/s1420_ceres3/              # 跨区域共享背景
│       └── ceres_aura.tfh/tfd           # ceres 行星光环
│
├── models/                                ← 公共模型库（需额外导入！）
│   ├── illumination/       # 模拟灯光模型
│   │   ├── rectlight.mdl-msh*           # 矩形灯光
│   │   ├── fed_dread_lights*.mdl-msh*   # 联邦无畏舰灯光组 (1~6)
│   │   ├── rotrig*.mdl-msh*             # 旋转信号灯
│   │   ├── runway.mdl-msh*              # 跑道引导灯
│   │   └── drillbeam.mdl-msh*           # 钻探光束
│   ├── objects/constructor/decal/        # 贴花模型
│   │   └── constructor_decal_0*.mdl-msh*
│   └── modules/decorative/dome/          # 穹顶装饰模型
│
├── levels/{area}/{mapname}/               ← 场景定义文件
│   ├── scene.xml           # 场景入口（EnvSettings 指定关卡名）
│   └── {mapname}.map       # 地图资源指向
│
├── levels/envsettings/{mapname}/          ← 环境设置
│   ├── envsetting.lua      # 天空背景路径、太阳参数、雾效
│   ├── irradiance*.tfh/tfd # IBL 辐照度立方体贴图
│   └── specularity*.tfh/tfd# IBL 镜面反射立方体贴图
│
└── materials/                              ← 材质预设定义
    ├── sky.mmp              # material sky 渲染 technique 定义
    └── skybackground.mmp    # material skybackground 渲染 technique 定义
```

### 天空盒（大圆球）的特殊说明

NinjaRipper 截帧中看到的大圆球天空盒**不是外部 .mdl-msh 文件**。它是 Hammer Engine 的内置几何体 `skydome`，由引擎在 GPU 端动态生成球体顶点。

```
sky.mmp:  OVERDRAW_GENERAL_VS( skydome, sky, ... )
```

**贴图来源**：`map.mdf` 中 `material sky` / `material skybackground` 块通过 `DiffuseSampler` / `ColormapSampler` 路径引用 `mapskit/backgrounds/` 下的贴图。pvp_omega 关卡有 14 层天空材质（地表、大陆、云影、云层、大气、行星光环、空间站等）。

> 在 Blender 中还原：手动创建一个大球体，赋予从 `map.mdf` 解析出的多层叠加材质。

### 定位关卡依赖的通用方法

1. **读取 `map.mdf`**：提取所有 `material sky` / `material skybackground` 块中的 `DiffuseSampler`、`ColormapSampler`、`NormalSampler` 路径 → 这些指向 `mapskit/backgrounds/` 下的天空资源
2. **读取 `scene.xml`**：查找 `<Entity Def="Lights_*">` 和 `<Entity Def="...">` — 引擎内置实体（如 `Lights_Flare`、`Lights_BeamWithHalo`）无外部模型文件
3. **检查 `envsetting.lua`**：包含 `sky;mapskit\backgrounds\...` 指向天空背景目录
4. **遍历 `models/` 目录**：灯光模型在 `illumination/`，贴花模型在 `objects/constructor/decal/`，共享场景模型在 `mapskit/maps/models/`

### Pins 参数速查

MMP 材质预设中定义的 pins 语义，控制天空渲染的混合模式和功能开关：

**material sky (`sky.mmp`)**：
| Pin | 值 | 含义 |
|-----|-----|------|
| User0 | 0 | Base 层级 |
| User0 | 1 | AlphaBlend 混合 |
| User0 | 2 | Additive 叠加（最常用，如星云层） |
| User0 | 3 | Modulate 调制 |
| User1 | 1 | LAYER2 启用第二层纹理 |
| User2 | 1 | COLORMAP 启用立方体贴图 |
| User3 | 1 | STATIC 静态（相机不跟随旋转） |

**material skybackground (`skybackground.mmp`)**：
| Pin | 值 | 含义 |
|-----|-----|------|
| User0 | 0-3 | 同 sky（base/alphablend/additive/soft-dynlight） |
| User1 | 1 | BUMP 启用法线贴图 |
| User2 | 1 | COLORMAP 启用立方体贴图 |
| User3 | 1 | GLOW 启用自发光 |

---

## v3.0 迭代记录（2026-07）

### FX UV 通道发现

**VBytes=28 + flag=0x0E** 的 airwall/gate 模型（animated_mock 材质）在顶点末尾 4 字节（offset 24-27）包含**第二套 UV**，以 `uint16_unorm` 格式存储。之前被误认为无效 tail bytes。

```
VBytes=28 flag=0x0E 顶点布局:
  offset 0-11:  Position (3×float32)
  offset 12-15: Packed normal
  offset 16-23: UV1 (2×float32) → gate_scroll 采样
  offset 24-27: UV2 (2×uint16_unorm) → gate_mask02 采样  ← 新发现！
```

`animated_mock.fx` 着色器验证：
```hlsl
VS_INPUT: float2 Tex0 : VTEXCOORD0;  // UV1 → gate_scroll
          float2 Tex1 : VTEXCOORD1;  // UV2 → gate_mask02
PS: baseUv = uv0.xy;  cmUv = uv0.zw;
    albedo.a = cm.a;  // gate_mask02 alpha → 透明度
```

对此 UV 层命名为 **FX**（区别于场景模型的 lightmap UV2），导入后 mesh 拥有三个 UV 层：

| UV 层名 | 来源 | 材质使用者 |
|---------|------|-----------|
| `map1` | UV1 | DiffuseSampler 等通用贴图 |
| `lightmap` | UV2 (所有模型) | LightmapSampler（PDO 光照） |
| **`FX`** | UV2 (VBytes=28 flag=0x0E) | ColormapSampler（gate_mask02） |

### 材质系统改进

- **ColormapSampler Alpha 双通道**：gate_mask02 的 alpha 常为纯白，添加 RGB→BW 备选通道，通过 Mix 节点切换
- **系数调控节点**：所有已连接的 Alpha / Roughness / Metallic / Emission Strength 前自动插入 `Value→Multiply` 节点，方便在 Shader Editor 中调控
- **内发光材质**：无 ColormapSampler 的 animated_mock（如 inner_glow）使用 Diffuse RGB→BW→Alpha + Emission=1.0
- **透明阴影**：FX 材质统一使用 `HASHED`（抖动）阴影方法

### 贴图搜索三层匹配

`texture_finder.py` 重构为三层渐进匹配（详见贴图搜索机制章节），解决同名 basename 在多个目录存在时的匹配错误。

### 静态映射覆盖表移除

MSH 头部 `[0x00]` 确认为 `material_block_index`（非 version），每个 MSH 自动匹配正确材质。`material_mapping.py`、`material_mapping_db.json`、`material_references/` 已移除。

### msh2fbx 同步

`msh2fbx.c` 同步支持 VBytes=28 flag=0x0E 的 UV2 提取，写入 FBX UV layer 1。

---

## v2.4 新增 — 关卡一键组装与场景导入

### 关卡文件结构

Star Conflict 关卡由**两层数据**组成：

```
unpack_root/
├── levels/<area>/<map>/          ← 关卡逻辑层
│   ├── scene.xml                 ← ⭐ 入口：实体列表、Model引用、变换数据
│   ├── pathfinding.nav           ← 寻路数据
│   └── irradiance*.tfh/tfd       ← IBL 光照数据（可选）
│
├── mapskit/maps/<area>/<map>/    ← 关卡场景层
│   ├── *.mdl-msh*                ← 静态场景网格（命名多变）
│   ├── *.mdf                     ← 关卡材质
│   ├── map.sot / ship.sot        ← 物体/舰船摆放表
│   ├── lightmaps/                ← 预计算光照贴图
│   └── ...
│
└── models/objects/...            ← 外部引用的独立模型
    └── trees/                    ← 树木、装饰等
```

### scene.xml 实体类型

```xml
<!-- 类型1: ModelEntity — 带 Model 路径引用（可自动解析导入） -->
<Entity Name="ModelEntity152" Def="ModelEntity"
        Pos="586.497 9.182 -598.117"
        Model="mapskit\maps\...\allidium_glass_02" />

<!-- 类型2: Def 实体 — 引擎内建类型（无 Model 路径，需额外映射） -->
<Entity Name="TurretBig1" Def="Alidium_TurretBig"
        Pos="246.042 -165.773 -22.604"
        Rot="0.000 0.707 0.000 0.707" />
```

### 一键组装（File → Import → Star Conflict Level）

选择 `scene.xml` 即可一键导入完整关卡：

1. 解析 scene.xml → 提取所有 ModelEntity（带 `Model="..."`）
2. 解析 Inheritance 继承链 → 递归加载子场景
3. 在 unpack_root 中解析 Model 路径 → 查找 `.mdl-msh*` 文件
4. 批量导入所有模型 + 自动应用 Pos/Rot 世界变换
5. 自动导入 `mapskit/maps/<area>/<map>/` 下的所有静态场景网格
6. 按 NameResolver 规则组织 Blender Collection 层级
7. 材质自动去重（MaterialRegistry）

**坐标系转换**：
- Hammer 引擎：Y-up → Blender：Z-up
- 位置：(hx, hy, hz) → (hx, hz, hy)
- 旋转：四元数 (qx, qy, qz, qw) → (qw, qx, qz, qy)

### 批量导入增强 — Auto-Place

批量导入新增 **Auto-Place from scene.xml** 选项（默认开启）：

```
导入 mapskit/maps/.../allidium_yard/ 目录
  → 自动扫描 levels/ 下所有 scene.xml
  → 建立模型名 → 位置映射表
  → 每个 MSH 导入后自动放置到世界坐标
```

无需手动选择 scene.xml，批量导入时自动生效。

### dyn_glass 材质

`dyn_glass` shader 无贴图采样器，完全由 MDF 参数驱动：

| 参数 | 含义 | 默认值 |
|------|------|:---:|
| `UserParam0_Float4` | 玻璃着色 (RGB) | `(0.174, 0.174, 0.174)` |
| `UserParam0_Float[0]` | Alpha 不透明度 | `0.5` |
| `UserParam1_Float4` | Fresnel 参数 | `(0.00011, 0.192, 0.636)` |

Principled BSDF 设置：Transmission=1.0, Blend Mode=Alpha Blend, Shadow=Hashed。

### 关卡组装限制

- **Def 实体**（`VitalPoint_*`、`Character_*`、`Debris_*` 等）模型嵌入引擎，解包数据中不存在 → 无法自动导入
- **灯光/特效实体**（`Lights_*`、`Effects_*`）无对应几何体 → 跳过
- **逻辑实体**（`Logic_Spawn*`、`Sound_*`、`Helpers_*`）仅游戏逻辑 → 跳过
