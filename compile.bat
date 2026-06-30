@echo off
REM Build a standalone blindtube executable with PyInstaller, via uv.

setlocal

set APP_NAME=blindtube
set ENTRY_POINT=main.py

where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed. Install it from https://docs.astral.sh/uv/
    exit /b 1
)

echo Syncing dependencies with uv...
uv sync

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APP_NAME%.spec del /q %APP_NAME%.spec

uv run pyinstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name %APP_NAME% ^
    %ENTRY_POINT%

echo.
echo Build finished. Executable is in the dist\ folder.

endlocal
