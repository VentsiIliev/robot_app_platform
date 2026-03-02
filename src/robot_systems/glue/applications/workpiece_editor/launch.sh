#!/bin/bash
# Quick launcher for Contour Editor Plugin in standalone mode

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=========================================="
echo "Contour Editor Plugin - Standalone Mode"
echo "=========================================="
echo ""
echo "Clearing Python cache..."
find "$SCRIPT_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$SCRIPT_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
echo "Starting plugin..."
echo ""

cd "$SCRIPT_DIR"
python3 run_standalone.py

