import os
import base64
import subprocess
import pypdf

# Convert sample image to base64
img_path = os.path.join(os.path.dirname(__file__), "images", "sample_71246_drawing.webp")
b64_img = ""
if os.path.exists(img_path):
    with open(img_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("utf-8")

HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <title>Panduan dan Standarisasi Digitalisasi Checksheet QC</title>
  <style>
    @page {{
      size: A4 portrait;
      margin: 10mm 12mm 10mm 12mm;
    }}
    
    * {{
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      font-size: 8.5pt;
      line-height: 1.38;
      color: #18181b;
      background-color: #ffffff;
      margin: 0;
      padding: 0;
    }}

    .page {{
      height: 275mm;
      max-height: 275mm;
      overflow: hidden;
      position: relative;
      page-break-after: always;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}

    .page:last-child {{
      page-break-after: avoid;
    }}

    .content-wrap {{
      flex: 1;
    }}

    /* Header Block */
    .doc-header {{
      border-bottom: 2px solid #0f172a;
      padding-bottom: 6px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: flex-end;
    }}

    .company-tag {{
      font-size: 7.5pt;
      font-weight: 700;
      color: #4f46e5;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 2px;
    }}

    .doc-title {{
      font-size: 13.5pt;
      font-weight: 900;
      color: #0f172a;
      margin: 0;
      line-height: 1.2;
      text-transform: uppercase;
      letter-spacing: -0.01em;
    }}

    .doc-subtitle {{
      font-size: 7.8pt;
      color: #64748b;
      margin: 2px 0 0 0;
      font-weight: 500;
    }}

    .meta-box {{
      font-size: 7.2pt;
      border-collapse: collapse;
      text-align: right;
    }}

    .meta-box td {{
      padding: 1px 4px;
    }}

    .meta-label {{
      color: #64748b;
    }}

    .meta-val {{
      font-family: ui-monospace, Menlo, monospace;
      font-weight: 700;
      color: #0f172a;
    }}

    /* Section Styling */
    h2 {{
      font-size: 9.8pt;
      font-weight: 800;
      color: #0f172a;
      background: #f1f5f9;
      border-left: 3.5px solid #4f46e5;
      padding: 3px 6px;
      margin: 8px 0 5px 0;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }}

    h3 {{
      font-size: 8.5pt;
      font-weight: 700;
      color: #334155;
      margin: 6px 0 3px 0;
    }}

    p {{
      margin: 0 0 5px 0;
      color: #334155;
    }}

    ul, ol {{
      margin: 0 0 5px 0;
      padding-left: 16px;
    }}

    li {{
      margin-bottom: 2px;
      color: #334155;
    }}

    /* Badges */
    .badge {{
      display: inline-block;
      padding: 1.5px 5px;
      border-radius: 3px;
      font-size: 7pt;
      font-weight: 700;
      letter-spacing: 0.02em;
      white-space: nowrap;
    }}

    .badge-subcont {{ background-color: #fef3c7; color: #92400e; border: 1px solid #fde68a; }}
    .badge-material {{ background-color: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }}
    .badge-std {{ background-color: #e0f2fe; color: #075985; border: 1px solid #bae6fd; }}
    .badge-ssw {{ background-color: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }}
    .badge-accuracy {{ background-color: #ede9fe; color: #5b21b6; border: 1px solid #ddd6fe; }}
    .badge-general {{ background-color: #f1f5f9; color: #475569; border: 1px solid #e2e8f0; }}

    /* Data Tables */
    table.data-table {{
      width: 100%;
      border-collapse: collapse;
      margin: 4px 0 6px 0;
      font-size: 7.6pt;
    }}

    table.data-table th, table.data-table td {{
      border: 1px solid #cbd5e1;
      padding: 3.5px 5.5px;
      vertical-align: top;
      text-align: left;
    }}

    table.data-table th {{
      background-color: #f8fafc;
      font-weight: 800;
      color: #0f172a;
      text-transform: uppercase;
      font-size: 7.2pt;
      letter-spacing: 0.02em;
    }}

    table.data-table tr:nth-child(even) td {{
      background-color: #f8fafc;
    }}

    .mono {{
      font-family: ui-monospace, Menlo, monospace;
      font-weight: 600;
    }}

    /* Comparison Box */
    .comparison-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 5px 0 6px 0;
    }}

    .comp-box {{
      border: 1px solid #e2e8f0;
      border-radius: 5px;
      padding: 6px 8px;
      font-size: 7.8pt;
    }}

    .comp-box.old {{
      background-color: #fff1f2;
      border-color: #fecdd3;
    }}

    .comp-box.new {{
      background-color: #f0fdf4;
      border-color: #bbf7d0;
    }}

    .comp-box h4 {{
      margin: 0 0 3px 0;
      font-size: 8.2pt;
      font-weight: 800;
    }}

    /* Callout */
    .callout {{
      border-radius: 4px;
      padding: 5px 8px;
      margin: 5px 0;
      font-size: 7.8pt;
      border-left: 3px solid #3b82f6;
      background: #eff6ff;
    }}

    /* Steps */
    .step-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin: 5px 0;
    }}

    .step-card {{
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 5px 7px;
      background: #ffffff;
      font-size: 7.6pt;
    }}

    .step-card .num {{
      display: inline-block;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #4f46e5;
      color: #ffffff;
      font-size: 6.8pt;
      font-weight: 800;
      text-align: center;
      line-height: 16px;
      margin-right: 4px;
    }}

    .step-card strong {{
      color: #0f172a;
    }}

    /* Signatures */
    .sig-table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 6px;
      font-size: 7.5pt;
      text-align: center;
    }}

    .sig-table th, .sig-table td {{
      border: 1px solid #cbd5e1;
      padding: 4px;
    }}

    .sig-table th {{
      background: #f8fafc;
      font-weight: 700;
    }}

    .sig-space {{
      height: 38px;
    }}

    /* Page Footer */
    .page-footer {{
      border-top: 1px solid #e2e8f0;
      padding-top: 4px;
      display: flex;
      justify-content: space-between;
      font-size: 6.8pt;
      color: #64748b;
      margin-top: 4px;
    }}
  </style>
</head>
<body>

  <!-- ==================== HALAMAN 1 ==================== -->
  <div class="page">
    <div class="content-wrap">
      <div class="doc-header">
        <div>
          <div class="company-tag">PT. SUMMIT ADYAWINSA INDONESIA • QUALITY CONTROL DEPARTMENT</div>
          <h1 class="doc-title">PANDUAN & STANDARISASI CHECKSHEET QC</h1>
          <div class="doc-subtitle">Pedoman Digitalisasi Studio, Format Titik Ukur & Sistem Pengkategorian FactoryHub</div>
        </div>
        <table class="meta-box">
          <tr><td class="meta-label">No. Dokumen:</td><td class="meta-val">SOP-QC-DIGITAL-01</td></tr>
          <tr><td class="meta-label">Revisi:</td><td class="meta-val">2.0 (Resmi)</td></tr>
          <tr><td class="meta-label">Berlaku:</td><td class="meta-val">Oktober 2026</td></tr>
          <tr><td class="meta-label">Klasifikasi:</td><td class="meta-val">Internal Standar Mutu</td></tr>
        </table>
      </div>

      <h2>1. Evaluasi Masalah: Kenapa "Accuracy Semua" Kemarin Salah</h2>
      <p>
        Pada migrasi awal sistem checksheet digital, seluruh 910 part checksheet sempat di-assign dengan kategori tunggal <strong>Accuracy</strong>. 
        Tindakan tersebut merupakan <strong>kekeliruan sistematis</strong> yang berdampak langsung pada operasional pabrik dan kepatuhan audit mutu customer (TMMIN, HPM, MMKI, SIM).
      </p>

      <div class="comparison-grid">
        <div class="comp-box old">
          <h4 style="color: #9f1239;">❌ Kesalahan Kemarin (Accuracy Semua)</h4>
          <ul>
            <li><strong>Salah Kamar di FactoryHub</strong>: Part bahan baku sheet coil dan part stamping subcont tercampur baur ke folder Accuracy. Tim Incoming QC tidak dapat menemukan part mereka.</li>
            <li><strong>Parameter Tidak Sesuai</strong>: Standar material (Spec SPC590, tebal, lebar, visual packing) dipaksa masuk ke template bodi 3D yang seharusnya mengecek koordinat X/Y/Z CMM.</li>
            <li><strong>Audit & Traceability Gagal</strong>: Rekapitulasi laporan inspeksi supplier tidak dapat difilter atau dilaporkan secara valid ke customer.</li>
          </ul>
        </div>
        <div class="comp-box new">
          <h4 style="color: #166534;">✅ Standarisasi Sistem Baru (5+1 Kategori Resmi)</h4>
          <ul>
            <li><strong>Pengelompokan Presisi 100%</strong>: Setiap part dialokasikan tepat ke template FactoryHub: Subcont Part, Material, Std Part, Accuracy SSW, Accuracy, atau General.</li>
            <li><strong>Parameter Sesuai Karakteristik Part</strong>: Item inspeksi, toleransi, dan alat ukur sinkron dengan standar kerja operasional aktual di area kerja.</li>
            <li><strong>Telemetri Dashboard & Workspace Realtime</strong>: Status pengerjaan dan filter kategori terintegrasi dua arah antara web studio dan database FactoryHub.</li>
          </ul>
        </div>
      </div>

      <h2>2. Matriks 5+1 Pengkategorian Resmi FactoryHub</h2>
      <p>
        Sebelum menyimpan checksheet di Studio, operator <strong>wajib memeriksa dropdown Kategori FactoryHub</strong> pada header Studio dan memilih kategori yang benar:
      </p>

      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 22%;">Kategori Resmi</th>
            <th style="width: 27%;">Definisi & Lingkup Part</th>
            <th style="width: 26%;">Karakteristik Titik Inspeksi</th>
            <th style="width: 25%;">Contoh Part & Dokumen</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><span class="badge badge-subcont">Incomming Subcont Part</span></td>
            <td>Part press stamping / sub-assembly yang disuplai oleh subkontraktor dan diperiksa di <strong>Incoming QC</strong>.</td>
            <td>• Spec. Material (SPC590, SPCC)<br>• Thickness, Length, Width<br>• Visual: No Rust, Scratch, Wave, Packing</td>
            <td>Part: <span class="mono">71246-BZ010</span>, <span class="mono">62143-TG4</span><br>Dok: <span class="mono">FO-45-01</span>, <span class="mono">FO-45-02</span></td>
          </tr>
          <tr>
            <td><span class="badge badge-material">Incomming Material</span></td>
            <td>Bahan baku mentah (Raw Material) berupa Sheet Plate, Coil Baja gulungan dari pabrik baja (Krakatau Steel, POSCO).</td>
            <td>• Tensile Strength, Hardness<br>• Tebal & Lebar Coil Baja<br>• Kondisi Burr, Oli, Label Mill Sheet</td>
            <td>Part: <span class="mono">COIL-SPC270-1.2</span><br>Dok: <span class="mono">FO-44-01 (IQC Material)</span></td>
          </tr>
          <tr>
            <td><span class="badge badge-std">Incomming Std Part</span></td>
            <td>Komponen standar yang dibeli jadi (purchased fastener / hardware) seperti bolt, nut, screw, rivet, clip, pin.</td>
            <td>• Thread Pitch & Diameter Luar<br>• Panjang Ulir, Lapisan Plating<br>• Uji Torsi & Go/No-Go Gauge</td>
            <td>Part: <span class="mono">90105-08123</span> (Flange Bolt)<br>Dok: <span class="mono">FO-46-01 (Fastener)</span></td>
          </tr>
          <tr>
            <td><span class="badge badge-ssw">Accuracy SSW</span></td>
            <td>Checksheet akurasi dimensi khusus part lini <strong>SSW (Sub-Assembly Spot Welding)</strong> atau stamping spesifik lini SSW.</td>
            <td>• Gap & Flushness assembly SSW<br>• Pitch / Jarak antar titik las spot<br>• Koordinat jig fixture SSW</td>
            <td>Part: <span class="mono">62144-TG4-T000-H1</span> (SSW)<br>Customer: PT. HPM / TMMIN</td>
          </tr>
          <tr>
            <td><span class="badge badge-accuracy">Accuracy</span></td>
            <td>Master checksheet akurasi geometri dimensi part utama stamping & main body assembly (Panel Roof, Floor, Door).</td>
            <td>• Koordinat 3D (X, Y, Z)<br>• Hole Dia, Flange Height, Profile<br>• Pengukuran CMM / Check Fixture</td>
            <td>Part: <span class="mono">76750C000P</span>, <span class="mono">73242E000P</span><br>Template: Accuracy Master</td>
          </tr>
          <tr>
            <td><span class="badge badge-general">General</span></td>
            <td>Template checksheet inspeksi umum yang tidak masuk ke dalam 5 kategori manufaktur di atas.</td>
            <td>• Verifikasi kelengkapan fisik umum<br>• Checksheet pendukung non-stamping</td>
            <td>Form inspeksi khusus / miscellaneous.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="page-footer">
      <span>PT. Summit Adyawinsa Indonesia • QC Department</span>
      <span>SOP-QC-DIGITAL-01 • Standarisasi Checksheet QC</span>
      <span>Halaman 1 dari 4</span>
    </div>
  </div>

  <!-- ==================== HALAMAN 2 ==================== -->
  <div class="page">
    <div class="content-wrap">
      <div class="doc-header">
        <div>
          <div class="company-tag">STANDARISASI PENGISIAN DATA & ALAT UKUR</div>
          <h1 class="doc-title" style="font-size: 12pt;">ATURAN PENULISAN TITIK INSPEKSI & DRAWING</h1>
        </div>
        <table class="meta-box">
          <tr><td class="meta-label">No. Dokumen:</td><td class="meta-val">SOP-QC-DIGITAL-01</td></tr>
          <tr><td class="meta-label">Bagian:</td><td class="meta-val">Format & Tooling Standard</td></tr>
        </table>
      </div>

      <h2>3. Standarisasi Format Penulisan Titik Inspeksi (Studio Grid)</h2>
      <p>
        Tabel titik inspeksi di Studio wajib mengikuti kaidah baku agar seragam, mudah dibaca, dan terbaca otomatis oleh sistem parser FactoryHub:
      </p>

      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 14%;">Kolom Studio</th>
            <th style="width: 36%;">Kaidah Baku Penulisan</th>
            <th style="width: 25%;">Contoh Benar ✅</th>
            <th style="width: 25%;">Contoh Salah ❌</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong># (NO)</strong></td>
            <td>Nomor balon ukur yang merujuk pada gambar sketsa. Jika 1 balon visual mencakup beberapa aspek, nomor ditulis sama.</td>
            <td><span class="mono">1</span>, <span class="mono">2</span>, <span class="mono">3</span>, <span class="mono">5</span> (berulang jika 1 balon)</td>
            <td><span class="mono">No. 1</span>, <span class="mono">P-1</span>, dikosongkan</td>
          </tr>
          <tr>
            <td><strong>Item Inspeksi</strong></td>
            <td>Gunakan istilah teknis standar, huruf kapital di awal kata, tanpa singkatan tidak baku.</td>
            <td><span class="mono">Thickness</span>, <span class="mono">Length</span>, <span class="mono">Width</span>, <span class="mono">Spec. Material</span>, <span class="mono">No Rust</span></td>
            <td><span class="mono">Tebal</span>, <span class="mono">Pjg</span>, <span class="mono">Karat</span>, <span class="mono">Visual 1</span></td>
          </tr>
          <tr>
            <td><strong>Standar / Toleransi</strong></td>
            <td>Tuliskan nilai nominal diikuti toleransi plus-minus (<span class="mono">±</span>). Untuk kualitatif tuliskan <span class="mono">OK / NG</span> atau kode material.</td>
            <td><span class="mono">0.9 ± 0.09</span><br><span class="mono">1242 ± 1.0</span><br><span class="mono">OK / NG</span><br><span class="mono">SPC590</span></td>
            <td><span class="mono">0.9 +0.09/-0.09</span><br><span class="mono">Bagus</span>, <span class="mono">Sesuai</span><br><span class="mono">Tidak Boleh Karat</span></td>
          </tr>
          <tr>
            <td><strong>Alat Ukur / Metode</strong></td>
            <td>Pilih nama alat ukur resmi dari tabel standar baku. Klik tombol <em>Standarkan</em> di toolbar untuk merapikan otomatis.</td>
            <td><span class="mono">Caliper</span>, <span class="mono">Visual</span>, <span class="mono">Roll Meter</span>, <span class="mono">Data Label</span></td>
            <td><span class="mono">Sigmat</span>, <span class="mono">Mata</span>, <span class="mono">Meteran</span>, <span class="mono">Lihat Label</span></td>
          </tr>
          <tr>
            <td><strong>Master Data</strong></td>
            <td>Kode titik ukur pada gambar koordinat (bila ada) atau dikosongkan jika tidak ada koordinat CMM.</td>
            <td><span class="mono">P1</span>, <span class="mono">Hole-A</span>, atau kosong</td>
            <td>Keterangan panjang / narasi</td>
          </tr>
        </tbody>
      </table>

      <h3>Tabel 10 Alat Ukur & Metode Inspeksi Baku:</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 25%;">Nama Standar Resmi</th>
            <th style="width: 25%;">Sebutan Lama / Sinonim</th>
            <th style="width: 50%;">Rentang Ukur & Kegunaan Utama</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><strong>Visual</strong></td><td>Mata, Penglihatan, Cek Fisik</td><td>Pemeriksaan visual cacat permukaan: No Rust, No Scratch, No Wave, Packing, Burring.</td></tr>
          <tr><td><strong>Caliper</strong></td><td>Sigmat, Jangka Sorong, Vernier</td><td>Pengukuran dimensi luar, dalam, dan step ketebalan hingga 300 mm.</td></tr>
          <tr><td><strong>Micrometer</strong></td><td>Mikrometer, Tebal Gauge</td><td>Pengukuran ketebalan sheet metal presisi tinggi (ketelitian 0.001 - 0.01 mm).</td></tr>
          <tr><td><strong>Height Gauge</strong></td><td>Height GG, Pengukur Tinggi</td><td>Pengukuran tinggi step part stamping pada surface plate referensi datum.</td></tr>
          <tr><td><strong>Roll Meter</strong></td><td>Meteran, Pita Ukur, Meter</td><td>Pengukuran part stamping berdimensi panjang/lebar besar (> 300 mm hingga ribuan mm).</td></tr>
          <tr><td><strong>Pin Gauge</strong></td><td>Pin GG, Plug Gauge</td><td>Pemeriksaan diameter lubang lingkaran presisi (Go / No-Go limits).</td></tr>
          <tr><td><strong>Data Label</strong></td><td>Mill Sheet, Label Tag, Barcode</td><td>Verifikasi kesesuaian spesifikasi material (misal SPC590) terhadap sertifikat tag supplier.</td></tr>
          <tr><td><strong>Check Fixture (CF)</strong></td><td>Jig CF, Checking Fixture</td><td>Pemeriksaan profil kontur dan posisi lubang menggunakan mal / jig periksa presisi.</td></tr>
          <tr><td><strong>Torque Wrench</strong></td><td>Kunci Torsi, Torque Meter</td><td>Pemeriksaan momen puntir kekencangan baut / mur standar assembly.</td></tr>
          <tr><td><strong>Profile Projector</strong></td><td>Proyektor Kontur, Optical</td><td>Pemeriksaan radius, chamfer, dan profil mikro dengan perbesaran bayangan optik.</td></tr>
        </tbody>
      </table>

      <h2>4. Standarisasi Gambar Sketsa Drawing & Nomor Balon</h2>
      <div class="callout">
        <strong>Aturan Wajib Gambar Sketsa:</strong>
        <ol style="margin: 3px 0 0 0; padding-left: 16px;">
          <li><strong>Kejelasan Gambar</strong>: Garis kontur part dan nomor balon harus terbaca tajam dengan kontras tinggi (latar belakang putih bersih).</li>
          <li><strong>Orientasi Tegak</strong>: Posisi part tidak boleh terbalik 180° atau miring 90°. Harus sesuai dengan posisi part di checksheet fisik.</li>
          <li><strong>100% Sinkronisasi Nomor Balon</strong>: Setiap lingkaran nomor balon pada gambar (1, 2, 3, 4, ...) wajib memiliki baris yang bersesuaian pada kolom <strong># (NO)</strong> di tabel Studio.</li>
        </ol>
      </div>
    </div>

    <div class="page-footer">
      <span>PT. Summit Adyawinsa Indonesia • QC Department</span>
      <span>SOP-QC-DIGITAL-01 • Standarisasi Checksheet QC</span>
      <span>Halaman 2 dari 4</span>
    </div>
  </div>

  <!-- ==================== HALAMAN 3 ==================== -->
  <div class="page">
    <div class="content-wrap">
      <div class="doc-header">
        <div>
          <div class="company-tag">STUDI KASUS & CONTOH STANDAR RESMI (GOLDEN SAMPLE)</div>
          <h1 class="doc-title" style="font-size: 12pt;">CONTOH IMPLEMENTASI CHECKSHEET SEMPURNA</h1>
        </div>
        <table class="meta-box">
          <tr><td class="meta-label">Part Referensi:</td><td class="meta-val">71246-BZ010</td></tr>
          <tr><td class="meta-label">Kategori:</td><td class="meta-val">Incomming Material</td></tr>
        </table>
      </div>

      <h2>5. Golden Sample: Part 71246-BZ010 (Plate RR Seat Cushion Set)</h2>
      <p>
        Berikut adalah contoh checksheet ideal kategori <strong>Incomming Material</strong> (Blank Sheet Plate). 
        Part ini berupa pelat lembaran potong mentah untuk customer <strong>PT. TMMIN</strong> dengan nomor dokumen <strong>FO-45-01</strong>:
      </p>

      <!-- Grid Gambar & Tabel Studi Kasus -->
      <div style="display: grid; grid-template-columns: 42% 58%; gap: 10px; margin: 6px 0 8px 0; align-items: start;">
        <!-- Kiri: Sketsa Drawing -->
        <div style="border: 1px solid #cbd5e1; border-radius: 5px; padding: 6px; background: #ffffff; text-align: center;">
          <div style="font-size: 7.2pt; font-weight: 700; color: #475569; margin-bottom: 4px; text-transform: uppercase;">
            Gambar Sketsa Drawing (Balon 1, 2, 3, 4)
          </div>
          <img src="data:image/webp;base64,{b64_img}" alt="Sketsa 71246-BZ010" style="max-width: 100%; height: auto; max-height: 140px; object-contain: contain; border: 1px solid #e2e8f0; border-radius: 4px; background: #fafafa;">
          <div style="font-size: 6.8pt; color: #64748b; margin-top: 4px;">
            Part Number: <span class="mono" style="font-weight: 700; color: #0f172a;">71246-BZ010</span> • Model: - • Customer: PT. TMMIN
          </div>
        </div>

        <!-- Kanan: Metadata & Status Box -->
        <div style="border: 1px solid #cbd5e1; border-radius: 5px; padding: 6px; background: #f8fafc;">
          <div style="font-size: 7.2pt; font-weight: 700; color: #475569; margin-bottom: 4px; text-transform: uppercase;">
            Parameter Dokumen Studio
          </div>
          <table style="width: 100%; font-size: 7.2pt; border-collapse: collapse;">
            <tr><td style="color: #64748b; width: 35%; padding: 2px 0;">No. Dokumen:</td><td class="mono" style="font-weight: 700;">FO-45-01</td></tr>
            <tr><td style="color: #64748b; padding: 2px 0;">Kategori:</td><td><span class="badge badge-material">Incomming Material</span></td></tr>
            <tr><td style="color: #64748b; padding: 2px 0;">Part Name:</td><td style="font-weight: 600;">PLATE RR SEAT CUSHION SET</td></tr>
            <tr><td style="color: #64748b; padding: 2px 0;">Customer:</td><td style="font-weight: 600;">PT. TMMIN</td></tr>
            <tr><td style="color: #64748b; padding: 2px 0;">Jumlah Titik:</td><td class="mono" style="font-weight: 700;">8 Baris Inspeksi</td></tr>
            <tr><td style="color: #64748b; padding: 2px 0;">Karakteristik:</td><td><span style="font-weight: 700; color: #065f46;">Sheared Blank Sheet Plate</span></td></tr>
          </table>
          <div style="margin-top: 5px; font-size: 6.8pt; color: #065f46; background: #d1fae5; padding: 3px 5px; border-radius: 3px; border: 1px solid #a7f3d0;">
            ✓ <strong>Kenapa Incomming Material?</strong> Bentuk part murni pelat datar potongan (tanpa lekukan stamping/lubang), dengan titik ukur tebal, panjang, lebar, dan spesifikasi baja SPC590.<br>
            ✓ Meski file fisik aslinya berasal dari folder vendor subcont shearing, checksheet mutunya adalah <em>Incomming Material</em>.
          </div>
        </div>
      </div>

      <!-- Tabel Titik Ukur 71246-BZ010 -->
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 8%; text-align: center;"># (NO)</th>
            <th style="width: 28%;">Item Inspeksi</th>
            <th style="width: 24%;">Standar / Toleransi</th>
            <th style="width: 22%;">Alat Ukur / Metode</th>
            <th style="width: 18%;">Kesesuaian Drawing</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="text-align: center; font-weight: 700;">1</td>
            <td><strong>Spec. Material</strong></td>
            <td><span class="mono">SPC590</span></td>
            <td><span class="mono">Data Label</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Balon 1 pada Drawing</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">2</td>
            <td><strong>Thickness</strong></td>
            <td><span class="mono">0.9 ± 0.09</span></td>
            <td><span class="mono">Caliper</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Balon 2 (Ketebalan pelat)</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">3</td>
            <td><strong>Length</strong></td>
            <td><span class="mono">1242 ± 1.0</span></td>
            <td><span class="mono">Roll Meter</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Balon 3 (Panjang pelat)</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">4</td>
            <td><strong>Width</strong></td>
            <td><span class="mono">434 ± 1.0</span></td>
            <td><span class="mono">Roll Meter</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Balon 4 (Lebar pelat)</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">5</td>
            <td><strong>No Rust</strong></td>
            <td><span class="mono">OK / NG</span></td>
            <td><span class="mono">Visual</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Aspek Visual Permukaan</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">5</td>
            <td><strong>No Scratch</strong></td>
            <td><span class="mono">OK / NG</span></td>
            <td><span class="mono">Visual</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Aspek Visual Permukaan</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">5</td>
            <td><strong>No Wave</strong></td>
            <td><span class="mono">OK / NG</span></td>
            <td><span class="mono">Visual</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Aspek Visual Permukaan</td>
          </tr>
          <tr>
            <td style="text-align: center; font-weight: 700;">5</td>
            <td><strong>Packing</strong></td>
            <td><span class="mono">OK / NG</span></td>
            <td><span class="mono">Visual</span></td>
            <td style="color: #166534; font-size: 7pt;">✓ Aspek Visual Kemasan</td>
          </tr>
        </tbody>
      </table>

      <div class="callout" style="background: #f0fdf4; border-color: #22c55e;">
        <strong>Perbedaan Kunci: Incomming Material vs Incomming Subcont Part</strong>
        <ul style="margin: 2px 0 0 0; padding-left: 16px;">
          <li><strong>Incomming Material (seperti 71246-BZ010)</strong>: Berupa pelat datar lembaran mentah (blank sheet / coil) dengan titik ukur dimensi potong (tebal, panjang, lebar, spesifikasi grade baja).</li>
          <li><strong>Incomming Subcont Part (seperti 57654-BZ090 Member RR Floor)</strong>: Sudah melalui proses pembentukan press stamping / bending / drawing (memiliki lekukan bodi, flange, lubang baut, dan profil part jadi).</li>
        </ul>
      </div>
    </div>

    <div class="page-footer">
      <span>PT. Summit Adyawinsa Indonesia • QC Department</span>
      <span>SOP-QC-DIGITAL-01 • Standarisasi Checksheet QC</span>
      <span>Halaman 3 dari 4</span>
    </div>
  </div>

  <!-- ==================== HALAMAN 4 ==================== -->
  <div class="page">
    <div class="content-wrap">
      <div class="doc-header">
        <div>
          <div class="company-tag">STANDAR OPERASIONAL PROSEDUR (SOP) KERJA</div>
          <h1 class="doc-title" style="font-size: 12pt;">LANGKAH OPERASIONAL STUDIO & SHORTCUT</h1>
        </div>
        <table class="meta-box">
          <tr><td class="meta-label">No. Dokumen:</td><td class="meta-val">SOP-QC-DIGITAL-01</td></tr>
          <tr><td class="meta-label">Bagian:</td><td class="meta-val">Alur Kerja & Ergonomi</td></tr>
        </table>
      </div>

      <h2>6. SOP Langkah Operasional Digitalisasi Checksheet</h2>

      <div class="step-grid">
        <div class="step-card">
          <span class="num">1</span><strong>Pilih Part di Workspace</strong>
          <p style="margin: 2px 0 0 0;">Buka menu <em>Daftar Checksheet</em>. Filter tab kategori atau gunakan pencarian part number. Klik tombol <em>Edit</em> atau double-click baris part.</p>
        </div>
        <div class="step-card">
          <span class="num">2</span><strong>Koreksi Kategori FactoryHub</strong>
          <p style="margin: 2px 0 0 0;">Di header Studio, periksa dropdown Kategori. Jika part IQC subcont, ubah dari Accuracy ke <span class="badge badge-subcont">Incomming Subcont Part</span>.</p>
        </div>
        <div class="step-card">
          <span class="num">3</span><strong>Input No. Dokumen & Customer</strong>
          <p style="margin: 2px 0 0 0;">Isi No. Dokumen sesuai form checksheet fisik (misal <span class="mono">FO-45-01</span>) beserta nama customer dan model mobil.</p>
        </div>
        <div class="step-card">
          <span class="num">4</span><strong>Input Titik Ukur & Toleransi</strong>
          <p style="margin: 2px 0 0 0;">Ketik titik ukur atau klik <em>Paste Excel</em> dari file aslinya. Klik tombol <em>Standarkan</em> agar nama alat ukur otomatis rapi.</p>
        </div>
        <div class="step-card">
          <span class="num">5</span><strong>Pasang Sketsa Drawing</strong>
          <p style="margin: 2px 0 0 0;">Cari di Google Drive via tombol <em>Cari di Drive</em> atau tekan <span class="mono">Ctrl+V</span> untuk menempelkan gambar screenshot langsung.</p>
        </div>
        <div class="step-card">
          <span class="num">6</span><strong>Simpan & Beri Status</strong>
          <p style="margin: 2px 0 0 0;">Tekan <span class="mono">Ctrl+S</span>. Bila sudah lengkap, klik <strong>Tandai Siap Kirim</strong>. Jika ada kendala, tandai <em>Revisi Gambar</em> / <em>Revisi Isi</em>.</p>
        </div>
      </div>

      <h2>7. Panduan Status Dokumen Checksheet</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 25%;">Status</th>
            <th style="width: 40%;">Kondisi Part</th>
            <th style="width: 35%;">Tindak Lanjut</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Belum Dikerjakan</strong></td>
            <td>Part baru terdaftar dari master catalog atau status dikembalikan.</td>
            <td>Operator melakukan review, input titik ukur, dan gambar.</td>
          </tr>
          <tr>
            <td><strong style="color: #0284c7;">Siap Kirim</strong></td>
            <td>Titik ukur, toleransi, gambar sketsa, dan kategori sudah 100% valid.</td>
            <td>Siap dikirim massal (batch dispatch) ke FactoryHub oleh Admin.</td>
          </tr>
          <tr>
            <td><strong style="color: #d97706;">Perlu Revisi Isi</strong></td>
            <td>Ada keraguan standar toleransi, salah ukuran, atau revisi engineering.</td>
            <td>Beri catatan pada keterangan revisi dan verifikasi ke engineering.</td>
          </tr>
          <tr>
            <td><strong style="color: #7c3aed;">Perlu Revisi Gambar</strong></td>
            <td>Gambar sketsa belum ada, nomor balon buram, atau posisi miring.</td>
            <td>Cari drawing revisi terbaru di Google Drive / database gambar.</td>
          </tr>
          <tr>
            <td><strong style="color: #166534;">Checksheet Done</strong></td>
            <td>Checksheet telah berhasil terkirim dan aktif di FactoryHub.</td>
            <td>Checksheet siap digunakan operasional inspeksi harian QC.</td>
          </tr>
        </tbody>
      </table>

      <h2>8. Shortcut Keyboard Studio (Ergonomi Kerja Instan)</h2>
      <table class="data-table">
        <thead>
          <tr>
            <th style="width: 28%;">Kombinasi Tombol</th>
            <th style="width: 32%;">Fungsi</th>
            <th style="width: 40%;">Keunggulan</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><span class="mono">Alt + →</span> / <span class="mono">N</span> / <span class="mono">]</span></td>
            <td>Pindah ke <strong>Next Part</strong></td>
            <td>Pindah seketika dalam <strong>0 milidetik</strong> tanpa delay.</td>
          </tr>
          <tr>
            <td><span class="mono">Alt + ←</span> / <span class="mono">P</span> / <span class="mono">[</span></td>
            <td>Pindah ke <strong>Prev Part</strong></td>
            <td>Kembali ke part sebelumnya seketika dari memory cache.</td>
          </tr>
          <tr>
            <td><span class="mono">Ctrl + S</span> / <span class="mono">Cmd + S</span></td>
            <td><strong>Simpan Data Studio</strong></td>
            <td>Menyimpan seluruh titik ukur & metadata ke database.</td>
          </tr>
          <tr>
            <td><span class="mono">Ctrl + V</span> / <span class="mono">Cmd + V</span></td>
            <td><strong>Paste Gambar Sketsa</strong></td>
            <td>Menempelkan gambar langsung dari clipboard ke layar.</td>
          </tr>
          <tr>
            <td><span class="mono">Enter</span></td>
            <td>Pindah ke Baris Bawah</td>
            <td>Navigasi sel tabel titik ukur layaknya Microsoft Excel.</td>
          </tr>
          <tr>
            <td><span class="mono">Esc</span></td>
            <td>Keluar / Tutup Studio</td>
            <td>Proteksi konfirmasi jika ada perubahan yang belum disimpan.</td>
          </tr>
        </tbody>
      </table>

    </div>

    <div class="page-footer">
      <span>PT. Summit Adyawinsa Indonesia • QC Department</span>
      <span>SOP-QC-DIGITAL-01 • Standarisasi Checksheet QC</span>
      <span>Halaman 4 dari 4</span>
    </div>
  </div>

</body>
</html>
"""

def generate_pdf():
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(docs_dir, "panduan_dan_standarisasi_checksheet_qc.html")
    pdf_path = os.path.join(docs_dir, "PANDUAN_DAN_STANDARISASI_CHECKSHEET_QC.pdf")
    static_pdf = os.path.join(os.path.dirname(docs_dir), "static", "docs", "PANDUAN_DAN_STANDARISASI_CHECKSHEET_QC.pdf")

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE)
    print(f"[*] HTML generated: {html_path}")

    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    cmd = [
        chrome_path,
        "--headless",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path}"
    ]
    subprocess.run(cmd, check=True)
    
    # Copy to static web
    import shutil
    shutil.copy2(pdf_path, static_pdf)
    print(f"[*] PDF generated: {pdf_path}")
    print(f"[*] Static copy: {static_pdf}")

    # Verify pages
    reader = pypdf.PdfReader(pdf_path)
    print(f"[SUCCESS] Total Pages: {len(reader.pages)}")

if __name__ == "__main__":
    generate_pdf()
