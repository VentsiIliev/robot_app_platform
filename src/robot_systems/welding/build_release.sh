#!/usr/bin/env bash
set -euo pipefail
PLATFORM_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PLATFORM_PROJECT_ROOT"
exec "${PYTHON_BIN:-$PLATFORM_PROJECT_ROOT/.venv/bin/python}" "$PLATFORM_PROJECT_ROOT/packaging/platform/build_and_release.py" welding "$@"
