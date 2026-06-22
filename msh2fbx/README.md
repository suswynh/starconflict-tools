# msh2fbx — Star Conflict MSH → FBX 转换器

纯 C 命令行工具，将 Hammer Engine 的 `.mdl-mshXXX` 静态网格转换为 Autodesk FBX 格式。
零外部依赖，无需 Noesis 或 Autodesk SDK。

## 编译

**前置条件**：Visual Studio 2019 或 2022（含 C++ 桌面开发工作负载）

```powershell
cd msh2fbx
.\build.bat
```

编译产物：`msh2fbx.exe`（约 500KB，单文件可分发）

## 用法

```
msh2fbx <input.msh>                  # 单文件，自动生成 <input>.fbx
msh2fbx <input.msh> <output.fbx>     # 单文件，指定输出路径
msh2fbx --batch <dir> <outdir>       # 批量递归转换目录树
msh2fbx --help                        # 显示帮助
```

## 参数说明

| 参数 | 说明 |
|------|------|
| `<input.msh>` | 输入的 `.mdl-mshXXX` 文件路径 |
| `<output.fbx>` | 输出 FBX 路径（可选，默认 = 输入路径 + `.fbx`） |
| `--batch <dir> <outdir>` | 批量模式：递归扫描 `<dir>` 下所有 `.mdl-msh*`，输出到 `<outdir>` |
| `--help`, `-h` | 显示帮助信息 |

## 命名规则

批量模式下，输出文件名遵循以下规则（与 Noesis 管道一致）：

| 输入 | 输出 |
|------|------|
| `plasma_gun_mod1.mdl-msh000` | `plasma_gun_mod1000.fbx` |
| `map.mdl-msh001` | `map001.fbx` |
| `ship_hull.mdl-msh005` | `ship_hull005.fbx` |

规则：移除 `.mdl-msh` 部分，保留模型名 + LOD 编号，追加 `.fbx` 扩展名。

## 批量转换

批量模式递归遍历输入目录，保持目录层级结构：

```powershell
# 转换整个 backgrounds 目录
.\msh2fbx.exe --batch quickbms_unpacksource\mapskit\backgrounds fbx_output\backgrounds
```

输出目录结构：
```
fbx_output/
└── backgrounds/
    └── area1/
        ├── allidium_in_danger/
        │   ├── map000.fbx
        │   ├── map001.fbx
        │   └── map002.fbx
        └── allidium_yard/
            ├── map000.fbx
            ├── map001.fbx
            └── map002.fbx
```

**断点续传**：已存在的输出文件（>0 字节）会自动跳过，中断后重新运行不会重复转换。

## 转换流程

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  .mdl-mshXXX     │ →   │  msh2fbx.exe     │ →   │  .fbx (7400)     │
│  (Hammer Engine) │     │  MSH解析 + FBX写  │     │  (Autodesk FBX)  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
```

导出内容：
- 顶点位置 (position xyz)
- UV 坐标 (set 0, per-vertex mapping, V 自动翻转)
- 三角形面索引

不包含（MSH 格式无此数据）：
- 骨骼/蒙皮
- 材质/纹理引用
- 动画
- 法线（可后续计算）

## 性能

| 规模 | 文件数 | 耗时 | 吞吐量 |
|------|--------|------|--------|
| 小批量 | 83 | 0.5 秒 | ~173 文件/秒 |
| 中批量 | 622 | 3.4 秒 | ~183 文件/秒 |
| 全量 (预估) | ~188,000 | ~17 分钟 | — |

## 支持的格式

| VBytes | flag 条件 | UV 偏移 | 常见用途 |
|--------|-----------|---------|----------|
| 20 | — | 12 | 基础网格 |
| 24 | — | 16 | 扩展网格 |
| 28 | flag=0xE, 5 | 16 | 场景物体 |
| 28 | flag=0x11 | 20 | 特殊物体 |
| 32 | — | 20 | 中型网格 |
| 36 | — | 20 | 大型网格 |
| 40 | — | 24 | 角色模型 |

编号范围：`.mdl-msh000` ~ `.mdl-msh1308`

## 依赖

- **编译时**：ufbx_write（MIT 许可，已随附在 `msh2fbx/` 目录）
- **运行时**：无外部依赖，单文件 `msh2fbx.exe` 即可运行

## 与 Noesis 管道的区别

| | Noesis 管道 | msh2fbx |
|---|---|---|
| 运行方式 | Noesis + Python 脚本 | 单文件 .exe |
| 依赖 | Noesis (闭源) + Python | 无 |
| 速度 | ~1-2 文件/秒 | ~183 文件/秒 |
| 并行 | Python 多进程 | 串行（I/O 已足够快） |
| FBX 版本 | Noesis 内部格式 | 7400 标准二进制 |
| 可分发性 | 需打包 Noesis | 单文件复制即用 |

## 常见问题

**Q: 生成的 FBX 能在哪些软件中打开？**
Blender、Unity、Unreal Engine、3ds Max、Maya 等主流 3D 软件均支持 FBX 7400 格式。

**Q: 为什么没有材质/纹理？**
`.mdl-mshXXX` 是纯网格数据，不包含材质信息。材质定义在 `.mdf` 文件中，纹理存储在 `.tfh`/`.tfd` 文件中。材质关联需要额外的处理脚本。

**Q: 能批量转换全量 188,000 个文件吗？**
可以。运行 `msh2fbx --batch quickbms_unpacksource fbx_output`，约需 17 分钟。断点续传机制确保中断后可以继续。

**Q: Linux 能用吗？**
源码是跨平台 C99。Linux 下编译：
```bash
gcc -O2 -DUFBXW_STATIC -o msh2fbx msh2fbx.c ufbx_write.c -lm
```

**Q: 转换失败了怎么办？**
检查 MSH 文件是否完整（TPAK 解包是否成功）。工具会打印错误信息到 stderr。
