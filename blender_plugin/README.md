# Star Conflict MSH Importer — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender。

**兼容版本**：Blender 4.2 LTS、Blender 5.0+
**Compatible with**: Blender 4.2 LTS, Blender 5.0+

> **v2.6** (2026-07-17) — Lightmap weak-reference material merging: core materials reduced 39%, cross-scene material sharing; full Blender 5.0 compatibility
> **v2.5.5** (2026-07-11) — Character model UV1 offset fixes, AlphaTest pin-driven transparency, static scene path narrowing
> **v2.5.4** (2026-07) — ClanShip_BaseGen subtype resolution (ShieldGeneratorA/TurretPowerB/TicketTowerC)
> **v2.5.3** (2026-07) — Rotation formula fix round 3: M conjugation negates all vector components
> **v2.4** (2026-07) — Pro Edition: one-click level assembly (scene.xml), batch auto-placement, Glass material, Shader Type aliases, experimental light import
> **v2.2** (2026-07) — VB=28 flag=0x0005 skybox UV offset fix (Basic + Pro)
> **v2.1** (2026-06) — Forward axis fix: MSH forward -Z→+Z, coordinate system Z-up→Y-up
> **Pro Edition** (`io_import_starconflict_msh_pro`) released: MDF material parsing, auto texture linking, Principled BSDF node networks, one-click level assembly

## 安装

### 方法 1：ZIP 安装（推荐）

1. 将 `io_import_starconflict_msh` 文件夹打包为 `.zip`（右键 → 发送到 → 压缩文件夹）
2. Blender → Edit → Preferences → Add-ons → 右上角 ▼ → **Install from Disk...**
3. 选择刚才的 `.zip` 文件
4. 搜索 "Star Conflict"，勾选启用

### 方法 2：手动复制

将 `io_import_starconflict_msh` 文件夹复制到 Blender addons 目录：

```
# Windows (Blender 4.2)
%APPDATA%\Blender Foundation\Blender\4.2\scripts\addons\

# Windows (Blender 5.0)
%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\
```

然后在 Preferences → Add-ons 中搜索并启用。

## 使用

安装后在 **File → Import** 菜单中出现两个选项：

### Import Star Conflict MSH (.mdl-msh*)
导入单个或多个 MSH 文件。

| 选项 | 说明 |
|------|------|
| Scale | 缩放系数（默认 1.0） |
| Join LOD Models | 将同模型的不同 LOD 文件分组 |

### Import Star Conflict MSH Batch (directory)
批量导入指定目录下所有 `.mdl-msh*` 文件。

| 选项 | 说明 |
|------|------|
| Scale | 缩放系数 |
| Max Files | 最大导入数量（0=无限制） |
| Show Details | 在控制台输出每个文件的状态 |

## 支持格式

| VBytes | 用途 |
|--------|------|
| 20 | 基础网格 |
| 24 | 扩展网格 |
| 28 | 场景物体 |
| 32 | 中型网格 |
| 36 | 大型网格 |
| 40 | 角色模型 |
| 44 | 装饰模型 |

编号范围：`.mdl-msh000` ~ `.mdl-msh1308`

## 导出 FBX

导入后使用 Blender 内置导出器：
**File → Export → FBX (.fbx)**

推荐设置：
- Path Mode: `Copy`（将纹理复制到 FBX 旁边）
- Scale: `1.00`
- Apply Scalings: `FBX All`

## 文件结构

```
blender_plugin/
├── io_import_starconflict_msh/          # 基础版（仅网格导入）
│   └── __init__.py
├── io_import_starconflict_msh_pro/      # Pro 版（完整材质管线）
│   ├── __init__.py
│   ├── msh_parser.py                    # MSH 网格解析
│   ├── msh_importer.py                  # 网格构建 + 材质链接 + Lightmap variant
│   ├── mdf_parser.py                    # MDF 材质定义解析
│   ├── material_builder.py              # Principled BSDF 节点网络 + 中性 lightmap + 变体创建
│   ├── material_registry.py             # 贴图指纹去重（LightmapSampler 弱引用）
│   ├── material_library.py              # 静态材质库
│   ├── texture_finder.py                # 多级贴图搜索
│   ├── shader_presets.py                # 着色器类型→采样器映射
│   ├── level_assembler.py               # 关卡组装 + Decals 生成
│   ├── scene_xml_parser.py              # Scene XML 解析
│   ├── decal_parser.py                  # Decals.dat 解析
│   ├── def_resolver.py                  # Def 实体→模型路径解析
│   ├── name_resolver.py                 # 模型命名冲突检测
│   ├── README_PRO.md                    # Pro 版完整文档
│   ├── DECALS_README.md                 # 贴花导入说明
│   └── ...
├── io_import_starconflict_msh_pro.zip   # Pro 版 ZIP包
└── README.md                            # 本文档
```

## 与 msh2fbx 配合

| 场景 | 推荐工具 |
|------|----------|
| 批量转换全量 62K 文件 | `msh2fbx.exe --batch` |
| 预览单个模型 | Blender 插件 |
| 需要手动编辑/绑定 | Blender 插件 |
| 自动化流水线 | `msh2fbx.exe` |

## Pro 版路径配置

Pro 版 (`io_import_starconflict_msh_pro`) 支持自动材质和贴图链接。配置路径：

| 设置项 | 推荐路径 | 说明 |
|--------|----------|------|
| Texture Search Paths | `scunpack\tex_universe_check\` | 已转换的 DDS 纹理目录 |
| MDF Search Paths | `scunpack\output\` | MDF 材质定义文件目录 |
| Texture Extensions | `.dds,.png,.tga` | 贴图扩展名优先级 |

> Pro 版支持**子文件夹递归搜索**，只需指定顶层目录即可覆盖所有子目录。
> 详见 `io_import_starconflict_msh_pro/README_PRO.md`。

---

## Pro 版注意事项

### 安装

| 事项 | 说明 |
|------|------|
| **独立安装** | Pro 版与基础版是**两个独立插件**，不要放在同一个 zip 包中 |
| **可共存** | 两个插件可以同时启用，互不冲突（菜单项不同） |
| **安装方式** | Pro 版文件夹名：`io_import_starconflict_msh_pro`，安装方法与基础版相同 |

### 前置条件

Pro 版需要以下资源已就绪才能自动创建材质：

| 资源 | 路径 | 生成方式 |
|------|------|----------|
| DDS 贴图 | `scunpack\tex_universe_check\` | `python batch_tex_all.py` |
| MDF 文件 | `scunpack\output\` | `tpak_extract.py` 解包产出 |

> ⚠️ 如果贴图目录不存在或为空，Pro 版仍可导入网格，但不会创建材质（效果与基础版相同）。

### 首次使用

1. 安装并启用插件
2. **Edit → Preferences → Add-ons → Star Conflict MSH Importer Pro** → 展开
3. 添加 **Texture Search Paths**：`<项目根>\scunpack\tex_universe_check`
4. 添加 **MDF Search Paths**：`<项目根>\scunpack\output`
5. 导入 MSH 文件 → 勾选 **Auto-Link Materials**

> 首次导入时会构建贴图索引（~11,628 个 DDS），约需 5-10 秒。后续导入直接使用缓存。

### 已知限制

| 限制 | 说明 |
|------|------|
| 材质槽-面映射 | MSH 不含材质-面映射，按序号 MDF块↔MSH编号分配 |
| Shader 还原 | 为手动预设映射，非 .fx 自动解析 |
| Cubemap | EnvSampler / ReflectionsSampler 暂未实现 |
| DDS 兼容性 | 部分 RGBA DDS 需 Honeyview/GIMP 查看 |
| Blender 5.0 | `Material.shadow_method` 已移除，插件通过 hasattr 兼容 |

### 问题排查

| 现象 | 可能原因 | 解决 |
|------|----------|------|
| 模型紫色/粉色 | 贴图未找到 | 检查 Texture Search Paths，清除缓存后重试 |
| 无材质创建 | MDF 未找到 | 确认 MDF 与 MSH 同目录，或添加 MDF Search Path |
| 贴图显示错误 | 缓存过期 | Sidebar → **Clear Texture Cache** |

### 完整关卡导入

导入整个关卡场景（如 `federation/pvp_omega`）时，仅导入 `maps/` 下的关卡主模型是不完整的。还需一并导入：

| 资源类型 | 目录 | 示例 |
|----------|------|------|
| 天空背景贴图 | `mapskit/backgrounds/` | `misc/clouds_*`, `textures/fed_station_*` |
| 模拟灯光模型 | `models/illumination/` | `rectlight`, `fed_dread_lights_*`, `rotrig_*` |
| 贴花模型 | `models/objects/constructor/decal/` | `constructor_decal_0*` |
| 共享场景模型 | `mapskit/maps/models/` | 小行星、集装箱、前哨站等 |
| 天空盒球体 | **引擎内置几何体 `skydome`** | 无 .mdl-msh 文件，需手动创建球体 |

### 灯光导入（实验性）

关卡组装时可导入 `Lights_` 实体为 Blender 原生灯光对象：

- **PointLight** → Blender Point Light
- **Beam / BeamWithHalo** → Blender Spot Light

> ⚠️ **实验性功能**：灯光方向可能不正确，导入后需手动调整旋转。导入的灯光放入 `Lights（Experimental - need user to edit）` Collection。
>
> 默认关闭。在 **Import Star Conflict Level** 面板中勾选 **Import Lights (Experimental)** 启用。

> 完整关卡导入的详细流程和依赖分析方法见 `io_import_starconflict_msh_pro/README_PRO.md` → **完整关卡导入** 章节。
