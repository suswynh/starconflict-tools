# Star Conflict MSH Importer — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender。

**兼容版本**：Blender 4.2 LTS、Blender 5.0+

> **v2.0** (2026-06) — 修复三角形卷绕方向（面法线反转问题）。MSH 原始卷绕与 Blender 正面约定相反，现已自动反转。
> **Pro 版** (`io_import_starconflict_msh_pro`) 已发布：支持 MDF 材质解析、自动贴图链接、Principled BSDF 节点网络。

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
├── io_import_starconflict_msh_pro/      # Pro 版（材质管线）
│   ├── __init__.py
│   ├── msh_parser.py
│   ├── msh_importer.py
│   ├── mdf_parser.py
│   ├── material_builder.py
│   └── ...
├── io_import_starconflict_msh_pro.zip   # Pro 版 ZIP包
└── README.md
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

### 问题排查

| 现象 | 可能原因 | 解决 |
|------|----------|------|
| 模型紫色/粉色 | 贴图未找到 | 检查 Texture Search Paths，清除缓存后重试 |
| 无材质创建 | MDF 未找到 | 确认 MDF 与 MSH 同目录，或添加 MDF Search Path |
| 贴图显示错误 | 缓存过期 | Sidebar → **Clear Texture Cache** |
