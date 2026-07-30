#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
DIST_DIR="$PROJECT_ROOT/dist"
WORK_DIR="$PROJECT_ROOT/build/pyinstaller"
MPLCONFIGDIR="$WORK_DIR/matplotlib"

if [[ ! -x "$PYTHON_BIN" ]]; then
    echo "Python environment not found: $PYTHON_BIN" >&2
    exit 1
fi

if ! "$PYTHON_BIN" -c "import PyInstaller" 2>/dev/null; then
    echo "PyInstaller is not installed in the build environment." >&2
    echo "Install it with:" >&2
    echo "  $PYTHON_BIN -m pip install -r packaging/requirements-build.txt" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
mkdir -p "$MPLCONFIGDIR"
export MPLCONFIGDIR
"$PYTHON_BIN" -m PyInstaller \
    --noconfirm \
    --clean \
    --distpath "$DIST_DIR" \
    --workpath "$WORK_DIR" \
    packaging/paint.spec

PYZ_TOC="$WORK_DIR/paint/PYZ-00.toc"
if grep -Eq "\\('src\\.robot_systems\\.(glue|welding)(\\.|')" "$PYZ_TOC"; then
    echo "ERROR: a non-paint robot-system module was bundled." >&2
    exit 1
fi

if grep -Eq "\\('src\\.robot_systems\\.paint\\..*\\.example_usage'" "$PYZ_TOC"; then
    echo "ERROR: a paint example module was bundled." >&2
    exit 1
fi

if find "$DIST_DIR/paint-robot" \
    \( -path "*/src/robot_systems/glue*" -o -path "*/src/robot_systems/welding*" \) \
    -print -quit | grep -q .; then
    echo "ERROR: a non-paint robot-system directory was bundled." >&2
    exit 1
fi

echo "Paint bundle created at: $DIST_DIR/paint-robot"
