@echo off
REM ============================================================================
REM Star Conflict LuaJIT 字节码反编译 — 拖拽工具
REM 支持拖放单/多个 .lua 字节码文件或文件夹到本 .bat 上
REM 依赖: pip install ljd
REM ============================================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "DECOMPILER=%SCRIPT_DIR%lua_decomp.py"

REM ── 查找 Python ──
set "PYTHON="
for %%p in (python python3 py) do (
    where %%p >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=%%p"
        goto :found_python
    )
)
echo [错误] 未找到 Python。请安装 Python 3.7+ 并添加到 PATH。
pause
exit /b 1

:found_python
echo [Lua Decomp] 使用: %PYTHON%
echo.

REM ── 检查 ljd 是否安装 ──
%PYTHON% -c "import ljd" >nul 2>&1
if errorlevel 1 (
    echo [错误] ljd 库未安装。
    echo.
    echo 请运行: pip install ljd
    echo 或从源码安装: https://github.com/NightNord/ljd
    pause
    exit /b 1
)

REM ── 无参数时提示 ──
if "%~1"=="" (
    echo 用法:
    echo   拖放 .lua 字节码文件到本窗口（反编译单个文件）
    echo   拖放整个文件夹到本窗口（批量反编译目录下所有 .lua 字节码）
    echo.
    echo 输出:
    echo   - 单文件: 反编译后的 .lua 源码输出到源文件同目录
    echo   - 批量模式: 输出到 <源目录>_decompiled/ 子目录
    echo.
    echo 注意: 仅处理 LuaJIT 2.0 字节码文件（以 1B 4C 4A 开头）
    echo.
    echo 按任意键退出...
    pause >nul
    exit /b 0
)

REM ── 处理拖放的文件/目录 ──
set "FILES="
set "DIRS="
set "HAS_DIR=0"

:parse_args
if "%~1"=="" goto :done_parsing

if exist "%~1\" (
    set "DIRS=!DIRS! "%~1""
    set "HAS_DIR=1"
) else if exist "%~1" (
    set "FILES=!FILES! "%~1""
) else (
    echo [警告] 路径不存在: %~1
)

shift
goto :parse_args

:done_parsing

REM ── 有目录时用批量模式（优先） ──
if "!HAS_DIR!"=="1" (
    for %%d in (!DIRS!) do (
        echo.
        echo ============================================================
        echo 批量反编译目录: %%d
        echo ============================================================
        %PYTHON% "%DECOMPILER%" --batch %%d
        if errorlevel 1 (
            echo [错误] 批量处理失败: %%d
        )
        echo.
    )
)

REM ── 单文件用 solo 模式 ──
if not "!FILES!"=="" (
    echo ============================================================
    echo 反编译文件...
    echo ============================================================
    %PYTHON% "%DECOMPILER%" !FILES!
    if errorlevel 1 (
        echo [错误] 处理失败
        pause
        exit /b 1
    )
    echo.
)

echo.
echo [完成] 所有文件已处理。
echo.
echo 按任意键退出...
pause >nul
exit /b 0
