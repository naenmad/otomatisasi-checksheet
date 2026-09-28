import asyncio
import json
import os
import re
from database.connection import AsyncSessionLocal
from sqlalchemy import text

def clean_pno(s):
    return re.sub(r'[^a-zA-Z0-9]', '', str(s)).upper()

async def enrich():
    with open('/tmp/dupe_report.json') as f:
        data = json.load(f)

    with open('data/factoryhub_catalog.json') as f:
        cat_data = json.load(f)
    catalog_parts = cat_data.get('parts', [])
    catalog_clean_map = {p.get('clean_number', ''): p for p in catalog_parts}

    hpm_items = data['CS MATERIAL  INCOMING HPM']
    sim_items = data['CS MATERIAL INCOMING SIM YHA']

    async with AsyncSessionLocal() as session:
        r = await session.execute(text('SELECT clean_part_number, part_number, part_name, model, customer, status FROM checksheets'))
        db_map = {row[0]: (row[1], row[2], row[3], row[4], row[5]) for row in r.fetchall()}

    def resolve_part_info(cpn, fallback_pno, fallback_pname):
        # 1. Check exact clean in DB
        if cpn in db_map and db_map[cpn][1] and db_map[cpn][1] != '-':
            return db_map[cpn][0], db_map[cpn][1], db_map[cpn][2]
        # 2. Check exact in catalog
        if cpn in catalog_clean_map:
            cp = catalog_clean_map[cpn]
            return cp.get('part_number', fallback_pno), cp.get('part_name', fallback_pname), '-'
        # 3. Check prefix in DB
        for k, v in db_map.items():
            if k.startswith(cpn) and v[1] and v[1] != '-':
                return v[0], v[1], v[2]
        # 4. Check prefix in catalog
        for cp in catalog_parts:
            if cp.get('clean_number', '').startswith(cpn):
                return cp.get('part_number', fallback_pno), cp.get('part_name', fallback_pname), '-'
        # 5. Fallback
        return fallback_pno, fallback_pname, '-'

    lines = []
    lines.append('# Dokumentasi Analisis Part Beririsan (Duplikat)')
    lines.append('### Folder Analisis: `CS IQC SUBCONT` vs 4 Folder Checksheet Lainnya\n')
    lines.append('> [!NOTE]')
    lines.append('> Dokumen ini memetakan seluruh **59 part unik** yang ditemukan di folder `CS IQC SUBCONT` dan juga terdapat di folder checksheet lainnya. Laporan ini merinci sumber file, nama part resmi FactoryHub, model, perbandingan isi, dan aturan integritas sistem.\n')

    lines.append('## 1. Ringkasan Eksekutif Antar Folder\n')
    lines.append('| Folder Pembanding | Total Part di Folder | Jumlah Beririsan | Status Keselarasan | Karakteristik Utama |')
    lines.append('| :--- | :---: | :---: | :---: | :--- |')
    lines.append('| **CS IQC MATERIAL HPM TG4R** | 68 | **0 part (0%)** | Unik | Khusus part model TG4R |')
    lines.append('| **CS MATERIAL INCOMING MMKI** | 80 | **0 part (0%)** | Unik | Khusus material incoming MMKI |')
    lines.append('| **CS MATERIAL  INCOMING HPM** | 89 | **14 part (15.7%)** | Identik | Format sheet satuan vs format buku gabungan |')
    lines.append('| **CS MATERIAL INCOMING SIM YHA** | 77 | **45 part (58.4%)** | Tumpang Tindih | Checksheet Coil/Sheet bahan baku vs Subcont |')
    lines.append('| **TOTAL IRISAN UNIK** | - | **59 PART** | Terdata di DB | Telah dinormalisasi di database |\n')

    lines.append('---\n')
    lines.append('## 2. Rincian 14 Part Beririsan: `CS IQC SUBCONT` vs `CS MATERIAL  INCOMING HPM`\n')
    lines.append('Pada bagian ini, part di folder **CS IQC SUBCONT** bersumber dari file buku kerja gabungan `c.sheet HPM/C.SHEET TCF HPM.xlsx`, sedangkan di folder **CS MATERIAL INCOMING HPM** tersimpan sebagai file satuan terpisah per part di subfolder modelnya masing-masing (`2WF (JAZZ)`, `2XP (HR-V)`, `T5L`, `TE7`). Poin inspeksi dan gambar sketsa pada kedua folder ini **sama persis**.\n')
    lines.append('| No | Part Number Resmi | Nama Part (Official Catalog / DB) | Model | Sumber Folder SUBCONT | Sumber Folder INCOMING HPM | Status Verifikasi |')
    lines.append('| :-: | :--- | :--- | :---: | :--- | :--- | :---: |')

    for idx, item in enumerate(hpm_items, 1):
        cpn = item['clean_pno']
        sc = item['subcont']
        ot = item['other']
        pno, pname, model = resolve_part_info(cpn, sc['part_no'], sc['part_name'])
        lines.append(f'| {idx} | `{pno}` | {pname} | {model} | `{sc["file_rel"]}`<br>*(Sheet: {sc["sheet"]})* | `{ot["file_rel"]}`<br>*(Sheet: {ot["sheet"]})* | Identik |')

    lines.append('\n---\n')
    lines.append('## 3. Rincian 45 Part Beririsan: `CS IQC SUBCONT` vs `CS MATERIAL INCOMING SIM YHA`\n')
    lines.append('Pada bagian ini, part di folder **CS IQC SUBCONT** bersumber dari proses subkontraktor SIM (`CS subcont SIM.xlsx`), sedangkan di folder **CS MATERIAL INCOMING SIM YHA** bersumber dari incoming bahan baku Coil/Sheet (`7.IQC/CS IQC  coil (BODY)..xlsx` dan `7.IQC/CS IQC  coil (SEAT).xlsx`). Sistem memprioritaskan data resmi dari folder `7.IQC`.\n')
    lines.append('| No | Part Number Resmi | Nama Part (Official Catalog / DB) | Model | Sumber Folder SUBCONT | Sumber Folder SIM YHA (7.IQC) | Prioritas Sistem |')
    lines.append('| :-: | :--- | :--- | :---: | :--- | :--- | :---: |')

    for idx, item in enumerate(sim_items, 1):
        cpn = item['clean_pno']
        sc = item['subcont']
        ot = item['other']
        pno, pname, model = resolve_part_info(cpn, sc['part_no'], sc['part_name'])
        lines.append(f'| {idx} | `{pno}` | {pname} | {model} | `{sc["file_rel"]}`<br>*(Sheet: {sc["sheet"]})* | `{ot["file_rel"]}`<br>*(Sheet: {ot["sheet"]})* | Data Resmi 7.IQC |')

    lines.append('\n---\n')
    lines.append('## 4. Aturan Integritas Data di Database & Otomasi FactoryHub\n')
    lines.append('1. **Deduplikasi via Clean Part Number**: Seluruh part number dinormalisasi (menghilangkan strip, spasi, titik). Dengan aturan ini, tidak akan ada baris ganda di database maupun saat antrean dikirim ke FactoryHub.')
    lines.append('2. **Preservasi Status `Reviewed`**: Setiap part yang telah diperiksa oleh operator di halaman *Review & Edit* dan ditandai `Reviewed` akan dipertahankan 100% dan tidak tertimpa kembali menjadi draft unreviewed saat proses impor massal.')
    lines.append('3. **Prioritas Acuan Resmi `7.IQC`**: Apabila terdapat perbedaan spesifikasi antara checksheet proses subkontraktor dan data bahan baku mentah, sistem memprioritaskan data master dari folder resmi `7.IQC`.')
    lines.append('4. **Isolasi Sketsa Gambar WebP**: Setiap sketsa drawing diisolasi strictly per worksheet (menggunakan relasi OpenXML drawing targets) sehingga sketsa part yang satu tidak tercampur atau tumpang tindih dengan part lain.')

    with open('documents/PERBANDINGAN_DUPLIKAT_CS_SUBCONT.md', 'w') as f:
        f.write('\n'.join(lines))
    print('Updated documents/PERBANDINGAN_DUPLIKAT_CS_SUBCONT.md with enriched catalog details!')

if __name__ == '__main__':
    asyncio.run(enrich())
