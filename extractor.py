"""
Excel Extractor for Checksheet Master Automation
Extracts:
- Part Number, Part Name, Doc Number, Model
- Reference Images (Machine/Part Drawings from PAGE 4 & PAGE 5)
- Inspection Points starting directly from PAGE 6 to PAGE 9
  (NO sequential 1, 2, 3..., blank method, blank master data)
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Any
import openpyxl

def extract_metadata(file_path: str) -> Dict[str, str]:
    """Extract metadata from file name and cover sheet."""
    filename = os.path.basename(file_path)
    
    # Extract Doc Number from filename prefix (e.g. '6. IR - ...' -> 'Form 6')
    doc_number = "Form 1"
    doc_match = re.match(r"^(\d+)", filename)
    if doc_match:
        doc_number = f"Form {doc_match.group(1)}"
    
    # Extract Part Number from filename (e.g. '51138E000P', '75511B040P', '58336-BZ130')
    part_number = ""
    tokens = re.split(r"[^0-9A-Za-z\-]+", filename)
    for t in tokens:
        if any(c.isdigit() for c in t) and len(t) >= 6 and not t.lower().startswith("form"):
            part_number = t.upper()
            break
        
    part_name = ""
    model = ""
    
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        # Find cover sheet (e.g. 'New cover', 'Cover', or first sheet)
        cover_sheet = None
        for s in wb.sheetnames:
            if "cover" in s.lower():
                cover_sheet = wb[s]
                break
        if cover_sheet is None and len(wb.sheetnames) > 0:
            cover_sheet = wb[wb.sheetnames[0]]

        if cover_sheet:
            for r in range(1, 30):
                for c in range(1, 20):
                    val = str(cover_sheet.cell(r, c).value or "").strip()
                    if "part no" in val.lower():
                        # check next cells in row
                        for offset in [1, 2, 3, 4, 18 - c]:
                            target_c = c + offset
                            if 1 <= target_c <= cover_sheet.max_column:
                                p_val = str(cover_sheet.cell(r, target_c).value or "").strip()
                                if p_val and p_val != ":" and len(p_val) >= 5 and not part_number:
                                    part_number = p_val
                                    break
                    if "name" in val.lower() and not part_name:
                        for offset in [1, 2, 3, 4]:
                            target_c = c + offset
                            if 1 <= target_c <= cover_sheet.max_column:
                                n_val = str(cover_sheet.cell(r, target_c).value or "").strip()
                                if n_val and n_val != ":" and len(n_val) > 2:
                                    part_name = n_val
                                    break
                    if "model" in val.lower() and not model:
                        for offset in [1, 2, 3]:
                            target_c = c + offset
                            if 1 <= target_c <= cover_sheet.max_column:
                                m_val = str(cover_sheet.cell(r, target_c).value or "").strip()
                                if m_val and m_val != ":" and len(m_val) >= 2:
                                    model = m_val
                                    break
    except Exception as e:
        print(f"[Warning] Error reading cover sheet metadata: {e}")

    return {
        "doc_number": doc_number,
        "part_number": part_number,
        "part_name": part_name,
        "model": model,
        "filename": filename
    }

def extract_reference_images(file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
    """Extract part machine and layout images from sheets PAGE 4, PAGE 5, and EO."""
    if not output_dir:
        sub = part_number or os.path.splitext(os.path.basename(file_path))[0]
        # Clean subfolder name
        sub = re.sub(r'[^0-9A-Za-z_-]', '_', sub)
        output_dir = os.path.join("extracted_images", sub)

    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []
    
    with zipfile.ZipFile(file_path, "r") as z:
        wb_xml = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = {}
        for s in wb_xml.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
            sheets[s.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]] = s.attrib["name"]
        
        wb_rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        sheet_files = {}
        for r in wb_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
            rId = r.attrib["Id"]
            target = r.attrib["Target"]
            if rId in sheets:
                sheet_files[target] = sheets[rId]

        target_sheets = ["PAGE 4", "PAGE 5", "EO"]
        target_image_names = set()

        for sheet_target, sheet_name in sheet_files.items():
            if any(ts in sheet_name for ts in target_sheets):
                sheet_xml_path = "xl/" + sheet_target if not sheet_target.startswith("xl/") else sheet_target
                sheet_rel_path = sheet_xml_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
                if sheet_rel_path in z.namelist():
                    s_rels = ET.fromstring(z.read(sheet_rel_path))
                    for rel in s_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                        if "drawing" in rel.attrib["Type"]:
                            drawing_target = rel.attrib["Target"]
                            drawing_path = "xl/" + drawing_target.replace("../", "")
                            drawing_rel_path = drawing_path.replace("drawings/", "drawings/_rels/") + ".rels"
                            if drawing_rel_path in z.namelist():
                                d_rels = ET.fromstring(z.read(drawing_rel_path))
                                for d_rel in d_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                                    if "image" in d_rel.attrib["Type"]:
                                        img_target = d_rel.attrib["Target"].replace("../", "xl/")
                                        target_image_names.add(img_target)

        if not target_image_names:
            for n in z.namelist():
                if n.startswith("xl/media/") and (n.endswith(".png") or n.endswith(".jpg") or n.endswith(".jpeg")):
                    target_image_names.add(n)

        for img_name in sorted(target_image_names):
            if not (img_name.endswith(".png") or img_name.endswith(".jpg") or img_name.endswith(".jpeg")):
                continue
            base = os.path.basename(img_name)
            data = z.read(img_name)
            if len(data) < 5000:
                continue
            out_file = os.path.join(output_dir, base)
            with open(out_file, "wb") as f:
                f.write(data)
            extracted_paths.append(os.path.abspath(out_file))

    return extracted_paths

def get_reference_images(
    file_path: str,
    manual_dir: Optional[str] = None,
    part_number: Optional[str] = None
) -> List[str]:
    """
    Get reference images with clear priority:
    1. If manual_dir is specified and exists, load images from there.
    2. If folder images/{part_number}/ exists and has images, load from there.
    3. If folder images/ has images directly, load from there.
    4. Otherwise, extract from Excel into extracted_images/{part_number}/.
    """
    image_exts = (".png", ".jpg", ".jpeg", ".webp")

    # 1. Custom manual directory specified
    if manual_dir and os.path.isdir(manual_dir):
        files = [
            os.path.abspath(os.path.join(manual_dir, f))
            for f in sorted(os.listdir(manual_dir))
            if f.lower().endswith(image_exts)
        ]
        if files:
            print(f"[*] Menggunakan {len(files)} gambar dari folder manual: {manual_dir}")
            return files

    # 2. images/{part_number}/
    if part_number:
        part_dir = os.path.join("images", part_number)
        if os.path.isdir(part_dir):
            files = [
                os.path.abspath(os.path.join(part_dir, f))
                for f in sorted(os.listdir(part_dir))
                if f.lower().endswith(image_exts)
            ]
            if files:
                print(f"[*] Menggunakan {len(files)} gambar dari folder part: {part_dir}")
                return files

    # 3. images/ directly (if has files, not just subdirs)
    if os.path.isdir("images"):
        files = [
            os.path.abspath(os.path.join("images", f))
            for f in sorted(os.listdir("images"))
            if f.lower().endswith(image_exts) and os.path.isfile(os.path.join("images", f))
        ]
        if files:
            print(f"[*] Menggunakan {len(files)} gambar dari folder images/")
            return files

    # 4. Fallback: Extract from Excel
    return extract_reference_images(file_path, part_number=part_number or "")

def extract_inspection_points(file_path: str) -> List[Dict[str, str]]:
    """
    Extract inspection points dynamically for ANY checksheet Excel file:
    - Automatically finds all sheets containing the 'Inspection Item' and 'Standard' table headers
    - Automatically locates the header row (works whether header is on row 4, 5, 6, etc.)
    - Extracts item numbers from balloon column (preserves duplicate balloon numbers like No 10)
    - Formats standard with nominal + upper/lower tolerances
    - Leaves method and master_data blank as per user specification
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    items = []
    current_balloon = ""

    # 1. Dynamically identify all sheets that contain inspection tables
    inspection_sheets = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for r in range(1, min(ws.max_row + 1, 20)):
            row_vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, min(ws.max_column + 1, 15))]
            if any("Inspection Item" in v for v in row_vals) and any("Standard" in v for v in row_vals):
                inspection_sheets.append((sheet_name, r))
                break

    # Fallback to PAGE 6..9 if dynamic search didn't catch specific sheets
    if not inspection_sheets:
        for p in wb.sheetnames:
            if p.upper().startswith("PAGE") and any(ch.isdigit() for ch in p):
                ws = wb[p]
                inspection_sheets.append((p, 5))

    # 2. Extract inspection rows from each detected sheet
    for sheet_name, header_row in inspection_sheets:
        ws = wb[sheet_name]
        
        # Check header labels in header_row
        headers_map = {}
        for c in range(1, min(ws.max_column + 1, 15)):
            val = str(ws.cell(header_row, c).value or "").strip().lower()
            if val:
                headers_map[c] = val

        # Detect format: Tabular "Inspection Standards" vs Multi-page IR
        # In "Inspection Standards" format:
        # Col 1: "No. / Item"
        # Col 2: "Inspection Item"
        # Col 3: "Standard"
        # Col 4: "Inspection Method"
        is_direct_table = any("no" in headers_map.get(1, "") or "item" in headers_map.get(1, "") for _ in [0]) and \
                          any("inspection" in headers_map.get(2, "") for _ in [0]) and \
                          any("standard" in headers_map.get(3, "") for _ in [0])

        if is_direct_table:
            # Direct Tabular format (e.g. Inspection_Standard_*.xlsx)
            r = header_row + 1
            while r <= ws.max_row:
                c1 = ws.cell(r, 1).value
                c2 = ws.cell(r, 2).value
                c3 = ws.cell(r, 3).value
                c4 = ws.cell(r, 4).value

                if c1 is not None and str(c1).strip():
                    m = re.search(r"\d+", str(c1))
                    current_balloon = m.group(0) if m else str(c1).strip()

                if c2 is not None and str(c2).strip():
                    item_name = str(c2).strip()
                    std = str(c3).strip() if c3 is not None else ""
                    std = re.sub(r"\s+", " ", std)
                    
                    items.append({
                        "item_no": current_balloon,
                        "inspection_item": item_name,
                        "standard": std,
                        "method": "",
                        "master_data": ""
                    })
                r += 1
        else:
            # Multi-page Summit/MMKI IR report format
            col_item_no = 2
            col_item_name = 3
            col_pos = 4
            col_std = 5
            col_tol = 6

            for c in range(1, min(ws.max_column + 1, 15)):
                header_val = str(ws.cell(header_row, c).value or "").strip()
                if "Standard" in header_val:
                    col_std = c
                    col_tol = c + 1

            r = header_row + 1
            while r <= ws.max_row:
                c2 = ws.cell(r, col_item_no).value  # Balloon No
                c3 = ws.cell(r, col_item_name).value  # Item Name
                c4 = ws.cell(r, col_pos).value  # Extra pos tag e.g. [ TL ], [ BL ]
                c5 = ws.cell(r, col_std).value  # Standard
                c6 = ws.cell(r, col_tol).value  # Tol upper
                next_c4 = ws.cell(r+1, col_pos).value if r+1 <= ws.max_row else None
                next_c5 = ws.cell(r+1, col_std).value if r+1 <= ws.max_row else None
                next_c6 = ws.cell(r+1, col_tol).value if r+1 <= ws.max_row else None

                # Skip repeat headers or footnotes
                if str(c2).strip() == "Inspection Item" or str(c5).strip() == "Standard":
                    r += 1
                    continue

                if c2 is not None and str(c2).strip():
                    current_balloon = str(c2).strip()

                if c3 is not None and str(c3).strip():
                    item_name = str(c3).strip()
                    
                    # Check position tag
                    pos = ""
                    if c4 is not None and str(c4).strip():
                        pos = str(c4).strip()
                    elif next_c4 is not None and "[" in str(next_c4):
                        pos = str(next_c4).strip()
                    
                    # Format item name (e.g. 'DATUM HOLE [TL]')
                    full_name = f"{item_name} {pos}".strip()
                    full_name = re.sub(r"\[\s+", "[", full_name)
                    full_name = re.sub(r"\s+\]", "]", full_name)

                    # Format standard (e.g. 'Ø 12 + 0.2 / 0')
                    std = str(c5).strip() if c5 is not None else ""
                    if next_c5 is not None and str(next_c5).strip() in ["OK / NG"]:
                        std = f"{std} {str(next_c5).strip()}".strip()

                    tol = ""
                    if c6 is not None:
                        tol = str(c6).strip()
                        if next_c6 is not None and str(next_c6).strip().startswith(("-", "0", "+")):
                            tol = f"{tol} / {str(next_c6).strip()}"

                    full_std = f"{std} {tol}".strip()
                    full_std = re.sub(r"\s+", " ", full_std)

                    items.append({
                        "item_no": current_balloon,
                        "inspection_item": full_name,
                        "standard": full_std,
                        "method": "",
                        "master_data": ""
                    })
                    
                r += 1

    return items

if __name__ == "__main__":
    test_excel = "6. IR - 51138E000P_BRKT ASSY-RR TOWING HOOK #Rev New EO.xlsx"
    pts = extract_inspection_points(test_excel)
    print(f"Extracted {len(pts)} inspection points.")
    for it in pts[:10]:
        print(f"{it['item_no']} | {it['inspection_item']} | {it['standard']} | method: '{it['method']}' | master: '{it['master_data']}'")
