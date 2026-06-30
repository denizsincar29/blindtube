@echo off
REM Build a standalone blindtube executable with PyInstaller.

setlocal

set APP_NAME=blindtube
set ENTRY_POINT=main.py

where python >nul 2>nul
if %errorlevel%==0 (
    set PY=python
) else (
    set PY=py
)

echo Using interpreter: %PY%

%PY% -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    %PY% -m pip install pyinstaller
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist %APP_NAME%.spec del /q %APP_NAME%.spec

%PY% -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --name %APP_NAME% ^
    %ENTRY_POINT%

echo.
echo Build finished. Executable is in the dist\ folder.

endlocal
