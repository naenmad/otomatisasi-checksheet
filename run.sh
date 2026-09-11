#!/usr/bin/env bash
# ==============================================================================
# FactoryHub Checksheet Master Automation Runner
#
# Penggunaan:
#   ./run.sh <part_number> [scan_image: yes/no]
#
# Contoh:
#   1. Hasil scan data (gambar di folder, tidak scan Excel):
#      ./run.sh 75511b040p no
#      (atau cukup: ./run.sh 75511b040p)
#
#   2. Excel mentah (ekstrak gambar tersemat dari Excel):
#      ./run.sh 51138e000p yes
#      (atau cukup: ./run.sh 51138e000p)
#
#   3. Pilih interaktif dari daftar part yang tersedia:
#      ./run.sh
#
#   4. Dry-run untuk uji ekstraksi tanpa membuka browser:
#      ./run.sh 75511b040p --dry-run
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

python3 run.py "$@"
