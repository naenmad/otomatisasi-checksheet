"""
Subcontractor Checksheet Batch Importer
Processes all checksheets under 'documents/CS INCOMING/CS IQC SUBCONT/'
Extracts per-sheet metadata, inspection points, and isolated drawing sketches (including WDP and PNG).
Updates existing checksheets or inserts new ones, then synchronizes to Google Sheets.
"""
import os
import sys
import glob
import re
import asyncio
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import openpyxl
from sqlalchemy import select, text

from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, PartImage
from database.crud import create_checksheet
from services.parser_service import match_catalog_status
from services.google_sheets_service import sync_all_checksheets_to_sheet
from parsers.image_extractor import extract_sheet_images, extract_excel_images
from parsers.smart_parser import FuzzyToolNormalizer

# Files that are superseded or identical duplicates
EXCLUDED_SUBSTRINGS = [
    "Copy of CS subcont SIM.xlsx",
    "CS subcont SIM.xlsx",  # "CS subcont SIM (Autosaved).xlsx" has 60 sheets vs 58
    "campur/UPDATE IQC SHEET 3K6A (YOSKA - ANDON - NKP).xlsx",  # "Rev#1" is newer
    "IQC MATERIAL COIL TOYOTA.xlsx",  # identical duplicate of IQC COIL.xlsx
    "IQC MATERIAL SHEET TOYOTA.xlsx",  # identical duplicate of IQC SHEET.xlsx
    "c.sheet SL..xlsx",  # identical duplicate of c.sheet SL.xlsx
]

# Sheet names to ignore if empty or template
DUMMY_SHEETS = {"form", "template", "blank", "sheet1", "sheet2", "sheet3", "general", "bracket", " ", "checksheet pin"}


def clean_str(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", str(s)).upper()


def get_cell_value(matrix, r: int, c: int) -> str:
    if 0 <= r - 1 < len(matrix) and 0 <= c - 1 < len(matrix[r - 1]):
        v = matrix[r - 1][c - 1]
        if v is None:
            return ""
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return str(v).strip()
    return ""


def parse_subcont_sheet_meta(matrix, fp: str, sname: str) -> Dict[str, str]:
    fname = os.path.basename(fp)
    fplow = fp.lower()

    part_no = ""
    part_name = ""
    customer = "PT. SUMMIT"
    model = ""
    doc_no = "FO-45-01"

    # Default customer by folder structure
    if "ttmin" in fplow or "toyota" in fplow:
        customer = "PT. TMMIN"
    elif "iami" in fplow or "isuzu" in fplow:
        customer = "PT. IAMI"
    elif "hpm" in fplow or "honda" in fplow:
        customer = "PT. HPM"
    elif "nut" in fplow:
        customer = "PT. MMKI"
    elif "sim" in fplow and "mmki" not in fplow:
        customer = "PT. SIM"
    elif "mmki" in fplow and "sim" not in fplow:
        customer = "PT. MMKI"

    # Default model by filename patterns
    for m_cand in ["5H45", "5J45", "4L45V", "3M0A", "T86A", "3K6A", "YTB", "AMC", "TG4R", "2TG"]:
        if m_cand.lower() in fname.lower():
            model = m_cand
            break

    # Scan header cells (rows 1-22, cols 1-35)
    max_r = min(len(matrix), 25)
    max_c = min(len(matrix[0]) if matrix else 0, 35)

    for r in range(1, max_r + 1):
        for c in range(1, max_c + 1):
            val = get_cell_value(matrix, r, c)
            if not val:
                continue
            low = val.lower()

            if "customer" in low:
                cand = val.split(":", 1)[1].strip() if ":" in val else ""
                if not cand and c < max_c:
                    cv = get_cell_value(matrix, r, c + 1)
                    if cv:
                        cand = cv.strip(": ")
                if cand:
                    cand_u = cand.upper()
                    if "TOYOTA" in cand_u or "TMMIN" in cand_u:
                        customer = "PT. TMMIN"
                    elif "SIM" in cand_u or "SUZUKI" in cand_u:
                        customer = "PT. SIM"
                    elif "MMKI" in cand_u or "MITSUBISHI" in cand_u:
                        customer = "PT. MMKI"
                    elif "HPM" in cand_u or "HONDA" in cand_u:
                        customer = "PT. HPM"
                    elif "IAMI" in cand_u or "ISUZU" in cand_u:
                        customer = "PT. IAMI"

            if "model" in low and not model:
                cand = val.split(":", 1)[1].strip() if ":" in val else ""
                if not cand and c < max_c:
                    cv = get_cell_value(matrix, r, c + 1)
                    if cv:
                        cand = cv.strip(": ")
                if cand and len(cand) >= 2 and "model" not in cand.lower():
                    model = cand

            if "part name" in low and not part_name:
                cand = val.split(":", 1)[1].strip() if ":" in val else ""
                if not cand:
                    for dc in range(1, 4):
                        if c + dc <= max_c:
                            cv = get_cell_value(matrix, r, c + dc)
                            if len(cv) >= 2 and "part name" not in cv.lower():
                                cand = cv
                                break
                if cand:
                    cand = re.sub(r"Part\s*Name\s*:\s*", " ", cand, flags=re.I)
                    cand = " ".join(cand.split())
                    part_name = cand

            if "part no" in low and not part_no:
                cand = val.split(":", 1)[1].strip() if ":" in val else ""
                if not cand:
                    for dc in range(1, 4):
                        if c + dc <= max_c:
                            cv = get_cell_value(matrix, r, c + dc)
                            if len(cv) >= 4 and "part no" not in cv.lower() and cv != ":":
                                cand = cv
                                break
                if cand and len(cand) >= 4:
                    part_no = cand.strip()

    # Fallback for part number from sheetname
    if not part_no:
        clean_s = re.sub(r"\(.*?\)", "", sname).strip()
        clean_s = clean_s.rstrip(".").strip()
        if len(clean_s) >= 4 and any(ch.isalnum() for ch in clean_s):
            part_no = clean_s

    # Fallback for part name
    if not part_name:
        part_name = part_no

    if not model:
        model = "-"

    return {
        "part_number": part_no,
        "part_name": part_name,
        "customer": customer,
        "model": model,
        "doc_number": doc_no
    }


def parse_subcont_sheet_points(matrix) -> List[Dict[str, str]]:
    max_r = len(matrix)
    max_c = len(matrix[0]) if matrix else 0

    hdr_row = None
    c_no, c_item, c_std, c_tool = 1, 2, 3, 4

    for r in range(1, min(max_r + 1, 25)):
        row_vals = [get_cell_value(matrix, r, c).upper() for c in range(1, min(max_c + 1, 15))]
        has_no = any(v in ["NO", "NO.", "NO / ITEM", "ITEM"] for v in row_vals)
        has_insp = any("INSPECTION" in v for v in row_vals)
        has_std = any("STANDAR" in v or "LIMIT" in v for v in row_vals)
        if (has_no or has_insp) and has_std:
            hdr_row = r
            for c in range(1, min(max_c + 1, 15)):
                val = get_cell_value(matrix, r, c).upper()
                if val in ["NO", "NO."]:
                    c_no = c
                elif "INSPECTION" in val and "RESULT" not in val:
                    c_item = c
                elif "STANDAR" in val or "LIMIT" in val:
                    c_std = c
                elif "ALAT" in val or "TOOL" in val:
                    c_tool = c
            break

    if not hdr_row:
        return []

    points = []
    balloon_counter = 1
    last_item = ""
    consecutive_empty = 0

    FOOTER_KEYWORDS = ["conformity", "good for use", "reject to vendor", "dibuat", "diperiksa", "no.doc", "reason :"]

    for r in range(hdr_row + 1, min(max_r + 1, hdr_row + 50)):
        v_no = get_cell_value(matrix, r, c_no)
        v_item = get_cell_value(matrix, r, c_item)
        v_std = get_cell_value(matrix, r, c_std)
        v_tool = get_cell_value(matrix, r, c_tool)

        combined_lower = f"{v_no} {v_item} {v_std} {v_tool}".lower()
        if any(kw in combined_lower for kw in FOOTER_KEYWORDS):
            # Reached footer summary block, finish parsing points
            break

        if not v_item and not v_std:
            if len(points) > 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
            else:
                consecutive_empty += 1
                if consecutive_empty >= 8:
                    break
            continue

        consecutive_empty = 0

        # Skip subheader sample rows (e.g. date, qty without item context)
        item_upper = v_item.strip().upper()
        if item_upper in ["DATE", "DATE :", "QTY", "QTY :", "JUDG", "JUDGEMENT", "TOTAL", "OK", "NG"]:
            continue
        if item_upper.isdigit() and len(item_upper) <= 2 and not v_std:
            continue

        if not v_item and v_no and not v_no.isdigit():
            v_item = v_no
            v_no = ""

        if not v_item and last_item:
            v_item = last_item
        elif v_item:
            last_item = v_item

        item_no_str = v_no if (v_no and v_no.isdigit()) else str(balloon_counter)
        if v_no and v_no.isdigit():
            balloon_counter = int(v_no) + 1
        else:
            balloon_counter += 1

        points.append({
            "item_no": item_no_str,
            "inspection_item": " ".join(v_item.split()) if v_item else f"Point {balloon_counter}",
            "standard": " ".join(v_std.split()) if v_std else "-",
            "method": FuzzyToolNormalizer.normalize(v_tool) if v_tool else "Visual",
            "master_data": ""
        })

    return points


async def import_subcont_checksheets(dry_run: bool = False):
    """
    Main importer routine for CS IQC SUBCONT folder.
    """
    base_folder = "documents/CS INCOMING/CS IQC SUBCONT"
    all_files = glob.glob(f"{base_folder}/**/*.xlsx", recursive=True)
    all_files = [
        f for f in sorted(all_files)
        if not os.path.basename(f).startswith("~$")
        and not os.path.basename(f).startswith("._")
    ]

    # Filter out excluded duplicates
    valid_files = []
    for f in all_files:
        if any(f.endswith(ex) or ex in f for ex in EXCLUDED_SUBSTRINGS):
            continue
        valid_files.append(f)

    print(f"[*] Found {len(valid_files)} valid Excel files in {base_folder} (excluded {len(all_files) - len(valid_files)} duplicates).")

    async with AsyncSessionLocal() as session:
        # Pre-fetch existing checksheets
        res = await session.execute(text("SELECT id, clean_part_number, status, doc_number FROM checksheets"))
        existing_db = {row[1]: (row[0], row[2], row[3]) for row in res.fetchall()}
        print(f"[*] Existing checksheets in database: {len(existing_db)}")

        processed_parts = set()
        created_count = 0
        updated_count = 0
        total_images_saved = 0
        error_count = 0

        for f_idx, fp in enumerate(valid_files, 1):
            fname = os.path.basename(fp)
            try:
                import zipfile
                z_archive = zipfile.ZipFile(fp, "r") if zipfile.is_zipfile(fp) else None
                from parsers.image_extractor import get_workbook_sheet_drawing_map
                drawing_map = get_workbook_sheet_drawing_map(z_archive) if z_archive else {}

                wb = openpyxl.load_workbook(fp, data_only=True, read_only=True)
                file_parts = 0
                for sname in wb.sheetnames:
                    sname_clean = sname.strip().lower()
                    if sname_clean in DUMMY_SHEETS:
                        continue

                    ws = wb[sname]
                    matrix = list(ws.iter_rows(values_only=True, max_row=45, max_col=35))
                    meta = parse_subcont_sheet_meta(matrix, fp, sname)
                    part_no = meta["part_number"]
                    cpn = clean_str(part_no)

                    if not cpn or len(cpn) < 3 or cpn in DUMMY_SHEETS:
                        continue

                    # Extract points
                    pts = parse_subcont_sheet_points(matrix)

                    # Extract sheet-specific drawings
                    imgs = []
                    try:
                        d_target = drawing_map.get(sname_clean)
                        imgs = extract_sheet_images(fp, sheet_name=sname, part_number=part_no, z=z_archive, drawing_target=d_target)
                        if not imgs and len(wb.sheetnames) == 1:
                            imgs = extract_excel_images(fp, part_number=part_no)
                    except Exception as img_err:
                        print(f"    [!] Image extraction warning on {fname} [{sname}]: {img_err}", flush=True)

                    total_images_saved += len(imgs)
                    cat_match = match_catalog_status(part_no)

                    is_update = cpn in existing_db or cpn in processed_parts
                    processed_parts.add(cpn)

                    if not dry_run:
                        cs_record = await create_checksheet(
                            session=session,
                            part_number=part_no,
                            part_name=meta["part_name"],
                            model=meta["model"],
                            customer=meta["customer"],
                            doc_number=meta["doc_number"],
                            template_type="IQCSubcontParser",
                            status=cat_match["status"],
                            assigned_to="Unassigned",
                            keterangan=cat_match["keterangan"],
                            raw_file_path=fp,
                            points=pts,
                            images=imgs
                        )

                    if is_update:
                        updated_count += 1
                    else:
                        created_count += 1
                    file_parts += 1

                wb.close()
                if z_archive:
                    z_archive.close()

                if not dry_run and file_parts > 0:
                    await session.commit()

                print(f"[{f_idx}/{len(valid_files)}] {fname} -> {file_parts} parts (Total: New={created_count}, Upd={updated_count}, Imgs={total_images_saved})", flush=True)

            except Exception as e:
                error_count += 1
                print(f"[!] Error processing file {fname}: {e}", flush=True)

        print("\n" + "=" * 60)
        print(f"[+] Subcontractor Import Complete {'(DRY RUN)' if dry_run else ''}!")
        print(f"    Files Processed    : {len(valid_files)}")
        print(f"    New Checksheets    : {created_count}")
        print(f"    Updated Checksheets: {updated_count}")
        print(f"    Total Drawings     : {total_images_saved}")
        print(f"    Errors             : {error_count}")
        print("=" * 60)

        if not dry_run:
            print("\n[*] Starting automatic Google Sheets sync for all master data...")
            try:
                await sync_all_checksheets_to_sheet()
                print("[✓] Google Sheets synchronization finished successfully!")
            except Exception as e:
                print(f"[!] Warning: Google Sheets sync error: {e}")


if __name__ == "__main__":
    is_dry = "--dry-run" in sys.argv
    asyncio.run(import_subcont_checksheets(dry_run=is_dry))
