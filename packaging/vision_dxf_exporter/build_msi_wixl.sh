#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

WINEPREFIX="${WINEPREFIX:-$ROOT_DIR/.wine-build}"
WINE_PYTHON_EXE="${WINE_PYTHON_EXE:-C:\\Python311\\python.exe}"
WIX_HEAT_EXE="${WIX_HEAT_EXE:-/tmp/wix311/bin/heat.exe}"

APP_DIR="$ROOT_DIR/dist/PLDxfVision"
BUILD_DIR="$ROOT_DIR/build/vision_dxf_exporter_msi"
WIXL_BUILD_DIR="$ROOT_DIR/build/vision_dxf_exporter_msi_wixl"
OUT_DIR="$ROOT_DIR/dist/installer"
OUT_MSI="$OUT_DIR/PLDxfVisionSetup.msi"

to_wine_path() {
  local path="$1"
  printf 'Z:%s' "${path//\//\\}"
}

if ! command -v wine >/dev/null 2>&1; then
  echo "wine is required to run Windows Python and WiX heat.exe." >&2
  exit 1
fi

if ! command -v wixl >/dev/null 2>&1; then
  echo "wixl is required to build the MSI. Install it with: sudo apt install wixl" >&2
  exit 1
fi

mkdir -p "$BUILD_DIR" "$WIXL_BUILD_DIR" "$OUT_DIR"

env WINEPREFIX="$WINEPREFIX" wine "$WINE_PYTHON_EXE" \
  -m PyInstaller packaging\\vision_dxf_exporter\\vision_dxf_exporter.spec \
  --noconfirm --clean

env WINEPREFIX="$WINEPREFIX" wine "$WIX_HEAT_EXE" \
  dir "$(to_wine_path "$APP_DIR")" \
  -cg AppFiles \
  -dr INSTALLFOLDER \
  -srd \
  -gg \
  -sfrag \
  -sreg \
  -var var.SourceDir \
  -out "$(to_wine_path "$BUILD_DIR/app_files.wxs")"

perl -pe 's#\\#/#g' "$BUILD_DIR/app_files.wxs" > "$WIXL_BUILD_DIR/app_files.wxs"

wixl \
  -a x64 \
  -D "SourceDir=$APP_DIR" \
  -o "$OUT_MSI" \
  packaging/vision_dxf_exporter/msi/product_wixl.wxs \
  "$WIXL_BUILD_DIR/app_files.wxs"

echo "Built $OUT_MSI"
