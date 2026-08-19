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

ORIGINAL_STTY=""
APP_PID=""

if [[ -t 0 ]]; then
  ORIGINAL_STTY="$(stty -g)"
  stty intr ^X
  echo "Press Ctrl+X in this terminal to stop the robot app."
fi

cleanup() {
  local status=$?
  trap - INT TERM HUP EXIT

  if [[ -n "${APP_PID}" ]] && kill -0 "${APP_PID}" 2>/dev/null; then
    kill -INT "${APP_PID}" 2>/dev/null || true
    for _ in {1..300}; do
      kill -0 "${APP_PID}" 2>/dev/null || break
      sleep 0.1
    done
    if kill -0 "${APP_PID}" 2>/dev/null; then
      kill -TERM "${APP_PID}" 2>/dev/null || true
    fi
    wait "${APP_PID}" 2>/dev/null || true
  fi

  if [[ -n "${ORIGINAL_STTY}" ]]; then
    stty "${ORIGINAL_STTY}" 2>/dev/null || true
  fi

  exit "${status}"
}

trap cleanup INT TERM HUP EXIT

"${PYTHON}" "${APP_DIR}/src/bootstrap/run_main.py" &
APP_PID=$!
wait "${APP_PID}"
