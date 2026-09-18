#!/usr/bin/env bash
# ==============================================================================
# Summit Checksheet Image Optimizer & WebP Compressor
# Rumus Shell untuk mengonversi semua gambar (PNG, JPG, JPEG) ke WebP terkompresi.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Resolve Python in virtual environment or fallback to system python3
if [ -f "./.venv/bin/python" ]; then
    PYTHON_CMD="./.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    echo "[-] Error: Python 3 tidak ditemukan!"
    exit 1
fi

# Run the optimizer
$PYTHON_CMD compress_webp.py "$@"
