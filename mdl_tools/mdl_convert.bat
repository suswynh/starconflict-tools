@echo off
REM ============================================================================
REM Star Conflict MDL 格式转换 — 拖拽工具
REM 支持拖放单/多个文件或文件夹到本 .bat 上
REM 输出 .txt 文件到源文件同目录
REM ============================================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "CONVERTER=%SCRIPT_DIR%mdl_convert.py"

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
echo [MDL Convert] 使用: %PYTHON%
echo.

REM ── 无参数时提示 ──
if "%~1"=="" (
    echo 用法:
    echo   拖放 .mdl-hdr / .mdl-geo / .mdp / .sot / .mdl-zon* 文件到本窗口
    echo   拖放整个文件夹到本窗口（批量转换目录下所有 MDL 文件）
    echo.
    echo 支持的格式: mdl-hdr, mdl-geo, mdp, sot, mdl-zon
    echo 输出: 每种文件生成对应的 .txt 文本文件在源文件同目录
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

REM 检查是文件还是目录
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
        echo 批量处理目录: %%d
        echo ============================================================
        %PYTHON% "%CONVERTER%" --batch %%d
        if errorlevel 1 (
            echo [错误] 批量处理失败: %%d
        )
        echo.
    )
)

REM ── 单文件用 solo 模式 ──
if not "!FILES!"=="" (
    echo ============================================================
    echo 处理文件...
    echo ============================================================
    %PYTHON% "%CONVERTER%" !FILES!
    if errorlevel 1 (
        echo [错误] 处理失败
        pause
        exit /b 1
    )
    echo.
)

echo.
echo [完成] 所有文件已处理。
echo 输出文件与源文件在同一目录，扩展名为 .txt
echo.
echo 按任意键退出...
pause >nul
exit /b 0
