# Noesis 插件集 — Star Conflict 资源逆向

Star Conflict 专用的 Noesis 插件包。

## 依赖

- **Noesis** (Rich Whitehouse) 4.x+
  - 官网: https://richwhitehouse.com/index.php?content=inc_projects.php
  - 将本目录插件放入 `Noesis\plugins\python\`

## 插件清单

### 纹理插件

| 文件 | 功能 | 解析方式 |
|------|------|----------|
| `tex_StarConflict_tfh_tfd_v2.py` | 位流头部解析 + guess_size 回退 | NoeBitStream |
| `tex_StarConflict_tfh_tfd_v3.py` | 🔥 主力 — PHP mip表逻辑 + v2 fallback | 字节级 mip 表 |
| `tex_StarConflict_tfh_tfd_v4_php.py` | 纯 PHP TargemImage 迁移（对比验证用） | 字节级 mip 表 |

**v2/v3/v4 差异**：v3 综合了 PHP 的 mip 表精确计算和 v2 的 fallback 鲁棒性，是推荐使用的版本。v4 仅用于对比验证，不含 fallback/font 检测。

### 模型插件

```
inc_starconflict_msh.py           ← 共享模块，包含 load_msh() 加载逻辑
fmt_StarConflict_msh_A~Z.py ×26   ← 注册壳，仅声明扩展名范围，import 共享模块
```

26 个插件覆盖 `.mdl-msh000` ~ `.mdl-msh987`（99.5% 文件）：

| 插件 | 覆盖范围 |
|------|----------|
| `fmt_StarConflict_msh_A.py` | .msh000 ~ .msh037 |
| `fmt_StarConflict_msh_B.py` | .msh038 ~ .msh075 |
| ... | ... |
| `fmt_StarConflict_msh_Z.py` | .msh950 ~ .msh987 |

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
| RGBA 格式渲染花屏 | format 0x0/5/6 纹理解析正确但 B/R 通道互换 | ⚠️ 分析中 |
| irradiance cubemap | 关卡环境光贴图缺 TFD 文件 | ⚠️ 需重解包 |
| VBytes=40 角色模型 | UV 偏移待修正（不影响飞船/场景） | ⚠️ 待修正 |

## 已解决

| 问题 | 解决版本 | 说明 |
|------|----------|------|
| fonts (R8/L8/ARGB) | v2.1 | 24-byte TFH 头，70/70 |
| _s1 非方形纹理 | v3 | format 0x07→DXT1，非方形正确解析 |
| _s 新版 specular | v3 | 全 format 码支持 |
| _d/_nm (DXT1/3/5) | v2+ | 简单/压缩 TFH 全覆盖 |
| mapskit/decorative | v3 | 全格式支持 |

## 归档文件 (`_archived/`)

### Original — 原始来源脚本 (`_archived/Original/`)

最初由俄罗斯社区提供的三个原始 Noesis 脚本：

| 文件 | 状态 |
|------|------|
| `tex_StarConflict_tfh_tfd.py` | ❌ 来源环境直接报错，不可用 |
| `tex_StarConflict_tfh_tfd_v2.py` | ✅ 来源环境可用，仅为简单位流解析版 |
| `fmt_StarConflict_mdl-msh000.py` | ⚠️ 仅能识别少数几个编号，覆盖极有限 |

## Noesis 运行时说明

- **Python 版本**: Noesis 4.x 使用 Python 3.2 运行时
- **⚠️ 更新方式**: 修改 `.py` 后必须删除 `__pycache__/` 目录再重载
- **验证方法**: 打开 Noesis → `Alt+T,R` 重载插件 → 拖入对应文件
