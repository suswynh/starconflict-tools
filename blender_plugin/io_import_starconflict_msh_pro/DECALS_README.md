# Decals（贴花）导入说明

## ⚠️ 重要提示

**贴花（Decals）是 Blender 插件在导入关卡时动态生成的，不是游戏解包文件。**

所有 decal 对象放置在 `Decals（need user to edit）` Collection 中，**导入后必须手动二次编辑**才能达到游戏中的视觉效果。

---

## 什么是 Decals

Star Conflict 的贴花系统（projection decals）在引擎中使用**投影盒**将纹理投射到场景几何体上。`levels/*/decals.dat` 存储的是投影参数（投影方向、位置、缩放），而非最终贴合结果。

插件无法模拟引擎的运行时投影计算，只能做刚性变换放置。

---

## 当前算法（v57 基准）

### 数据来源

| 文件 | 内容 |
|------|------|
| `levels/<关卡>/decals.dat` | 二进制，贴花实例（位置、方向、缩放、纹理名） |
| `gamedata/decals.dat` | 文本，贴花材质定义（UV 窗口、混合模式等） |

### 转换流程

```
direction → 法线方向（不用 M 变换，几何向量直用）
rotation  → 纹理上方向（默认 (0,1,0) 即世界 up，非默认值用于特殊旋转）
q_align   → plane 法线对齐
q_tex     → 纹理上方向对齐
final     → q_align @ q_tex
```

### 关键实现

- **网格**：`bmesh.ops.create_grid` 生成 1×1 XY 平面，UV 根据 `gamedata/decals.dat` 的 UV 窗口裁剪
- **材质**：Principled BSDF + BLEND 模式 + 无阴影
- **缩放**：`0.5 × M @ scale`（实践值，与 Hammer decal 单位比例对应）
- **UV 收缩**：×0.5 向质心收缩，防止 atlas 边缘渗透

---

## 已知限制

### 1. 曲面投影无法精确匹配

游戏引擎在运行时做 ray-projection，贴花会紧密贴合飞船曲面。插件只能做刚性放置，**曲面上的贴花位置和方向会有偏差**。

### 2. 位置偏差

投影盒原点 ≠ 最终贴合点，部分贴花可能有约 0.5 单位的深度偏差。

### 3. 默认朝向假设

当前算法假设贴花纹理上方向为世界 Z-up（对应 Hammer Y-up）。非默认朝向的贴花（如某些标签 decal）需要手动旋转。

### 4. 不包含在解包产物中

贴花 Collection 及其内的所有 mesh/material 对象都是**导入时动态生成的**，不属于 `scunpack/output/` 解包产物。删除后可通过重新导入关卡重新生成。

---

## 手动编辑建议

1. 在 Blender 中定位 `Decals（need user to edit）` Collection
2. 参考游戏内截图或参考模型，手动调整：
   - **旋转**：绕法线旋转使纹理方向正确
   - **位置**：沿法线方向微调贴合表面
   - **缩放**：根据实际需要调整
3. 使用 Snapping（吸附到面）功能辅助贴合几何体
4. X-flip / Y-flip 问题可在 `_make_decal_plane_mesh()` 的 UV 阶段调整

---

## 开关控制

导入面板中 `Import Decals (Experimental)` 复选框控制是否导入贴花。默认开启。

关闭后可跳过贴花导入，仅导入关卡静态几何和实体模型。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `decal_parser.py` | decals.dat 二进制/文本解析 |
| `level_assembler.py` | 贴花网格生成、材质创建、变换放置 |
| `operators.py` | 导入面板 `Import Decals` 开关 |
