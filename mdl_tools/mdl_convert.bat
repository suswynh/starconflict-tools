@echo off
REM ============================================================================
REM Star Conflict MDL Convert - Drag & Drop Tool
REM ============================================================================
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
set "CONVERTER=%SCRIPT_DIR%\mdl_convert.py"

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

REM --- No args: show help ---
if "%~1"=="" (
    echo.
    echo ============================================================
    echo  Star Conflict MDL Convert
    echo ============================================================
    echo.
    echo  Drag supported files or folders onto this .bat file.
    echo.
    echo  Supported: mdl-hdr, mdl-geo, mdp, sot, mdl-zon, decals.dat
    echo  Output:    .txt file next to each source file
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
        echo Batch: %%d
        echo ============================================================
        %PYTHON% "%CONVERTER%" --batch %%d
        echo.
    )
)

REM --- Solo mode (files) ---
if not "!FILES!"=="" (
    echo.
    echo ============================================================
    echo Processing files...
    echo ============================================================
    %PYTHON% "%CONVERTER%" !FILES!
    echo.
)

echo ============================================================
echo  Done. Output .txt files are next to each source file.
echo ============================================================
echo.
pause
exit /b 0
