"""
Parser for PDF Checksheets and drawings.
Extracts metadata, table lines, and drawing pages from PDF documents.
"""
import os
import re
from typing import Dict, List, Optional, Any
from parsers.base import BaseParser

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    from PIL import Image
except ImportError:
    Image = None


class PDFParser(BaseParser):
    """Parser for PDF checksheet documents."""

    def can_parse(self, file_path: str, wb: Optional[Any] = None) -> bool:
        return file_path.lower().endswith(".pdf")

    def extract_metadata(self, file_path: str, wb: Optional[Any] = None) -> Dict[str, str]:
        meta = {
            "part_number": "",
            "part_name": "",
            "model": "-",
            "customer": "-",
            "doc_number": "Form 1",
            "filename": os.path.basename(file_path)
        }

        if not pdfplumber:
            return meta

        try:
            with pdfplumber.open(file_path) as pdf:
                full_text = ""
                for page in pdf.pages[:3]:
                    text = page.extract_text() or ""
                    full_text += "\n" + text

                # Part Number heuristic
                match_pno = re.search(r"(?:Part\s*No\.?|PART\s*NO\.?)\s*[:]?\s*([0-9A-Z\s\-]+)", full_text, re.I)
                if match_pno:
                    meta["part_number"] = match_pno.group(1).strip()

                # Part Name heuristic
                match_pname = re.search(r"(?:Part\s*Name|PART\s*NAME)\s*[:]?\s*([0-9A-Z\s\,\-]+)", full_text, re.I)
                if match_pname:
                    meta["part_name"] = match_pname.group(1).strip()

                # Model heuristic
                match_model = re.search(r"(?:Model|MODEL)\s*[:]?\s*([0-9A-Z\s\-]+)", full_text, re.I)
                if match_model:
                    meta["model"] = match_model.group(1).strip()

                # Customer
                if "HPM" in full_text or "HONDA" in full_text:
                    meta["customer"] = "PT. HPM"
                elif "MMKI" in full_text or "MITSUBISHI" in full_text:
                    meta["customer"] = "PT. MMKI"
                elif "SUZUKI" in full_text:
                    meta["customer"] = "PT. SIM"
        except Exception as e:
            print(f"[Warning] Error extracting PDF metadata: {e}")

        if not meta["part_number"]:
            base = os.path.splitext(os.path.basename(file_path))[0]
            m = re.search(r"([0-9]{4,5}[A-Z0-9_-]{3,})", base)
            if m:
                meta["part_number"] = m.group(1)

        return meta

    def extract_inspection_points(self, file_path: str, wb: Optional[Any] = None) -> List[Dict[str, str]]:
        points = []
        if not pdfplumber:
            return points

        try:
            with pdfplumber.open(file_path) as pdf:
                balloon_counter = 1
                for page in pdf.pages:
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            if not row or len(row) < 3:
                                continue
                            row_clean = [str(cell or "").strip() for cell in row]
                            # Check if row looks like an inspection row
                            no_val = row_clean[0]
                            item_val = row_clean[1] if len(row_clean) > 1 else ""
                            std_val = row_clean[2] if len(row_clean) > 2 else ""
                            meth_val = row_clean[3] if len(row_clean) > 3 else "Visual"

                            if any(hdr in item_val.upper() for hdr in ["ITEM", "INSPECTION", "POINT", "STANDAR"]):
                                continue

                            if item_val or std_val:
                                item_no = no_val if no_val and no_val.isdigit() else str(balloon_counter)
                                points.append({
                                    "item_no": item_no,
                                    "inspection_item": item_val or f"Point {balloon_counter}",
                                    "standard": std_val or "-",
                                    "method": meth_val or "Visual",
                                    "master_data": ""
                                })
                                balloon_counter += 1
        except Exception as e:
            print(f"[Warning] Error extracting PDF inspection points: {e}")

        return points

    def extract_images(self, file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
        if not output_dir:
            sub = part_number or os.path.splitext(os.path.basename(file_path))[0]
            sub = re.sub(r"[^0-9A-Za-z_-]", "_", sub)
            output_dir = os.path.join("storage", "images", sub)

        os.makedirs(output_dir, exist_ok=True)
        extracted = []
        if not pdfplumber or not Image:
            return extracted

        try:
            with pdfplumber.open(file_path) as pdf:
                for idx, page in enumerate(pdf.pages, 1):
                    # Render page as image (great for drawing review)
                    p_img = page.to_image(resolution=150).original
                    out_path = os.path.join(output_dir, f"page_{idx}.webp")
                    p_img.save(out_path, "WEBP", quality=80)
                    extracted.append(os.path.abspath(out_path))
        except Exception as e:
            print(f"[Warning] Error extracting PDF pages: {e}")

        return extracted
