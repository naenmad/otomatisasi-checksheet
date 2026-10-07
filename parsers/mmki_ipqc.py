"""
Parser for In-Process Quality Control (IPQC) checksheets.
Handles Appearance and Dimension multi-page inspection tables, datum markers,
and merges two-row upper/lower tolerances into canonical format (e.g. '0 + 0.3 / - 0').
"""
import os
import re
from typing import Dict, List, Optional, Any
import openpyxl

from parsers.base import BaseParser
from parsers.image_extractor import extract_excel_images


class MMKIIPQCParser(BaseParser):
    """Parser dedicated to In-Process Quality Control (IPQC) Checksheets."""

    def can_parse(self, file_path: str, wb: Optional[Any] = None) -> bool:
        if not file_path.lower().endswith((".xlsx", ".xls")):
            return False

        fp_lower = file_path.lower()
        if "ipqc" in fp_lower or "ipq" in fp_lower:
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
                for sname in wb.sheetnames[:5]:
                    ws = wb[sname]
                    for r in range(1, min(ws.max_row or 30, 40)):
                        c_val = str(ws.cell(r, 3).value or "").strip().upper()
                        h_val = str(ws.cell(r, 8).value or "").strip().upper()
                        if ("APPEARANCE" in c_val or "DIMENSION" in c_val) and ("STANDARD" in h_val or "METHOD" in h_val):
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
                # Find target operational sheet (prefer numbered sheets '1', '2', etc., ignore 'Master')
                valid_sheets = [s for s in wb.sheetnames if s.strip().isdigit()]
                if not valid_sheets:
                    valid_sheets = [s for s in wb.sheetnames if s.strip().lower() not in ["master", "cover"]]
                target_sheet = valid_sheets[0] if valid_sheets else wb.sheetnames[0]
                ws = wb[target_sheet]

                for r in range(1, min(ws.max_row + 1, 25)):
                    for c in range(1, min(ws.max_column + 1, 35)):
                        v = str(ws.cell(r, c).value or "").strip()
                        v_u = v.upper()
                        if any(k in v_u for k in ["PART NO", "NO. PART", "NO PART", "PART NUMBER"]) and not part_number:
                            if ":" in v:
                                part_number = v.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip().lstrip(": ")
                                    if len(cval) >= 4 and not any(k in cval.upper() for k in ["PART", "NO"]):
                                        part_number = cval
                                        break
                        if any(k in v_u for k in ["PART NAME", "NAMA PART", "NAME"]) and not part_name:
                            if ":" in v:
                                part_name = v.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip().lstrip(": ")
                                    if len(cval) >= 2 and not any(k in cval.upper() for k in ["PART", "NAMA"]):
                                        part_name = cval
                                        break
                        if "MODEL" in v_u and model == "-":
                            if ":" in v:
                                model = v.split(":", 1)[1].strip()
                            else:
                                for dc in range(1, 3):
                                    cval = str(ws.cell(r, c + dc).value or "").strip().lstrip(": ")
                                    if len(cval) >= 2 and "MODEL" not in cval.upper():
                                        model = cval
                                        break
            finally:
                if should_close:
                    try:
                        wb.close()
                    except Exception:
                        pass

        fname = os.path.basename(file_path)
        match = re.search(r"([0-9A-Z]{4,5}[A-Z0-9_-]{3,})", fname)
        if match:
            fn_part = match.group(1).replace("_", "").strip()
            if not part_number or len(part_number) < 5 or part_number.startswith("5251D"):
                part_number = fn_part
            elif fn_part.endswith("P") and fn_part != part_number:
                part_number = fn_part
                if "LH" in fname.upper() or fn_part[-4] in ["1", "3", "5", "7", "9"]:
                    part_name = part_name.replace("RH", "LH")
                elif "RH" in fname.upper() or fn_part[-4] in ["0", "2", "4", "6", "8"]:
                    part_name = part_name.replace("LH", "RH")

        return {
            "part_number": part_number,
            "part_name": part_name,
            "model": model,
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
            # Strictly filter out 'Master' template sheet which contains legacy parts (e.g. 5251D445)
            valid_sheets = [s for s in wb.sheetnames if s.strip().isdigit()]
            if not valid_sheets:
                valid_sheets = [s for s in wb.sheetnames if s.strip().lower() not in ["master", "cover"]]

            item_seq = 1
            for sname in valid_sheets:
                ws = wb[sname]
                current_sec = ""
                r = 1
                while r <= ws.max_row:
                    b_val = str(ws.cell(r, 2).value or "").strip()
                    c_val = str(ws.cell(r, 3).value or "").strip()
                    h_val = str(ws.cell(r, 8).value or "").strip()
                    i_val = str(ws.cell(r, 9).value or "").strip()
                    j_val = str(ws.cell(r, 10).value or "").strip()
                    l_val = str(ws.cell(r, 12).value or "").strip()

                    c_u = c_val.upper()
                    if not current_sec and "APPEARANCE" in c_u and not any(x in c_u for x in ["(+", "BURRY", "CRACK"]):
                        current_sec = "A"
                        r += 1
                        continue
                    elif "DIMENSION" in c_u:
                        current_sec = "B"
                        r += 1
                        continue
                    elif any(k in c_u for k in ["JUDGEMENT", "JML. PROD."]):
                        break

                    if not current_sec:
                        r += 1
                        continue
                    if any(k in c_u for k in ["SPESIFIKASI", "WAKTU PENGECEKAN", "AWAL PROSES"]):
                        r += 1
                        continue
                    if not c_val:
                        r += 1
                        continue

                    if current_sec == "A":
                        std_val = h_val or i_val or "OK / NG"
                        mth_val = l_val or "Visual"
                        if "MATA" in mth_val.upper() or "VISUAL" in mth_val.upper():
                            mth_val = "Visual"
                        elif "CALIPER" in mth_val.upper() or "CAIPER" in mth_val.upper():
                            mth_val = "Caliper"

                        ino = b_val if b_val.isdigit() else str(item_seq)
                        item_seq += 1
                        all_points.append({
                            "item_no": ino,
                            "inspection_item": " ".join(c_val.split()),
                            "standard": " ".join(std_val.split()),
                            "method": mth_val,
                            "master_data": ""
                        })
                        r += 1
                    elif current_sec == "B":
                        nom = i_val or h_val
                        tol = j_val
                        next_j = str(ws.cell(r + 1, 10).value or "").strip() if r + 1 <= ws.max_row else ""
                        skip = False
                        if tol and next_j and (next_j.startswith("-") or next_j.startswith("+") or next_j == "0"):
                            tol = f"{tol} / {next_j}"
                            skip = True
                        full_std = f"{nom} {tol}".strip() if tol and tol not in nom else (nom or "OK / NG")

                        mth_val = l_val or "Caliper"
                        m_u = mth_val.upper()
                        if "PIN GO" in m_u:
                            mth_val = "Pin Go/No Go"
                        elif "PIN" in m_u:
                            mth_val = "Insert Pin Datum"
                        elif "FEELER" in m_u or "SHIM" in c_u:
                            mth_val = "Feeler Gg"
                        elif "TAPPER" in m_u or "GAP" in c_u:
                            mth_val = "Tapper Gg"
                        elif "STEEL" in m_u or "TRIM" in c_u:
                            mth_val = "Steelrule"
                        elif "CALIPER" in m_u or "CAIPER" in m_u or "THICKNESS" in c_u:
                            mth_val = "Caliper"
                        elif "VISUAL" in m_u or "MATA" in m_u:
                            mth_val = "Visual"

                        ino = b_val if b_val.isdigit() else str(item_seq)
                        item_seq += 1
                        all_points.append({
                            "item_no": ino,
                            "inspection_item": " ".join(c_val.split()),
                            "standard": " ".join(full_std.split()),
                            "method": mth_val,
                            "master_data": ""
                        })
                        r += (2 if skip else 1)
        finally:
            if should_close:
                try:
                    wb.close()
                except Exception:
                    pass

        return all_points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        return extract_excel_images(file_path, output_dir=output_dir, part_number=part_number)
