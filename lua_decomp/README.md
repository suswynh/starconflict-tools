# Star Conflict LuaJIT 字节码反编译工具 — 中文文档

## 一、概述

将 Star Conflict（星际争端）的 LuaJIT 2.0 编译字节码（`.lua` 二进制文件）反编译为可读的 Lua 5.1 源码。

游戏使用 LuaJIT 作为脚本引擎，所有游戏逻辑（UI、AI、任务系统等）以编译后的字节码形式存储在 `.pak` 资源包中。解包后的文件虽以 `.lua` 为扩展名，但实际内容为 LuaJIT 字节码（以 `1B 4C 4A` 魔术字节开头）。

**工具文件**：`lua_decomp/lua_decomp.py`

**依赖**：Python 3.7+ + [ljd](https://github.com/NightNord/ljd)（LuaJIT Decompiler）

---

## 二、原理

### 2.1 LuaJIT 字节码识别

LuaJIT 2.0 字节码文件以固定的 3 字节魔术头开头：

```
1B 4C 4A   ← ESC + "LJ"
```

工具会先检查文件头，仅处理 LuaJIT 字节码文件，自动跳过已经是纯文本的 `.lua` 文件。

### 2.2 反编译流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐
│ .lua 字节码   │ ──→ │ rawdump 解析  │ ──→ │ AST 构建     │ ──→ │ Lua 源码  │
│ (二进制)      │     │ (header+proto)│     │ (builder+    │     │ (writer)  │
└──────────────┘     └──────────────┘     │  mutator)    │     └──────────┘
                                           └──────────────┘
```

1. **rawdump 解析** — `ljd.rawdump.parser.parse()` 读取字节码头和函数原型，还原操作码和常量表
2. **AST 构建** — `ljd.ast.builder.build()` 将线性字节码指令重构为抽象语法树（控制流、表达式、变量作用域）
3. **AST 优化** — `ljd.ast.mutator` 进行多轮变换：变量槽位分配、循环结构识别、表达式化简
4. **源码生成** — `ljd.lua.writer.write()` 将 AST 序列化为 Lua 5.1 源码

### 2.3 局限性

| 问题 | 原因 |
|------|------|
| 变量名为 `slot0, slot1...` | 字节码中变量名信息已剥离（LuaJIT 默认 `-s` 编译） |
| 部分复杂控制流可能无法完美还原 | `if-elseif-else` 链、`goto` 等结构的歧义 |
| 元表、协程等高级特性 | 反编译器主要针对常规游戏逻辑 |

> 这些限制是**所有** LuaJIT 反编译器的固有问题，不是本工具特有的。反编译结果与 `scripts_decompiled/` 目录中的内容一致。

---

## 三、安装依赖

```bash
pip install ljd
```

验证安装：

```bash
python -c "import ljd.rawdump.parser; print('OK')"
```

> 如 `pip install ljd` 失败，可从源码安装：
> ```bash
> git clone https://github.com/NightNord/ljd.git
> cd ljd && python setup.py install
> ```

---

## 四、使用方式

### 4.1 命令行

```bash
# 单个文件 → 输出到同目录的 <原名>_decompiled.lua
python lua_decomp.py bindings.lua

# 多个文件
python lua_decomp.py a.lua b.lua c.lua

# 批量反编译整个目录 → 输出到 <目录名>_decompiled/
python lua_decomp.py --batch ./scripts

# 批量反编译 + 指定输出目录
python lua_decomp.py --batch ./scripts --output ./my_decompiled

# 查看帮助
python lua_decomp.py --help
```

### 4.2 拖拽（Windows）

将文件或文件夹直接拖到 `lua_decomp.bat` 上：

- **拖 `.lua` 字节码文件** → 反编译单个文件，输出 `*_decompiled.lua`
- **拖文件夹** → 批量反编译所有字节码，输出到 `<源目录>_decompiled/`

工具自动跳过已经是纯文本的 `.lua` 文件。

### 4.3 作为 Python 模块

```python
from lua_decomp import lua_decomp

# 检查是否为字节码
if lua_decomp.is_luajit_bytecode("bindings.lua"):
    lua_decomp.decompile_file("bindings.lua", "bindings_decompiled.lua")
```

---

## 五、输出格式

反编译后的 Lua 源码示例（`bindings.lua`）：

```lua
if not UserBindings then
    UserBindings = {}
end

KeyBindings_GetNum = function()
    return #UserBindings
end

KeyBindings_GetIdx = function(slot0)
    for slot4, slot5 in ipairs(UserBindings) do
        if slot5.name == slot0 then
            return slot4
        end
    end
end
```

---

## 六、文件结构

```
lua_decomp/
├── lua_decomp.py       ← 核心反编译脚本
└── lua_decomp.bat      ← Windows 拖拽脚本
```

### 项目中的相关目录

```
scunpack/output/
├── scripts/                  ← 原始 LuaJIT 字节码（87 个文件，633 KB）
│   ├── ai/
│   ├── general/
│   ├── open_space/
│   └── ...
└── scripts_decompiled/       ← 已反编译的 Lua 源码（87 个文件，904 KB）
    ├── ai/
    ├── general/
    ├── open_space/
    └── ...
```

---

## 七、验证状态

| 项目 | 数量 | 状态 |
|------|------|------|
| 源字节码文件 | 87 | ✅ 全部为 LuaJIT 2.0 |
| 反编译成功 | 87 | ✅ 100%（含 ljd slot 警告，不影响输出） |
| 与现有 `scripts_decompiled/` 对比 | - | ✅ 输出一致 |
