#!/bin/bash
# ==============================================================================
# Summit Checksheet Master Automation - Batch Runner
# Eksekusi massal semua checksheet dengan auto-submit ke FactoryHub
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
fi

python3 batch_run.py "$@"
