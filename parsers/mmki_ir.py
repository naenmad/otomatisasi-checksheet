"""
Parser for Mitsubishi Motors Krama Yudha Indonesia (MMKI) Inspection Reports (IR).
Handles multi-page IR reports (e.g. PAGE 6..11, IR CHILD PART, MONTHLY FG) with
standard columns for Item No (col 18), Item Name (col 20), Standard/Tolerance (col 26), and Method (col 30).
"""
import os
import re
from typing import Dict, List, Optional, Any
import openpyxl

from parsers.base import BaseParser
from parsers.image_extractor import extract_excel_images


def determine_measuring_position(item_name: str, standard: str) -> str:
    item_u = item_name.upper().strip()
    std_u = standard.upper().strip()

    # Rule 3: Hole Position -> Off Center
    if "HOLE POSITION" in item_u:
        return "Off Center"

    # Rule 2: Hole ... (except hole position), where standard has Ø or starts with dimension -> Hole Site
    if "HOLE" in item_u and "HOLE POSITION" not in item_u and "QTY" not in item_u and "PITCH" not in item_u:
        if "Ø" in std_u or re.match(r"^\d", std_u):
            return "Hole Site"

    # Rule 4: Shim -> Datum Surface
    if "SHIM" in item_u:
        return "Datum Surface"

    # Rule 5: Trimline -> Trimline
    if "TRIMLINE" in item_u or "TRIM LINE" in item_u or "TRIM" in item_u:
        return "Trimline"

    # Rule 6: Gap -> Surface
    if "GAP" in item_u:
        return "Surface"

    # Rule 7 & 8: Position (bukan Hole Position)
    if "POSITION" in item_u:
        clean_std = std_u.replace("DEV. WITHIN", "").replace("DEV.WITHIN", "").strip()
        if "DEV. WITHIN" in std_u or "DEV.WITHIN" in std_u or std_u.startswith("0") or clean_std.startswith("0"):
            return "Off Center"
        else:
            return "Surface"

    # Rule 9: Qty Spot -> Spot Welding
    if "SPOT" in item_u:
        return "Spot Welding"

    # Rule 10: Qty Hole -> Hole
    if "QTY HOLE" in item_u:
        return "Hole"

    # Rule 11: NUT -> Nut
    if "NUT" in item_u:
        return "Nut"

    # Rule 12: BOLT -> Bolt
    if "BOLT" in item_u:
        return "Bolt"

    # Rule 13: Identification Marking -> Marking
    if "IDENTIFICATION" in item_u or "MARKING" in item_u:
        return "Marking"

    return ""


class MMKIIRParser(BaseParser):
    """Parser dedicated to MMKI Inspection Report Checksheets."""

    def can_parse(self, file_path: str, wb: Optional[Any] = None) -> bool:
        if not file_path.lower().endswith((".xlsx", ".xls")):
            return False

        fp_lower = file_path.lower()
        if "mmki" in fp_lower or "ir child" in fp_lower or "monthly fg" in fp_lower or "final" in fp_lower:
            return True

        should_close = False
        if wb is None and file_path.lower().endswith(".xlsx"):
            try:
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                should_close = True
            except Exception:
                return False

        if wb is not None:
            try:
                sheet_names_upper = [s.upper() for s in wb.sheetnames]
                if any(s.startswith("PAGE") for s in sheet_names_upper):
                    if should_close:
                        wb.close()
                    return True

                ws = wb.active
                for r in range(1, min(ws.max_row or 10, 15)):
                    row_str = " ".join([str(ws.cell(r, c).value or "") for c in range(1, 15)]).upper()
                    if "MMKI" in row_str or "MITSUBISHI" in row_str:
                        if should_close:
                            wb.close()
                        return True
            except Exception:
                pass
            finally:
                if should_close:
                    try:
                        wb.close()
                    except Exception:
                        pass

        return False

    def extract_metadata(self, file_path: str, wb: Optional[Any] = None) -> Dict[str, str]:
        doc_number = "Form 1"
        part_number = ""
        part_name = ""
        model = "-"
        customer = "PT. MMKI"

        should_close = False
        if wb is None:
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True)
                should_close = True
            except Exception:
                wb = None

        if wb is not None:
            try:
                ws = wb.active
                for r in range(1, min(ws.max_row + 1, 15)):
                    for c in range(1, min(ws.max_column + 1, 30)):
                        val = str(ws.cell(r, c).value or "").strip()
                        val_upper = val.upper()

                        if "PART NO" in val_upper and not part_number:
                            if ":" in val:
                                part_number = val.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) > 5 and "PART" not in cval.upper():
                                        part_number = cval
                                        break

                        if "PART NAME" in val_upper and not part_name:
                            if ":" in val:
                                part_name = val.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) > 2 and "PART" not in cval.upper():
                                        part_name = cval
                                        break

                        if "MODEL" in val_upper and model == "-":
                            if ":" in val:
                                model = val.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 3):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) >= 2 and "MODEL" not in cval.upper():
                                        model = cval
                                        break

                        if any(k in val_upper for k in ["DOC NO", "NO DOKUMEN", "FORM"]):
                            if ":" in val:
                                doc_number = val.split(":", 1)[1].strip()
            finally:
                if should_close:
                    try:
                        wb.close()
                    except Exception:
                        pass

        # Fallback from filename
        fname = os.path.basename(file_path)
        match = re.search(r"([0-9A-Z]{4,5}[A-Z0-9]{3,4}[A-Z0-9])", fname)
        if match:
            fn_part = match.group(1).replace("_", "").strip()
            if not part_number:
                part_number = fn_part
            elif fn_part.endswith("P") and fn_part != part_number:
                part_number = fn_part

        if not part_name or len(part_name) < 3:
            name_cand = os.path.splitext(fname)[0]
            if "_" in name_cand:
                pname = name_cand.split("_", 1)[1].strip()
                pname = re.sub(r"[-\s_]*#?Rev.*$", "", pname, flags=re.I).strip()
                if pname:
                    part_name = pname

        return {
            "part_number": part_number,
            "part_name": part_name,
            "model": model or "-",
            "customer": customer,
            "doc_number": doc_number,
            "filename": fname
        }

    def extract_inspection_points(self, file_path: str, wb: Optional[Any] = None) -> List[Dict[str, str]]:
        should_close = False
        if wb is None:
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True)
                should_close = True
            except Exception:
                return []

        all_points = []
        try:
            # 1. First, search for Appearance and Burr criteria (typically PAGE 4)
            appearance_found = False
            for sname in wb.sheetnames:
                ws = wb[sname]
                for r in range(1, min(ws.max_row + 1, 15)):
                    row_text = " ".join(str(ws.cell(r, c).value or "") for c in range(1, 10)).upper()
                    if "SURFACE SHOULD BE FREE FROM" in row_text or ("APPEARANCE" in row_text and "CRACK" in row_text):
                        for ar in range(r, min(r + 8, ws.max_row + 1)):
                            txt = str(ws.cell(ar, 1).value or ws.cell(ar, 2).value or "").strip()
                            txt_u = txt.upper()
                            if "SURFACE SHOULD BE FREE" in txt_u or ("CRACK" in txt_u and "SCRATCH" in txt_u):
                                clean_std = "Free From Crack, Wrinkle, Necking, Scratch, Dent, Rust, Spatter"
                                all_points.append({
                                    "item_no": "1",
                                    "inspection_item": "Appearance",
                                    "measuring_position": "",
                                    "standard": clean_std,
                                    "method": "Visual",
                                    "master_data": ""
                                })
                                appearance_found = True
                            elif "BURR" in txt_u:
                                all_points.append({
                                    "item_no": "2",
                                    "inspection_item": "Burry",
                                    "measuring_position": "",
                                    "standard": "≤ 0.3 mm",
                                    "method": "Caliper",
                                    "master_data": ""
                                })
                        break
                if appearance_found:
                    break

            # 2. Extract dimensional inspection tables from report pages (PAGE 6, PAGE 7, etc.)
            target_sheets = [s for s in wb.sheetnames if re.search(r"(PAGE\s*\d+|HAL\s*\d+|IR)", s, re.I)]
            if not target_sheets:
                target_sheets = [wb.sheetnames[0]]

            current_balloon = 1
            for sname in target_sheets:
                ws = wb[sname]
                hdr_row = None
                for r in range(1, min(ws.max_row + 1, 15)):
                    row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, 12)]
                    if any("INSPECTION ITEM" in v for v in row_vals) and any("STANDARD" in v for v in row_vals):
                        hdr_row = r
                        break

                if not hdr_row:
                    continue

                last_item_name = ""
                r = hdr_row + 2
                while r <= ws.max_row:
                    col2 = ws.cell(r, 2).value
                    col3 = ws.cell(r, 3).value
                    col4 = ws.cell(r, 4).value
                    col5 = ws.cell(r, 5).value
                    col6 = ws.cell(r, 6).value

                    c3_str = str(col3 or "").strip()
                    if any(k in c3_str.upper() for k in ["JUDGEMENT", "TOTAL POINT", "MMKI"]):
                        break
                    if col2 is None and col3 is None and col4 is None and col5 is None and col6 is None:
                        r += 1
                        continue

                    c2_str = str(col2 or "").strip()
                    if c2_str and c2_str.isdigit():
                        current_balloon = int(c2_str)

                    v_item = c3_str
                    v_coord = str(col4 or "").strip()
                    v_nom = col5
                    v_tol = str(col6 or "").strip()

                    # Skip redundant sub-row "OK / NG" without item name (e.g. right under INSERT PIN DATUM)
                    if not v_item and str(v_nom or "").strip() in ("OK / NG", "OK/NG"):
                        r += 1
                        continue

                    # Merge stacked tolerances (e.g. + 0.3 on row r and - 0 on row r+1)
                    next_col6 = str(ws.cell(r + 1, 6).value or "").strip() if r + 1 <= ws.max_row else ""
                    skip_next = False
                    if v_tol and next_col6 and (next_col6 == "0" or next_col6.startswith("-") or next_col6.startswith("+")):
                        v_tol = f"{v_tol} / {next_col6}"
                        skip_next = True

                    item_name = v_item if v_item else last_item_name
                    if v_item:
                        last_item_name = v_item

                    # Check sub-row r+1 for continuation of item name or coordinate
                    sub_col3 = str(ws.cell(r + 1, 3).value or "").strip() if r + 1 <= ws.max_row else ""
                    if sub_col3 and sub_col3 not in ("OK / NG", "OK/NG") and not any(k in sub_col3.upper() for k in ["JUDGMENT", "MMKI"]):
                        item_name = f"{item_name} {sub_col3}".strip()

                    sub_col4 = str(ws.cell(r + 1, 4).value or "").strip() if r + 1 <= ws.max_row else ""
                    if sub_col4 and not v_coord:
                        v_coord = sub_col4

                    # Keep coordinate tags [TL], [WL], [BL] in inspection_item
                    coord_str = ""
                    if v_coord:
                        clean_c = v_coord.strip("[] ").strip()
                        if clean_c:
                            coord_str = clean_c

                    if item_name and "[" in item_name and "]" in item_name:
                        coord_match = re.search(r"\[\s*([A-Za-z0-9,\s]+)\s*\]", item_name)
                        if coord_match:
                            if not coord_str:
                                coord_str = coord_match.group(1).strip()
                            item_name = re.sub(r"\[\s*[A-Za-z0-9,\s]+\s*\]", "", item_name).strip()

                    if coord_str:
                        item_name = f"{item_name} [{coord_str}]".strip()

                    nom_str = str(v_nom).strip() if v_nom is not None else ""
                    if nom_str.endswith(".0") and nom_str[:-2].isdigit():
                        nom_str = nom_str[:-2]

                    was_insert_pin = "INSERT PIN" in nom_str.upper() or "DATUM PIN" in nom_str.upper() or "INSERT PIN" in item_name.upper()

                    if v_tol and v_tol not in nom_str:
                        if nom_str and not nom_str.upper().startswith("INSERT PIN") and "OK" not in nom_str.upper():
                            full_std = f"{nom_str} {v_tol}".strip()
                        elif not nom_str:
                            full_std = v_tol
                        else:
                            full_std = nom_str
                    else:
                        full_std = nom_str

                    if was_insert_pin:
                        full_std = "OK / NG"

                    if not item_name or not full_std:
                        r += (2 if skip_next else 1)
                        continue

                    measuring_pos = ""

                    # Standardize method according to QC standards
                    m_upper = f"{item_name} {full_std}".upper()
                    std_upper = full_std.upper()
                    item_upper = item_name.upper()

                    if was_insert_pin or "INSERT PIN" in m_upper or "DATUM PIN" in m_upper or "GUIDE DIAMOND PIN" in m_upper or "GUIDE ROUND PIN" in m_upper:
                        method = "Insert Pin Datum"
                    elif "MARKING CTR LINE" in std_upper or "MARK CTR LINE" in std_upper or "CTR LINE" in std_upper:
                        method = "Marking Ctr Line"
                    elif ("IDENTIFICATION" in item_upper or "IDENTIFICATON" in item_upper) and not ("HOLE" in item_upper or "Ø" in std_upper):
                        method = "Visual"
                    elif "TRIM" in item_upper or "TRIM" in std_upper:
                        if "HOLE" in item_upper or "Ø" in std_upper or "Ø" in item_upper:
                            method = "Caliper"
                        else:
                            method = "Steel Ruler"
                    elif "SHIM" in item_upper or "SHIM" in std_upper:
                        if "HOLE" in item_upper or "Ø" in std_upper or "Ø" in item_upper:
                            method = "Caliper"
                        else:
                            method = "Feeler Gauge"
                    elif "INSERT PIN" in m_upper or "DATUM PIN" in m_upper or "GUIDE DIAMOND PIN" in m_upper or "GUIDE ROUND PIN" in m_upper:
                        method = "Insert Pin Datum"
                    elif "GAP" in m_upper or "TAPPER" in m_upper:
                        method = "Tapper Gg"
                    elif "BOLT" in m_upper or "NUT WELD" in m_upper or "THREAD" in m_upper:
                        method = "Bolt"
                    elif "Ø" in m_upper or "HOLE" in m_upper:
                        method = "Caliper"
                    else:
                        method = "Caliper"

                    all_points.append({
                        "item_no": str(current_balloon),
                        "inspection_item": " ".join(item_name.split()),
                        "measuring_position": measuring_pos,
                        "standard": " ".join(full_std.split()),
                        "method": method,
                        "master_data": ""
                    })

                    r += (2 if skip_next else 1)
        finally:
            if should_close:
                try:
                    wb.close()
                except Exception:
                    pass

        return all_points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        return extract_excel_images(file_path, output_dir=output_dir, part_number=part_number)
