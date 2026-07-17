# 项目规则

## 工具转换内容标记

以下后缀/模式的文件是 **工具转换产物**（由 mdl_tools 等工具生成），**不是** 游戏原始解包文件：

- `scunpack/output/` 目录下所有 `*.dat.txt` 文件 — 由 `mdl_convert.py` 从 `.dat` 二进制/文本文件解析生成
- `scunpack/output/` 目录下所有 `*.mdl-hdr.txt`, `*.mdl-geo.txt`, `*.mdp.txt`, `*.sot.txt`, `*.mdl-zon.txt` 文件 — 同理

### 注意事项

1. 转换产物可随时删除并通过重新运行 `mdl_convert.py` 重新生成
2. 修改转换产物不会影响原始 `.dat` 文件
3. 不纳入版本控制（建议加入 `.gitignore`）

---

## 反编译内容标记

以下目录/文件中的 Lua 源码是 **反编译产物**（由 LuaJIT 字节码反编译而来），**不是** 原始解包文件：

- `scunpack/output/gamedata_decompiled/` 目录下的所有 `.lua` 文件
- `scunpack/output/levels/` 目录及其子目录下所有带 `_decompiled.lua` 后缀的文件

### 注意事项

1. 反编译内容可能包含与原字节码语义等价但语法不完全一致的代码（如变量名、控制流结构等）
2. 当需要引用源代码时，优先参考反编译后的 `.lua` 文件
3. 对反编译内容的任何修改都不会影响原始字节码文件

---

## 备份文件夹

- 项目根目录及子目录下所有 `*.bak` / `.bak` 文件夹是 **本地备份目录**，**不纳入版本控制**
- `blender_plugin/old ver backup/` 目录是插件历史版本备份，**不纳入版本控制、不参与同步**
- AI 搜索时**不应主动搜索** `.bak` 目录和 `old ver backup` 目录，也不应将其内容作为参考源
- 备份目录的创建和删除不影响项目正常功能

---

## 双仓库工作流

本项目采用**双仓库**结构管理代码：

| 目录 | 用途 | Git |
|------|------|-----|
| `D:\starconflict upcak\` | **项目工作目录** — 日常开发、迭代、实验 | ✅ 本地跟踪，不推送 |
| `D:\starconflict upcak\starconflict-tools\` | **GitHub 本地仓库** — 用于对外发布 | ✅ 推送至 GitHub |

### 工作流程

1. 在工作目录 `D:\starconflict upcak\` 中进行开发迭代、修改文件、测试
2. 迭代稳定后，将改动**同步**到 `starconflict-tools/` 本地仓库
3. 在 `starconflict-tools/` 中 `git diff` 检查变更，确认无误
4. `git commit` + `git push` 推送至 GitHub

### 同步规则

- **以工作目录为准**：工作目录中的内容为权威源，`starconflict-tools/` 中的对应文件应被覆盖
- **范围**：仅同步以下路径（其他目录如 `scunpack/`、`StarConflict/` 等游戏资源不参与同步）
  - `blender_plugin/`
  - `msh2fbx/`
  - `mdl_tools/`
  - `lua_decomp/`
  - 根目录的共享脚本：`batch_*.py`、`batch_*.ps1`、`*.bms`、`tpak_extract.py`、`tex_targem_py.py` 等
  - 根目录的共享文档：`README.md`、`README_EN.md`、`PROJECT_NOTES.txt`、`TPAK_README_*.md`
- **排除**：`.git` 目录、`.bak` 目录、`old ver backup` 备份目录、临时脚本（`fix_*.py`、`scan_*.py`、`translate_*.py`）、日志文件（`*.log`）、编译产物（`*.obj`）
- **方式**：子目录使用 `robocopy /MIR` 镜像同步，根文件使用 `Copy-Item` 逐个覆盖

### AI 助手执行同步

当用户要求"同步到 starconflict-tools"时：
1. 对共享子目录执行 `robocopy /MIR`（自动处理新增、修改、删除）
2. 对根目录共享文件执行 `Copy-Item -Force`
3. 执行 `git status` 展示变更摘要供用户确认
4. 用户确认后自行 commit/push
