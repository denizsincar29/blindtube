#!/usr/bin/env bash
# Build a standalone blindtube executable with PyInstaller, via uv.
# Works in git bash, MSYS2, and regular Linux/macOS shells.
#
# By default this does an INCREMENTAL build (fast, reuses PyInstaller's
# cache). Pass --clean (or set CLEAN=1) to force a full from-scratch
# rebuild, e.g. after upgrading dependencies or if the build looks broken.
set -e

APP_NAME="blindtube"
ENTRY_POINT="main.py"
CLEAN_BUILD="${CLEAN:-0}"

for arg in "$@"; do
    if [ "$arg" = "--clean" ]; then
        CLEAN_BUILD=1
    fi
done

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is not installed. Install it from https://docs.astral.sh/uv/" >&2
    exit 1
fi

echo "Syncing dependencies with uv..."
uv sync

PYI_FLAGS=(--noconfirm --onefile --windowed --name "$APP_NAME" --collect-all pygame --collect-data accessible_output3)

if [ "$CLEAN_BUILD" = "1" ]; then
    echo "Doing a full clean rebuild..."
    rm -rf build dist "${APP_NAME}.spec"
    PYI_FLAGS+=(--clean)
else
    echo "Doing an incremental build (pass --clean for a full rebuild)..."
fi

uv run pyinstaller "${PYI_FLAGS[@]}" "$ENTRY_POINT"

echo
echo "Build finished. Executable is in the dist/ folder."
