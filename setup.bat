@echo off
rem ==============================================================================
rem Installer & Dependency Setup Script for Windows (Command Prompt / Explorer)
rem PT. Summit Adyawinsa Indonesia - Otomatisasi Checksheet
rem ==============================================================================

setlocal enabledelayedexpansion
title Setup Otomatisasi Checksheet Summit Adyawinsa

echo ====================================================================
echo   INSTALLER ^& SETUP OTOMATISASI CHECKSHEET SUMMIT ADYAWINSA
echo ====================================================================
echo.

rem 1. Periksa Python
echo [*] Memeriksa instalasi Python...
set PYTHON_CMD=
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py -3
    )
)

if "%PYTHON_CMD%"=="" (
    echo [!] Python 3.9+ TIDAK DITEMUKAN.
    echo [*] Mencoba memasang via winget...
    winget install -e --id Python.Python.3.11 --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] Gagal memasang Python otomatis.
        echo Silakan unduh dan pasang manual dari: https://www.python.org/downloads/windows/
        echo PENTING: Centang kotak "Add Python to PATH" saat instalasi!
        pause
        exit /b 1
    )
    set PYTHON_CMD=python
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set PY_VER=%%i
echo [v] Python siap: %PY_VER%

rem 2. Periksa Node.js & npm
echo.
echo [*] Memeriksa instalasi Node.js ^& npm...
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [!] Node.js TIDAK DITEMUKAN.
    echo [*] Mencoba memasang via winget...
    winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
    if %errorlevel% neq 0 (
        echo [X] Gagal memasang Node.js otomatis.
        echo Silakan unduh dan pasang manual dari: https://nodejs.org/
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
for /f "tokens=*" %%i in ('npm --version 2^>^&1') do set NPM_VER=%%i
echo [v] Node.js siap: %NODE_VER%
echo [v] npm siap: v%NPM_VER%

rem 3. Siapkan Virtual Environment (.venv)
echo.
echo [*] Menyiapkan Python Virtual Environment (.venv)...
if not exist ".venv" (
    %PYTHON_CMD% -m venv .venv
    echo [v] Virtual environment .venv berhasil dibuat.
) else (
    echo [v] Virtual environment .venv sudah ada.
)

set VENV_PY=.venv\Scripts\python.exe
set VENV_PIP=.venv\Scripts\pip.exe

rem 4. Install Dependencies Python
echo.
echo [*] Menginstal dependensi Python dari requirements.txt...
call %VENV_PIP% install --upgrade pip --quiet
call %VENV_PIP% install -r requirements.txt --quiet
echo [v] Seluruh dependensi Python berhasil diinstal.

rem 5. Install Browser Playwright
echo.
echo [*] Memeriksa browser Playwright Chromium...
call %VENV_PY% -m playwright install chromium
echo [v] Browser Chromium siap untuk otomasi Playwright.

rem 6. Install Dependensi npm
echo.
echo [*] Menjalankan npm install...
call npm install --silent
echo [v] Dependensi Node/npm siap.

rem 7. Periksa File .env
echo.
echo [*] Memeriksa file konfigurasi .env...
if not exist ".env" (
    echo [*] Membuat file .env default...
    (
        echo FACTORYHUB_BASE_URL=https://factoryhub.summitadyawinsa.co.id
        echo FACTORYHUB_NIK=070817-033
        echo FACTORYHUB_PASSWORD=sai2026
        echo DEFAULT_EXCEL_FILE=6. IR - 51138E000P_BRKT ASSY-RR TOWING HOOK #Rev New EO.xlsx
        echo SUPABASE_URL=https://pkccxrqjnnhgjalcpnot.supabase.co
        echo SUPABASE_KEY=sb_publishable_ffPoXsFoLE3wFZjszPtSMQ_pfhPbdw6
        echo DATABASE_URL=postgresql://postgres.pkccxrqjnnhgjalcpnot:digitalisasi-checksheet@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
        echo GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/1iHoOMUJryHYAnjjC0-n6HN2zrcpU_y7u6TCoceLrTUY/edit?usp=sharing
    ) > .env
    echo [v] File .env berhasil dibuat.
) else (
    echo [v] File .env sudah ada.
)

rem 8. Seed Auth
echo.
echo [*] Menyiapkan akun sistem default...
call %VENV_PY% services\seed_auth.py >nul 2>nul

rem 9. Selesai
echo.
echo ====================================================================
echo   SEMUA KEBUTUHAN DAN DEPENDENSI BERHASIL DI-SETUP!
echo ====================================================================
echo.
echo Perintah untuk menjalankan aplikasi kapan saja:
echo   npm run dev
echo.

set /p START_APP="Jalankan server aplikasi sekarang? [Y/n]: "
if /i "%START_APP%"=="n" (
    echo Server siap dijalankan dengan perintah: npm run dev
    pause
    exit /b 0
)

echo [*] Menjalankan server aplikasi di http://localhost:8000 ...
call %VENV_PY% run_server.py
pause
