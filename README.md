# Star Conflict 资源逆向工具集

Star Conflict（星际争端）资源提取与格式转换工具。游戏由 Star Gem Inc. 开发，使用 **Hammer Engine**。

## 工具列表

| 工具 | 功能 | 依赖 |
|------|------|------|
| `tpak_extract.py` | TPAK v7/v8 容器解包（844 .pak 全部支持） | Python 3.7+ |
| `msh_to_obj_v3.py` | MSH 网格 → OBJ（VBytes 20-44，覆盖 000~1308） | Python 3.7+ |
| `msh2fbx/` | ⚡ **MSH → FBX 独立转换器** — 纯 C，零依赖，~175 files/s | Visual Studio 2019+ |
| `blender_plugin/` | 🎨 **Blender 导入插件** — 基础版 + Pro版(MDF材质)，支持 4.2 LTS / 5.0+ | Blender 4.2+ |
| `tex_targem_py.py` | 🔥 **主力纹理转换器** — 纯 Python，基于 PHP TargemImage 逻辑，支持全格式 | Python 3.7+ |
| `rawtex_py.py` | 简单 TFH+DDSx 纹理 → 标准 DDS（已被 `tex_targem_py.py` 取代） | Python 3.7+ |
| `batch_tex_all.py` | 批量转换全部 .tfh → .dds，多进程，保持源目录结构 | Python 3.7+ |
| `batch_extract.py` | 批量解包所有 .pak | Python 3.7+ |
| `batch_msh_export.py` | 批量 MSH → OBJ 导出 | Python 3.7+ |
| `organize_assets.py` | 清理无效文件、生成资源报告 | Python 3.7+ |
| `batch_quickbms.ps1` | 批量 quickbms 解包（备用方案） | quickbms |
| `clutch.bms` | quickbms 脚本，TPAK v7/v8 解析 | quickbms |
| `batch_noesis_fbx.py` | 批量 Noesis MSH → FBX 导出 | Noesis 4.x+ |
| `rename_fbx.py` | FBX 文件批量重命名 | Python 3.7+ |
| `test_noesis_cmd.py` | Noesis 命令行测试脚本 | Noesis 4.x+ |
| `noesis_plugins/` | **完整 Noesis 插件包**（26 模型 + 3 纹理插件） | Noesis 4.x+ |
| **音频工具** | | |
| `fsbext/` | 🔈 **FSB 音频提取器** — Luigi Auriemma，支持 FSB1~FSB5，CLI | Windows/Linux |
| `vgmstream/` | 🔈 **Vorbis 音频修复** — vgmstream-cli，生成有效 WAV 头 | Windows/Linux |
| `FsbExtractor_16.10.21/` | 🖱️ FSB Extractor GUI — 图形界面备选方案 | Windows |

## 工具链管线

```
┌──────────────────────────────────────────────────────────────────┐
│                    TPAK v7/v8 容器解包                            │
│                  tpak_extract.py / scunpack.exe                   │
└─────────┬────────────────┬───────────────┬───────────────────────┘
          │                │               │
   ┌──────▼──────┐ ┌───────▼──────┐ ┌──────▼──────┐
   │ .mdl-mshXXX │ │ .tfh + .tfd  │ │ .dds / .lua │
   │  模型文件   │ │  纹理文件对  │ │  / .fsb 等  │
   └──────┬──────┘ └───────┬──────┘ └─────────────┘
          │                │
   ┌──────▼───────────────────────────────┐
   │         模型转换 (3条路线)            │
   │                                      │
   │  ┌─────────────┐  ┌──────────────┐   │
   │  │ msh_to_obj   │  │  msh2fbx     │   │     ┌──────────────────┐
   │  │ _v3.py       │  │  (C, ~183/s) │   │     │ blender_plugin   │
   │  │ (Python)     │  │  独立 .exe   │   │     │ (Blender 导入)   │
   │  └──────┬───────┘  └──────┬───────┘   │     └────────┬─────────┘
   │         │                 │           │              │
   │         ▼                 ▼           │              ▼
   │      .obj              .fbx          │      Blender → .fbx
   └──────────────────────────────────────┘
            │                │
   ┌────────▼────────────────▼────────────┐
   │          纹理转换                     │
   │  tex_targem_py.py (纯Python)         │
   │  batch_tex_all.py (批量, 保持目录)    │
   │  Noesis v2/v3/v4 插件 (预览用)       │
   └──────────────────┬───────────────────┘
                      │
               ┌──────▼──────┐
               │   .dds      │
               │  标准纹理   │
                └─────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    音频提取 (.fsb)                            │
│                                                              │
│  ┌──────────────────┐       ┌──────────────────────────┐     │
│  │ fsbext (CLI)     │       │ Fs bExtractor (GUI)      │     │
│  │ PCM/MPEG → WAV/  │       │ 拖入 FSB → 右键提取     │     │
│  │ MP3 (可播放)     │       │                          │     │
│  └────────┬─────────┘       └──────────────────────────┘     │
│           │                                                   │
│           │ Vorbis 编码 → .ogg (缺容器头，不可播放)           │
│           │                                                   │
│  ┌────────▼─────────┐                                        │
│  │ vgmstream-cli    │                                        │
│  │ 重新提取 → .wav  │                                        │
│  │ 标准 RIFF 头     │                                        │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

## `msh2fbx` — MSH → FBX 独立转换器

> 纯 C99 实现，零运行时依赖，单文件可执行。详见 [`msh2fbx/README.md`](msh2fbx/README.md)

| 特性 | 说明 |
|------|------|
| 速度 | ~183 files/s（单线程，I/O 绑定） |
| 格式 | FBX 7400 Binary |
| 范围 | `.mdl-msh000` ~ `.mdl-msh1308`（VBytes 20/24/28/32/36/40/44） |
| 编号含义 | ⚠️ 非传统LOD编号，见下方 LOD 说明 |
| 实测 | 62,825 文件 → 100% 成功率，1.65 GB |

```powershell
# 编译
cd msh2fbx; .\build.bat

# 使用
.\msh2fbx.exe model.mdl-msh000
.\msh2fbx.exe --batch input_dir output_dir
```

## `blender_plugin` — Blender 导入插件

> 在 Blender 中直接导入 `.mdl-mshXXX` 文件，支持 4.2 LTS / 5.0+。详见 [`blender_plugin/README.md`](blender_plugin/README.md)

| 特性 | 说明 |
|------|------|
| 导入方式 | File → Import → Star Conflict MSH (.mdl-msh*) |
| UV 支持 | ✅ UV 通道（命名 "map1"） |
| 坐标系 | 5 种预设（默认 Y-up → Z-up） |
| 批量 | 支持目录批量导入 |
| 顶点色 | ❌ MSH 格式不含顶点色数据 |

**安装**：打包为 `.zip` → Blender Preferences → Add-ons → Install from Disk。

## `.mdl-mshXXX` 编号含义

**编号不是传统 LOD 层级**。不同模型使用不同约定：

| 模型类型 | 命名规律 | 示例 |
|---------|------|------|
| 简单模型（炮塔/武器） | 编号递增 = 精度递减 | `物体_01/02/03_mshxxx` = LOD1/2/3 |
| 复杂无畏舰 | 命名差异大 | `bigship_fed`=LOD0, `bigship_fed_2`=LOD1 |
| | | `bigship_jer_03`=LOD0, `bigship_jer`=LOD1, `bigship_jer_2`=LOD2 |
| 多部件模型 | 间隔编号对应子网格 | `r1_h_t1` msh000/004/008 是 3 个部件高精度 |
| 变体 | `_mod1~4` / `_s1~3` | 装备升级 / 皮肤（仅 MDF） |

> **已知问题**：部分 LOD 长度不一致（低精度简化了延展结构），旋转值可能不统一。
> 详见 [`blender_plugin/io_import_starconflict_msh_pro/README_PRO.md`](blender_plugin/io_import_starconflict_msh_pro/README_PRO.md)

## Noesis 插件包（`noesis_plugins/`）

> **依赖**: [Noesis](https://richwhitehouse.com/index.php?content=inc_projects.php) 4.x+

| 类别 | 文件 | 数量 | 功能 |
|------|------|------|------|
| 纹理插件 | `tex_StarConflict_tfh_tfd_v2.py` | 1 | 位流解析 + guess_size 回退（fonts/DXT） |
| 纹理插件 | `tex_StarConflict_tfh_tfd_v3.py` | 1 | PHP mip表逻辑 + v2 fallback（全格式） |
| 纹理插件 | `tex_StarConflict_tfh_tfd_v4_php.py` | 1 | 纯PHP迁移版（对比验证用） |
| 模型插件 | `fmt_StarConflict_msh_A~Z.py` | 26 | 覆盖 `.mdl-msh000` ~ `.msh987` |
| 归档 | `_archived/` | 3 | v1纹理插件、早期模型基类等 |

## 音频提取（FSB → WAV / MP3）

FSB（FMOD Sample Bank）是 FMOD 音频引擎的容器格式，Star Conflict 包含 **41 个 FSB 文件**（~0.96 GB），内含三种编码的音频流。

### 编码分布

| 编码 | 文件数 | 工具 | 说明 |
|------|--------|------|------|
| MPEG (MP3) | 2,136 | fsbext | 直接提取即用 |
| PCM16 (WAV) | 488 | fsbext | 自动添加 RIFF 头 |
| Vorbis (OGG) | 578 | fsbext + vgmstream | fsbext 缺失容器头，需 vgmstream 修复 |

> ⚠️ **已知问题**：fsbext 提取 Vorbis 音频时只输出原始 Vorbis 数据块，缺少 OGG 容器头（`OggS`），导致 PotPlayer / Windows Media Player 等无法播放。需用 vgmstream 重新提取以生成有效 WAV。

### Vorbis 影响的 14 个 FSB

`aura` `hangar` `hit` `mnstr` `modules_vorbis` `raid` `swarm` `ui2` `weapon` `weapon2` `weapon3` `weapon4` `weapon_paper` `weapon_vorbis`

### 使用方法

```powershell
# 方法 1：批量提取（推荐）
# 第一步 — fsbext 快速提取全部 .fsb
$fsbext = ".\fsbext\fsbext.exe"
Get-ChildItem .\sound -Filter *.fsb | ForEach-Object {
    New-Item -ItemType Directory -Force -Path $_.BaseName
    & $fsbext -d "$($_.BaseName)" $_.FullName
}

# 第二步 — 检查 Vorbis（.ogg 文件），用 vgmstream 修复
$vgm = ".\vgmstream\vgmstream-cli.exe"
$oggFsbs = @("aura","hangar","hit","mnstr","modules_vorbis","raid",
             "swarm","ui2","weapon","weapon2","weapon3","weapon4",
             "weapon_paper","weapon_vorbis")
foreach ($name in $oggFsbs) {
    $count = (& $vgm -m "$name.fsb" 2>&1 | Select-String "stream count: (\d+)").Matches.Groups[1].Value
    for ($i = 1; $i -le $count; $i++) {
        $sname = (& $vgm -m -s $i "$name.fsb" 2>&1 | Select-String "stream name: (.+)").Matches.Groups[1].Value
        & $vgm -s $i -o "$name\$sname.wav" "$name.fsb"
    }
}
```

### 工具来源

| 工具 | 版本 | 下载 | 许可 |
|------|------|------|------|
| fsbext | 0.3.8a | [aluigi.org/papers.htm#fsbext](https://aluigi.altervista.org/search.php?src=fsbext) | 开源 (GPL) |
| vgmstream | r1916+ | [github.com/vgmstream/vgmstream](https://github.com/vgmstream/vgmstream) | 开源 (ISC) |
| FSB Extractor | 16.10.21 | [aezay.dk/aezay/fsbextractor](http://aezay.dk/aezay/fsbextractor/) | 免费软件 |

## 快速开始

```powershell
# 1. 解包
python tpak_extract.py "StarConflict\data" -o ./extracted

# 2. 批量纹理转换（一键全量）
python batch_tex_all.py --workers 8

# 3. 单文件纹理转换
python tex_targem_py.py texture.tfh
python tex_targem_py.py texture.tfh output.dds

# 4. 批量模型导出（OBJ / FBX）
python batch_msh_export.py --root ./extracted          # OBJ
.\msh2fbx\msh2fbx.exe --batch extracted fbx_output     # FBX

# 5. Blender 中预览
# 安装 blender_plugin/ 后在 File → Import 中导入

# 6. 资源报告
python organize_assets.py --root ./extracted --report
```

## 格式支持

| 格式 | 破解程度 | 工具 | 说明 |
|------|----------|------|------|
| TPAK v7/v8 | ██████ 100% | `tpak_extract.py` | 844 .pak 全部支持 |
| MSH 模型 | ██████ 99.7% | `msh_to_obj_v3.py` + `msh2fbx` + 26 Noesis 插件 | .msh000~1308，VBytes 20-44 |
| TFH 纹理 | ██████ 99.6% | `tex_targem_py.py` | 11,671 个 .tfh → 11,623 个成功 |
| FSB 音频 | ██████ 100% | `fsbext` + `vgmstream` | 41 .fsb → 3,247 个可播放 (WAV+MP3) |

### 纹理支持现状（2026-06-18）

| 贴图类型 | 状态 | 格式 | 说明 |
|----------|------|------|------|
| _d, _nm (diffuse/normal) | ✅ 完全 | DXT1/3/5 | 全量支持 |
| _s (specular) | ✅ 完全 | DXT1/5/RGBA | 新旧版均支持 |
| _s1 (specular) | ✅ 完全 | DXT1/5/RGBA | format 0x07→DXT1，非方形支持 |
| fonts (R8/L8/ARGB) | ✅ 完全 | 独立格式 | 70/70, Noesis v2/v3 |
| mapskit / decorative | ✅ 完全 | DXT1/3/5/RGBA | 全量支持 |
| levels / 背景 | ✅ 基本 | 混合 | 部分缺TFD（irradiance cubemap） |
| particles / reaper / ui | ✅ 完全 | 混合 | 全量支持 |

## 进度

已从 844 个 .pak 中提取 **113,749 个文件**，包括：

| 资源类型 | 数量 | 状态 |
|----------|------|------|
| DDS 纹理 | 11,628 | ✅ 99.6% 成功转换 |
| FBX 模型 | 62,825 | ✅ 100% 成功转换 |
| OBJ 模型 | 487 | ✅ 可用 |
| Lua 脚本 | 1,005 | ✅ 已提取 |
| FSB 音频 | 3,247 | ✅ 100% 可播放 (1,066 WAV + 2,136 MP3) |

### 已知限制

| 问题 | 影响 | 状态 |
|------|------|------|
| Noesis RGBA 渲染花屏 | RGBA 格式纹理预览时 B/R 通道互换 | ⚠️ 分析中（建议使用脚本批量导出 DDS 文件） |
| 极小尺寸纹理 | 部分 mip 级纹理仅几个像素，查看器误判为空 | ℹ️ 正常现象 |
| RGBA DDS 兼容性 | 部分图片查看器不支持无压缩 RGBA DDS | ℹ️ 用 Honeyview/GIMP/PS 查看 |
| irradiance cubemap | 关卡环境光贴图缺 TFD 文件 | ⚠️ 需重新解包/涉及到的相关内容是游戏运行时生成，非形态数据 |
| VBytes=44 角色模型 | UV 偏移为推测值，骨骼数据已识别 | ⚠️ UV 待精确验证 |
| 顶点色 | MSH 格式不含顶点色数据 | ℹ️ 无需支持 |

## 版本历史

| 版本 | 日期 | 更新 |
|------|------|------|
| v5 | 2026-06 | 新增 FSB 音频提取方案 (fsbext + vgmstream)，修复 Vorbis OGG 容器头问题 |
| v4 | 2026-06 | 新增 `msh2fbx` (C FBX转换器) + `blender_plugin` (Blender导入) |
| v3 | 2026-06 | tex_v3 PHP mip表精确计算 + v2 fallback |
| v2 | 2026-05 | tex_v2 NoeBitStream + guess_size fallback + font |
| v1 | 2026-04 | 初始工具集 (rawtex_py, tpak_extract, msh_to_obj) |

## 致谢

- **Mater (gamemodels3D)** — 提供 TargemImage.php，为纹理转换提供了关键解决思路
- **Suigintou (Discord channel)** — 提供了 Noesis 查看纹理与模型的原始脚本与 quickbms 脚本

---

## Star Conflict Asset Reverse Engineering Toolkit

A collection of tools for extracting and converting Star Conflict game assets. The game is developed by Star Gem Inc. using **Hammer Engine**.

### Tools

| Tool | Function | Dependency |
|------|----------|------------|
| `tpak_extract.py` | TPAK v7/v8 container unpacking (844 .pak supported) | Python 3.7+ |
| `msh_to_obj_v3.py` | MSH mesh → OBJ (VBytes 20-44, covers 000~1308) | Python 3.7+ |
| `msh2fbx/` | ⚡ **MSH → FBX standalone converter** — Pure C, zero deps, ~183 files/s | Visual Studio 2019+ |
| `blender_plugin/` | 🎨 **Blender import add-on** — Import .mdl-msh* directly, 4.2 LTS / 5.0+ | Blender 4.2+ |
| `tex_targem_py.py` | Primary texture converter — Pure Python, PHP TargemImage logic | Python 3.7+ |
| `batch_tex_all.py` | Batch .tfh → .dds conversion, multi-process | Python 3.7+ |
| `noesis_plugins/` | Noesis plugin pack (26 model + 3 texture plugins) | Noesis 4.x+ |

### Quick Start

```powershell
# 1. Unpack
python tpak_extract.py "StarConflict\data" -o ./extracted

# 2. Batch texture conversion
python batch_tex_all.py --workers 8

# 3. Batch model export
python batch_msh_export.py --root ./extracted              # OBJ
.\msh2fbx\msh2fbx.exe --batch extracted fbx_output         # FBX

# 4. Preview in Blender
# Install blender_plugin/ (基础版 io_import_starconflict_msh 或 Pro版 io_import_starconflict_msh_pro)
# File → Import → Star Conflict MSH / Star Conflict MSH Pro
```

### 版本历史

#### v1.2 (当前, 2026-06-23) — 修复前向轴

> **结论**：MSH 的前向轴是 **-Z**，与 Maya（前=+Z）相反。对 Z 坐标取反即可同时解决法线翻转和轴向问题。

| 工具 | 修改 | 效果 |
|------|------|------|
| `msh2fbx/msh2fbx.c` | Z 取反：`pz→-pz` | Maya 即开即用，Blender 走标准 FBX 导入 |
| `NOESIS/plugins/.../inc_starconflict_msh.py` | offset+8 Z 取反 | v1.2 |
| `blender_plugin/*/__init__.py` + `msh_importer.py` | `(x,y,z)→(x,y,-z)`，默认 Z-up→Y-up | Blender 直接导入即标准姿势 |
| `msh_to_obj_v3.py` | `(x,y,z)→(x,y,-z)` | OBJ 前向正确 |

#### v1.1 (2026-06-22) — 试错：X 镜像 + 卷绕反转

尝试通过 X 轴取反和三角形索引反转修复法线。**部分有效但 Maya 仍需 Y180° 旋转**。

#### v1.0 (初始)

面法线翻转，模型在 Blender/Maya 中显示异常。Noesis 通过 `RPGOPT_TRIWINDBACKWARD=1` 内部修正。

### Progress

From 844 .pak files, **113,749 files** extracted:

| Asset Type | Count | Status |
|------------|-------|--------|
| DDS Textures | 11,628 | ✅ 99.6% success |
| FBX Models | 62,825 | ✅ 100% success |
| OBJ Models | 487 | ✅ Available |
| Lua Scripts | 1,005 | ✅ Extracted |
| FSB Audio | TBD | ⚠️ Pending |
