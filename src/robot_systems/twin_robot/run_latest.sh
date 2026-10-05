#!/usr/bin/env bash
set -euo pipefail
PLATFORM_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PLATFORM_PROJECT_ROOT"
exec /usr/bin/python3 "$PLATFORM_PROJECT_ROOT/packaging/platform/local_release.py" run twin_robot "$@"
