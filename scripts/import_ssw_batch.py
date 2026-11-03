#!/usr/bin/env python3
"""
Import & Standardize SSW Checksheets from CHECKSHEET SSW A into FaketoryHub (Supabase PostgreSQL).
==================================================================================================
Imports all 63 unique SSW checksheets from `documents/CHECKSHEET SSW A`:
  - 11 Machines: A.15, A.16, MA 1, MA 2, MA 4, MA 5, MB 1, MB 2, MB 3, MS 1, MS 2
  - Category: 'SSW', Format: 'daily', Template Type: 'IPQC SSW'
  - Status: 'Perlu Revisi Gambar' (TODO tab)
  - Keterangan: 'IPQC SSW <Proses> (<Machine>) - Gambar drawing menunggu upload manual'
  - Assigned evenly to Zul, Iqbal, Rama
  - Images: [] (Drawing uploaded manually by operator/user)

Usage:
  python scripts/import_ssw_batch.py          # Dry-run preview
  python scripts/import_ssw_batch.py --apply  # Commit to FaketoryHub DB
"""
import os
import sys
import re
import argparse
import asyncio
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import openpyxl
from sqlalchemy import select, delete
from database.connection import AsyncSessionLocal, engine
from database.models import Checksheet, InspectionPoint, PartImage, ActivityLog

FOLDER = os.path.join(BASE_DIR, "documents", "CHECKSHEET SSW A")

OPERATORS = [
    {"name": "Zul", "id": 2},
    {"name": "Iqbal", "id": 3},
    {"name": "Rama", "id": 4}
]


def clean_method(tool: str, item_text: str) -> str:
    t = str(tool or "").strip().upper()
    it = item_text.upper()
    if "MATA" in t or "VISUAL" in t:
        return "Visual"
    if "CALIPER" in t:
        return "Caliper"
    if "TORQUE" in t:
        return "Torque Wrench"
    if "PUSH" in t:
        return "Push Test"
    if "HAMMER" in t or "PALU" in t:
        return "Hammer Test"
    if "BOLT" in t:
        return "Bolt"
    if "NUT" in t:
        return "Nut"
    if "DESTRUCTIVE" in t:
        return "Destructive Test"
    if not t:
        if any(k in it for k in ["TORQUE", "KGF", "WELDING STRENGTH"]):
            return "Torque Wrench"
        if any(k in it for k in ["PUSH", "KN"]):
            return "Push Test"
        if any(k in it for k in ["DESTRUKTIF", "DESTRUCTIVE", "NUGGET"]):
            return "Destructive Test"
        if "BURRY" in it or "BURR" in it:
            return "Caliper"
        if "ULIR" in it:
            return "Bolt"
        return "Visual"
    return tool.strip()


def parse_point_row(no_val: str, spec_val: str, qty_val: str, tool_val: str, seq: int) -> Dict[str, Any]:
    raw_item = spec_val.strip()
    raw_qty = str(qty_val or "").strip().lstrip(": ")
    raw_tool = clean_method(tool_val, raw_item)
    item_u = raw_item.upper()

    # 1. Burry
    if "BURRY" in item_u or "BURR" in item_u:
        item_name = "Burry"
        if "1.0" in raw_item and "3.2" in raw_item:
            std_name = "t ≤ 1.0 = 0.2 mm, 1 ≤ t ≤ 3.2 = 0.3 mm"
        elif "0.3" in raw_item:
            std_name = "≤ 0.3 mm"
        elif raw_qty:
            std_name = raw_qty
        else:
            std_name = "≤ 0.3 mm"
        return {
            "item_no": str(seq),
            "inspection_item": item_name,
            "standard": std_name,
            "method": "Caliper",
            "master_data": "",
            "measuring_position": ""
        }

    # 2. Welding Strength / Torque Test
    if "WELDING STRENGTH" in item_u or "KGF" in item_u:
        m_nut = re.search(r"(Nut\s*M\d+|Bolt\s*M?\d*|Plate\s*Nut\s*[\d/]+)", raw_item, re.I)
        nut_str = f" ({m_nut.group(1)})" if m_nut else ""
        item_name = f"Welding Strength{nut_str}"

        # Extract torque value
        m_min = re.search(r"(?:Min\s*)?(\d+(?:\.\d+)?\s*Kgf[./]cm(?:\s*\(min\))?)", raw_item, re.I)
        if not m_min:
            m_min = re.search(r"\((Min[^)]+)\)", raw_item, re.I)

        if m_min:
            val = m_min.group(1).strip()
            if not val.lower().startswith("min"):
                val = f"Min {val}"
            val = val.replace("(min)", "").strip()
            std_name = f"{val} (n = 1 / Lot)"
        elif raw_qty:
            std_name = raw_qty
        else:
            std_name = "Min 190 Kgf.cm (n = 1 / Lot)"

        return {
            "item_no": str(seq),
            "inspection_item": item_name,
            "standard": std_name,
            "method": "Torque Wrench",
            "master_data": "",
            "measuring_position": ""
        }

    # 3. Push Test (kN)
    if "KN" in item_u and ("MIN" in item_u or "PUSH" in raw_tool.upper()):
        m_part = re.search(r"(Plate\s*Nut\s*[\d/]+|Bolt\s*M?\d+|Nut\s*M?\d*)", raw_item, re.I)
        part_str = f" ({m_part.group(1)})" if m_part else ""
        item_name = f"Push Test{part_str}"

        m_kn = re.search(r"(\d+(?:\.\d+)?\s*Kn)", raw_item, re.I)
        if m_kn:
            kn_val = m_kn.group(1).replace("Kn", "kN").replace("kn", "kN")
            std_name = f"Min {kn_val}"
        elif raw_qty:
            std_name = raw_qty
        else:
            std_name = "Min 6.67 kN"

        return {
            "item_no": str(seq),
            "inspection_item": item_name,
            "standard": std_name,
            "method": "Push Test",
            "master_data": "",
            "measuring_position": ""
        }

    # 4. Destructive Test
    if "DESTRUKTIF" in item_u or "DESTRUCTIVE" in item_u or "NUGGET" in item_u or raw_tool == "Destructive Test":
        if "NUGGET" in item_u or "Ø" in item_u or "ø" in raw_item:
            item_name = "Destructive Test (Nugget)"
            m_dia = re.search(r"[øØ]\s*(\d+(?:\.\d+)?\s*mm)", raw_item)
            std_name = f"Min ø {m_dia.group(1)}" if m_dia else "Min ø 3.5 mm"
        else:
            m_part = re.search(r"(Bolt\s*M\d+|Nut\s*M\d+)", raw_item, re.I)
            part_suffix = f" ({m_part.group(1)})" if m_part else ""
            item_name = f"Destructive Test{part_suffix}"
            std_name = raw_qty if raw_qty else "OK / NG"
        return {
            "item_no": str(seq),
            "inspection_item": item_name,
            "standard": std_name,
            "method": raw_tool if "Hammer" in raw_tool else "Destructive Test",
            "master_data": "",
            "measuring_position": ""
        }

    # 5. Appearance / Defects standardizations
    item_clean = raw_item
    std_clean = raw_qty if raw_qty else "OK / NG"

    if "SPATER" in item_u or "SPATTER" in item_u:
        item_clean = "Tidak Ada Spatter"
        std_clean = "OK / NG"
    elif "DEFORM" in item_u:
        item_clean = "Tidak Deform"
        std_clean = "OK / NG"
    elif "WRINKLE" in item_u:
        item_clean = "Tidak Wrinkle"
        std_clean = "OK / NG"
    elif "CRACK" in item_u:
        item_clean = "Tidak Crack"
        std_clean = "OK / NG"
    elif "NO RUST" in item_u:
        item_clean = "No Rust"
        std_clean = "OK / NG"
    elif "MISSING NUT" in item_u:
        item_clean = "No Missing Nut"
        std_clean = "OK / NG"
    elif "NUT NO REVERSED" in item_u or "REVERSED" in item_u:
        item_clean = "Nut No Reversed"
        std_clean = "OK / NG"
    elif "PEEL OFF" in item_u:
        item_clean = "Nut No Peel Off"
        std_clean = "OK / NG"
    elif "WRONG TYPE" in item_u:
        item_clean = "No Wrong Type Nut"
        std_clean = "OK / NG"
    elif "EASY TO ASSY" in item_u:
        item_clean = "Thread Easy to Assy"
        std_clean = "OK / NG"
    elif "NUT CENTER" in item_u:
        item_clean = "Nut Center"
        std_clean = "OK / NG"
    elif "BOLT CENTER" in item_u:
        item_clean = "Bolt Center"
        std_clean = "OK / NG"
    elif any(k in item_u for k in ["ULIT T/ SERET", "ULIR T/ SERET", "ULIR TIDAK SERET"]):
        item_clean = "Ulir Tidak Seret"
        std_clean = "OK / NG"
    elif any(k in item_u for k in ["ULIT T/ BLONG", "ULIR T/ BLONG", "ULIR TIDAK BLONG"]):
        item_clean = "Ulir Tidak Blong"
        std_clean = "OK / NG"
    elif any(k in item_u for k in ["ULIT T/ RUSAK", "ULIR T/ RUSAK", "ULIR TIDAK RUSAK"]):
        item_clean = "Ulir Tidak Rusak"
        std_clean = "OK / NG"
    elif "TOTAL KOMPONEN" in item_u:
        item_clean = "Total Komponen"
    elif "SPOT WELD" in item_u:
        item_clean = "Spot Weld"

    # Standardize qty format
    if raw_qty:
        m_q = re.search(r"(\d+)\s*(?:pcs|pc|titik)?", raw_qty, re.I)
        if m_q:
            unit = "Titik" if "titik" in raw_qty.lower() else "Pcs"
            std_clean = f"Qty : {m_q.group(1)} {unit}"

    return {
        "item_no": str(seq),
        "inspection_item": item_clean,
        "standard": std_clean,
        "method": raw_tool,
        "master_data": "",
        "measuring_position": ""
    }


def parse_ssw_sheet(ws) -> List[Dict[str, Any]]:
    points = []
    seq = 1
    for r in range(15, min(ws.max_row + 1, 50)):
        c1 = str(ws.cell(r, 1).value or "").strip()
        c2 = str(ws.cell(r, 2).value or "").strip()
        c3 = str(ws.cell(r, 3).value or "").strip()
        c6 = str(ws.cell(r, 6).value or "").strip()
        c7 = str(ws.cell(r, 7).value or "").strip()

        # End of Table 1 check
        if r > 20:
            if any(stop in c2.upper() for stop in ["JUMLAH PRODUKSI", "JUMLAH PROD", "CHECKED & VERIFIED", "INSPEKTOR", "DIPERIKSA"]):
                break
            if any(stop in c1.upper() for stop in ["JUMLAH PRODUKSI", "JUMLAH PROD", "INSPEKTOR", "DIPERIKSA"]):
                break
            if c2.upper() == "NO." or c3.upper() == "SPESIFIKASI":
                break

        if not c3 or any(h in c3.upper() for h in ["SPESIFIKASI", "TANGGAL CHECK", "TANGGAL"]):
            continue
        if c2 in ["*", "#"] and "SOP" in c3.upper():
            continue
        if "APPEARANCE" in c3.upper() and (not c2 or c2 == "#"):
            continue
        if "PERFORMANCE TEST" in c3.upper() and (not c2 or c2 == "#"):
            continue

        pt = parse_point_row(c2, c3, c6, c7, seq)
        points.append(pt)
        seq += 1

    return points


def collect_all_ssw_checksheets() -> List[Dict[str, Any]]:
    machine_parts = defaultdict(dict)

    for machine in sorted(os.listdir(FOLDER)):
        mpath = os.path.join(FOLDER, machine)
        if not os.path.isdir(mpath):
            continue

        files = [f for f in sorted(os.listdir(mpath)) if f.endswith(".xlsx") and not f.startswith("~$")]

        for f in files:
            if f.lower().startswith("copy of"):
                continue
            fp = os.path.join(mpath, f)
            mtime = os.path.getmtime(fp)

            try:
                wb = openpyxl.load_workbook(fp, data_only=True)
                for sn in wb.sheetnames:
                    if sn.lower() in ["sheet1", "sheet2", "sheet3"]:
                        continue
                    ws = wb[sn]
                    if ws.max_row < 20:
                        continue

                    pno = str(ws.cell(13, 3).value or "").lstrip(": ").strip()
                    pname = str(ws.cell(12, 3).value or "").lstrip(": ").strip()
                    proses = str(ws.cell(13, 13).value or "").lstrip(": ").strip()
                    model = str(ws.cell(14, 3).value or "").lstrip(": ").strip()
                    cust = str(ws.cell(13, 16).value or ws.cell(12, 16).value or "").lstrip(": ").strip()

                    if not pno or not pname:
                        continue

                    clean_pn = re.sub(r"[^A-Za-z0-9]", "", pno).upper()
                    info = {
                        "machine": machine,
                        "file": f,
                        "sheet": sn,
                        "full_path": fp,
                        "rel_path": os.path.relpath(fp, BASE_DIR),
                        "part_number": pno,
                        "clean_part_number": clean_pn,
                        "part_name": pname,
                        "proses": proses or "SPOT NUT",
                        "model": model or "-",
                        "customer": cust or "PT. MMKI",
                        "mtime": mtime,
                        "is_all": "all" in f.lower(),
                        "ws": ws
                    }

                    prev = machine_parts[machine].get(clean_pn)
                    if prev is None:
                        machine_parts[machine][clean_pn] = info
                    else:
                        if not info["is_all"] and (info["mtime"] > prev["mtime"]):
                            machine_parts[machine][clean_pn] = info
                        elif prev["is_all"] and not info["is_all"]:
                            machine_parts[machine][clean_pn] = info
            except Exception as e:
                print(f"Error {fp}: {e}")

    final_list = []
    for machine, parts in sorted(machine_parts.items()):
        for cpn, item in sorted(parts.items()):
            pts = parse_ssw_sheet(item["ws"])
            item["points"] = pts
            del item["ws"]
            final_list.append(item)

    return final_list


async def run_import(apply_mode: bool = False):
    print("=" * 80)
    print("SUMMIT BATCH IMPORT ENGINE: CHECKSHEET SSW A (11 MESIN)")
    print(f"Mode: {'>>> APPLY (MENYIMPAN KE SUPABASE POSTGRESQL) <<<' if apply_mode else 'DRY-RUN (PREVIEW ONLY)'}")
    print("=" * 80)

    checksheets = collect_all_ssw_checksheets()
    total_cs = len(checksheets)
    print(f"[*] Total checksheet unik yang ditemukan: {total_cs}")

    total_points = sum(len(c["points"]) for c in checksheets)
    print(f"[*] Total titik inspeksi: {total_points}")

    async with AsyncSessionLocal() as session:
        created_count = 0
        updated_count = 0
        total_pts_saved = 0

        for idx, item in enumerate(checksheets):
            assigned_op = OPERATORS[idx % len(OPERATORS)]
            pno = item["part_number"]
            cpn = item["clean_part_number"]
            pname = item["part_name"]
            machine = item["machine"]
            proses = item["proses"]
            model = item["model"]
            cust = item["customer"]
            rfp = f"{item['rel_path']}#{item['sheet']}"
            doc_no = f"IPQC SSW - {machine}"
            target_status = "Perlu Revisi Gambar"
            target_ket = f"IPQC SSW {proses} ({machine}) - Gambar drawing menunggu upload manual"

            # Check if this checksheet already exists in DB by raw_file_path or by (clean_part_number, doc_number)
            res = await session.execute(
                select(Checksheet).where(
                    (Checksheet.raw_file_path == rfp) |
                    ((Checksheet.clean_part_number == cpn) & (Checksheet.doc_number == doc_no) & (Checksheet.category == "SSW"))
                )
            )
            existing_cs = res.scalars().first()

            if apply_mode:
                if existing_cs:
                    cs = existing_cs
                    cs.part_number = pno
                    cs.clean_part_number = cpn
                    cs.part_name = pname
                    cs.model = model
                    cs.customer = cust
                    cs.doc_number = doc_no
                    cs.template_type = "IPQC SSW"
                    cs.category = "SSW"
                    cs.format = "daily"
                    cs.status = target_status
                    cs.keterangan = target_ket
                    cs.assigned_to = assigned_op["name"]
                    cs.assigned_user_id = assigned_op["id"]
                    cs.raw_file_path = rfp
                    await session.flush()
                    updated_count += 1
                else:
                    cs = Checksheet(
                        part_number=pno,
                        clean_part_number=cpn,
                        part_name=pname,
                        model=model,
                        customer=cust,
                        doc_number=doc_no,
                        template_type="IPQC SSW",
                        category="SSW",
                        format="daily",
                        status=target_status,
                        keterangan=target_ket,
                        assigned_to=assigned_op["name"],
                        assigned_user_id=assigned_op["id"],
                        raw_file_path=rfp,
                        is_part_available=True
                    )
                    session.add(cs)
                    await session.flush()
                    created_count += 1

                # Clean & insert inspection points
                await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
                for pt_idx, pt in enumerate(item["points"]):
                    ip = InspectionPoint(
                        checksheet_id=cs.id,
                        item_no=pt["item_no"],
                        inspection_item=pt["inspection_item"],
                        standard=pt["standard"],
                        method=pt["method"],
                        master_data="",
                        measuring_position="",
                        order_index=pt_idx
                    )
                    session.add(ip)

                # Images are uploaded manually by user
                await session.execute(delete(PartImage).where(PartImage.checksheet_id == cs.id))
                total_pts_saved += len(item["points"])

            # Console output progress
            if idx < 10 or idx % 10 == 0 or idx == total_cs - 1:
                print(f"  [{idx+1:2d}/{total_cs}] {machine:12s} | PN: {pno:16s} | {len(item['points']):2d} pts | Assign: {assigned_op['name']:6s} | {pname[:25]}")

        if apply_mode:
            log = ActivityLog(
                action="IMPORT_SSW_BATCH",
                operator="Antigravity System",
                status="SUCCESS",
                details=f"Imported {created_count} new + {updated_count} updated SSW checksheets ({total_pts_saved} points) across 11 machines into FaketoryHub",
                created_at=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
            print("\n" + "=" * 80)
            print("[✓] COMMIT SUKSES! Seluruh checksheet SSW berhasil disimpan ke Supabase Database.")
        else:
            print("\n" + "=" * 80)
            print("[*] DRY-RUN SELESAI. Tidak ada data yang diubah di database.")

        print(f"    - Checksheet Baru Dibuat    : {created_count if apply_mode else total_cs}")
        print(f"    - Checksheet Diperbarui     : {updated_count if apply_mode else 0}")
        print(f"    - Total Titik Inspeksi      : {total_pts_saved if apply_mode else total_points}")
        print(f"    - Status                    : 'Perlu Revisi Gambar' (Workflow: Perlu Dikerjakan / TODO)")
        print(f"    - Gambar Drawing            : Menunggu upload manual oleh operator/user")
        print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import SSW Checksheets")
    parser.add_argument("--apply", action="store_true", help="Apply changes to Supabase database")
    args = parser.parse_args()

    asyncio.run(run_import(apply_mode=args.apply))
