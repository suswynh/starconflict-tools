# Star Conflict 资源逆向工具集

Star Conflict（星际争端）资源提取与格式转换工具。游戏由 Star Gem Inc. 开发，使用 **Hammer Engine**。

## 工具列表

| 工具 | 功能 | 依赖 |
|------|------|------|
| `tpak_extract.py` | TPAK v7/v8 容器解包（844 .pak 全部支持） | Python 3.7+ |
| `msh_to_obj_v3.py` | 简单/复杂 MSH 网格 → OBJ（VBytes 20-40） | Python 3.7+ |
| `tex_targem_py.py` | 🔥 **主力纹理转换器** — 纯 Python，基于 PHP TargemImage 逻辑，支持全格式 | Python 3.7+ |
| `rawtex_py.py` | 简单 TFH+DDSx 纹理 → 标准 DDS（自研，已被 `tex_targem_py.py` 取代） | Python 3.7+ |
| `batch_tex_all.py` | 批量转换全部 .tfh → .dds，多进程，保持源目录结构 | Python 3.7+ |
| `batch_extract.py` | 批量解包所有 .pak | Python 3.7+ |
| `batch_msh_export.py` | 批量 MSH → OBJ 导出 | Python 3.7+ |
| `organize_assets.py` | 清理无效文件、生成资源报告 | Python 3.7+ |
| `batch_quickbms.ps1` | 批量 quickbms 解包（备用方案） | quickbms |
| `clutch.bms` | quickbms 脚本，TPAK v7/v8 解析 | quickbms |
| `noesis_plugins/` | **完整 Noesis 插件包**（26 模型 + 3 纹理插件） | Noesis |

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
     ┌──────▼──────┐ ┌──────▼──────────────────────────────┐
     │ msh_to_obj  │ │  tex_targem_py.py (纯Python)         │
     │   _v3.py    │ │  batch_tex_all.py (批量, 保持目录)   │
     └──────┬──────┘ │  Noesis v3/v4 插件 (预览用)         │
            │        └──────┬──────────────────────────────┘
     ┌──────▼──────┐ ┌──────▼──────┐
     │   .obj      │ │   .dds      │
     │  标准模型   │ │  标准纹理   │
     └─────────────┘ └─────────────┘
```

## Noesis 插件包（`noesis_plugins/`）

> **依赖**: [Noesis](https://richwhitehouse.com/index.php?content=inc_projects.php) 4.x+

| 类别 | 文件 | 数量 | 功能 |
|------|------|------|------|
| 纹理插件 | `tex_StarConflict_tfh_tfd_v2.py` | 1 | 位流解析 + guess_size 回退（fonts/DXT） |
| 纹理插件 | `tex_StarConflict_tfh_tfd_v3.py` | 1 | PHP mip表逻辑 + v2 fallback（全格式） |
| 纹理插件 | `tex_StarConflict_tfh_tfd_v4_php.py` | 1 | 纯PHP迁移版（对比验证用） |
| 模型插件 | `fmt_StarConflict_msh_A~Z.py` | 26 | 覆盖 `.mdl-msh000` ~ `.msh987` |
| 归档 | `_archived/` | 3 | v1纹理插件、早期模型基类等 |

**安装**: 将所需插件复制到 `Noesis\plugins\python\` 目录。详见 [`noesis_plugins/README.md`](noesis_plugins/README.md)。

## 快速开始

```powershell
# 1. 解包
python tpak_extract.py "StarConflict\data" -o ./extracted

# 2. 批量纹理转换（一键全量）
python batch_tex_all.py --workers 8

# 3. 单文件纹理转换
python tex_targem_py.py texture.tfh
python tex_targem_py.py texture.tfh output.dds

# 4. 批量模型导出
python batch_msh_export.py --root ./extracted

# 5. 资源报告
python organize_assets.py --root ./extracted --report
```

## 格式支持

| 格式 | 破解程度 | 工具 | 说明 |
|------|----------|------|------|
| TPAK v7/v8 | ██████ 100% | `tpak_extract.py` | 844 .pak 全部支持 |
| MSH 模型 | ██████ 99.5% | `msh_to_obj_v3.py` + 26 Noesis | .msh000~987 |
| TFH 纹理 | ██████ 99.6% | `tex_targem_py.py` | 11,671 个 .tfh → 11,623 个成功 |

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
| OBJ 模型 | 487 | ✅ 可用 |
| Lua 脚本 | 1,005 | ✅ 已提取 |
| FSB 音频 | 数量待统计 | ⚠️ 待验证 |

### 已知限制

| 问题 | 影响 | 状态 |
|------|------|------|
| Noesis RGBA 渲染花屏 | RGBA 格式纹理预览时 B/R 通道互换 | ⚠️ 分析中（DDS导出正常） |
| 极小尺寸纹理 | 部分 mip 级纹理仅几个像素，查看器误判为空 | ℹ️ 正常现象 |
| RGBA DDS 兼容性 | 部分图片查看器不支持无压缩 RGBA DDS | ℹ️ 用 Honeyview/GIMP/PS 查看 |
| irradiance cubemap | 关卡环境光贴图缺 TFD 文件 | ⚠️ 需重新解包 |
| VBytes=40 角色模型 | UV 偏移待修正（不影响飞船/场景） | ⚠️ 待修正 |
