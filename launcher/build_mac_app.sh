#!/usr/bin/env bash
set -eu

PROJECT_DIR="/Users/hankmacmini/Documents/Projects/AI-Investment-Research"
SCRIPT_PATH="$PROJECT_DIR/launcher/AI_Investment_Research.applescript"
DIST_DIR="$PROJECT_DIR/dist"
APP_PATH="$DIST_DIR/AI Investment Research.app"

if ! command -v osacompile >/dev/null 2>&1; then
  printf '%s\n' "osacompile not found. This build script must run on macOS."
  exit 1
fi

if [ ! -f "$SCRIPT_PATH" ]; then
  printf '%s\n' "AppleScript source not found: $SCRIPT_PATH"
  exit 1
fi

mkdir -p "$DIST_DIR"
osacompile -o "$APP_PATH" "$SCRIPT_PATH"

printf 'Built: %s\n' "$APP_PATH"
