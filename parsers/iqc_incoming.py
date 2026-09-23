"""
Parser for Incoming Quality Control (IQC) / Raw Material Checksheets (e.g. HPM, SSW).
Handles material specification, dimensions (thickness, length, width), appearance,
and conformity / non-conformity judgement rows.
"""
import os
import re
from typing import Dict, List, Optional, Any
import openpyxl

from parsers.base import BaseParser
from parsers.image_extractor import extract_excel_images


class IQCIncomingParser(BaseParser):
    """Parser dedicated to Incoming Material Checksheets."""

    def can_parse(self, file_path: str, wb: Optional[Any] = None) -> bool:
        if not file_path.lower().endswith((".xlsx", ".xls")):
            return False

        # Quick check filename/path clues
        fp_lower = file_path.lower()
        if "cs iqc" in fp_lower or "cs incoming" in fp_lower or "iqc" in fp_lower:
            return True

        # Inspect workbook sheet headers
        should_close = False
        if wb is None and file_path.lower().endswith(".xlsx"):
            try:
                wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
                should_close = True
            except Exception:
                return False

        if wb is not None:
            try:
                for sheetname in wb.sheetnames[:3]:
                    ws = wb[sheetname]
                    for r in range(1, min(ws.max_row or 15, 20)):
                        row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, 15)]
                        if any("INSPECTION" in v for v in row_vals) and any("STANDAR" in v or "LIMIT" in v for v in row_vals):
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
        model = ""
        customer = "PT. HPM"

        should_close = False
        if wb is None:
            try:
                wb = openpyxl.load_workbook(file_path, data_only=True)
                should_close = True
            except Exception:
                wb = None

        if wb is not None:
            try:
                # Find best sheet
                ws = wb.active
                for sname in wb.sheetnames:
                    if "(rev)" in sname.lower() or "rev" in sname.lower():
                        ws = wb[sname]
                        break

                for r in range(1, min(ws.max_row + 1, 16)):
                    for c in range(1, min(ws.max_column + 1, 26)):
                        val = str(ws.cell(r, c).value or "").strip()
                        val_lower = val.lower()

                        if "part no" in val_lower and not part_number:
                            if ":" in val:
                                p = val.split(":", 1)[1].strip()
                                if len(p) > 5:
                                    part_number = p
                            if not part_number:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) > 5 and "part no" not in cval.lower():
                                        part_number = cval
                                        break

                        if "part name" in val_lower and not part_name:
                            if ":" in val:
                                p = val.split(":", 1)[1].strip()
                                if len(p) > 2:
                                    part_name = p
                            if not part_name:
                                for dc in range(1, 4):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) > 2 and "part name" not in cval.lower():
                                        part_name = cval
                                        break

                        if "model" in val_lower and not model:
                            if ":" in val:
                                m = val.split(":", 1)[1].strip()
                                if len(m) >= 2:
                                    model = m
                            if not model:
                                for dc in range(1, 3):
                                    cval = str(ws.cell(r, c + dc).value or "").strip()
                                    if len(cval) >= 2 and "model" not in cval.lower():
                                        model = cval
                                        break

                        if "no.doc" in val_lower or "doc. no" in val_lower or "no dokumen" in val_lower:
                            if ":" in val:
                                d = val.split(":", 1)[1].strip()
                                if len(d) >= 3:
                                    doc_number = d
            finally:
                if should_close:
                    try:
                        wb.close()
                    except Exception:
                        pass

        # Fallback from filename / folder path
        fname = os.path.basename(file_path)
        if not part_number:
            clean_fn = re.sub(r"^(CS\s*IQC\s*)", "", fname, flags=re.I)
            clean_fn = os.path.splitext(clean_fn)[0].strip()
            if len(clean_fn) >= 6:
                part_number = clean_fn

        if not model:
            parent_dir = os.path.basename(os.path.dirname(file_path))
            if parent_dir and any(c.isalnum() for c in parent_dir):
                model = parent_dir.split(" ")[0].strip("()")

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
            # Prefer active sheet or first sheet with inspection table
            sheets_to_try = wb.sheetnames
            for sname in sheets_to_try:
                ws = wb[sname]
                hdr_row = None
                c_no, c_item, c_std, c_tool = 1, 2, 3, 4

                for r in range(1, min(ws.max_row + 1, 25)):
                    row_vals = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, 15)]
                    has_no = any(v in ["NO", "NO.", "NO / ITEM"] for v in row_vals)
                    has_insp = any("INSPECTION" in v for v in row_vals)
                    has_std = any("STANDAR" in v or "LIMIT" in v for v in row_vals)
                    if (has_no or has_insp) and has_std:
                        hdr_row = r
                        for c in range(1, 15):
                            val = str(ws.cell(r, c).value or "").strip().upper()
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
                    continue

                balloon_counter = 1
                last_item = ""
                sheet_points = []

                for r in range(hdr_row + 1, min(ws.max_row + 1, hdr_row + 35)):
                    v_no = str(ws.cell(r, c_no).value or "").strip()
                    v_item = str(ws.cell(r, c_item).value or "").strip()
                    v_std = str(ws.cell(r, c_std).value or "").strip()
                    v_tool = str(ws.cell(r, c_tool).value or "").strip()

                    # Skip empty rows or inspection result subheaders
                    if not v_item and not v_std:
                        continue
                    if any(skip in v_item.upper() for skip in ["DATE", "QTY", "JUDG", "JUDGEMENT"]):
                        continue
                    if v_item.isdigit() and len(v_item) <= 2:
                        continue

                    if not v_item and v_no and not v_no.isdigit():
                        v_item = v_no
                        v_no = ""

                    # Inherit from last_item for merged rows (e.g. Conformity)
                    if not v_item and last_item:
                        v_item = last_item
                    elif v_item:
                        last_item = v_item

                    item_no_str = v_no if v_no else str(balloon_counter)
                    if v_no and v_no.isdigit():
                        balloon_counter = int(v_no) + 1
                    else:
                        balloon_counter += 1

                    sheet_points.append({
                        "item_no": item_no_str,
                        "inspection_item": " ".join(v_item.split()) if v_item else f"Point {balloon_counter}",
                        "standard": " ".join(v_std.split()) if v_std else "-",
                        "method": " ".join(v_tool.split()) if v_tool else "Visual",
                        "master_data": ""
                    })

                if sheet_points:
                    all_points.extend(sheet_points)
                    break  # Found the primary IQC table

        finally:
            if should_close:
                try:
                    wb.close()
                except Exception:
                    pass

        return all_points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        return extract_excel_images(file_path, output_dir=output_dir, part_number=part_number)
