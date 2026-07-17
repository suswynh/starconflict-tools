# Star Conflict MDL 格式解析工具 — 中文文档

## 一、概述

将 Star Conflict（星际争端）Hammer Engine 的六种二进制/文本辅助文件格式解析为可读文本。这些文件与 `.mdl-mshXXX`（渲染网格）并存，服务于游戏的碰撞检测、场景布置和区域触发系统。

**工具目录**：`mdl_tools/`

**依赖**：Python 3.7+，标准库（零第三方依赖）

---

## 二、支持的六种格式

| 扩展名 | 含义 | 实际用途 | 典型大小 | 输出文件 |
|--------|------|----------|----------|----------|
| `.mdl-hdr` | Model Header | 模型轴对齐包围盒（AABB） | 80 B | `.mdl-hdr.txt` |
| `.mdl-geo` | Model Geometry | 简化碰撞/LOD 代理网格 | 0.5–150 KB | `.mdl-geo.txt` |
| `.mdp` | Model Data Physics | TCF 碰撞物理网格 | ~8 KB | `.mdp.txt` |
| `.sot` | Scene Object Table | 场景物体放置变换表（层级+位置） | ~3 KB | `.sot.txt` |
| `.mdl-zon` | Model Zone | 触发/杀伤区域（Maya 导出） | ~1 KB | `.mdl-zon.txt` |
| `decals.dat` | Decals | 贴花材质库（文本） / 实例放置数据（二进制） | 0.4–47 KB | `decals.dat.txt` |

---

## 三、各格式详解

### 3.1 `.mdl-hdr` — 模型包围盒

**结构**（80 字节，小端序）：

```
Offset  Size   内容
0x00    12     float32×3  BBox Min (x, y, z)
0x0C    4      float32 padding (=0)
0x10    12     float32×3  BBox Max (x, y, z)
0x1C    4      float32 padding (=0)
0x20    24     6×float32  reserved (全零)
0x38    4      uint32     标志位/子模型计数
0x3C    4      uint32     0
0x40    4      uint32     0xFFFFFFFF（终止标记）
0x44    12     3×uint32   零填充
```

**用途**：引擎根据包围盒进行视锥剔除和 LOD 切换判断。Blender 导入后可自动设置对象边界显示。

### 3.2 `.mdl-geo` — 简化几何体

**结构**（小端序）：

```
Offset  Size   内容
0x00    4      uint32 version (=1)
0x04    4      uint32 未知标识
0x08    8      2×uint32 reserved
0x10    4      uint32 VBytes（顶点字节步长）
0x14    4      uint32 VStride（实际步长）
0x18    4      uint32 VCount（顶点数）
0x1C    4      uint32 FCount（面索引数 ×3）
0x20    36     9×uint32 reserved
0x44    -      float32×3 顶点位置 [x,y,z] × VCount
0x44+N  -      uint16    面索引（triangle list）
```

**与 MSH 的区别**：仅含位置数据（VStride=20，5 个 float），无 UV/法线。用于碰撞检测或低精度 LOD。

### 3.3 `.mdp` — TCF 碰撞物理

**结构**（小端序，含 ASCII 头）：

```
Offset  Size   内容
0x00    16     char[16]  "TCF STATIC_PHYS\0"（Targem Collision Format）
0x10    4      uint32 version (=5)
0x14    4      uint32 子网格数
0x18    4      uint32 数据块大小
0x1C    4      uint32 0
0x20    4      uint32 面数（碰撞三角形）
0x24    4      uint32 顶点数
0x28    4      uint32 0
0x2C    4      uint32 0
0x30    4      uint32 0x0910
0x34    4      float32 缩放因子 (≈1.0)
0x38    -      碰撞数据块（含嵌入的 ASCII 材质标签）
```

**用途**：物理引擎使用的碰撞网格，与渲染网格（MSH）分离。文件中嵌入 `#NO_BONE#`、`Metal`、`Glass` 等材质标签，用于物理材质的音效/粒子响应。

### 3.4 `.sot` — 场景对象表

**结构**（小端序）：

```
Offset  Size   内容
0x00    4      char[4]   "OT02"（Object Table v2）
0x04    4      uint32    对象数
0x08    4      uint32    参数（条目步长）
0x0C    116    29×uint32 reserved（全零）
0x40    -      对象条目列表（每条 64 字节）：
                 ├─ 16B  4×float32 变换参数
                 ├─ 8B   8×uint8 标志位
                 ├─ 4B   uint32 分隔符
                 └─ 32B  8×uint32 子对象索引
```

**用途**：定义场景中每件物体的世界空间变换和父子层级。导入后可批量放置模型到正确位置。

### 3.5 `.mdl-zon` — 触发区域

**结构**（混合 ASCII + 二进制，小端序）：

```
Offset  Size   内容
0x00    32     char[32]  Maya 形状名（如 "pCubeShape1-lib"）
0x20    4      uint32 reserved (=0)
0x24    4      uint32 未知 (=1)
0x28    4      uint32 顶点计数字段
0x2C    4      uint32 三角形计数字段
0x30    4      uint32 未知 (=1)
0x34    4      uint32 索引计数总计
0x38    2      uint16 索引计数
0x3A    2      uint16 额外字段
0x3C    4      uint32 未知 (=3)
0x40    48     4×float32×3 包围盒/元数据顶点
0x70~   -      char[]  纹理路径（如 "textures\graylightmap"）
...     -      变换矩阵行（~96 字节）
...     -      float32×4 三角带顶点（w=0, xyz=位置）
```

**用途**：Maya 中建模的简单形状（立方体、球体等），定义触发区域——杀伤区、传送门、任务触发器等。`.mdl-zon000` 为 LOD0。

> ⚠️ 顶点数据的精确偏移依赖启发式搜索，格式仍在逆向中。当前可正确提取实际网格顶点。

### 3.6 `decals.dat` — 贴花系统

Star Conflict 的贴花系统使用 **两种不同格式** 的 `decals.dat`，解析器自动检测：

#### A. 文本格式：`gamedata/decals.dat`

材质库定义，Hammer Engine 自定义文本格式，约 346 条记录：

```
name {
    diffuse "textures\decals\xxx_d"
    normal "textures\decals\xxx_nm"
    glow "textures\decals\xxx_glow"
    uv ( u1 u2 v1 v2 )
    blend alpha_glow
    material bump
    spec_color ( r g b )
    gloss value
}
```

**字段说明**：
| 字段 | 类型 | 含义 |
|------|------|------|
| `diffuse` | path | 漫反射纹理路径 |
| `normal` | path | 法线贴图路径 |
| `glow` | path | 自发光纹理路径 |
| `spec` | path | 高光纹理路径 |
| `uv` | vec4 | UV 坐标裁剪 (u_min, u_max, v_min, v_max) |
| `blend` | enum | 混合模式：`alpha_glow`, `alpha_test`, `none` |
| `material` | enum | 材质类型：`bump`, `alphatest` |
| `spec_color` | vec3 | 高光颜色 (r, g, b) |
| `gloss` | float | 光泽度 |

#### B. 二进制格式：`levels/*/decals.dat`

关卡级贴花实例放置数据（**小端序**，96 字节/记录）：

```
Offset  Size   内容
0x00    4      uint32 version (=5)
0x04    4      uint32 count (实例数)
0x08    8      uint64 padding (零)
0x10    —      记录数组

每条记录 (96 字节):
0x00    12     float32×3  position (x, y, z)     — Hammer Y-up 世界坐标
0x0C    4      float32    padding
0x10    16     float32×4  rotation (x, y, z, w)   — 四元数
0x20    12     float32×3  direction (dx, dy, dz)  — 贴花法向
0x2C    4      float32    padding
0x30    12     float32×3  scale (sx, sy, sz)
0x3C    4      float32    padding
0x40    N      char[]     texture name (null-terminated ASCII)
—       —      —          padding 至 96 字节
```

**坐标系**：Hammer Engine 使用 Y-up，Blender 使用 Z-up，转换由调用方处理。

**用途**：场景中血迹、弹痕、标志、损坏痕迹等贴花的空间放置。每个实例引用 `gamedata/decals.dat` 中定义的材质模板。

---

## 四、使用方式

### 4.1 命令行

```bash
# 单个文件
python mdl_convert.py model.mdl-hdr

# 多个文件
python mdl_convert.py a.mdl-geo b.mdp c.sot d.mdl-zon000

# 批量转换整个目录
python mdl_convert.py --batch ./mapskit/mainmenu

# 查看帮助
python mdl_convert.py --help
```

输出文件与源文件在同一目录，扩展名为 `.txt`。

### 4.2 拖拽（Windows）

将文件或文件夹直接拖到 `mdl_convert.bat` 上：

- **拖文件** → 单个转换，输出到同目录
- **拖文件夹** → 递归批量转换目录下所有 MDL 文件
- **拖多个文件+文件夹** → 分别处理

### 4.3 作为 Python 模块

```python
from mdl_tools import mdl_hdr_parser

result = mdl_hdr_parser.parse_mdl_hdr("model.mdl-hdr")
print(result["bbox_min"])   # (-1026.98, -140.15, -44.49)
print(result["bbox_max"])   # (121.98, 281.20, 617.17)
print(result["center"])     # (-452.50, 70.53, 286.34)
```

每个解析器都返回 `dict`，可作为模块导入到 Blender 插件或其他工具中。

---

## 五、与 Blender Pro 插件的关系

当前 Pro 版插件已支持：
- ✅ `.mdl-mshXXX` → 渲染网格导入
- ✅ `.mdf` → 材质定义解析

**本工具提供的扩展方向**：

| 格式 | Blender 集成方式 |
|------|-----------------|
| `.mdl-hdr` | 导入后设置对象包围盒显示 |
| `.mdl-zon` | 导入触发区域为半透明碰撞体（线框模式） |
| `.mdp` | 导入物理网格为隐藏碰撞体 |
| `.sot` | 批量放置多个模型到场景正确位置 |
| `decals.dat` | 批量放置贴花实例到场景表面 |

---

## 六、文件结构

```
mdl_tools/
├── mdl_convert.py         ← 统一入口（自动识别格式）
├── mdl_convert.bat        ← Windows 拖拽脚本
├── mdl_hdr_parser.py      ← .mdl-hdr 包围盒解析
├── mdl_geo_parser.py      ← .mdl-geo 简化几何解析
├── mdp_parser.py          ← .mdp TCF 碰撞物理解析
├── sot_parser.py          ← .sot 场景对象表解析
├── decals_parser.py        ← decals.dat 贴花解析（自动检测文本/二进制）
└── mdl_zon_parser.py       ← .mdl-zon 触发区域解析
```
