@echo off
REM ---------------------------------------------------------------------------
REM Build script for FormulaSnap Python sidecar (Windows)
REM
REM Usage:
REM     cd sidecar && build.bat
REM
REM Output:
REM     src-tauri\binaries\formulasnap-sidecar-<target-triple>.exe
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set PROJECT_ROOT=%SCRIPT_DIR%\..
set OUTPUT_DIR=%PROJECT_ROOT%\src-tauri\binaries
set SPEC_FILE=%SCRIPT_DIR%\pyinstaller.spec
set BINARY_NAME=formulasnap-sidecar

REM ---------------------------------------------------------------------------
REM Detect target triple
REM ---------------------------------------------------------------------------
set TARGET_TRIPLE=x86_64-pc-windows-msvc

REM Check for ARM64 (PROCESSOR_ARCHITECTURE or PROCESSOR_ARCHITEW6432)
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set TARGET_TRIPLE=aarch64-pc-windows-msvc
if /i "%PROCESSOR_ARCHITEW6432%"=="ARM64" set TARGET_TRIPLE=aarch64-pc-windows-msvc

set OUTPUT_NAME=%BINARY_NAME%-%TARGET_TRIPLE%.exe

echo ==^> Platform:  %TARGET_TRIPLE%
echo ==^> Output:    %OUTPUT_DIR%\%OUTPUT_NAME%
echo.

REM ---------------------------------------------------------------------------
REM Clean previous build artifacts
REM ---------------------------------------------------------------------------
echo ==^> Cleaning previous build artifacts...
if exist "%SCRIPT_DIR%\build" rmdir /s /q "%SCRIPT_DIR%\build"
if exist "%SCRIPT_DIR%\dist" rmdir /s /q "%SCRIPT_DIR%\dist"
if exist "%OUTPUT_DIR%\%OUTPUT_NAME%" del /f /q "%OUTPUT_DIR%\%OUTPUT_NAME%"

REM ---------------------------------------------------------------------------
REM Ensure output directory exists
REM ---------------------------------------------------------------------------
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM ---------------------------------------------------------------------------
REM Build with PyInstaller
REM ---------------------------------------------------------------------------
echo ==^> Running PyInstaller...
cd /d "%SCRIPT_DIR%"
pyinstaller pyinstaller.spec --noconfirm --clean
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    exit /b 1
)

REM ---------------------------------------------------------------------------
REM Verify bundle contents (best-effort, does NOT block the build)
REM ---------------------------------------------------------------------------
echo ==^> 验证 bundle 内容...
python -c "from PyInstaller.utils.cliutils import archive_viewer" 2>nul
if errorlevel 1 (
    echo   archive_viewer 不可用，跳过 bundle 验证
    goto :COPY
)
python -m PyInstaller.utils.cliutils.archive_viewer "%SCRIPT_DIR%\dist\%BINARY_NAME%.exe" -l > "%TEMP%\sidecar-bundle-list.txt" 2>nul
echo --- bundle TOC ---
type "%TEMP%\sidecar-bundle-list.txt"
echo --- end TOC ---
for %%i in (_ssl libcrypto libssl VCRUNTIME140 _socket _hashlib) do (
    findstr "%%i" "%TEMP%\sidecar-bundle-list.txt" >nul && echo   OK %%i || echo   MISSING %%i
)
echo ==^> Bundle 验证完成

:COPY

REM ---------------------------------------------------------------------------
REM Copy output to Tauri binaries directory
REM ---------------------------------------------------------------------------
echo ==^> Copying binary to %OUTPUT_DIR%\
copy /y "%SCRIPT_DIR%\dist\%BINARY_NAME%.exe" "%OUTPUT_DIR%\%OUTPUT_NAME%"
if errorlevel 1 (
    echo ERROR: Failed to copy binary.
    exit /b 1
)

echo.
echo ==^> Build complete: %OUTPUT_DIR%\%OUTPUT_NAME%

endlocal
