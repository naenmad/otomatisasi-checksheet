# FactoryHub Checksheet Master Automation

Sistem otomatisasi untuk mengekstrak data checksheet dari file Excel (*Inspection Report*) dan mengisikannya secara otomatis ke portal **FactoryHub (PT. Summit Adyawinsa Indonesia)** menggunakan Python dan Playwright.

---

## 👥 Platform Kolaborasi Tim (Zul, Iqbal, Rama, Yogi)

Sistem ini kini dilengkapi dengan **Web Dashboard Multi-User**, **Shared Database (Supabase PostgreSQL)**, dan **Batch Automator** yang memungkinkan tim berkolaborasi secara real-time.

```text
┌─────────────────────────────────────────────────────────────┐
│                 TEAM SHARED DATABASE                        │
│            Supabase PostgreSQL (atau SQLite Fallback)       │
└──────────────────────────────┬──────────────────────────────┘
                               │
                ┌──────────────┴──────────────┐
                │  FastAPI Backend (Port 8000)│
                └──────────────┬──────────────┘
                               │
     ┌──────────────────┬──────┴───────────┬──────────────────┐
     │                  │                  │                  │
┌────┴─────┐      ┌─────┴────┐       ┌─────┴────┐       ┌─────┴────┐
│   Zul    │      │  Iqbal   │       │   Rama   │       │   Yogi   │
└──────────┘      └──────────┘       └──────────┘       └──────────┘
```

### 1. Menjalankan Web Dashboard
```bash
# Jalankan server
python run_server.py
```
Buka di browser: **`http://localhost:8000`**

### 2. Berbagi Akses ke Laptop Rekan Tim (`./share.sh`)
Gunakan script pembagi jaringan untuk membagikan akses ke Zul, Iqbal, Rama, atau Yogi:
```bash
./share.sh
```
Pilihan koneksi:
- **Pilihan 1 (Jaringan Wi-Fi / Kantor Sama):**
  Rekan tim cukup membuka URL IP lokal di browser mereka (contoh: `http://192.168.1.171:8000`).
- **Pilihan 2 (Cloudflare Tunnel - Remote / WFH):**
  Membuat URL publik HTTPS gratis (contoh: `https://xxxx.trycloudflare.com`) sehingga rekan tim bisa mengakses dari mana saja tanpa perlu satu jaringan Wi-Fi.

### 3. Fitur Utama Web Dashboard
1. **Filter Pembagian Tugas Tim:**
   - Tab filter instan untuk melihat part milik **Semua**, **Zul**, **Iqbal**, **Rama**, atau **Yogi**.
2. **Batch Upload & Modular Parsers:**
   - Drag & drop banyak file Excel/PDF sekaligus. Sistem otomatis mendeteksi format (MMKI IR, MMKI IPQC, IQC Incoming, PDF) dan mengekstrak tabel serta gambar part.
3. **Multi-Select & Batch Actions:**
   - Centang beberapa part sekaligus.
   - Pindahkan penugasan tim hanya dengan 1 klik.
   - **Batch Submit ke FactoryHub**: Eksekusi pengisian checksheet berurutan di browser dengan streaming log realtime via SSE.
4. **Export & Google Spreadsheet Sync:**
   - **Download Excel**: Unduh rekap format resmi langsung dari browser.
   - **Sync Google Sheet**: Sinkronisasi data ke Google Spreadsheet monitoring tim hanya dengan 1 klik.

---

## Fitur Utama Sistem

- **Web Dashboard GUI Studio (`python run_server.py` & `http://localhost:8000`)**:
  - Tampilan modern berbasis Vue 3 + Tailwind CSS (zero Node.js build requirement) untuk review, edit titik inspeksi, live stream log otomasi, dan batch submission.
- **Shared Cloud Database (Supabase PostgreSQL)**:
  - Database terpusat sehingga seluruh anggota tim melihat data progres yang sinkron secara real-time.
- **Modular Parsers (`parsers/`)**:
  - `mmki_ir.py`, `mmki_ipqc.py`, `iqc_incoming.py`, `pdf_parser.py`, `generic_excel.py`.
- **Partisi Dokumen Terorganisir (`documents/belum/` & `documents/done/`)**:
  - Memisahkan dokumen yang belum dikerjakan dengan yang sudah selesai.
- **Pencatatan Log Terpusat (`logs/history.xlsx`)**:
  - Mencatat riwayat eksekusi checksheet dan hasil pencarian part.
- **Mode Review Visual (Headed Mode)**:
  - Mengisi seluruh field, gambar, dan tabel inspeksi secara otomatis dengan browser terbuka untuk verifikasi manual sebelum simpan.

---

## Struktur Proyek

```text
.
├── documents/                              # Direktori utama dokumen checksheet
│   ├── belum/                              # Dokumen part yang belum selesai (10 part)
│   └── done/                               # Dokumen part yang sudah selesai
├── static/                                 # Antarmuka Web Dashboard GUI (HTML/CSS/JS)
├── logs/                                   # Folder log terpusat
│   ├── history.xlsx                        # Excel 2 Sheets: Execution & Search History
│   ├── execution_history.json              # Data log terstruktur JSON
│   └── activity.log                        # Log teks berurutan
├── gui.sh                                  # Script launcher Web Dashboard GUI
├── run.sh                                  # Script eksekusi otomasi checksheet (Bash)
├── search.sh                               # Script batch checker part number (Bash)
├── web_app.py                              # Backend server FastAPI untuk Web Dashboard
├── extractor.py                            # Modul ekstraksi data & gambar (Excel & PDF)
├── automator.py                            # Modul otomatisasi Playwright & Diff Engine
├── logger.py                               # Modul pencatatan log Excel & JSON
├── run.py                                  # CLI runner otomasi checksheet
├── search.py                               # CLI runner pencarian batch part
├── requirements.txt                        # Dependensi Python
├── .env.example                            # Template konfigurasi environment
├── .gitignore                              # Konfigurasi keamanan Git
└── README.md                               # Dokumentasi proyek
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
   ```

---

## Cara Penggunaan

### 1. Menjalankan Part Tertentu

Format perintah:
```bash
./run.sh <part_number> [scan_image: yes/no]
```

#### Contoh A: Hasil Scan Data (Hanya data di Excel, gambar dari folder)
```bash
# Otomatis mendeteksi gambar lokal di folder 75511b040p/:
./run.sh 75511b040p

# Atau tegaskan tanpa scan Excel (no/tidak):
./run.sh 75511b040p no
```

#### Contoh B: Excel Mentah (Gambar diekstrak dari dalam Excel)
```bash
# Otomatis mengekstrak gambar tersemat karena folder tidak memuat gambar lokal:
./run.sh 51138e000p

# Atau paksa ekstrak dari sheet Excel (yes/ya):
./run.sh 51138e000p yes
```

---

### 2. Memilih Part Secara Interaktif

Jika Anda menjalankan `./run.sh` tanpa parameter, sistem akan menampilkan daftar part yang ada di folder `documents/`:
```bash
./run.sh
```
Contoh tampilan:
```text
==================================================
   FactoryHub Checksheet Master Automation
==================================================
Tersedia dokumen part di folder documents/:
  [1] 51138e000p (Part No: 51138E000P) -> Excel Mentah (scan dari excel)
  [2] 75511b040p (Part No: 75511B040P) -> Hasil Scan Data (4 gambar)
==================================================
Pilih nomor [1-2] atau ketik part number [1]:
```

---

### 3. Uji Coba Tanpa Buka Browser (Dry Run)

Gunakan flag `--dry-run` untuk memverifikasi apakah pembacaan tabel dan gambar sudah benar tanpa login atau membuka browser:
```bash
./run.sh 75511b040p --dry-run
./run.sh 51138e000p --dry-run
```

---

### 4. Opsi Lanjutan

- **Melihat daftar part di folder `documents/`:**
  ```bash
  ./run.sh --list
  ```

- **Menjalankan di latar belakang tanpa jendela (Headless):**
  ```bash
  ./run.sh 75511b040p --headless
  ```

- **Langsung klik "Save Template" otomatis:**
  ```bash
  ./run.sh 75511b040p --submit
  ```

- **Menentukan Doc Number kustom:**
  ```bash
  ./run.sh 75511b040p --doc-number "Form 7"
  ```

- **Menggunakan path Excel langsung:**
  ```bash
  ./run.sh --excel "path/ke/file_lain.xlsx"
  ```

---

## Pengecekan Cepat Part Number (`./search.sh`)

Gunakan script ini untuk memeriksa secara massal apakah part-part yang ingin Anda proses sudah terdaftar di portal FactoryHub (**Regular Production Part** maupun **New Project Part**):

### 1. Menggunakan File `parts.txt` (Paling Praktis)
Tuliskan daftar kode part di file `parts.txt` (satu baris satu part):
```text
62130-3K6-K001-H1
65750-T86A-K002-H1
75511B040P
51138E000P
```
Lalu cukup jalankan:
```bash
./search.sh
```

### 2. Cek Part Langsung Lewat Argumen
```bash
./search.sh 65750-T86A-K002-H1
# Atau banyak part sekaligus:
./search.sh 62130-3K6-K001-H1 65750-T86A-K002-H1 75511B040P
```

### 3. Cek Semua Part yang Ada di Folder `documents/`
```bash
./search.sh --documents
```

> **Catatan**: Script ini hanya membuka halaman FactoryHub sekali di background (headless) dan mengecek seluruh part dalam beberapa detik saja. Hasilnya langsung dicetak dalam bentuk tabel dan diekspor ke `search_results.txt` serta `search_results.csv`.


---

## Optimasi & Kompresi Gambar ke WebP (`./compress_images.sh` & Web GUI)

Untuk menghemat ruang disk dan mempercepat proses upload gambar ke portal FactoryHub (mencegah lag / timeout saat upload foto kamera ponsel beresolusi tinggi), sistem menyediakan **WebP Image Optimizer**:

### 1. Lewat Antarmuka Web Dashboard
- Klik tombol **`⚡ Kompres WebP`** di bagian atas header.
- Modal akan menampilkan perbandingan ukuran sebelum & sesudah, persentase penghematan (~85%), slider kualitas WebP (50% - 95%), serta opsi hapus file asli (*auto clean*).

### 2. Rumus Shell Script (`./compress_images.sh`)
Script bash siap pakai yang otomatis mengonversi seluruh file gambar (`.png`, `.jpg`, `.jpeg`) menjadi `.webp` berukuran optimal:
```bash
# Jalankan kompresi standar (kualitas 82%, hapus file lama untuk hemat storage):
./compress_images.sh

# Cek statistik penggunaan & potensi hemat tanpa mengubah file:
./compress_images.sh --stats

# Simulasi konversi tanpa menulis file (Dry Run):
./compress_images.sh --dry-run

# Kustomisasi kualitas (misal 85%) dan batasan resolusi (maks 1920px):
./compress_images.sh --quality 85 --max-dim 1920

# Hanya simpan WebP tanpa menghapus file PNG/JPG asli:
./compress_images.sh --keep-original
```

### 3. Rumus One-Liner CLI (Python / Shell)
```bash
# Menjalankan optimasi langsung via CLI Python:
python3 compress_webp.py documents extracted_images --quality 82

# Rumus cepat satu baris (One-liner):
python3 -c "from compress_webp import convert_images_to_webp; print(convert_images_to_webp(['documents', 'extracted_images']))"
```

---

## Menambahkan Dokumen Part Baru

Cukup buat folder baru di dalam `documents/` dengan nama part number:
1. Buat folder `documents/<part_number>/` (contoh: `documents/58336-bz130/`).
2. Masukkan file Excel checksheet (`.xlsx`).
3. Jika form hasil scan (tidak ada gambar di Excel), letakkan file foto/gambar part (`.jpg`/`.png`) di folder tersebut.
4. Jalankan:
   ```bash
   ./run.sh 58336-bz130
   ```

---

## Keamanan Data Sensitif

Repository ini secara ketat mengabaikan file rahasia melalui `.gitignore`:
- File kredensial `.env`
- Seluruh file Excel (`*.xlsx`, `*.xls`)
- Seluruh file gambar (`*.jpg`, `*.png`, `extracted_images/`)
- Virtual environment (`.venv/`)

---

## Lisensi

Proyek ini dibuat untuk keperluan internal otomatisasi checksheet quality control PT. Summit Adyawinsa Indonesia.
