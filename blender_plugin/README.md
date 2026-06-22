# Star Conflict MSH Importer — Blender 插件

将 Hammer Engine (Star Conflict) 的 `.mdl-mshXXX` 静态网格导入 Blender。

**兼容版本**：Blender 4.2 LTS、Blender 5.0+

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
io_import_starconflict_msh/
└── __init__.py    # 插件全部逻辑（MSH解析 + Blender导入 + 批量）
```

## 与 msh2fbx 配合

| 场景 | 推荐工具 |
|------|----------|
| 批量转换全量 62K 文件 | `msh2fbx.exe --batch` |
| 预览单个模型 | Blender 插件 |
| 需要手动编辑/绑定 | Blender 插件 |
| 自动化流水线 | `msh2fbx.exe` |
