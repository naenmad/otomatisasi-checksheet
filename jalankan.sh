#!/usr/bin/env bash
# Jalankan Otomatisasi Checksheet FactoryHub dalam Mode Visible (Jendela Browser Terbuka)
cd "$(dirname "$0")"

if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python run.py "$@"
