#!/bin/sh
# Builds aseprite-mcp:arch (Dockerfile.arch) using the Aseprite package
# yay built from the AUR (`yay -S aseprite`).
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PKG_DIR="${ASEPRITE_PKG_DIR:-$HOME/.cache/yay/aseprite}"
exec docker build -t aseprite-mcp:arch \
  --build-context aseprite_pkg="$PKG_DIR" \
  -f "$REPO/Dockerfile.arch" "$REPO"
