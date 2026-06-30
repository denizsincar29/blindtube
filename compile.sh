#!/usr/bin/env bash
# Build a standalone blindtube executable with PyInstaller.
# Works in git bash, MSYS2, and regular Linux/macOS shells.
set -e

APP_NAME="blindtube"
ENTRY_POINT="main.py"

# Pick whichever python is available
PY="python"
if ! command -v "$PY" >/dev/null 2>&1; then
    PY="python3"
fi

echo "Using interpreter: $(command -v "$PY")"

# Make sure pyinstaller is installed
"$PY" -m PyInstaller --version >/dev/null 2>&1 || "$PY" -m pip install pyinstaller

# Clean previous builds
rm -rf build dist "${APP_NAME}.spec"

"$PY" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    "$ENTRY_POINT"

echo
echo "Build finished. Executable is in the dist/ folder."
