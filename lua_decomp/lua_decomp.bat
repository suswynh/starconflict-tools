@echo off
REM ============================================================================
REM Star Conflict LuaJIT Bytecode Decompiler - Drag & Drop Tool
REM ============================================================================
setlocal enabledelapsedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "DECOMPILER=%SCRIPT_DIR%\lua_decomp.py"

REM --- Find Python ---
set "PYTHON="
for %%p in (python python3 py) do (
    where %%p >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=%%p"
        goto :found_python
    )
)
echo.
echo ============================================================
echo  [ERROR] Python not found!
echo  Install Python 3.7+ from https://www.python.org/
echo ============================================================
echo.
pause
exit /b 1

:found_python

REM --- Check ljd ---
%PYTHON% -c "import ljd" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  [ERROR] ljd library not installed.
    echo.
    echo  Run: pip install ljd
    echo  Source: https://github.com/NightNord/ljd
    echo ============================================================
    echo.
    pause
    exit /b 1
)

REM --- No args: show help ---
if "%~1"=="" (
    echo.
    echo ============================================================
    echo  Star Conflict LuaJIT Decompiler
    echo ============================================================
    echo.
    echo  Drag .lua bytecode files or folders onto this .bat file.
    echo.
    echo  Output:
    echo    Single file: decompiled .lua next to source file
    echo    Folder:       output to ^<source^>_decompiled/ subdirectory
    echo.
    echo  Note: Only processes LuaJIT 2.0 bytecode (starts with 1B 4C 4A)
    echo.
    pause
    exit /b 0
)

REM --- Collect args ---
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
    echo [WARNING] Path not found: %~1
)
shift
goto :parse_args

:done_parsing

REM --- Batch mode (directories) ---
if "!HAS_DIR!"=="1" (
    for %%d in (!DIRS!) do (
        echo.
        echo ============================================================
        echo Batch decompile: %%d
        echo ============================================================
        %PYTHON% "%DECOMPILER%" --batch %%d
        echo.
    )
)

REM --- Solo mode (files) ---
if not "!FILES!"=="" (
    echo.
    echo ============================================================
    echo Decompiling files...
    echo ============================================================
    %PYTHON% "%DECOMPILER%" !FILES!
    echo.
)

echo ============================================================
echo  Done. Decompiled .lua files are next to each source file,
echo  or in ^<source^>_decompiled/ for batch mode.
echo ============================================================
echo.
pause
exit /b 0
