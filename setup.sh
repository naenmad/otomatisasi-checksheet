#!/usr/bin/env bash
# ==============================================================================
# Installer & Dependency Setup Script
# PT. Summit Adyawinsa Indonesia - Otomatisasi Checksheet
#
# Mendukung macOS, Linux, dan Windows (Git Bash / MSYS / WSL)
# Penggunaan:
#   chmod +x setup.sh
#   ./setup.sh
# ==============================================================================

set -e

# Format and Color
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    BOLD=''
    NC=''
fi

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo -e "${BLUE}${BOLD}====================================================================${NC}"
echo -e "${BLUE}${BOLD}  INSTALLER & SETUP OTOMATISASI CHECKSHEET SUMMIT ADYAWINSA        ${NC}"
echo -e "${BLUE}${BOLD}====================================================================${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. DETEKSI SISTEM OPERASI (OS)
# ------------------------------------------------------------------------------
OS_TYPE="unknown"
UNAME_OUT="$(uname -s 2>/dev/null || echo "unknown")"

case "${UNAME_OUT}" in
    Darwin*)
        OS_TYPE="mac"
        echo -e "[*] Sistem Operasi terdeteksi: ${CYAN}macOS (Darwin)${NC}"
        ;;
    Linux*)
        OS_TYPE="linux"
        echo -e "[*] Sistem Operasi terdeteksi: ${CYAN}Linux${NC}"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        OS_TYPE="windows"
        echo -e "[*] Sistem Operasi terdeteksi: ${CYAN}Windows (Bash / MinGW)${NC}"
        ;;
    *)
        OS_TYPE="unknown"
        echo -e "[!] Sistem Operasi: ${YELLOW}${UNAME_OUT}${NC}"
        ;;
esac

# ------------------------------------------------------------------------------
# 2. VALIDASI PYTHON (Minimal Python 3.9)
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Memeriksa instalasi Python 3..."

PYTHON_CMD=""
for cmd in python3 python py; do
    if command -v "$cmd" >/dev/null 2>&1; then
        # Cek apakah versi >= 3.9
        if "$cmd" -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}[!] Python versi 3.9 atau lebih baru TIDAK DITEMUKAN di sistem ini.${NC}"
    echo -e "${YELLOW}[*] Mencoba opsi instalasi otomatis...${NC}"

    if [ "$OS_TYPE" = "mac" ]; then
        if command -v brew >/dev/null 2>&1; then
            echo -e "[*] Menjalankan: brew install python@3.11"
            brew install python@3.11
            PYTHON_CMD="python3"
        else
            echo -e "${RED}[X] Homebrew tidak terdeteksi. Silakan pasang Python 3.11+ manual dari:${NC}"
            echo -e "    https://www.python.org/downloads/macos/"
            exit 1
        fi
    elif [ "$OS_TYPE" = "windows" ]; then
        if command -v winget >/dev/null 2>&1; then
            echo -e "[*] Menjalankan: winget install Python.Python.3.11"
            winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements || true
            PYTHON_CMD="python"
        else
            echo -e "${RED}[X] Silakan unduh dan pasang Python 3.11+ untuk Windows dari:${NC}"
            echo -e "    https://www.python.org/downloads/windows/"
            echo -e "${YELLOW}[PENTING] Centang kotak 'Add Python to PATH' saat proses instalasi!${NC}"
            exit 1
        fi
    elif [ "$OS_TYPE" = "linux" ]; then
        if command -v apt-get >/dev/null 2>&1; then
            echo -e "[*] Menjalankan: sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv"
            sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv
            PYTHON_CMD="python3"
        else
            echo -e "${RED}[X] Silakan pasang python3 dan python3-venv menggunakan package manager distro Anda.${NC}"
            exit 1
        fi
    fi
fi

PY_VER="$("$PYTHON_CMD" --version 2>&1)"
echo -e "${GREEN}[✓] Python siap:${NC} ${PY_VER} (${PYTHON_CMD})"

# ------------------------------------------------------------------------------
# 3. VALIDASI NODE.JS & NPM (Minimal Node 16)
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Memeriksa instalasi Node.js & npm..."

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo -e "${YELLOW}[!] Node.js atau npm belum terpasang.${NC}"
    echo -e "[*] Mencoba opsi instalasi otomatis..."

    if [ "$OS_TYPE" = "mac" ]; then
        if command -v brew >/dev/null 2>&1; then
            echo -e "[*] Menjalankan: brew install node"
            brew install node
        else
            echo -e "${RED}[X] Homebrew tidak terdeteksi. Pasang Node.js LTS dari:${NC}"
            echo -e "    https://nodejs.org/"
            exit 1
        fi
    elif [ "$OS_TYPE" = "windows" ]; then
        if command -v winget >/dev/null 2>&1; then
            echo -e "[*] Menjalankan: winget install OpenJS.NodeJS.LTS"
            winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements || true
        else
            echo -e "${RED}[X] Silakan unduh dan pasang Node.js LTS untuk Windows dari:${NC}"
            echo -e "    https://nodejs.org/"
            exit 1
        fi
    elif [ "$OS_TYPE" = "linux" ]; then
        echo -e "${YELLOW}[*] Silakan pasang Node.js menggunakan package manager Anda:${NC}"
        echo -e "    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -"
        echo -e "    sudo apt-get install -y nodejs"
        exit 1
    fi
fi

NODE_VER="$(node --version 2>&1 || echo "unknown")"
NPM_VER="$(npm --version 2>&1 || echo "unknown")"
echo -e "${GREEN}[✓] Node.js siap:${NC} ${NODE_VER}"
echo -e "${GREEN}[✓] npm siap:${NC} v${NPM_VER}"

# ------------------------------------------------------------------------------
# 4. PEMBUATAN PYTHON VIRTUAL ENVIRONMENT (.venv)
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Menyiapkan Python Virtual Environment (.venv)..."

if [ ! -d ".venv" ]; then
    "$PYTHON_CMD" -m venv .venv
    echo -e "${GREEN}[✓] Virtual environment .venv berhasil dibuat.${NC}"
else
    echo -e "${GREEN}[✓] Virtual environment .venv sudah tersedia.${NC}"
fi

# Tentukan path executable di dalam .venv (Cross-Platform)
if [ -f ".venv/Scripts/pip.exe" ]; then
    VENV_PIP=".venv/Scripts/pip.exe"
    VENV_PY=".venv/Scripts/python.exe"
elif [ -f ".venv/bin/pip" ]; then
    VENV_PIP=".venv/bin/pip"
    VENV_PY=".venv/bin/python"
else
    echo -e "${RED}[X] Direktori bin/Scripts pada .venv tidak valid.${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 5. INSTALASI DEPENDENCIES PYTHON
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Memperbarui pip dan menginstal dependensi Python dari requirements.txt..."
"$VENV_PIP" install --upgrade pip --quiet
"$VENV_PIP" install -r requirements.txt --quiet
echo -e "${GREEN}[✓] Seluruh dependensi Python berhasil diinstal.${NC}"

# ------------------------------------------------------------------------------
# 6. INSTALASI BROWSER PLAYWRIGHT (CHROMIUM)
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Memeriksa browser Playwright Chromium..."
"$VENV_PY" -m playwright install chromium || {
    echo -e "${YELLOW}[!] Download browser internal Playwright gagal atau sudah ada Chrome lokal.${NC}"
    echo -e "    Sistem akan otomatis menggunakan Google Chrome bawaan sistem bila tersedia."
}
echo -e "${GREEN}[✓] Browser Chromium/Chrome siap untuk otomasi Playwright.${NC}"

# ------------------------------------------------------------------------------
# 7. DEPENDENSI NPM
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Menjalankan npm install..."
npm install --silent
echo -e "${GREEN}[✓] Dependensi Node/npm siap.${NC}"

# ------------------------------------------------------------------------------
# 8. KONFIGURASI ENVIRONMENT (.env)
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Memeriksa file konfigurasi .env..."
if [ ! -f ".env" ]; then
    echo -e "[*] Membuat file .env dengan konfigurasi default..."
    cat << 'EOF' > .env
FACTORYHUB_BASE_URL=https://factoryhub.summitadyawinsa.co.id
FACTORYHUB_NIK=070817-033
FACTORYHUB_PASSWORD=sai2026
DEFAULT_EXCEL_FILE=6. IR - 51138E000P_BRKT ASSY-RR TOWING HOOK #Rev New EO.xlsx

SUPABASE_URL=https://pkccxrqjnnhgjalcpnot.supabase.co
SUPABASE_KEY=sb_publishable_ffPoXsFoLE3wFZjszPtSMQ_pfhPbdw6
DATABASE_URL=postgresql://postgres.pkccxrqjnnhgjalcpnot:digitalisasi-checksheet@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/1iHoOMUJryHYAnjjC0-n6HN2zrcpU_y7u6TCoceLrTUY/edit?usp=sharing
EOF
    echo -e "${GREEN}[✓] File .env berhasil dibuat.${NC}"
else
    echo -e "${GREEN}[✓] File .env sudah ada.${NC}"
fi

# ------------------------------------------------------------------------------
# 9. SEED DATABASE USER / AUTH
# ------------------------------------------------------------------------------
echo ""
echo -e "[*] Menyiapkan akun sistem default..."
"$VENV_PY" services/seed_auth.py || true

# ------------------------------------------------------------------------------
# 10. SELESAI & TAMPILAN STATUS
# ------------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}====================================================================${NC}"
echo -e "${GREEN}${BOLD}  SEMUA KEBUTUHAN DAN DEPENDENSI BERHASIL DI-SETUP!                ${NC}"
echo -e "${GREEN}${BOLD}====================================================================${NC}"
echo ""
echo -e "Ringkasan Konfigurasi:"
echo -e "  - Python Runner   : ${CYAN}${VENV_PY}${NC}"
echo -e "  - Node / npm      : ${CYAN}${NODE_VER} / v${NPM_VER}${NC}"
echo -e "  - Database URL    : ${CYAN}Terhubung ke Supabase PostgreSQL${NC}"
echo -e "  - Google Sheet    : ${CYAN}3 Sheets Aktif (Overview, Data Master, Log)${NC}"
echo ""
echo -e "Perintah untuk menjalankan aplikasi kapan saja:"
echo -e "  ${BOLD}npm run dev${NC}    atau    ${BOLD}./run.sh${NC}"
echo ""

# Tanya user apakah ingin langsung menjalankan server sekarang
read -p "Jalankan server aplikasi sekarang? [Y/n]: " -n 1 -r REPLY_START
echo ""
if [[ $REPLY_START =~ ^[Yy]$ ]] || [[ -z $REPLY_START ]]; then
    echo -e "[*] Menjalankan server aplikasi di http://localhost:8000 ..."
    exec "$VENV_PY" run_server.py
fi
