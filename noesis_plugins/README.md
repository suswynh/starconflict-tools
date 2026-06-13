# Noesis 插件集 — Star Conflict 资源逆向

Star Conflict 专用的 Noesis 插件包。

## 依赖

- **Noesis** (Rich Whitehouse) 4.x+
  - 官网: https://richwhitehouse.com/index.php?content=inc_projects.php
  - 将本目录插件放入 `Noesis\plugins\python\`

## 插件清单

### 纹理插件

| 文件 | 功能 |
|------|------|
| `tex_StarConflict_tfh_tfd_v2.py` | TFH/TFD → DDS，字节级头部解析 + fix_format + guess_size 回退 |

### 模型插件

```
inc_starconflict_msh.py           ← 共享模块，包含 load_msh() 加载逻辑
fmt_StarConflict_msh_A~Z.py ×26   ← 注册壳，仅声明扩展名范围，import 共享模块
```

26 个插件覆盖 `.mdl-msh000` ~ `.mdl-msh987`（99.5% 文件），每插件约 38 个扩展名：

| 插件 | 覆盖范围 |
|------|----------|
| `fmt_StarConflict_msh_A.py` | .msh000 ~ .msh037 |
| `fmt_StarConflict_msh_B.py` | .msh038 ~ .msh075 |
| ... | ... |
| `fmt_StarConflict_msh_Z.py` | .msh950 ~ .msh987 |

> 逻辑修改只需改 `inc_starconflict_msh.py` 一处。A~Z 文件为纯注册壳，无需单独维护。
> `.mdl-msh988` 及以上（仅 342 个地图碎片）用项目根目录的 `msh_to_obj_v3.py` 命令行转换。

### 支持的 MSH 顶点格式

| VBytes | Flag | UV 偏移 | 典型用途 |
|--------|------|---------|---------|
| 20 | — | 12 | 精简模型 |
| 24 | — | 16 | 标准模型 |
| 28 | 0xE/5 | 16 | 带额外数据 |
| 28 | 0x11 | 20 | 特殊布局 |
| 32 | — | 20 | 复杂模型 |
| 36 | — | 20 | 高精度模型 |
| 40 | — | 24 | 角色模型 (UV 待修正) |

## 安装

```powershell
# 复制所有插件到 Noesis
Copy-Item *.py "Noesis\plugins\python\"
```

## 已知限制

| 问题 | 影响范围 | 状态 |
|------|----------|------|
| _s1 非方形纹理（BC5/ATI2） | 飞船装备装饰品贴图，全部无法解析 | ❌ 未解决 |
| _s 新版 specular 纹理 | 新版格式映射不完整，部分可解 | ⚠️ 部分 |
| 背景/关卡贴图（irradiance 等） | cubemap，缺TFD + 复杂头部 | ❌ 未解决 |
| VBytes=40, flag=0x10 角色模型 | UV 偏移待修正（不影响飞船/场景） | ⚠️ 待修正 |
| fonts 字体纹理 | R8/L8/ARGB 格式，24-byte TFH | ✅ 已解决 (v2.1) |

## 归档文件 (`_archived/`)

### Original — 原始来源脚本 (`_archived/Original/`)

最初由俄罗斯社区提供的三个原始 Noesis 脚本：

| 文件 | 状态 |
|------|------|
| `tex_StarConflict_tfh_tfd.py` | ❌ 来源环境直接报错，不可用 |
| `tex_StarConflict_tfh_tfd_v2.py` | ✅ 来源环境可用，仅为简单位流解析版 |
| `fmt_StarConflict_mdl-msh000.py` | ⚠️ 仅能识别少数几个编号，覆盖极有限 |

这三个脚本是后续所有自研插件（A-Z 模型系列、v2 纹理字节解析版）的起点和逆向参考。

## Noesis 运行时说明

- **Python 版本**: Noesis 4.x 使用 **Python 3.2** 运行时（`inc_noesis` 模块内置）
- **`.pyc` 缓存**: Noesis 首次加载 `.py` 插件后会在 `__pycache__/` 生成 `cpython-32.pyc` 编译缓存，后续直接加载 `.pyc` 加速启动
- **⚠️ 更新方式**: 修改**任何** `.py` 后必须删除 `__pycache__/` 整个目录再重载，否则 Noesis 会读取旧缓存导致修改不生效。建议每次改脚本后直接 `Remove-Item __pycache__ -Recurse -Force`
- **LSP / IDE 静态检查**: 此目录下**不可用**。脚本依赖 Noesis 原生二进制模块 (`noesis`, `rapi`)，仅在 Noesis 运行时存在。不要期望 IDE 红波浪线能正常工作
- **验证方法**: 打开 Noesis → `Alt+T,R` 重载插件 → 拖入对应文件 → 确认模型/纹理正常显示
