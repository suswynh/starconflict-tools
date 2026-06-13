# Star Conflict 资源逆向工具集

Star Conflict（星际争端）资源提取与格式转换工具。游戏由 Star Gem Inc. 开发，使用 **Hammer Engine**。

## 工具列表

| 工具 | 功能 | 依赖 |
|------|------|------|
| `tpak_extract.py` | TPAK v7/v8 容器解包（844 .pak 全部支持） | Python 3.7+ |
| `msh_to_obj_v3.py` | 简单/复杂 MSH 网格 → OBJ（VBytes 20-40） | Python 3.7+ |
| `rawtex_py.py` | 简单 TFH+DDSx 纹理 → 标准 DDS（自研） | Python 3.7+ |
| `tex_StarConflict_tfh_tfd_v2.py` | 压缩 TFD 纹理 → DDS（Noesis 插件，字节级解析） | Noesis |
| `batch_extract.py` | 批量解包所有 .pak | Python 3.7+ |
| `batch_msh_export.py` | 批量 MSH → OBJ 导出 | Python 3.7+ |
| `organize_assets.py` | 清理无效文件、生成资源报告 | Python 3.7+ |
| `batch_quickbms.ps1` | 批量 quickbms 解包（备用方案） | quickbms |
| `clutch.bms` | quickbms 脚本，TPAK v7/v8 解析 | quickbms |
| `noesis_plugins/` | **完整 Noesis 插件包**（26 模型 + 1 纹理插件） | Noesis |

## 工具链管线

```
┌────────────────────────────────────────────────────────────────┐
│                     TPAK v7/v8 容器解包                         │
│                    tpak_extract.py / scunpack.exe               │
└───────────┬───────────────┬───────────────┬────────────────────┘
            │               │               │
     ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
     │ .mdl-mshXXX │ │ .tfh + .tfd │ │ .dds / .lua │
     │  模型文件   │ │  纹理文件对 │ │  / .fsb 等  │
     └──────┬──────┘ └──────┬──────┘ └─────────────┘
            │               │
     ┌──────▼──────┐ ┌──────▼─────────────────┐
     │ msh_to_obj  │ │ 简单 TFH → rawtex_py   │
     │   _v3.py    │ │ 压缩 TFD → tfh_tfd_v2  │
     └──────┬──────┘ └──────┬─────────────────┘
            │               │
     ┌──────▼──────┐ ┌──────▼──────┐
     │   .obj      │ │   .dds      │
     │  标准模型   │ │  标准纹理   │
     └─────────────┘ └─────────────┘
```

## Noesis 插件包（`noesis_plugins/`）

> **依赖**: [Noesis](https://richwhitehouse.com/index.php?content=inc_projects.php) 4.x+ — 第三方 3D 模型/纹理查看器

此目录包含所有依赖 Noesis 运行时的 Star Conflict 专用插件，与纯 Python 工具独立维护：

| 类别 | 文件 | 数量 | 功能 |
|------|------|------|------|
| 纹理插件 | `tex_StarConflict_tfh_tfd_v2.py` | 1 | 主力纹理加载器（字节解析 + guess_size 回退，支持 fonts/DXT） |
| 模型插件 | `fmt_StarConflict_msh_A~Z.py` | 26 | 覆盖 `.mdl-msh000` ~ `.msh987` |
| 归档 | `_archived/` | 3 | `tex_StarConflict_tfh_tfd.py`(v1)、`fmt_StarConflict_mdl-msh000.py`(早期基类) 等 |

**安装**: 将所需插件复制到 `Noesis\plugins\python\` 目录。详见 [`noesis_plugins/README.md`](noesis_plugins/README.md)。

## 快速开始

> **注意**：所有命令需要在仓库根目录下运行，各辅助脚本会自动寻找同目录下的 `tpak_extract.py` 和 `msh_to_obj_v3.py`。

```powershell
# 1. 解包单个 .pak 文件
python tpak_extract.py "StarConflict\data\gamedata.pak" -o ./extracted

# 2. 解包整个 data 目录（844 个 pak）
python tpak_extract.py "StarConflict\data" -o ./extracted

# 3. 批量提取 — 分类解包
python batch_extract.py --pak-dir "StarConflict\data" --out ./extracted --gamedata
python batch_extract.py --pak-dir "StarConflict\data" --out ./extracted --textures
python batch_extract.py --pak-dir "StarConflict\data" --out ./extracted --models

# 4. 导出模型（单文件 / 批量）
python msh_to_obj_v3.py ./extracted/models/.../model.mdl-msh000 -o model.obj
python batch_msh_export.py --root ./extracted

# 5. 纹理转换
#   简单 TFH（Mip 表可读）→ 自动检测+转换
python rawtex_py.py ./extracted --auto
#   压缩 TFD（需要位流解析）→ 在 Noesis 中加载 .tfh 文件即可预览/导出

# 6. 清理无效文件 + 生成资源报告
python organize_assets.py --root ./extracted --clean
python organize_assets.py --root ./extracted --report
```

### 路径替换说明

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `StarConflict\data` | Star Conflict 安装目录下的 data 文件夹 | `D:\Steam\steamapps\common\Star Conflict\data` |
| `./extracted` | 任意输出目录 | `./extracted` 或 `D:\output` |

所有脚本均**不包含硬编码路径**，通过命令行参数指定。辅助脚本会自动从自身所在目录定位 `tpak_extract.py` 和 `msh_to_obj_v3.py`，无需额外配置。

## 格式支持

| 格式 | 破解程度 | 工具 | 说明 |
|------|----------|------|------|
| TPAK v7/v8 | ██████ 100% | `tpak_extract.py` | 容器完全破解，844 个 .pak 全部支持 |
| 简单 MSH | ██████ 100% | `msh_to_obj_v3.py` | VBytes=24/36，含 UV → OBJ |
| 复杂 MSH | █████░ 95% | `msh_to_obj_v3.py` + 26 Noesis 插件 | VBytes=20/24/28/32/36/40，覆盖 .msh000~987 |
| 简单 TFH | ██████ 100% | `rawtex_py.py` | Mip 表可读 → DDS（DXT1/3/5 自检测） |
| 压缩 TFD | ███░░░ ~50% | `tex_StarConflict_tfh_tfd_v2.py` | 位流解析，fonts ✅ / _d,_nm ✅ / _s1,_s,背景 ❌ |

### 纹理格式详解

Star Conflict 使用 Hammer Engine 的 **DDSx** 纹理容器格式，纹理存储为 `.tfh`（头）+ `.tfd`（数据）文件对：

| 类型 | TFH 特征 | 转换方式 | 占比 |
|------|----------|----------|------|
| **简单 TFH** | 头部未压缩，Mip 表以 uint32 三元组存储 | `rawtex_py.py` 直接解析 | ~70% |
| **压缩 TFH** | 头部经过位流编码，需要 NoeBitStream 解析 | `tex_StarConflict_tfh_tfd_v2.py`（Noesis） | ~30% |

两者配合覆盖：DXT1 (BC1)、DXT3 (BC2)、DXT5 (BC3)。**仍未解决的格式**：_s1 非方形（BC5/ATI2）、新版 _s、背景/关卡贴图。

### 纹理支持现状（2026-06）

| 贴图类型 | 状态 | 工具 | 说明 |
|----------|------|------|------|
| fonts (R8/L8/ARGB) | ✅ 完全 | v2 插件 | 70/70，24-byte TFH 头 |
| _d, _nm (DXT1/3/5) | ✅ 基本 | rawtex_py + v2 | 简单TFH直解，压缩TFH位流解 |
| _s 旧版 (specular) | ✅ 部分 | rawtex_py | stride 简单布局可解 |
| _s 新版 (specular) | ❌ 未解决 | — | 压缩TFH，格式映射不完整 |
| _s1 (BC5/ATI2) 非方形 | ❌ 未解决 | — | bitstream 头 + 非标准尺寸 |
| levels / 背景贴图 | ❌ 大部分 | — | irradiance 缺 TFD，复杂 cubemap |
| mapskit / decorative | ✅ 基本 | rawtex_py + v2 | DXT5/BC5 混合，少数缺TFD |

## 进度

已从 844 个 .pak 中提取 **113,749 个文件 (12.5 GB)**，包括：

| 资源类型 | 数量 | 状态 |
|----------|------|------|
| DDS 纹理 | 3,400+ | ⚠️ 部分可用（fonts ✅, _d/_nm ✅, _s1/_s/背景 ❌） |
| OBJ 模型 | 487 | ✅ 可用 |
| Lua 脚本 | 1,005 | ✅ 已提取 |
| FSB 声音库 | 41 (0.96 GB) | ✅ 已提取 |
| Collada 源模型 | 8 | ✅ 已提取 |
| XML / CFG 配置 | 数千 | ✅ 已提取 |

## 已知问题

| 问题 | 影响范围 | 优先级 |
|------|----------|--------|
| _s1 非方形纹理（BC5/ATI2） | 飞船装备贴图（装饰品_s1），全部无法解析 | 🔴 高 |
| _s 新版 specular 纹理 | 飞船/装备 specular 贴图，新版格式映射不完整 | 🔴 高 |
| 背景/关卡贴图（irradiance 等） | levels 目录 cubemap，缺TFD + 复杂头部 | 🟡 中 |
| VBytes=40, flag=0x10 角色模型 UV 偏移 | 少数角色模型 UV 不准确 | 🟡 中 |
| Noesis 插件上限 ~26 个，高序号 MSH (.988~1308) 需命令行 | 极少数模型需命令行转换 | 🟡 中 |

## 引擎说明

Star Conflict 使用 **Hammer Engine**（Targem/Star Gem），与 Crossout 同引擎。TPAK 容器格式与 Dagor Engine（War Thunder）兼容，但内部资源编码各自独立。

## 参考

- [Johnnynator/tpak](https://github.com/Johnnynator/tpak) — C 语言参考实现
- [CGIG.ru 论坛](https://cgig.ru/forum/viewtopic.php?t=2602) — Hammer 引擎讨论
- [AceWell Noesis 插件](https://yadi.sk/d/iJiQ4Ajr3PeySZ) — 复杂模型导入
- [rawtex (id-daemon)](https://zenhax.com/viewtopic.php@t=7099.html) — DDSx 原始纹理转换
- [scunpack (learn_more)](https://unknowncheats.me) — 专用解包+转换工具
- [quickbms + clutch.bms](http://quickbms.aluigi.org) — 通用 BMS 解包方案
