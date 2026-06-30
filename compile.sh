#!/usr/bin/env bash
# Build a standalone blindtube executable with PyInstaller, via uv.
# Works in git bash, MSYS2, and regular Linux/macOS shells.
set -e

APP_NAME="blindtube"
ENTRY_POINT="main.py"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it from https://docs.astral.sh/uv/" >&2
    exit 1
fi

echo "Syncing dependencies with uv..."
uv sync

# Clean previous builds
rm -rf build dist "${APP_NAME}.spec"

uv run pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --collect-all pygame \
    "$ENTRY_POINT"

echo
echo "Build finished. Executable is in the dist/ folder."
