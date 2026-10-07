#!/usr/bin/env python3
"""
Import & Standardize DQC 1 OKTOBER Checksheets into Supabase PostgreSQL.
======================================================================
Imports all 5P45 checksheets from `documents/DQC_1 OKTOBER`:
  1. IPQC 1. STAMPING (20 parts)
  2. IPQC 2. SSW (7 parts from CS SPOT NUT 5P45.xlsx)
  3. IPQC 3. FINAL (6 parts)
  4. IR CHILD PART (19 parts)
  5. IR MONTHLY FG (47 parts)

Requirements:
  - NO image scanning/extraction (images=[]); drawing will be uploaded manually by operators.
  - Status set to 'Belum di review' (NOT 'Checksheet Done' or 'Butuh Revisi').
  - Keterangan: 'Perlu review & verifikasi drawing manual (Batch 1 Oktober)'.
  - Even assignment distribution across Zul, Iqbal, Rama.
  - Standardized inspection points with One Numbering Rule & Burr ≤ 0.3 mm.

Usage:
  python scripts/import_dqc_1_oktober.py          # Dry-run preview
  python scripts/import_dqc_1_oktober.py --apply  # Commit to Supabase
"""
import asyncio
import os
import sys
import glob
import re
from datetime import datetime
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import openpyxl
from sqlalchemy import select, delete
from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, PartImage, User, ActivityLog
from parsers.mmki_ipqc import MMKIIPQCParser
from parsers.mmki_ir import MMKIIRParser
from parsers.smart_parser import TextNormalizer


OPERATORS = [
    {"name": "Zul", "id": 2},
    {"name": "Iqbal", "id": 3},
    {"name": "Rama", "id": 4}
]


def clean_str(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(s)).upper()


def parse_ssw_sheet(ws, sheet_name: str) -> Dict[str, Any]:
    """Parse single part sheet inside CS SPOT NUT 5P45.xlsx."""
    pname = str(ws.cell(12, 3).value or "").lstrip(": ").strip()
    pno = str(ws.cell(13, 3).value or "").lstrip(": ").strip()
    model = str(ws.cell(14, 3).value or "").lstrip(": ").strip() or "5P45"

    if not pno:
        pno = sheet_name

    points = []
    balloon = 1
    for r in range(15, min(ws.max_row + 1, 40)):
        no_val = str(ws.cell(r, 2).value or "").strip()
        spec_val = str(ws.cell(r, 3).value or "").strip()
        qty_val = str(ws.cell(r, 6).value or "").strip()
        tool_val = str(ws.cell(r, 7).value or "").strip()

        if not spec_val or any(h in spec_val.upper() for h in ["SPESIFIKASI", "TANGGAL", "APPEARANCE"]):
            continue
        if no_val in ["*", "#"] and "SOP" in spec_val:
            continue
        if "SHIFT" in spec_val.upper() or "MESIN" in spec_val.upper():
            continue

        std_val = qty_val if qty_val else "OK / NG"
        method_val = tool_val if tool_val else "Visual"
        if "MATA" in method_val.upper():
            method_val = "Visual"

        item_name = spec_val
        if "WELDING STRENGTH" in spec_val.upper():
            m_nut = re.search(r"(Nut\s*M\d+|Bolt\s*M?\d*)", spec_val, re.I)
            nut_suffix = f" ({m_nut.group(1)})" if m_nut else ""
            item_name = f"Welding Strength{nut_suffix}"
            m_min = re.search(r"\((Min[^)]+)\)", spec_val, re.I)
            min_val = m_min.group(1).strip() if m_min else "Min 190 Kgf.cm"
            std_val = f"{min_val} (n = 1 / Lot)"

        ino = no_val if no_val.isdigit() else str(balloon)
        balloon += 1
        points.append({
            "item_no": ino,
            "inspection_item": item_name,
            "standard": std_val,
            "method": method_val,
            "master_data": ""
        })

    return {
        "part_number": pno,
        "part_name": pname,
        "model": model,
        "customer": "PT. MMKI",
        "doc_number": "IPQC SSW - Spot Nut",
        "points": points
    }


def parse_final_wb(fp: str) -> tuple[Dict[str, str], List[Dict[str, str]]]:
    """Parse IPQC Final Assembly workbook (Cols 25-35 on Page 1..4)."""
    wb = openpyxl.load_workbook(fp, data_only=True)
    points = []
    current_balloon = 1
    last_method = "Caliper"

    fname = os.path.basename(fp)
    match_pn = re.search(r"([0-9A-Z]{4,5}[A-Z0-9]{3,4}[A-Z0-9])", fname)
    fn_pn = match_pn.group(1).replace("_", "").strip() if match_pn else ""

    ws_first = wb[wb.sheetnames[0]]
    cell_pn = str(ws_first.cell(1, 28).value or "").strip()
    cell_pname = str(ws_first.cell(3, 28).value or "").strip()
    cell_model = str(ws_first.cell(3, 11).value or "").strip() or "5P45"
    cell_cust = str(ws_first.cell(1, 11).value or "").strip() or "PT. MMKI"
    cell_doc = str(ws_first.cell(5, 11).value or "").strip() or "Form 1"

    # Handle 73230 copy-paste anomaly where Page 1 retained 73210
    if fn_pn and fn_pn != cell_pn:
        part_number = fn_pn
        if "73230" in fn_pn:
            part_name = "RAIL ASSY -ROOF, RR"
        else:
            part_name = cell_pname
    else:
        part_number = cell_pn or fn_pn
        part_name = cell_pname

    meta = {
        "part_number": part_number,
        "part_name": part_name,
        "model": cell_model,
        "customer": cell_cust,
        "doc_number": cell_doc,
    }

    for sname in wb.sheetnames:
        if not sname.lower().startswith("page"):
            continue
        ws = wb[sname]

        hdr_row = None
        for r in range(1, 15):
            val26 = str(ws.cell(r, 26).value or "").strip().upper()
            if "INSPECTION ITEM" in val26:
                hdr_row = r
                break
        if not hdr_row:
            continue

        r = hdr_row + 5  # data usually starts at r=12
        while r <= ws.max_row:
            c25 = ws.cell(r, 25).value
            c26 = ws.cell(r, 26).value
            c30 = ws.cell(r, 30).value
            c31 = ws.cell(r, 31).value
            c32 = ws.cell(r, 32).value
            c33 = ws.cell(r, 33).value
            c35 = ws.cell(r, 35).value
            c38 = ws.cell(r, 38).value

            c26_str = str(c26 or "").strip()
            c25_str = str(c25 or "").strip()

            if any(k in c26_str.upper() for k in ["JUDGEMENT", "TOTAL POINT", "MMKI"]):
                break
            if c25 is None and c26 is None and c30 is None and c31 is None and c32 is None and c33 is None and c35 is None:
                r += 1
                continue

            if c25_str and c25_str.isdigit():
                current_balloon = int(c25_str)

            if not c26_str and not c31 and not c32 and not c33:
                r += 1
                continue

            item_name = c26_str
            coord = str(c30 or "").strip()
            if coord:
                item_name = f"{item_name} {coord}".strip()

            tol = str(c33 or "").strip()
            next_tol = str(ws.cell(r + 1, 33).value or "").strip() if r + 1 <= ws.max_row else ""
            skip_next = False
            if tol and next_tol and (next_tol == "0" or next_tol.startswith("-") or next_tol.startswith("+")):
                tol = f"{tol} / {next_tol}"
                skip_next = True

            nom = str(c32 or "").strip() if c32 is not None else ""
            if not nom and c31 is not None:
                nom = str(c31).strip()

            if tol and tol not in nom:
                if nom and not nom.upper().startswith("INSERT PIN") and "OK" not in nom.upper():
                    full_std = f"{nom} {tol}".strip()
                elif not nom:
                    full_std = tol
                else:
                    full_std = nom
            else:
                full_std = nom or "OK / NG"

            mth = str(c35 or "").strip()
            if mth:
                last_method = mth
            else:
                mth = last_method

            m_u = f"{item_name} {mth}".upper()
            if "PIN GO" in m_u:
                clean_method = "Pin Go/No Go"
            elif "INSERT PIN" in m_u or "DATUM PIN" in m_u:
                clean_method = "Insert Pin Datum"
            elif "PIN CHECK" in m_u:
                clean_method = "Pin Check + Caliper"
            elif "MARK" in m_u and "CTR" in m_u:
                clean_method = "Marking Center Line"
            elif "TAPPER" in m_u or "GAP" in m_u:
                clean_method = "Tapper Gg"
            elif "FEELER" in m_u or "SHIM" in m_u:
                clean_method = "Feeler Gg"
            elif "STEELRULE" in m_u or "TRIM" in m_u:
                clean_method = "Steelrule"
            elif "VISUAL" in m_u:
                clean_method = "Visual"
            elif "CALIPER" in m_u or "CAIPER" in m_u:
                clean_method = "Caliper"
            else:
                clean_method = mth or "Caliper"

            clean_item_name = " ".join(item_name.split())
            if clean_item_name.upper().startswith("HOEL POSITION"):
                clean_item_name = clean_item_name.replace("HOEL", "HOLE").replace("Hoel", "Hole")

            if item_name:
                points.append({
                    "item_no": str(current_balloon),
                    "inspection_item": clean_item_name,
                    "standard": " ".join(full_std.split()),
                    "method": clean_method,
                    "master_data": str(c38 or "").strip()
                })
            r += (2 if skip_next else 1)

    wb.close()
    return meta, points


async def run_import(apply_mode: bool = False):
    print("=" * 80)
    print("[*] IMPORT DQC 1 OKTOBER CHECKSHEETS TO SUPABASE")
    print(f"[*] Mode: {'>>> APPLY (COMMITTING TO SUPABASE DB) <<<' if apply_mode else 'DRY-RUN (PREVIEW ONLY)'}")
    print("=" * 80)

    ipqc_parser = MMKIIPQCParser()
    ir_parser = MMKIIRParser()

    tasks_to_import = []

    # 1. IPQC Stamping
    stamping_files = sorted(glob.glob("documents/DQC_1 OKTOBER/1. IPQC/1. STAMPING/*.xlsx"))
    print(f"[*] Parsing IPQC Stamping ({len(stamping_files)} files)...")
    for fp in stamping_files:
        if os.path.basename(fp).startswith("~$"):
            continue
        try:
            wb = openpyxl.load_workbook(fp, data_only=True)
            meta = ipqc_parser.extract_metadata(fp, wb=wb)
            raw_pts = ipqc_parser.extract_inspection_points(fp, wb=wb)
            wb.close()
        except Exception as e:
            print(f"[!] Error parsing {fp}: {e}")
            meta = {"part_number": os.path.splitext(os.path.basename(fp))[0], "part_name": "", "doc_number": "Form 1"}
            raw_pts = []

        tasks_to_import.append({
            "part_number": meta.get("part_number") or os.path.splitext(os.path.basename(fp))[0],
            "part_name": meta.get("part_name", ""),
            "model": "5P45",
            "customer": "PT. MMKI",
            "doc_number": f"IPQC Stamping - {meta.get('doc_number', 'Form 1')}",
            "template_type": "MMKIIPQCParser",
            "raw_file_path": fp,
            "raw_points": raw_pts,
            "category": "IPQC Stamping"
        })

    # 2. IPQC SSW
    ssw_file = "documents/DQC_1 OKTOBER/1. IPQC/2. SSW/CS SPOT NUT 5P45.xlsx"
    if os.path.exists(ssw_file):
        print("[*] Parsing IPQC SSW (CS SPOT NUT 5P45.xlsx)...")
        wb_ssw = openpyxl.load_workbook(ssw_file, data_only=True)
        for sname in ["743F4", "76742", "76743", "76759", "73211", "745A2", "745A3"]:
            if sname in wb_ssw.sheetnames:
                ssw_res = parse_ssw_sheet(wb_ssw[sname], sname)
                tasks_to_import.append({
                    "part_number": ssw_res["part_number"],
                    "part_name": ssw_res["part_name"],
                    "model": "5P45",
                    "customer": "PT. MMKI",
                    "doc_number": ssw_res["doc_number"],
                    "template_type": "MMKIIPQCParser",
                    "raw_file_path": f"{ssw_file}#{sname}",
                    "raw_points": ssw_res["points"],
                    "category": "IPQC SSW"
                })
        wb_ssw.close()

    # 3. IPQC Final
    final_files = sorted(glob.glob("documents/DQC_1 OKTOBER/1. IPQC/3. FINAL/*.xlsx"))
    print(f"[*] Parsing IPQC Final ({len(final_files)} files)...")
    for fp in final_files:
        if os.path.basename(fp).startswith("~$"):
            continue
        try:
            meta, raw_pts = parse_final_wb(fp)
        except Exception as e:
            print(f"[!] Error parsing {fp}: {e}")
            meta = {"part_number": os.path.splitext(os.path.basename(fp))[0], "part_name": "", "doc_number": "Form 1"}
            raw_pts = []

        tasks_to_import.append({
            "part_number": meta.get("part_number") or os.path.splitext(os.path.basename(fp))[0],
            "part_name": meta.get("part_name", ""),
            "model": "5P45",
            "customer": "PT. MMKI",
            "doc_number": f"IPQC Final - {meta.get('doc_number', 'Form 1')}",
            "template_type": "MMKIIRParser",
            "raw_file_path": fp,
            "raw_points": raw_pts,
            "category": "IPQC Final"
        })

    # 4. IR Child Part
    child_files = sorted(glob.glob("documents/DQC_1 OKTOBER/2. IR CHILD PART/*.xlsx"))
    print(f"[*] Parsing IR Child Part ({len(child_files)} files)...")
    for fp in child_files:
        if os.path.basename(fp).startswith("~$"):
            continue
        try:
            wb = openpyxl.load_workbook(fp, data_only=True)
            meta = ir_parser.extract_metadata(fp, wb=wb)
            raw_pts = ir_parser.extract_inspection_points(fp, wb=wb)
            wb.close()
        except Exception as e:
            print(f"[!] Error parsing {fp}: {e}")
            meta = {"part_number": os.path.splitext(os.path.basename(fp))[0], "part_name": "", "doc_number": "Report"}
            raw_pts = []

        tasks_to_import.append({
            "part_number": meta.get("part_number") or os.path.splitext(os.path.basename(fp))[0],
            "part_name": meta.get("part_name", ""),
            "model": "5P45",
            "customer": "PT. MMKI",
            "doc_number": f"IR Child Part - {meta.get('doc_number', 'Report')}",
            "template_type": "MMKIIRParser",
            "raw_file_path": fp,
            "raw_points": raw_pts,
            "category": "IR Child Part"
        })

    # 5. IR Monthly FG
    fg_files = sorted(glob.glob("documents/DQC_1 OKTOBER/3. IR MONTHLY FG/*.xlsx"))
    print(f"[*] Parsing IR Monthly FG ({len(fg_files)} files)...")
    for fp in fg_files:
        if os.path.basename(fp).startswith("~$"):
            continue
        try:
            wb = openpyxl.load_workbook(fp, data_only=True)
            meta = ir_parser.extract_metadata(fp, wb=wb)
            raw_pts = ir_parser.extract_inspection_points(fp, wb=wb)
            wb.close()
        except Exception as e:
            print(f"[!] Error parsing {fp}: {e}")
            meta = {"part_number": os.path.splitext(os.path.basename(fp))[0], "part_name": "", "doc_number": "Report"}
            raw_pts = []

        tasks_to_import.append({
            "part_number": meta.get("part_number") or os.path.splitext(os.path.basename(fp))[0],
            "part_name": meta.get("part_name", ""),
            "model": "5P45",
            "customer": "PT. MMKI",
            "doc_number": f"IR Monthly FG - {meta.get('doc_number', 'Report')}",
            "template_type": "MMKIIRParser",
            "raw_file_path": fp,
            "raw_points": raw_pts,
            "category": "IR Monthly FG"
        })

    print(f"\n[*] Total checksheets to import/update: {len(tasks_to_import)}")

    async with AsyncSessionLocal() as session:
        op_idx = 0
        imported_count = 0
        total_points_created = 0

        for item in tasks_to_import:
            assigned_op = OPERATORS[op_idx % len(OPERATORS)]
            op_idx += 1

            pno = item["part_number"]
            clean_pno = clean_str(pno)
            pname = item["part_name"]
            rfp = item["raw_file_path"]
            doc_no = item["doc_number"]
            tt = item["template_type"]

            # Standardize inspection points directly without defect explosion slop
            raw_pts = item["raw_points"]
            std_pts = raw_pts if raw_pts else []

            # Check if record already exists by raw_file_path OR (clean_part_number and doc_number)
            stmt = select(Checksheet).where(
                (Checksheet.raw_file_path == rfp) |
                ((Checksheet.clean_part_number == clean_pno) & (Checksheet.doc_number == doc_no))
            )
            res = await session.execute(stmt)
            existing_cs = res.scalars().first()

            target_status = "Belum di review"
            target_keterangan = f"Perlu review & verifikasi drawing manual (Batch 1 Oktober - {item['category']})"

            if apply_mode:
                if existing_cs:
                    cs = existing_cs
                    cs.part_number = pno
                    cs.clean_part_number = clean_pno
                    cs.part_name = pname or cs.part_name
                    cs.model = "5P45"
                    cs.customer = "PT. MMKI"
                    cs.doc_number = doc_no
                    cs.template_type = tt
                    cs.status = target_status
                    cs.keterangan = target_keterangan
                    cs.assigned_to = assigned_op["name"]
                    cs.assigned_user_id = assigned_op["id"]
                    cs.raw_file_path = rfp
                    await session.flush()
                else:
                    cs = Checksheet(
                        part_number=pno,
                        clean_part_number=clean_pno,
                        part_name=pname,
                        model="5P45",
                        customer="PT. MMKI",
                        doc_number=doc_no,
                        template_type=tt,
                        status=target_status,
                        keterangan=target_keterangan,
                        assigned_to=assigned_op["name"],
                        assigned_user_id=assigned_op["id"],
                        raw_file_path=rfp
                    )
                    session.add(cs)
                    await session.flush()

                # Clear old points and insert standardized points
                await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
                for idx, pt in enumerate(std_pts):
                    raw_item = pt.get("inspection_item") or f"Point {idx + 1}"
                    if raw_item.upper().startswith("HOEL POSITION"):
                        raw_item = raw_item.replace("HOEL", "HOLE").replace("Hoel", "Hole")

                    raw_mth = (pt.get("method") or "Visual").strip()
                    mth_low = raw_mth.lower()
                    if mth_low == "caiper":
                        raw_mth = "Caliper"
                    elif mth_low == "tapper":
                        raw_mth = "Tapper Gg"
                    elif "marking ctr" in mth_low:
                        raw_mth = "Marking Center Line"
                    elif "pin go" in mth_low:
                        raw_mth = "Pin Go/No Go"
                    elif mth_low == "caliper/micrometer":
                        raw_mth = "Caliper / Micrometer"

                    ip = InspectionPoint(
                        checksheet_id=cs.id,
                        item_no=pt.get("item_no") or str(idx + 1),
                        inspection_item=raw_item,
                        standard=pt.get("standard") or "-",
                        method=raw_mth,
                        master_data=pt.get("master_data") or "",
                        order_index=idx
                    )
                    session.add(ip)

                # Clear old images (drawings are to be uploaded manually by operator)
                await session.execute(delete(PartImage).where(PartImage.checksheet_id == cs.id))

            imported_count += 1
            total_points_created += len(std_pts)

            if imported_count <= 8 or imported_count % 20 == 0:
                print(f"  [{item['category']:14s}] PN: {pno:12s} | {len(std_pts):3d} pts | Assign: {assigned_op['name']:6s} | {pname[:25]}")

        if apply_mode:
            log = ActivityLog(
                action="IMPORT_DQC_1_OKTOBER",
                operator="Antigravity System",
                status="SUCCESS",
                details=f"Imported {imported_count} checksheets ({total_points_created} points) with status 'Belum di review' assigned across Zul, Iqbal, Rama",
                created_at=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
            print("\n" + "=" * 80)
            print("[✓] COMMIT SUKSES! Seluruh checksheet berhasil disimpan di Supabase.")
        else:
            print("\n" + "=" * 80)
            print("[*] DRY-RUN SELESAI. Tidak ada perubahan yang disimpan ke database.")

        print(f"    - Total Checksheet Diproses   : {imported_count}")
        print(f"    - Total Titik Inspeksi Dibuat : {total_points_created}")
        print(f"    - Status Ditugaskan           : 'Belum di review'")
        print(f"    - Pembagian Operator          : Rata Zul, Iqbal, Rama")
        print("=" * 80)


if __name__ == "__main__":
    apply_flag = "--apply" in sys.argv
    asyncio.run(run_import(apply_mode=apply_flag))
