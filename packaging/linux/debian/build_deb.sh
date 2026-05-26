#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"
VERSION="${1:-0.1.0}"
ARCH="${ROBOT_APP_PLATFORM_ARCH:-amd64}"
PACKAGE_NAME="robot-app-platform"
PREFIX="/opt/robot-app-platform"
BUILD_ROOT="$REPO_ROOT/build/linux-debian"
PACKAGE_ROOT="$BUILD_ROOT/${PACKAGE_NAME}_${VERSION}_${ARCH}"
OUTPUT_DIR="$REPO_ROOT/dist/linux"
DEB_PATH="$OUTPUT_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

if [[ ! "$VERSION" =~ ^[0-9]+([.][0-9]+){1,2}([+~.-][A-Za-z0-9.]+)?$ ]]; then
    printf 'Invalid Debian package version: %s\n' "$VERSION" >&2
    exit 1
fi

if [[ ! -x "$REPO_ROOT/.venv/bin/python" ]]; then
    printf 'Missing project runtime: %s/.venv/bin/python\n' "$REPO_ROOT" >&2
    printf 'Build the package from the prepared Ubuntu development checkout.\n' >&2
    exit 1
fi

for command in dpkg-deb git rsync tar; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'Required build command is unavailable: %s\n' "$command" >&2
        exit 1
    fi
done

rm -rf "$PACKAGE_ROOT"
mkdir -p \
    "$PACKAGE_ROOT/DEBIAN" \
    "$PACKAGE_ROOT$PREFIX/app" \
    "$PACKAGE_ROOT$PREFIX/runtime" \
    "$PACKAGE_ROOT/usr/bin" \
    "$PACKAGE_ROOT/usr/share/applications" \
    "$PACKAGE_ROOT/usr/share/icons/hicolor/256x256/apps" \
    "$OUTPUT_DIR"

# Package only committed source content; build and ignored runtime output do not leak in.
git -C "$REPO_ROOT" archive --format=tar HEAD | tar -xf - -C "$PACKAGE_ROOT$PREFIX/app"

# Bundle the prepared Linux runtime so installation does not require PyPI access.
rsync -a \
    --exclude '__pycache__/' \
    --exclude '*.pyc' \
    "$REPO_ROOT/.venv/" \
    "$PACKAGE_ROOT$PREFIX/runtime/"

install -Dm755 "$SCRIPT_DIR/robot-app-platform" "$PACKAGE_ROOT/usr/bin/robot-app-platform"
install -Dm644 "$SCRIPT_DIR/robot-app-platform.desktop" \
    "$PACKAGE_ROOT/usr/share/applications/robot-app-platform.desktop"
install -Dm644 "$REPO_ROOT/packaging/vision_dxf_exporter/Logo.png" \
    "$PACKAGE_ROOT/usr/share/icons/hicolor/256x256/apps/robot-app-platform.png"
printf '%s\n' "$VERSION" > "$PACKAGE_ROOT$PREFIX/VERSION"

INSTALLED_SIZE="$(du -sk "$PACKAGE_ROOT" | awk '{print $1}')"
cat > "$PACKAGE_ROOT/DEBIAN/control" <<EOF
Package: $PACKAGE_NAME
Version: $VERSION
Section: science
Priority: optional
Architecture: $ARCH
Installed-Size: $INSTALLED_SIZE
Maintainer: Zewyn1 <danail.atanasov33@gmail.com>
Depends: python3 (>= 3.12), rsync, libc6, libglib2.0-0, libgl1, libxkbcommon-x11-0, libxcb-cursor0
Description: Vision-guided industrial robot application platform
 Robot App Platform provides the PyQt6 operator shell and the active paint
 system with vision calibration, contour workflows, marker-based paint-base
 positioning, and robot process tooling. This package bundles the prepared
 Ubuntu amd64 Python runtime and installs a desktop launcher.
EOF

dpkg-deb --build --root-owner-group "$PACKAGE_ROOT" "$DEB_PATH"
dpkg-deb --info "$DEB_PATH"
printf '\nCreated package: %s\n' "$DEB_PATH"
