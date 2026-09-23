# ARCHITECTURE & ROADMAP: Collaborative Checksheet Automation System

Dokumen ini mendokumentasikan blueprint arsitektur baru untuk kolaborasi tim 4 orang (Zul, Iqbal, Rama, dsb.), sistem parsing modular, database storage, dan FastAPI web rebuild.

---

## 1. Struktur Folder Baru

```text
Otomatisasi Checksheet/
├── parsers/                    # [MODULAR PARSER ENGINE]
│   ├── __init__.py             # Auto-detector & parser factory
│   ├── base.py                 # Abstract BaseParser class
│   ├── mmki_ir.py              # Parser format MMKI IR Checksheet
│   ├── mmki_ipqc.py            # Parser format MMKI IPQC (Appearance & Dimension)
│   ├── iqc_incoming.py         # Parser format IQC Incoming Material (HPM, SSW, dsb)
│   ├── generic_excel.py        # Fallback parser untuk format Excel tabular umum
│   └── pdf_parser.py           # Parser format PDF & balloon drawing coordinates
│
├── database/                   # [PERSISTENCE LAYER]
│   ├── __init__.py             # Database engine & session maker (SQLite WAL / Postgres)
│   ├── models.py               # ORM Models (User, Checksheet, InspectionPoint, Image, SubmissionQueue)
│   └── crud.py                 # Create, Read, Update, Delete helper functions
│
├── services/                   # [BUSINESS LOGIC & WORKERS]
│   ├── __init__.py
│   ├── parser_service.py       # Orchestrator parsing berkas -> simpan ke DB & media storage
│   ├── queue_service.py        # Worker antrean otomasi Playwright (mencegah tabrakan sesi login)
│   └── catalog_service.py      # Sinkronisasi & fuzzy match Master Part FactoryHub
│
├── storage/                    # [FILE & MEDIA REPOSITORY]
│   ├── uploads/                # Arsip berkas checksheet mentah (Excel/PDF)
│   └── images/                 # Gambar referensi sketsa hasil ekstraksi (.webp/.png)
│
├── server/                     # [FASTAPI ASGI BACKEND]
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entrypoint
│   └── routes/                 # API Endpoints (upload, checksheets, review, queue, stream_logs)
│
├── automator.py                # Core Playwright automation script (FactoryHub Web Driver)
├── run.py                      # Standalone CLI runner
└── requirements.txt            # Python dependencies
```

---

## 2. Model Database Utama (`database/models.py`)

1. **User**:
   - `id`: Integer Primary Key
   - `name`: String (`Zul`, `Iqbal`, `Rama`, dll.)
   - `nik`: String
   - `role`: String

2. **Checksheet**:
   - `id`: Integer Primary Key
   - `assigned_user_id`: ForeignKey(`User.id`)
   - `part_number`: String (Index)
   - `part_name`: String
   - `model`: String
   - `customer`: String (`PT. HPM`, `PT. MMKI`, dll.)
   - `doc_number`: String (`Form 1 REV: 00`, dll.)
   - `template_type`: String (`IQC_INCOMING`, `MMKI_IR`, `IPQC`, dll.)
   - `status`: String (`DRAFT`, `READY_FOR_SUBMIT`, `IN_QUEUE`, `SUBMITTED`, `TIDAK_ADA_PART`)
   - `factoryhub_id`: String / Nullable
   - `factoryhub_url`: String / Nullable
   - `raw_file_path`: String (Path ke file di `storage/uploads/`)
   - `created_at`: DateTime
   - `updated_at`: DateTime

3. **InspectionPoint**:
   - `id`: Integer Primary Key
   - `checksheet_id`: ForeignKey(`Checksheet.id`)
   - `item_no`: String (Balloon number, e.g. `1`, `2`)
   - `inspection_item`: String
   - `standard`: String
   - `method`: String (`Visual`, `Caliper`, `Millsheet`, dll.)
   - `master_data`: String / Nullable

4. **PartImage**:
   - `id`: Integer Primary Key
   - `checksheet_id`: ForeignKey(`Checksheet.id`)
   - `image_path`: String (Path lokal di `storage/images/`)
   - `image_url`: String (Web accessible URL)

5. **SubmissionQueue**:
   - `id`: Integer Primary Key
   - `checksheet_id`: ForeignKey(`Checksheet.id`)
   - `queued_by`: ForeignKey(`User.id`)
   - `status`: String (`PENDING`, `RUNNING`, `SUCCESS`, `FAILED`)
   - `log_output`: Text
   - `started_at`: DateTime
   - `completed_at`: DateTime

---

## 3. Workflow Tim 4 Orang

1. **Upload**: Anggota tim mengunggah file checksheet melalui web dashboard.
2. **Auto-Parse & Storage**: Backend mengidentifikasi template, mengekstrak tabel & gambar, lalu menyimpannya langsung ke database.
3. **Review & Edit**: Tim dapat memeriksa tabel di browser, mengedit poin inspeksi, atau mengganti gambar referensi jika perlu.
4. **Queue & Auto-Submit**: Klik tombol Submit akan memasukkan pekerjaan ke antrean background worker Playwright tanpa tabrakan sesi.
5. **Real-time Monitoring**: Progress dan log eksekusi di-stream langsung ke browser menggunakan Server-Sent Events (SSE).
