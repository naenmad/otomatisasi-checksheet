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
        if "mmki" in fp_lower or "ir child" in fp_lower or "monthly fg" in fp_lower:
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
        if not part_number:
            match = re.search(r"([0-9]{4,5}[A-Z0-9_-]{3,})", fname)
            if match:
                part_number = match.group(1)

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
            # Inspection pages in MMKI IR are typically named PAGE 6, PAGE 7... or HAL 1, HAL 2
            target_sheets = [s for s in wb.sheetnames if re.search(r"(PAGE\s*\d+|HAL\s*\d+|IR)", s, re.I)]
            if not target_sheets:
                target_sheets = [wb.sheetnames[0]]

            balloon_counter = 1
            for sname in target_sheets:
                ws = wb[sname]
                # Look for header row with standard MMKI column offsets
                for r in range(1, min(ws.max_row + 1, 150)):
                    # Check column 18/20/26 layout
                    val_no = str(ws.cell(r, 18).value or ws.cell(r, 2).value or "").strip()
                    val_item = str(ws.cell(r, 20).value or ws.cell(r, 4).value or "").strip()
                    val_std = str(ws.cell(r, 26).value or ws.cell(r, 8).value or "").strip()
                    val_method = str(ws.cell(r, 30).value or ws.cell(r, 12).value or "").strip()

                    if not val_item and not val_std:
                        continue

                    if any(header_text in val_item.upper() for header_text in ["ITEM", "STANDAR", "INSPECTION", "POINT"]):
                        continue

                    item_no_str = val_no if val_no else str(balloon_counter)
                    if val_no.isdigit():
                        balloon_counter = int(val_no) + 1
                    else:
                        balloon_counter += 1

                    all_points.append({
                        "item_no": item_no_str,
                        "inspection_item": " ".join(val_item.split()) if val_item else f"Point {balloon_counter}",
                        "standard": " ".join(val_std.split()) if val_std else "-",
                        "method": " ".join(val_method.split()) if val_method else "Visual",
                        "master_data": ""
                    })
        finally:
            if should_close:
                try:
                    wb.close()
                except Exception:
                    pass

        return all_points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        return extract_excel_images(file_path, output_dir=output_dir, part_number=part_number)
