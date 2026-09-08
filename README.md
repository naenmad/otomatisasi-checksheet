# FactoryHub Checksheet Master Automation

Sistem otomatisasi untuk mengekstrak data checksheet dari file Excel (*Inspection Report*) dan mengisikannya secara otomatis ke portal **FactoryHub (PT. Summit Adyawinsa Indonesia)** menggunakan Python dan Playwright.

---

## Fitur Utama

- **Ekstraksi Data Excel Otomatis**:
  - Membaca metadata Part Number, Part Name, Model, dan Doc Number dari awalan nama file (contoh: `6. IR ...` $\rightarrow$ `Form 6`).
  - Deteksi sheet dinamis: otomatis mendeteksi sheet mana pun yang memuat tabel inspeksi (*Inspection Item* & *Standard*).
  - Mengekstrak semua gambar referensi mesin/part layout yang tersemat di lembar Excel.
  - Mengekstrak seluruh baris inspection points dengan nomor titik (balloon number), standar nominal, dan toleransi.
- **Pencocokan Part Otomatis**:
  - Memeriksa ketersediaan part di **Regular Production Part**.
  - Jika belum terdaftar, otomatis beralih ke **New Project Part** dan mencocokkan part number.
- **Mode Review Visual (Headed Mode)**:
  - Secara default membuka jendela browser Chrome di layar Anda.
  - Mengisi seluruh field, gambar, dan tabel inspeksi di depan Anda.
  - Jendela browser tetap terbuka agar Anda bisa memeriksa dan menekan tombol **"Save Template"** sendiri.
- **Keamanan Kredensial**:
  - Menggunakan file `.env` untuk NIK, password, dan URL FactoryHub sehingga tidak ada data sensitif yang bocor ke repository publik.

---

## Struktur Proyek

```text
.
├── extractor.py        # Modul pembaca dan parser data dari file Excel
├── automator.py        # Modul otomatisasi browser (Playwright) ke FactoryHub
├── run.py              # CLI Runner utama
├── jalankan.sh         # Script shortcut eksekusi cepat
├── requirements.txt    # Daftar dependensi Python
├── .env.example        # Template konfigurasi environment
├── .gitignore          # Konfigurasi file yang diabaikan Git (termasuk .env & file Excel)
└── README.md           # Dokumentasi proyek
```

---

## Persyaratan Sistem

- Python 3.10 atau versi lebih baru
- Google Chrome atau Chromium browser (diinstal otomatis via Playwright)
- Koneksi ke jaringan FactoryHub Summit Adyawinsa

---

## Instalasi

1. **Clone repository:**
   ```bash
   git clone https://github.com/naenmad/otomatisasi-checksheet.git
   cd otomatisasi-checksheet
   ```

2. **Buat virtual environment dan aktifkan:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependensi:**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Konfigurasi Environment (`.env`):**
   Salin file `.env.example` menjadi `.env`:
   ```bash
   cp .env.example .env
   ```
   Buka file `.env` dan sesuaikan kredensial Anda:
   ```env
   FACTORYHUB_BASE_URL=https://factoryhub.summitadyawinsa.co.id
   FACTORYHUB_NIK=your_employee_id
   FACTORYHUB_PASSWORD=your_password
   DEFAULT_EXCEL_FILE=6. IR - 51138E000P_BRKT ASSY-RR TOWING HOOK #Rev New EO.xlsx
   ```

---

## Cara Penggunaan

### 1. Eksekusi Cepat (Rekomendasi)
Cukup jalankan script shortcut:
```bash
./jalankan.sh
```

Browser Chrome akan otomatis terbuka di layar, login ke FactoryHub, memilih part, mengunggah gambar referensi, dan mengisi seluruh titik inspeksi. Jendela browser akan tetap terbuka sehingga Anda bisa mereview hasilnya dan klik tombol **"Save Template"** sendiri.

### 2. Opsi Perintah Lanjutan (CLI)

- **Menjalankan file Excel lain:**
  ```bash
  python run.py --excel "path/ke/file_checksheet_lain.xlsx"
  ```

- **Menyertakan gambar manual (jika di Excel tidak ada gambar):**
  Anda bisa menaruh gambar secara manual tanpa takut tertimpa:
  1. **Otomatis per Part Number:** Buat folder `images/<part_number>/` (contoh: `images/75511B040P/`), skrip otomatis membaca gambar dari folder tersebut.
  2. **Atau langsung di folder `images/`**.
  3. **Atau tentukan folder bebas via opsi `--images-dir`:**
     ```bash
     python run.py --excel "Inspection_Standard_75511B040P.xlsx" --images-dir "path/ke/folder_gambar"
     ```

- **Menentukan Doc Number kustom:**
  ```bash
  python run.py --doc-number "Form 7"
  ```

- **Menjalankan di latar belakang tanpa membuka jendela (Headless):**
  ```bash
  python run.py --headless
  ```

- **Langsung submit / save template secara otomatis tanpa jeda review:**
  ```bash
  python run.py --submit
  ```

---

## Keamanan Data Sensitif

Repository ini secara ketat mengabaikan file rahasia melalui `.gitignore`:
- File kredensial `.env`
- Seluruh file Excel (`*.xlsx`, `*.xls`)
- Gambar dan tangkapan layar sementara (`extracted_images/`, `*.png`)
- Virtual environment (`.venv/`)

---

## Lisensi

Proyek ini dibuat untuk keperluan internal otomatisasi checksheet quality control PT. Summit Adyawinsa Indonesia.
