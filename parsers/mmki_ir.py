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
                pname = re.sub(r"[\s-_]*#?Rev.*$", "", pname, flags=re.I).strip()
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
            balloon_counter = 1

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
                                clean_std = re.sub(r"^.*?SURFACE SHOULD BE FREE FROM\s*[,:]?\s*", "", txt, flags=re.I).strip(" :,.")
                                all_points.append({
                                    "item_no": str(balloon_counter),
                                    "inspection_item": "Appearance",
                                    "standard": clean_std if clean_std else txt,
                                    "method": "Visual",
                                    "master_data": ""
                                })
                                balloon_counter += 1
                                appearance_found = True
                            elif "BURR" in txt_u:
                                all_points.append({
                                    "item_no": str(balloon_counter),
                                    "inspection_item": "Burry",
                                    "standard": "≤ 0.3 mm",
                                    "method": "Caliper",
                                    "master_data": ""
                                })
                                balloon_counter += 1
                        break
                if appearance_found:
                    break

            # 2. Extract dimensional inspection tables from report pages
            target_sheets = [s for s in wb.sheetnames if re.search(r"(PAGE\s*\d+|HAL\s*\d+|IR)", s, re.I)]
            if not target_sheets:
                target_sheets = [wb.sheetnames[0]]

            for sname in target_sheets:
                ws = wb[sname]
                hdr_row = None
                c_item, c_std, c_tol = 3, 5, 6

                for r in range(1, min(ws.max_row + 1, 15)):
                    row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, 12)]
                    if any("INSPECTION ITEM" in v for v in row_vals) and any("STANDARD" in v for v in row_vals):
                        hdr_row = r
                        for c in range(1, 12):
                            v = row_vals[c - 1]
                            if "INSPECTION ITEM" in v:
                                c_item = c
                            elif "STANDARD" in v:
                                c_std = c
                                c_tol = c + 1
                        break

                if not hdr_row:
                    # Check alternate layout where table is offset to the right (cols 15-35)
                    for r in range(1, min(ws.max_row + 1, 20)):
                        row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(15, min(ws.max_column + 1, 35))]
                        if any("INSPECT" in v for v in row_vals) and any("STANDAR" in v for v in row_vals):
                            hdr_row = r
                            for c in range(15, min(ws.max_column + 1, 35)):
                                v = str(ws.cell(r, c).value or "").strip().upper()
                                if "INSPECT" in v:
                                    c_item = c
                                elif "STANDAR" in v:
                                    c_std = c
                                    c_tol = c + 1
                            break

                if not hdr_row:
                    # This sheet does not contain an inspection data table (e.g. sketch or history page)
                    continue

                # Standard MMKI IR Table reader
                prev_pt = None
                last_item_name = ""

                c_no = (c_item - 1) if c_item > 2 else 2
                for r in range(hdr_row + 2, min(ws.max_row + 1, 150)):
                    v_no = str(ws.cell(r, c_no).value or ws.cell(r, 2).value or ws.cell(r, 1).value or "").strip()
                    v_item = str(ws.cell(r, c_item).value or "").strip()
                    v_loc = str(ws.cell(r, c_item + 1).value or "").strip()
                    v_std = str(ws.cell(r, c_std).value or "").strip()
                    v_tol = str(ws.cell(r, c_tol).value or "").strip()

                    row_all = f"{v_no} {v_item} {v_loc} {v_std} {v_tol}".upper()
                    if "NOTE:" in row_all or "TOTAL" in row_all:
                        continue
                    if not v_item and not v_std and not v_loc and not v_tol:
                        continue

                    # Continuation row (tolerance lower limit or sub-view)
                    if not v_std and not v_item and prev_pt:
                        if v_tol and v_tol not in prev_pt["standard"]:
                            prev_pt["standard"] = f"{prev_pt['standard']}/{v_tol}".strip()
                        if v_loc and v_loc not in prev_pt["inspection_item"]:
                            prev_pt["inspection_item"] = f"{prev_pt['inspection_item']} {v_loc}".strip()
                        continue

                    # Sub-judgment (e.g. OK/NG under INSERT PIN DATUM)
                    if not v_item and v_std in ("OK / NG", "OK/NG") and prev_pt:
                        continue

                    full_std = v_std
                    if v_tol and v_tol not in full_std:
                        full_std = f"{full_std} {v_tol}".strip()

                    item_title = v_item if v_item else last_item_name
                    if v_loc:
                        item_title = f"{item_title} {v_loc}".strip()
                    if v_item:
                        last_item_name = v_item

                    if not full_std:
                        continue

                    # Determine method
                    full_upper = f"{item_title} {full_std}".upper()
                    if "INSERT PIN" in full_upper or "DATUM PIN" in full_upper:
                        method = "Insert Pin Datum"
                    elif "Ø" in full_upper or "HOLE" in full_upper or "DIAMETER" in full_upper:
                        method = "Caliper"
                    elif "TRIM" in full_upper or "GAP" in full_upper or "STEP" in full_upper:
                        method = "Tapper Gg"
                    elif "BOLT" in full_upper or "NUT" in full_upper or "TORQUE" in full_upper:
                        method = "Bolt"
                    elif "THICKNESS" in full_upper:
                        method = "Micrometer"
                    else:
                        method = "Caliper"

                    ino = v_no if (v_no and v_no.isdigit()) else str(balloon_counter)
                    if v_no and v_no.isdigit():
                        balloon_counter = int(v_no) + 1
                    else:
                        balloon_counter += 1

                    cur_pt = {
                        "item_no": ino,
                        "inspection_item": " ".join(item_title.split()),
                        "standard": " ".join(full_std.split()),
                        "method": method,
                        "master_data": ""
                    }
                    all_points.append(cur_pt)
                    prev_pt = cur_pt
        finally:
            if should_close:
                try:
                    wb.close()
                except Exception:
                    pass

        return all_points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        return extract_excel_images(file_path, output_dir=output_dir, part_number=part_number)
