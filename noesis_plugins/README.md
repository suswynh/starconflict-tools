Star Conflict Noesis 插件
=======================

## 结构

```
inc_starconflict_msh.py          ← 共享模块，包含 load_msh() 加载逻辑（56行）
fmt_StarConflict_msh_A~Z.py ×26  ← 注册壳，仅声明扩展名范围（~15行/个）
```

A~Z 共 26 个插件覆盖 .mdl-msh000 ~ .mdl-msh987。
988~1308 仅 342 个地图碎片，用项目根目录的 msh_to_obj_v3.py 命令行转。

插件限制: Noesis 最多加载 ~26 个 Python 插件（故拆分为 A~Z）。
逻辑修改只需改 inc_starconflict_msh.py 一处。

## 版本

| 版本 | 日期 | 修改 |
|------|------|------|
| v1.0 | 初始 | RPGOPT_TRIWINDBACKWARD=1 反转卷绕 |
| v1.1 | 2026-06-22 | X 轴取反 (试错: 片面修复) |
| **v1.2** | **2026-06-23** | **Z 轴取反 (正确: MSH 前向 -Z→+Z)** |

贴图: tex_StarConflict_tfh_tfd_v2.py  (位流+TFD反推混合)

## 验证

LSP / IDE 静态检查在此目录下**不可用**（脚本依赖 Noesis 原生二进制模块 noesis/rapi）。
验证方法: 打开 Noesis → Alt+T,R 重载插件 → 拖入 .mdl-mshXXX 文件 → 确认模型正常显示。

详见项目根目录 PROJECT_NOTES.txt
