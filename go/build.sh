#!/usr/bin/env bash
# Build a standalone blindtube-go executable.
# Mirrors ../compile.sh's flags so muscle memory carries over.
set -e

cd "$(dirname "$0")"

APP_NAME="blindtube"
CLEAN_BUILD="${CLEAN:-0}"

for arg in "$@"; do
    if [ "$arg" = "--clean" ]; then
        CLEAN_BUILD=1
    fi
done

if ! command -v go >/dev/null 2>&1; then
    echo "go is not installed. Install Go 1.26+ from https://go.dev/dl/" >&2
    exit 1
fi

if [ "$CLEAN_BUILD" = "1" ]; then
    echo "Cleaning module/build cache for a full rebuild..."
    go clean -cache
fi

echo "Fetching/locking dependencies..."
go mod tidy

echo "Building..."
go build -o "$APP_NAME" ./cmd/blindtube

echo
echo "Build finished: ./go/$APP_NAME"
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "Note: ffmpeg not found on PATH — video downloads will use a single"
    echo "pre-muxed stream instead of best-quality composite download."
fi
