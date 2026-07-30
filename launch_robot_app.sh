#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${APP_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON}" ]]; then
  echo "Python virtualenv not found: ${PYTHON}" >&2
  exit 1
fi

export PYTHONPATH="${APP_DIR}:${PYTHONPATH:-}"
cd "${APP_DIR}"

exec "${PYTHON}" "${APP_DIR}/src/bootstrap/main.py"
