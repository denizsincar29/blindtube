@echo off
REM Build a standalone blindtube executable with PyInstaller, via uv.
REM
REM By default this does an INCREMENTAL build (fast, reuses PyInstaller's
REM cache). Pass --clean to force a full from-scratch rebuild, e.g. after
REM upgrading dependencies or if the build looks broken.

setlocal

set APP_NAME=blindtube
set ENTRY_POINT=main.py
set CLEAN_BUILD=0

if "%1"=="--clean" set CLEAN_BUILD=1

where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed. Install it from https://docs.astral.sh/uv/
    exit /b 1
)

echo Syncing dependencies with uv...
uv sync

set PYI_FLAGS=--noconfirm --onefile --windowed --name %APP_NAME% --collect-all pygame

if "%CLEAN_BUILD%"=="1" (
    echo Doing a full clean rebuild...
    if exist build rmdir /s /q build
    if exist dist rmdir /s /q dist
    if exist %APP_NAME%.spec del /q %APP_NAME%.spec
    set PYI_FLAGS=%PYI_FLAGS% --clean
) else (
    echo Doing an incremental build ^(pass --clean for a full rebuild^)...
)

uv run pyinstaller %PYI_FLAGS% %ENTRY_POINT%

echo.
echo Build finished. Executable is in the dist\ folder.

endlocal
