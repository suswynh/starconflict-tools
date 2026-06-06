# Star Conflict 资源逆向工具集

Star Conflict（星际争端）资源提取与格式转换工具。游戏由 Star Gem Inc. 开发，使用 **Hammer Engine**。

## 工具列表

| 工具 | 功能 | 依赖 |
|------|------|------|
| `tpak_extract.py` | TPAK v7 容器解包（844 .pak 全部支持） | Python 3.7+ |
| `msh_to_obj_v2.py` | 简单/蒙皮 MSH 网格 → OBJ | Python 3.7+ |
| `rawtex_py.py` | DDSx 纹理 → 标准 DDS（自研） | Python 3.7+ |
| `batch_extract.py` | 批量解包所有 .pak | Python 3.7+ |
| `batch_msh_export.py` | 批量 MSH → OBJ 导出 | Python 3.7+ |
| `organize_assets.py` | 清理无效文件、生成资源报告 | Python 3.7+ |

## 快速开始

> **注意**：所有命令需要在仓库根目录下运行，各辅助脚本会自动寻找同目录下的 `tpak_extract.py` 和 `msh_to_obj_v2.py`。

```powershell
# 1. 解包单个 .pak 文件
python tpak_extract.py "你的游戏目录\StarConflict\data\gamedata.pak" -o ./extracted

# 2. 解包整个 data 目录（844 个 pak）
python tpak_extract.py "你的游戏目录\StarConflict\data" -o ./extracted

# 3. 批量提取 — 分类解包（需指定游戏 data 目录）
python batch_extract.py --pak-dir "你的游戏目录\StarConflict\data" --out ./extracted --gamedata
python batch_extract.py --pak-dir "你的游戏目录\StarConflict\data" --out ./extracted --textures
python batch_extract.py --pak-dir "你的游戏目录\StarConflict\data" --out ./extracted --models

# 4. 导出模型（单文件 / 批量）
python msh_to_obj_v2.py ./extracted/models_misc/.../model.mdl-msh000 -o model.obj
python batch_msh_export.py --root ./extracted

# 5. 纹理转换（单文件 / 批量 + 自动检测）
python rawtex_py.py ./extracted --auto

# 6. 清理无效文件 + 生成资源报告
python organize_assets.py --root ./extracted --clean
python organize_assets.py --root ./extracted --report
```

### 路径替换说明

上述命令中的路径需替换为你本机的实际路径：

| 占位符 | 替换为 | 示例 |
|--------|--------|------|
| `你的游戏目录\StarConflict\data` | Star Conflict 安装目录下的 data 文件夹 | `D:\Steam\steamapps\common\Star Conflict\data` |
| `./extracted` | 任意输出目录 | `./extracted` 或 `D:\output` |

所有脚本均**不包含硬编码路径**，通过命令行参数指定。辅助脚本（`batch_extract.py`、`batch_msh_export.py` 等）会自动从自身所在目录定位 `tpak_extract.py` 和 `msh_to_obj_v2.py`，无需额外配置。

## 格式支持

| 格式 | 破解程度 | 说明 |
|------|----------|------|
| TPAK v7 | ██████ 100% | 容器完全破解 |
| 简单 MSH | ██████ 100% | stride=24/36 自适应 → OBJ |
| 复杂 MSH | ███░░░ 30% | Hammer 引擎压缩，需 Noesis + AceWell 插件 |
| 简单 TFH | ██████ 100% | Mip 表可读 → DDS |
| 压缩 TFH | ██░░░░ 20% | 需 rawtex (id-daemon) 工具 |

## 详细文档

- [TPAK 格式与使用说明（中文）](TPAK_README_CN.md)
- [TPAK Format & Usage (English)](TPAK_README_EN.md)

## 进度

已从 844 个 .pak 中提取 **113,749 个文件 (12.5 GB)**，包括：
- ✅ 3,400 个有效 DDS 纹理
- ✅ 487 个 OBJ 模型
- ✅ 1,005 个 Lua 脚本
- ✅ 41 个 FSB 声音库 (0.96 GB)
- ✅ 8 个 Collada 源模型

## 引擎说明

Star Conflict 使用 **Hammer Engine**（Targem/Star Gem），与 Crossout 同引擎。TPAK 容器格式与 Dagor Engine（War Thunder）兼容，但内部资源编码各自独立。

## 参考

- [Johnnynator/tpak](https://github.com/Johnnynator/tpak) — C 语言参考实现
- [CGIG.ru 论坛](https://cgig.ru/forum/viewtopic.php?t=2602) — Hammer 引擎讨论
- [AceWell Noesis 插件](https://yadi.sk/d/iJiQ4Ajr3PeySZ) — 复杂模型导入
- [rawtex (id-daemon)](https://zenhax.com/viewtopic.php@t=7099.html) — 原始纹理转换
