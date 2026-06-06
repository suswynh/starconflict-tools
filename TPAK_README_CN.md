# Star Conflict TPAK 解包器 — 中文文档

## 一、概述

TPAK 是 Star Conflict（星际争端）使用的资源容器格式，版本 7。游戏由 Star Gem Inc. 开发，使用 Hammer Engine（与 Crossout 同引擎）。本解包器可从 `.pak` 文件中提取所有原始资源文件。

**解包器文件**：`tpak_extract.py`

**依赖**：Python 3.7+，标准库（无第三方依赖）

---

## 二、TPAK 格式结构（算法思路）

### 2.1 整体架构

```
┌──────────────────────────────────────────────┐
│ HEADER (28 字节)                              │
│  TPAK | ver=7 | flags | file_count | reserved │
│  uncomp_nametable | comp_nametable            │
├──────────────────────────────────────────────┤
│ 文件名表 (raw deflate 压缩)                    │
│  → 解压前：前 4 字节 XOR file_count            │
│  → 解压后：逐条目 XOR 解码文件名               │
├──────────────────────────────────────────────┤
│ 文件索引表 (file_count × 4B, 跳过)             │
├──────────────────────────────────────────────┤
│ 文件数据表 (raw deflate 压缩)                  │
│  → XOR key = file_count + comp_size          │
│  → 每条目 16B: size|name_off|chunks|chunk_idx  │
├──────────────────────────────────────────────┤
│ 文件块表 (raw deflate 压缩)                    │
│  → XOR key = file_count + comp_cs + chunks    │
│  → 每条目 16B: unkwn|uncomp|offset|comp_size   │
├──────────────────────────────────────────────┤
│ 原始文件数据块 (raw deflate 或未压缩)           │
└──────────────────────────────────────────────┘
```

### 2.2 核心算法步骤

```
1. 读取头部 → 获取 file_count, comp_nametable_size
2. 解压文件名表:
   a. 读取 comp_nametable_size 字节
   b. 前 4 字节 XOR file_count
   c. zlib raw deflate (wbits=-15) 解压
   d. 逐条目 XOR 解码文件名:
      每个字节 ^= ((位置 + 长度) × 2 + (长度%5 + 序号))
      条目跳过 = 4(长度头) + 长度(名字) + 1(额外null)
3. 跳过文件索引表 (file_count × 4 字节)
4. 解压文件数据表:
   a. 扫描找到压缩大小（索引表后有0-3字节填充）
   b. 前 4 字节 XOR (file_count + comp_size)
   c. raw deflate 解压 → 每个文件 16 字节元数据
5. 解压文件块表:
   a. 4字节对齐
   b. 前 4 字节 XOR (file_count + comp_cs + chunk_count)
   c. raw deflate 解压 → 每个块 16 字节元数据
6. 提取文件:
   a. 根据块表定位数据
   b. 若 compressed == uncompressed → 直接读取
   c. 否则 raw deflate 解压
```

### 2.3 关键发现

| 技术点 | 说明 |
|--------|------|
| 压缩算法 | zlib raw deflate（非标准 zlib 包装） |
| 加密方式 | XOR 混淆（非 AES），不同表用不同密钥 |
| 文件名解码 | 自定义 XOR，依赖条目长度和序号 |
| 字节序 | 全部小端 (little-endian) |
| 步长填充 | 文件名表每个条目后有 1 字节额外 null |

---

## 三、使用方法

> **路径说明**：所有脚本不含硬编码路径。辅助脚本（`batch_extract.py` 等）会自动从同目录定位 `tpak_extract.py`。使用时将 `<游戏data目录>` 替换为实际路径，如 `D:\Steam\steamapps\common\Star Conflict\data`。

### 3.1 基本用法

```powershell
# 列出 pak 文件内容（不提取）
python tpak_extract.py "<游戏data目录>\gamedata.pak" -l

# 提取单个 pak 到指定目录
python tpak_extract.py "<游戏data目录>\gamedata.pak" -o ./extracted

# 提取整个 data 目录的所有 pak
python tpak_extract.py "<游戏data目录>" -o ./extracted

# 只提取特定类型文件（如纹理）
python tpak_extract.py "<游戏data目录>" -o ./extracted -t .tfd,.tfh,.dds
```

### 3.2 参数说明

| 参数 | 说明 |
|------|------|
| `path` | `.pak` 文件路径 或 `data/` 目录路径 |
| `-o` / `--output` | 输出目录（默认 `./extracted`） |
| `-l` / `--list` | 仅列出文件，不提取 |
| `-t` / `--type` | 过滤扩展名，逗号分隔（如 `.dds,.lua`） |

### 3.3 批量提取示例

```powershell
# 分类批量提取（batch_extract.py 需指定游戏 data 目录）
python batch_extract.py --pak-dir "<游戏data目录>" --out ./extracted --gamedata
python batch_extract.py --pak-dir "<游戏data目录>" --out ./extracted --textures
python batch_extract.py --pak-dir "<游戏data目录>" --out ./extracted --models

# 批量 MSH → OBJ 导出
python batch_msh_export.py --root ./extracted --dry-run   # 先预览
python batch_msh_export.py --root ./extracted             # 实际导出

# 纹理转换
python rawtex_py.py ./extracted --auto

# 清理整理 + 生成报告
python organize_assets.py --root ./extracted --clean
python organize_assets.py --root ./extracted --report
```

### 3.4 输出结构

```
output/
├── gamedata/
│   └── gamedata/def/ex/active.lua    ← 游戏脚本
├── textures_armor_part1/
│   └── textures/armor/bp21_fabric.tfh  ← 纹理头
│   └── textures/armor/bp21_fabric.tfd  ← 纹理数据
├── models_modules_part1/
│   └── models/modules/m_active/
│       ├── module_destroyerring.mdl-hdr   ← 模型包围盒
│       ├── module_destroyerring.mdl-msh000 ← 网格 LOD0
│       ├── module_destroyerring.mdl-skl   ← 骨骼数据
│       └── module_destroyerring_d.tfh     ← 纹理
└── sound/
    └── sound/music.fsb                ← 音乐库
```

---

## 四、代码结构

```python
# 核心函数
decode_nametable()    # XOR 解码文件名表
read_tpak()           # 主解析函数，返回 (names, files, chunks, data_start, raw_data)
extract_file()        # 提取单个文件（含 raw deflate 解压）
extract_all()         # 提取全部文件
list_files()          # 列出文件（不提取）

# 辅助函数
xor4()                # 对前 4 字节 XOR
try_decompress()      # raw deflate 解压封装
scan_valid_int32()    # 扫描寻找有效 int32（处理对齐偏移）
```

---

## 五、验证状态

| 文件 | 文件数 | 状态 |
|------|--------|------|
| `gamedata.pak` | 333 (Lua) | ✅ 333/333 |
| `textures_armor_part1.pak` | 22 (DDS) | ✅ 22/22 |
| `textures_effects_simple.pak` | 81 (DDS) | ✅ 81/81 |
| `fonts.pak` | 88 (字体) | ✅ 88/88 |
| `models_modules_part1.pak` | 906 (模型) | ✅ 906/906 |
| `models_weapons_part2.pak` | 4368 (模型) | ✅ 4368/4368 |
| `sound_music.pak` | 1 (FSB) | ✅ 1/1 |
| 全部 844 pak | 113,749 文件 | ✅ 753/844 |

---

## 六、提取后格式转换

TPAK 解包得到的原始文件**并非全部可直接使用**，需要根据文件类型进行后续转换：

### 6.1 纹理 (.tfd + .tfh → .dds)

`.tfd` 是 Hammer 引擎的 DDSx 纹理数据，`.tfh` 是纹理元数据头。

| 工具 | 覆盖率 | 用法 |
|------|--------|------|
| `rawtex_py.py`（自研） | ~32% (3,649/11,468) | `python rawtex_py.py dir/ --auto` |
| `rawtex` (id-daemon) | ~90% | `RawtexCmd.exe file.dds DXT5` |
| AceWell Noesis 插件 | ~90% | 拖放 .tfd 到 Noesis |

**已转换**：3,400 个有效 DDS 纹理，可用 GIMP / Noesis / PVRTexTool 打开。

**卡点**：约 7,819 个纹理的 TFH 元数据被压缩/加密，自研 `rawtex_py.py` 无法解析，需 `rawtex` 或 Noesis 插件。

- rawtex 下载：[ZenHAX](https://zenhax.com/viewtopic.php@t=7099.html)（需注册）或 [MEGA](https://mega.nz/file/nV8EVZyC#o-53r4Vqu93iMMypPC4NvL1wmYCr6P15nVN4tpf3afk)

### 6.2 模型 (.mdl-msh → .obj)

模型分两种格式：

| 格式 | 占比 | 工具 | 说明 |
|------|------|------|------|
| **简单 MSH** (未压缩) | ~11% (487个) | `msh_to_obj_v2.py`（自研）✅ | stride=24/36 自适应，直接导出 OBJ |
| **复杂 MSH** (压缩) | ~89% (3,871个) | Noesis + AceWell 插件 ⚠️ | 高熵压缩数据，无法纯 Python 解析 |

**卡点**：复杂 MSH 使用 Hammer 引擎自定义压缩，不是标准 zlib/zstd。目前唯一已知导入方案是 AceWell 的 Noesis 插件（与 Crossout 共享）。

- AceWell 插件下载：[Yandex Disk](https://yadi.sk/d/iJiQ4Ajr3PeySZ)
- Noesis 下载：[richwhitehouse.com](https://richwhitehouse.com/noesis/)
- CGIG 论坛讨论：[cgig.ru/forum/viewtopic.php?t=2602](https://cgig.ru/forum/viewtopic.php?t=2602)
- 备用方案：Ninja Ripper（运行时截取）、RenderDoc（GPU 帧捕获）

### 6.3 声音 (.fsb → .wav/.ogg)

`.fsb` 是 FMOD Sound Bank 标准格式，共 41 个文件 (0.96 GB)。

| 工具 | 用法 |
|------|------|
| `fsb_aud_extr` | `fsb_aud_extr.exe music.fsb` |
| foobar2000 + vgmstream 插件 | 拖放 .fsb → 右键 Convert |
| FSBExtractor (GUI) | 图形界面操作 |

### 6.4 游戏脚本 (.lua / .blk)

✅ 无需转换，直接可读。Lua 脚本包含飞船、武器、任务配置，BLK 文件为键值对配置。

### 6.5 转换工具总览

```
TPAK 解包
  │
  ├── .tfd + .tfh ──→ rawtex / Noesis ──→ .dds (可用)
  │     └── 卡点: 68% TFH 压缩，需外部工具
  │
  ├── .mdl-msh ──→ msh_to_obj_v2.py ──→ .obj (11% 简单格式)
  │     └── 卡点: 89% 复杂压缩格式，需 Noesis + AceWell 插件
  │
  ├── .fsb ──→ fsb_aud_extr ──→ .wav / .ogg ✅
  │
  ├── .lua / .blk ──→ 直接可读 ✅
  │
  └── .dae / .ma ──→ Blender 直接导入 ✅
```

---

## 七、参考

- Johnnynator/tpak — C 语言参考实现：https://github.com/Johnnynator/tpak
- clutch.bms — QuickBMS 脚本：http://aluigi.org/bms/clutch.bms
- CGIG.ru — Hammer 引擎讨论：https://cgig.ru/forum/viewtopic.php?t=2602
