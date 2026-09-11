#!/usr/bin/env bash
# ==============================================================================
# FactoryHub Fast Batch Part Checker
#
# Penggunaan:
#   1. Menggunakan file default (parts.txt):
#      ./search.sh
#
#   2. Cek part langsung dari parameter:
#      ./search.sh 65750-T86A-K002-H1
#      ./search.sh 62130-3K6-K001-H1 65750-T86A-K002-H1 75511B040P
#
#   3. Menggunakan file teks kustom:
#      ./search.sh daftar_part.txt
#
#   4. Cek seluruh dokumen yang ada di folder documents/:
#      ./search.sh --documents
# ==============================================================================

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Aktifkan virtual environment jika ada
if [ -d "$DIR/.venv" ]; then
    source "$DIR/.venv/bin/activate"
elif [ -d "$DIR/venv" ]; then
    source "$DIR/venv/bin/activate"
fi

python3 search.py "$@"
