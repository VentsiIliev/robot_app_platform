#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v wine >/dev/null 2>&1; then
  echo "Missing wine. Install Wine first, then install Windows Python inside the Wine prefix." >&2
  exit 1
fi

if [[ -n "${WINE_PYTHON_EXE:-}" ]]; then
  PYTHON_CMD=(wine "${WINE_PYTHON_EXE}")
else
  PYTHON_CMD=(wine py.exe -3)
fi

if [[ -n "${WINE_ISCC_EXE:-}" ]]; then
  ISCC_CMD=(wine "${WINE_ISCC_EXE}")
else
  ISCC_CMD=(wine "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe")
fi

"${PYTHON_CMD[@]}" -m PyInstaller packaging\\vision_dxf_exporter\\vision_dxf_exporter.spec --noconfirm --clean

if ! "${ISCC_CMD[@]}" packaging\\vision_dxf_exporter\\installer.iss; then
  echo "PyInstaller build completed, but Inno Setup did not run." >&2
  echo "Install Inno Setup 6 inside Wine, or set WINE_ISCC_EXE to ISCC.exe." >&2
  exit 1
fi
