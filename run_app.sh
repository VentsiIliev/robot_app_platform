#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH="$(pwd)"
exec python src/bootstrap/main.py "$@"