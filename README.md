# FactoryHub Checksheet Master Automation

Sistem otomatisasi untuk mengekstrak data checksheet dari file Excel (*Inspection Report*) dan mengisikannya secara otomatis ke portal **FactoryHub (PT. Summit Adyawinsa Indonesia)** menggunakan Python dan Playwright.

---

## Fitur Utama

- **Struktur Dokumen Terorganisir (`documents/<part_number>/`)**:
  - File Excel dan gambar referensi dikelompokkan rapi per part number di dalam folder masing-masing.
- **Deteksi Form Fleksibel (Hasil Scan Data vs Excel Mentah)**:
  - **Hasil Scan Data (Hanya Teks)**: Jika checksheet berasal dari data ketikan/scan standar tanpa gambar tersemat di Excel, skrip otomatis mengambil gambar fisik dari folder part tanpa membongkar file Excel.
  - **Excel Mentah (Embedded Drawing)**: Jika file Excel memiliki gambar layout/mesin tersemat (seperti file IR asli), skrip mengekstrak gambar langsung dari sheet lembar kerja Excel (PAGE 4, PAGE 5, EO).
  - Mode ini dapat dideteksi secara otomatis atau ditentukan secara manual via argumen `yes`/`no`.
- **Pencocokan Part Otomatis di Portal**:
  - Memeriksa ketersediaan part di **Regular Production Part**.
  - Jika belum terdaftar, otomatis beralih ke **New Project Part** dan mencocokkan part number.
- **Mode Review Visual (Headed Mode)**:
  - Membuka jendela browser Chrome di layar Anda.
  - Mengisi seluruh field, gambar, dan tabel inspeksi secara otomatis.
  - Jendela browser tetap terbuka agar Anda bisa memeriksa dan menekan tombol **"Save Template"** sendiri.
- **Perintah Eksekusi Cepat (`run.sh`)**:
  - Cukup jalankan `./run.sh <part_number>` atau `./run.sh` untuk memilih part secara interaktif.

---

## Struktur Proyek

```text
.
├── documents/                              # Direktori utama semua checksheet
│   ├── 75511b040p/                         # Folder part number (case-insensitive)
│   │   ├── Inspection_Standard_...xlsx     # File Excel data
│   │   └── IMG_6329.JPG, ...               # File gambar foto/layout part
│   └── 51138e000p/
│       └── 6. IR - 51138E000P...xlsx       # File Excel mentah dengan gambar tersemat
├── extractor.py                            # Modul parser data & gambar Excel
├── automator.py                            # Modul otomatisasi browser Playwright
├── run.py                                  # CLI runner utama Python
├── run.sh                                  # Script shortcut eksekusi cepat (Bash)
├── jalankan.sh                             # Alias untuk run.sh
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
