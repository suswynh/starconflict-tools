@echo off
REM ============================================================================
REM msh2fbx build script (Windows MSVC)
REM Requires: Visual Studio 2019 or 2022 with C++ desktop workload
REM ============================================================================

setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0"
set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

echo [msh2fbx] Build started...

REM Locate vcvarsall.bat
set "VCVARS="
for %%v in (2022 2019) do (
    if exist "C:\Program Files\Microsoft Visual Studio\%%v\Community\VC\Auxiliary\Build\vcvarsall.bat" (
        set "VCVARS=C:\Program Files\Microsoft Visual Studio\%%v\Community\VC\Auxiliary\Build\vcvarsall.bat"
    )
    if exist "C:\Program Files\Microsoft Visual Studio\%%v\Professional\VC\Auxiliary\Build\vcvarsall.bat" (
        set "VCVARS=C:\Program Files\Microsoft Visual Studio\%%v\Professional\VC\Auxiliary\Build\vcvarsall.bat"
    )
    if exist "C:\Program Files\Microsoft Visual Studio\%%v\Enterprise\VC\Auxiliary\Build\vcvarsall.bat" (
        set "VCVARS=C:\Program Files\Microsoft Visual Studio\%%v\Enterprise\VC\Auxiliary\Build\vcvarsall.bat"
    )
)

if "%VCVARS%"=="" (
    echo ERROR: vcvarsall.bat not found. Install Visual Studio 2019/2022 with C++ tools.
    exit /b 1
)

echo [msh2fbx] Using: %VCVARS%

REM Setup MSVC environment (x64 native)
call "%VCVARS%" x64 >nul 2>&1
if errorlevel 1 (
    echo ERROR: Failed to setup MSVC environment
    exit /b 1
)

REM Compile
echo [msh2fbx] Compiling...

cl /nologo /O2 /W3 /Fe:"%PROJECT_DIR%\msh2fbx.exe" ^
    /DUFBXW_STATIC ^
    /I"%PROJECT_DIR%" ^
    "%PROJECT_DIR%\msh2fbx.c" ^
    "%PROJECT_DIR%\ufbx_write.c" ^
    /link /LTCG

if errorlevel 1 (
    echo.
    echo [msh2fbx] BUILD FAILED
    exit /b 1
)

echo.
echo [msh2fbx] BUILD SUCCESS: %PROJECT_DIR%\msh2fbx.exe
exit /b 0
