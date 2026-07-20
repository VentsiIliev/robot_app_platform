#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${APP_DIR}/.venv/bin/python"
GUI_CORES="${ROBOT_APP_GUI_CORES:-1}"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtualenv not found: ${PYTHON}" >&2
  exit 1
fi

export PYTHONPATH="${APP_DIR}:${PYTHONPATH:-}"
cd "${APP_DIR}"

exec taskset -c "${GUI_CORES}" "${PYTHON}" "${APP_DIR}/src/bootstrap/main.py"
