"""
Document Extractor for Checksheet Master Automation
Supports:
- Excel (.xlsx, .xls) and PDF (.pdf) documents
- Partitioned storage: documents/belum/ and documents/done/
- Metadata extraction: Part Number, Part Name, Doc Number, Model
- Reference Images: Machine/Part drawings from Excel sheets (PAGE 4, PAGE 5, EO) or PDF embedded media
- Inspection Points: Dynamic multi-page table extraction from Excel and PDF
"""

import os
import re
import io
import json
import zipfile
import xml.etree.ElementTree as ET
import warnings
from typing import Dict, List, Any, Optional, Tuple
import openpyxl

from parsers.smart_parser import (
    SemanticStandardParser,
    FuzzyToolNormalizer,
    SpatialBlockDetector,
)

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    import pypdf
except ImportError:
    pypdf = None

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Known company logo dimensions (PT. Summit Adyawinsa, MMKI, Honda, ISO badges) to strictly exclude
KNOWN_LOGO_DIMENSIONS = {
    (530, 200), (396, 158), (240, 119), (149, 52), (154, 53), (162, 56), (144, 72), (629, 245)
}


def extract_pdf_metadata(file_path: str) -> Dict[str, str]:
    """Extract metadata from PDF filename and text contents."""
    filename = os.path.basename(file_path)

    # Extract Doc Number from filename prefix
    doc_number = "Form 1"
    doc_match = re.match(r"^(\d+)", filename)
    if doc_match:
        doc_number = f"Form {doc_match.group(1)}"

    # Extract Part Number candidate from filename
    part_number = ""
    tokens = re.split(r"[^0-9A-Za-z\-]+", filename)
    for t in tokens:
        if any(c.isdigit() for c in t) and len(t) >= 6 and not t.lower().startswith("form") and not t.lower().startswith("rev"):
            part_number = t.upper()
            break

    part_name = ""
    model = ""

    if pdfplumber:
        try:
            with pdfplumber.open(file_path) as pdf:
                num_pages_to_check = min(3, len(pdf.pages))
                for p_idx in range(num_pages_to_check):
                    text = pdf.pages[p_idx].extract_text() or ""
                    for line in text.split("\n"):
                        # Part number match
                        m_part = re.search(r"PART\s*NO\.?\s*:\s*([A-Za-z0-9\-_]+)", line, re.IGNORECASE)
                        if m_part and not part_number:
                            part_number = m_part.group(1).strip().upper()

                        # Part name match
                        m_name = re.search(r"PART\s*NAME\s*:\s*([^:]+?)(?:\s+(?:FINAL|CHECK|DWG|RANK|EFFECTIVE|DOC|\d)|$)", line, re.IGNORECASE)
                        if m_name and not part_name:
                            p_clean = m_name.group(1).strip()
                            if len(p_clean) > 2:
                                part_name = p_clean

                        # Model match
                        m_model = re.search(r"MODEL\s*:\s*([A-Za-z0-9\-]+)", line, re.IGNORECASE)
                        if m_model and not model:
                            model = m_model.group(1).strip()

                        # Doc number match from content if still default
                        if doc_number == "Form 1":
                            m_doc = re.search(r"DOC\.?\s*NO\.?\s*:\s*([A-Za-z0-9\/\-_]+)", line, re.IGNORECASE)
                            if m_doc:
                                doc_number = m_doc.group(1).strip()
        except Exception as e:
            print(f"[Warning] Error reading PDF metadata: {e}")

    result = {
        "doc_number": doc_number,
        "part_number": part_number,
        "part_name": part_name,
        "model": model,
        "filename": filename
    }
    return result


_METADATA_CACHE: Dict[Tuple[str, float], Dict[str, str]] = {}
_POINTS_CACHE: Dict[Tuple[str, float], List[Dict[str, str]]] = {}
_IMAGE_INFO_CACHE: Dict[Tuple[str, float], Dict[str, Any]] = {}
_PARTS_LIST_CACHE: Dict[str, Any] = {"fingerprint": "", "parts": []}
_DISK_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", ".doc_cache.json")
_DISK_CACHE_DIRTY = False


def _load_disk_cache():
    legacy_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".doc_cache.json")
    cache_to_load = _DISK_CACHE_FILE if os.path.isfile(_DISK_CACHE_FILE) else (legacy_file if os.path.isfile(legacy_file) else None)
    if cache_to_load and os.path.isfile(cache_to_load):
        try:
            with open(cache_to_load, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in data.get("metadata", {}).items():
                    p = k.split(":::")
                    if len(p) == 2:
                        _METADATA_CACHE[(p[0], float(p[1]))] = v
                for k, v in data.get("images", {}).items():
                    p = k.split(":::")
                    if len(p) == 2:
                        _IMAGE_INFO_CACHE[(p[0], float(p[1]))] = v
        except Exception:
            pass


def _save_disk_cache(force: bool = False):
    global _DISK_CACHE_DIRTY
    if not _DISK_CACHE_DIRTY and not force:
        return
    try:
        data = {
            "metadata": {f"{k[0]}:::{k[1]}": v for k, v in _METADATA_CACHE.items()},
            "images": {f"{k[0]}:::{k[1]}": v for k, v in _IMAGE_INFO_CACHE.items()}
        }
        os.makedirs(os.path.dirname(_DISK_CACHE_FILE), exist_ok=True)
        with open(_DISK_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        _DISK_CACHE_DIRTY = False
        legacy_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".doc_cache.json")
        if os.path.isfile(legacy_file):
            try:
                os.remove(legacy_file)
            except OSError:
                pass
    except Exception:
        pass


import atexit
atexit.register(_save_disk_cache)
_load_disk_cache()


def clear_document_caches():
    """Clear all in-memory and on-disk caches when documents or files are modified/uploaded."""
    global _DISK_CACHE_DIRTY
    _METADATA_CACHE.clear()
    _POINTS_CACHE.clear()
    _IMAGE_INFO_CACHE.clear()
    _PARTS_LIST_CACHE["fingerprint"] = ""
    _PARTS_LIST_CACHE["parts"] = []
    _DISK_CACHE_DIRTY = False
    for cf in [_DISK_CACHE_FILE, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".doc_cache.json")]:
        if os.path.isfile(cf):
            try:
                os.remove(cf)
            except OSError:
                pass


def get_cached_image_info(img_path: str) -> Dict[str, Any]:
    """Inspect and cache image dimensions, size, and logo classification."""
    abs_p = os.path.abspath(img_path)
    try:
        mtime = os.path.getmtime(abs_p)
        fsize = os.path.getsize(abs_p)
    except OSError:
        return {"width": 0, "height": 0, "size_kb": 0, "format": "IMAGE", "is_logo": False}

    key = (abs_p, mtime)
    if key in _IMAGE_INFO_CACHE:
        return _IMAGE_INFO_CACHE[key]

    w, h, fmt = 0, 0, "IMAGE"
    is_logo = False
    if Image and os.path.isfile(abs_p):
        try:
            with Image.open(abs_p) as im:
                w, h = im.size
                base_name = os.path.basename(abs_p).lower()
                if "sketch" in base_name:
                    is_logo = False
                elif (w < 120 and h < 120) or (w > 0 and h > 0 and (w / h > 5 or h / w > 5) and (w < 350 and h < 150)):
                    is_logo = True
        except Exception:
            pass

    info = {
        "width": w,
        "height": h,
        "size_kb": round(fsize / 1024, 1),
        "format": fmt,
        "is_logo": is_logo
    }
    _IMAGE_INFO_CACHE[key] = info
    global _DISK_CACHE_DIRTY
    _DISK_CACHE_DIRTY = True
    return info


def get_documents_fingerprint(documents_dir: str = "documents") -> str:
    """Generate a fast signature of documents directory state to avoid redundant full scans."""
    parts_state = []
    if os.path.isdir(documents_dir):
        for sub in ["belum", "tidak_ada_part", "done"]:
            sp = os.path.join(documents_dir, sub)
            if os.path.isdir(sp):
                try:
                    entries = sorted(os.listdir(sp))
                    parts_state.append(f"{sub}:{os.path.getmtime(sp)}:{len(entries)}")
                except OSError:
                    pass
        try:
            parts_state.append(f"root:{os.path.getmtime(documents_dir)}")
        except OSError:
            pass
    return "|".join(parts_state)


def extract_metadata(file_path: str) -> Dict[str, str]:
    """Extract metadata from file name and cover sheet (Excel or PDF) with mtime caching."""
    abs_p = os.path.abspath(file_path)
    try:
        mtime = os.path.getmtime(abs_p)
    except OSError:
        mtime = 0
    cache_key = (abs_p, mtime)
    if cache_key in _METADATA_CACHE:
        return dict(_METADATA_CACHE[cache_key])

    if file_path.lower().endswith(".pdf"):
        res = extract_pdf_metadata(file_path)
        _METADATA_CACHE[cache_key] = res
        return dict(res)

    # Try specialized modular parser
    try:
        from parsers import get_parser_for_file
        mod_parser = get_parser_for_file(file_path)
        mod_meta = mod_parser.extract_metadata(file_path)
        if mod_meta and mod_meta.get("part_number"):
            _METADATA_CACHE[cache_key] = mod_meta
            return dict(mod_meta)
    except Exception:
        pass

    filename = os.path.basename(file_path)

    # Extract Doc Number from filename prefix (e.g. '6. IR - ...' -> 'Form 6')
    doc_number = "Form 1"
    doc_match = re.match(r"^(\d+)", filename)
    if doc_match:
        doc_number = f"Form {doc_match.group(1)}"

    # Extract Part Number from filename
    part_number = ""
    tokens = re.split(r"[^0-9A-Za-z\-]+", filename)
    for t in tokens:
        if any(c.isdigit() for c in t) and len(t) >= 6 and not t.lower().startswith("form") and not t.lower().startswith("rev"):
            part_number = t.upper()
            break

    # Extract target revision from filename if present (e.g. Rev.02 -> '02')
    file_rev_m = re.search(r"rev\.?\s*(\d+)", filename, re.IGNORECASE)
    file_rev = file_rev_m.group(1) if file_rev_m else ""

    part_name = ""
    model = ""

    wb = None
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        cover_sheet = None
        for s in wb.sheetnames:
            if "cover" in s.lower():
                cover_sheet = wb[s]
                break

        if cover_sheet is None and len(wb.sheetnames) > 0:
            rev_sheets = [s for s in wb.sheetnames if "(rev)" in s.lower()]
            if rev_sheets:
                cover_sheet = wb[rev_sheets[0]]
            else:
                cover_sheet = wb[wb.sheetnames[0]]
                for s in wb.sheetnames:
                    if any(skip in s.lower() for skip in ["drawing", "eo"]):
                        continue
                    s_lower = s.lower().replace(" ", "").replace("_", "")
                    if file_rev and (f"rev.{file_rev}".lower() in s_lower or f"rev{file_rev}".lower() in s_lower):
                        cover_sheet = wb[s]
                        break

        if cover_sheet:
            for row in cover_sheet.iter_rows(min_row=1, max_row=30, max_col=35, values_only=True):
                for idx, cell_val in enumerate(row):
                    val = str(cell_val or "").strip()
                    val_lower = val.lower()
                    if any(k in val_lower for k in ["part no", "no. part", "no part"]):
                        if ":" in val:
                            cand_p = val.split(":", 1)[1].strip()
                            if cand_p and len(cand_p) >= 5 and any(c.isdigit() for c in cand_p):
                                part_number = cand_p.upper()
                        for offset in range(1, min(6, len(row) - idx)):
                            p_val = str(row[idx + offset] or "").strip().lstrip(":").strip()
                            if p_val and len(p_val) >= 5 and any(c.isdigit() for c in p_val):
                                # Clean potential extra zeros from manual typos (e.g. 80149E0000P -> 80149E000P)
                                p_clean = re.sub(r"([A-Z0-9]{5}E)0+([0-9]{3}P)", r"\1\2", p_val.upper())
                                cand_p = p_clean or p_val.upper()
                                # If cover sheet part number is 9 chars missing letter (e.g. 76715000P) and filename has 10 chars (76715E000P), prefer filename
                                if len(cand_p) == 9 and part_number and len(part_number) == 10:
                                    pass
                                else:
                                    part_number = cand_p
                                break
                    if any(k in val_lower for k in ["part name", "nama part", "item name"]) and not part_name:
                        if ":" in val:
                            n_val = val.split(":", 1)[1].strip()
                            if n_val and len(n_val) > 2 and not any(n_val.lower().startswith(x) for x in ["customer", "supplier"]):
                                part_name = n_val
                        for offset in range(1, min(6, len(row) - idx)):
                            n_val = str(row[idx + offset] or "").strip().lstrip(":").strip()
                            if n_val and len(n_val) > 2:
                                part_name = n_val
                                break
                    if "model" in val_lower and not model:
                        if ":" in val:
                            m_val = val.split(":", 1)[1].strip()
                            if m_val and len(m_val) >= 2:
                                model = m_val
                        for offset in range(1, min(6, len(row) - idx)):
                            m_val = str(row[idx + offset] or "").strip().lstrip(":").strip()
                            if m_val and len(m_val) >= 2:
                                model = m_val
                                break
                    if any(k in val_lower for k in ["no. dokumen", "no dokumen", "doc. no", "doc no", "document no"]) and doc_number == "Form 1":
                        if ":" in val:
                            d_val = val.split(":", 1)[1].strip()
                            if d_val and len(d_val) >= 3:
                                doc_number = d_val
                        for offset in range(1, min(6, len(row) - idx)):
                            d_val = str(row[idx + offset] or "").strip().lstrip(":").strip()
                            if d_val and len(d_val) >= 3:
                                doc_number = d_val
                                break
    except Exception as e:
        print(f"[Warning] Error reading cover sheet metadata: {e}")
    finally:
        if wb:
            try:
                wb.close()
            except Exception:
                pass

    res = {
        "doc_number": doc_number,
        "part_number": part_number,
        "part_name": part_name,
        "model": model,
        "filename": filename
    }
    _METADATA_CACHE[cache_key] = res
    global _DISK_CACHE_DIRTY
    _DISK_CACHE_DIRTY = True
    return dict(res)


def extract_pdf_reference_images(file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
    """
    Extract ONLY part sketch drawings from PDF checksheets using pdfplumber & pypdf.
    Strictly filters out company logos (header logos at top < 75pt),
    legend/stamp icons, and non-sketch graphics.
    """
    if not output_dir:
        sub = part_number or os.path.splitext(os.path.basename(file_path))[0]
        sub = re.sub(r"[^0-9A-Za-z_-]", "_", sub)
        output_dir = os.path.join("extracted_images", sub)

    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []

    if not pypdf:
        print("[Warning] pypdf not installed, cannot extract PDF images.")
        return extracted_paths

    try:
        reader = pypdf.PdfReader(file_path)

        # Use pdfplumber to identify coordinate bounding boxes of sketches on each page
        valid_image_names_by_page = {}
        if pdfplumber:
            try:
                with pdfplumber.open(file_path) as pdf:
                    for p_idx, page in enumerate(pdf.pages):
                        v_names = set()
                        for img_obj in page.images:
                            name = img_obj.get("name")
                            top = img_obj.get("top", 0)
                            w = img_obj.get("width", 0)
                            h = img_obj.get("height", 0)
                            x0 = img_obj.get("x0", 0)

                            # LOGO & ICON FILTER:
                            # 1. Header logos are located at top < 75pt (Summit Adyawinsa, customer logos, ISO badges)
                            if top < 75:
                                continue
                            # 2. Checkboxes / tiny indicators
                            if w < 30 or h < 20:
                                continue
                            # 3. Outside sketch column (e.g. inside inspection table or inspector note column)
                            if x0 > 250:
                                continue

                            v_names.add(name)
                        valid_image_names_by_page[p_idx] = v_names
            except Exception as e:
                print(f"[Warning] Error analyzing PDF layout with pdfplumber: {e}")

        # Clean existing files in output_dir to prevent old logos from persisting
        for old_f in os.listdir(output_dir):
            if old_f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                try:
                    os.remove(os.path.join(output_dir, old_f))
                except Exception:
                    pass

        img_idx_total = 0
        for p_idx, page in enumerate(reader.pages):
            valid_names = valid_image_names_by_page.get(p_idx)
            for img in page.images:
                base_name = os.path.splitext(img.name)[0]

                # If we have layout validation, enforce it
                if valid_names is not None and base_name not in valid_names:
                    continue

                # Filter out tiny icon / line artifacts (< 3000 bytes)
                if len(img.data) < 3000:
                    continue

                # Inspect with PIL
                if Image:
                    try:
                        with Image.open(io.BytesIO(img.data)) as im:
                            w, h = im.size
                            # Filter known company logo dimensions
                            if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                continue
                            # Filter small icons or markers
                            if w < 180 or h < 80:
                                continue
                    except Exception:
                        continue

                img_idx_total += 1
                out_name = f"sketch_page_{p_idx+1}_{img_idx_total}"
                if Image:
                    try:
                        with Image.open(io.BytesIO(img.data)) as im:
                            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                                im_c = im.convert("RGBA")
                            else:
                                im_c = im.convert("RGB")
                            out_file = os.path.join(output_dir, f"{out_name}.webp")
                            im_c.save(out_file, "WEBP", quality=82, method=6)
                            extracted_paths.append(os.path.abspath(out_file))
                            continue
                    except Exception:
                        pass

                ext = os.path.splitext(img.name)[1] or ".png"
                out_path = os.path.join(output_dir, f"{out_name}{ext}")
                with open(out_path, "wb") as f:
                    f.write(img.data)
                extracted_paths.append(os.path.abspath(out_path))

    except Exception as e:
        print(f"[Warning] Error extracting PDF images: {e}")

    return extracted_paths


def extract_reference_images(file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
    """
    Extract ONLY part sketch drawings from Excel checksheets or PDF.
    Strictly filters out company logos, header icons, stamp marks, and non-sketch graphics.
    """
    if file_path.lower().endswith(".pdf"):
        return extract_pdf_reference_images(file_path, output_dir=output_dir, part_number=part_number)

    if not output_dir:
        sub = part_number or os.path.splitext(os.path.basename(file_path))[0]
        sub = re.sub(r"[^0-9A-Za-z_-]", "_", sub)
        output_dir = os.path.join("extracted_images", sub)

    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            wb_xml = ET.fromstring(z.read("xl/workbook.xml"))
            sheets = {}
            for s in wb_xml.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheets/{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
                rId = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                sheets[rId] = s.attrib.get("name", "")

            wb_rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            sheet_targets = {}
            for r in wb_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                if r.attrib.get("Id") in sheets:
                    sheet_targets[r.attrib["Target"]] = sheets[r.attrib["Id"]]

            anchored_sketches = []
            seen_media = set()

            for sheet_target, sheet_name in sheet_targets.items():
                sheet_path = "xl/" + sheet_target if not sheet_target.startswith("xl/") else sheet_target
                s_rel_path = sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
                if s_rel_path not in z.namelist():
                    continue

                s_rels = ET.fromstring(z.read(s_rel_path))
                for rel in s_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                    if "drawing" in rel.attrib.get("Type", ""):
                        d_target = rel.attrib["Target"].replace("../", "xl/")
                        d_path = d_target if d_target.startswith("xl/") else "xl/" + d_target
                        d_rel_path = d_path.replace("drawings/", "drawings/_rels/") + ".rels"
                        if d_rel_path not in z.namelist():
                            continue

                        d_rels = ET.fromstring(z.read(d_rel_path))
                        media_map = {}
                        for d_r in d_rels.findall("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                            if "image" in d_r.attrib.get("Type", ""):
                                media_map[d_r.attrib["Id"]] = d_r.attrib["Target"].replace("../", "xl/")

                        d_xml = ET.fromstring(z.read(d_path))
                        for child in d_xml:
                            blip = child.find(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip")
                            if blip is None:
                                continue
                            embed = blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                            media_file = media_map.get(embed)
                            if not media_file or media_file not in z.namelist():
                                continue

                            from_c = child.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}from")
                            f_r = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row").text) + 1 if from_c is not None else 1
                            f_c = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}col").text) + 1 if from_c is not None else 1

                            # STRICT SKETCH FILTERING:
                            # 1. Header logo filter: top 4 rows and left 3 columns
                            if f_r <= 4 and f_c <= 3:
                                continue
                            # 2. Bottom signature / stamp boxes or far right off-sheet columns
                            if f_r > 95 or f_c > 60:
                                continue

                            # 3. File type check (exclude vector stamp formats like EMF/WMF)
                            if not media_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                                continue

                            # 4. Check file size
                            data = z.read(media_file)
                            if len(data) < 3000:
                                continue

                            # 5. Check image dimensions with PIL
                            if Image:
                                try:
                                    with Image.open(io.BytesIO(data)) as im:
                                        w, h = im.size
                                        if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                            continue
                                        # Tiny datum markers / checkmarks
                                        if w < 100 or h < 50:
                                            continue
                                except Exception:
                                    continue

                            if media_file not in seen_media:
                                seen_media.add(media_file)
                                anchored_sketches.append(media_file)

            # Clean existing files in output_dir to prevent old logos from persisting
            for old_f in os.listdir(output_dir):
                if old_f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    try:
                        os.remove(os.path.join(output_dir, old_f))
                    except Exception:
                        pass

            # Write only valid sketches to output_dir
            for idx, media_file in enumerate(anchored_sketches, start=1):
                if Image:
                    try:
                        raw_data = z.read(media_file)
                        with Image.open(io.BytesIO(raw_data)) as im:
                            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                                im_c = im.convert("RGBA")
                            else:
                                im_c = im.convert("RGB")
                            out_file = os.path.join(output_dir, f"sketch_{idx}.webp")
                            im_c.save(out_file, "WEBP", quality=82, method=6)
                            extracted_paths.append(os.path.abspath(out_file))
                            continue
                    except Exception:
                        pass

                ext = os.path.splitext(media_file)[1] or ".png"
                out_name = f"sketch_{idx}{ext}"
                out_file = os.path.join(output_dir, out_name)
                with open(out_file, "wb") as f:
                    f.write(z.read(media_file))
                extracted_paths.append(os.path.abspath(out_file))

    except Exception as e:
        print(f"[Warning] Error extracting Excel reference images: {e}")

    return extracted_paths


def list_available_parts(documents_dir: str = "documents") -> List[Dict[str, Any]]:
    """
    List all available part folders inside documents_dir.
    Traverses subdirectories (including 'belum/' and 'done/').
    """
    if not os.path.isdir(documents_dir):
        return []

    fp = get_documents_fingerprint(documents_dir)
    if fp and _PARTS_LIST_CACHE.get("fingerprint") == fp and _PARTS_LIST_CACHE.get("parts"):
        return [dict(p) for p in _PARTS_LIST_CACHE["parts"]]

    parts = []
    image_exts = (".png", ".jpg", ".jpeg", ".webp")

    # Find candidate folders in documents/, documents/belum/, documents/done/
    candidate_folders = []

    # 1. Check subfolders 'belum', 'tidak_ada_part', and 'done'
    for status_folder in ["belum", "tidak_ada_part", "done"]:
        s_path = os.path.join(documents_dir, status_folder)
        if os.path.isdir(s_path):
            for entry in sorted(os.listdir(s_path)):
                f_path = os.path.join(s_path, entry)
                if os.path.isdir(f_path):
                    candidate_folders.append((f_path, status_folder, entry))

    # 2. Check direct folders in documents/ (excluding 'belum', 'done', 'tidak_ada_part', hidden)
    for entry in sorted(os.listdir(documents_dir)):
        if entry.lower() in ["belum", "done", "tidak_ada_part"] or entry.startswith("."):
            continue
        f_path = os.path.join(documents_dir, entry)
        if os.path.isdir(f_path):
            candidate_folders.append((f_path, "belum", entry))

    for folder_path, status, entry in candidate_folders:
        # Check files inside
        files = os.listdir(folder_path)

        doc_candidates = [
            f for f in files
            if (f.lower().endswith((".xlsx", ".xls", ".pdf"))) and not f.startswith("~$")
        ]
        if not doc_candidates:
            continue

        # Sort so that xlsx comes first if multiple, prefer 'rev' in name, else pdf
        doc_candidates.sort(key=lambda x: (not x.lower().endswith((".xlsx", ".xls")), 0 if "rev" in os.path.basename(x).lower() else 1, x))
        main_doc = doc_candidates[0]
        doc_path = os.path.join(folder_path, main_doc)
        file_type = "pdf" if main_doc.lower().endswith(".pdf") else "excel"

        # Count images in folder and subfolders
        images = [
            os.path.join(folder_path, f)
            for f in files
            if f.lower().endswith(image_exts)
        ]
        img_sub = os.path.join(folder_path, "images")
        if os.path.isdir(img_sub):
            images.extend([
                os.path.join(img_sub, f)
                for f in os.listdir(img_sub)
                if f.lower().endswith(image_exts)
            ])

        # Extract metadata
        meta = extract_metadata(doc_path)
        folder_base = entry.upper().strip()
        if re.match(r"^[0-9A-Z\-\s]+$", folder_base) and any(c.isdigit() for c in folder_base) and len(folder_base) >= 5:
            part_no = folder_base
        else:
            part_no = meta.get("part_number") or folder_base

        part_name = meta.get("part_name", "")
        doc_num = meta.get("doc_number", "Form 1")
        info_file = os.path.join(folder_path, "info.json")
        if os.path.isfile(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f_info:
                    info_data = json.load(f_info)
                    if info_data.get("part_number"):
                        part_no = info_data["part_number"].upper()
                    if info_data.get("part_name"):
                        part_name = info_data["part_name"]
                    if info_data.get("doc_number"):
                        doc_num = info_data["doc_number"]
            except Exception:
                pass

        parts.append({
            "folder_name": entry,
            "folder_path": folder_path,
            "status": status,
            "part_number": part_no,
            "part_name": part_name,
            "doc_number": doc_num,
            "model": meta.get("model", ""),
            "file_type": file_type,
            "excel_file": main_doc,
            "excel_path": doc_path,
            "image_count": len(images),
            "is_scan_data": len(images) > 0
        })

    if fp:
        _PARTS_LIST_CACHE["fingerprint"] = fp
        _PARTS_LIST_CACHE["parts"] = parts

    if _DISK_CACHE_DIRTY:
        _save_disk_cache()

    return parts


def resolve_part_document(
    part_or_path: str,
    scan_images: Optional[bool] = None,
    documents_dir: str = "documents",
    manual_images_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolves part directory, document file (Excel or PDF), and reference images.

    Args:
        part_or_path: Part number (e.g. '75510W050P'), folder name, or direct file path.
        scan_images:
            - True: force extract embedded images from document (excel/pdf mentah)
            - False: do not scan document; use images found in the part folder (hasil scan data)
            - None: auto-detect (if local images found in folder -> False, else True)
        documents_dir: Root directory for part documents (default: 'documents')
        manual_images_dir: Optional custom folder containing images
    """
    image_exts = (".png", ".jpg", ".jpeg", ".webp")
    status = "belum"

    raw_path = part_or_path.strip()

    # Case 1: Direct file passed
    if os.path.isfile(raw_path):
        doc_path = os.path.abspath(raw_path)
        folder_path = os.path.dirname(doc_path)
        meta = extract_metadata(doc_path)
        part_no = meta.get("part_number") or os.path.splitext(os.path.basename(doc_path))[0]
        file_type = "pdf" if doc_path.lower().endswith(".pdf") else "excel"
        if "tidak_ada_part" in folder_path:
            status = "tidak_ada_part"
        elif "done" in folder_path:
            status = "done"
    else:
        folder_path = None

        # Case 2: Direct folder path passed (absolute or relative)
        if os.path.isdir(raw_path):
            folder_path = os.path.abspath(raw_path)
            if "tidak_ada_part" in folder_path:
                status = "tidak_ada_part"
            elif "done" in folder_path:
                status = "done"
            else:
                status = "belum"
        else:
            # Case 3: Match folder in documents_dir (checking belum, tidak_ada_part, done, and root)
            target = raw_path.strip("/").strip("\\")

            # Check candidate paths: documents/belum/<target>, documents/tidak_ada_part/<target>, documents/done/<target>, documents/<target>
            candidate_paths = [
                (os.path.join(documents_dir, "belum", target), "belum"),
                (os.path.join(documents_dir, "tidak_ada_part", target), "tidak_ada_part"),
                (os.path.join(documents_dir, "done", target), "done"),
                (os.path.join(documents_dir, target), "belum"),
            ]
            for p, s in candidate_paths:
                if os.path.isdir(p):
                    folder_path = os.path.abspath(p)
                    status = s
                    break

            if not folder_path:
                # Fuzzy / case-insensitive search across list_available_parts
                all_parts = list_available_parts(documents_dir)
                target_clean = re.sub(r"[^0-9A-Za-z]", "", target).lower()

                for p in all_parts:
                    entry_clean = re.sub(r"[^0-9A-Za-z]", "", p["folder_name"]).lower()
                    part_clean = re.sub(r"[^0-9A-Za-z]", "", p["part_number"]).lower()
                    file_clean = re.sub(r"[^0-9A-Za-z]", "", p["excel_file"]).lower()

                    if target_clean in [entry_clean, part_clean, file_clean] or target_clean in entry_clean:
                        folder_path = p["folder_path"]
                        status = p.get("status", "belum")
                        break

        if not folder_path or not os.path.isdir(folder_path):
            available = [f"[{p.get('status', 'belum')}] {p['folder_name']}" for p in list_available_parts(documents_dir)]
            avail_str = ", ".join(available) if available else "(folder documents/ kosong)"
            raise FileNotFoundError(
                f"Folder part '{part_or_path}' tidak ditemukan di '{documents_dir}/'. "
                f"Part yang tersedia: {avail_str}"
            )

        # Locate Excel or PDF in folder
        doc_candidates = [
            os.path.join(folder_path, f)
            for f in sorted(os.listdir(folder_path))
            if f.lower().endswith((".xlsx", ".xls", ".pdf")) and not f.startswith("~$")
        ]
        if not doc_candidates:
            raise FileNotFoundError(f"Tidak ada file Excel/PDF di dalam folder: {folder_path}")

        # Prefer xlsx if multiple, prefer 'rev' in name, else first
        doc_candidates.sort(key=lambda x: (not x.lower().endswith((".xlsx", ".xls")), 0 if "rev" in os.path.basename(x).lower() else 1, x))
        doc_path = doc_candidates[0]
        meta = extract_metadata(doc_path)
        folder_base = os.path.basename(folder_path).upper().strip()
        if re.match(r"^[0-9A-Z\-\s]+$", folder_base) and any(c.isdigit() for c in folder_base) and len(folder_base) >= 5:
            part_no = folder_base
            meta["part_number"] = part_no
        else:
            part_no = meta.get("part_number") or folder_base

        # Check info.json in folder if present for authoritative part_number and part_name
        info_file = os.path.join(folder_path, "info.json")
        if os.path.isfile(info_file):
            try:
                with open(info_file, "r", encoding="utf-8") as f_info:
                    info_data = json.load(f_info)
                    if info_data.get("part_number"):
                        part_no = info_data["part_number"].upper()
                        meta["part_number"] = part_no
                    if info_data.get("part_name"):
                        meta["part_name"] = info_data["part_name"]
                    if info_data.get("checksheet_category"):
                        meta["checksheet_category"] = info_data["checksheet_category"]
                    if info_data.get("doc_number"):
                        meta["doc_number"] = info_data["doc_number"]
            except Exception:
                pass

        file_type = "pdf" if doc_path.lower().endswith(".pdf") else "excel"

    # Find local images in folder
    local_images = []
    if manual_images_dir and os.path.isdir(manual_images_dir):
        local_images = [
            os.path.abspath(os.path.join(manual_images_dir, f))
            for f in sorted(os.listdir(manual_images_dir))
            if f.lower().endswith(image_exts)
        ]
    else:
        local_images = [
            os.path.abspath(os.path.join(folder_path, f))
            for f in sorted(os.listdir(folder_path))
            if f.lower().endswith(image_exts)
        ]
        img_sub = os.path.join(folder_path, "images")
        if os.path.isdir(img_sub):
            local_images.extend([
                os.path.abspath(os.path.join(img_sub, f))
                for f in sorted(os.listdir(img_sub))
                if f.lower().endswith(image_exts)
            ])

    # Filter out logos and tiny icons from local_images using cached metadata
    clean_local_images = []
    for limg in local_images:
        info = get_cached_image_info(limg)
        if not info.get("is_logo", False):
            clean_local_images.append(limg)
    local_images = clean_local_images

    # Determine scan_images strategy
    if scan_images is True:
        print(f"[*] Mode: Scan Image dari Dokumen ({file_type.upper()}) (Paksa) - Part: {part_no}")
        images = extract_reference_images(doc_path, part_number=part_no)
    elif scan_images is False:
        print(f"[*] Mode: Tanpa Scan Dokumen (Hasil Scan Data) - Part: {part_no}")
        print(f"[*] Mengambil {len(local_images)} gambar referensi dari folder: {folder_path}")
        images = local_images
    else:
        # Auto-detect
        if len(local_images) > 0:
            print(f"[*] Deteksi Otomatis: Ditemukan {len(local_images)} gambar di folder '{os.path.basename(folder_path)}'.")
            print(f"[*] Menggunakan file gambar folder (tanpa scan dokumen).")
            images = local_images
            scan_images = False
        else:
            clean_sub = re.sub(r"[^0-9A-Za-z_-]", "_", part_no)
            existing_ext = []
            for ext_candidate in [part_no, clean_sub, os.path.basename(folder_path)]:
                c_dir = os.path.join("extracted_images", ext_candidate)
                if os.path.isdir(c_dir):
                    existing_ext = [
                        os.path.abspath(os.path.join(c_dir, f))
                        for f in sorted(os.listdir(c_dir))
                        if f.lower().endswith(image_exts)
                    ]
                    if existing_ext:
                        break

            if existing_ext:
                images = existing_ext
                scan_images = True
            else:
                print(f"[*] Deteksi Otomatis: Tidak ada gambar di folder '{os.path.basename(folder_path)}'.")
                print(f"[*] Mengekstrak gambar tersemat dari file {file_type.upper()}...")
                images = extract_reference_images(doc_path, part_number=part_no)
                scan_images = True

    return {
        "part_number": part_no,
        "part_name": meta.get("part_name", ""),
        "doc_number": meta.get("doc_number", ""),
        "folder_path": folder_path,
        "excel_path": doc_path,
        "file_path": doc_path,
        "file_type": file_type,
        "images": images,
        "scan_images": scan_images,
        "local_images": local_images,
        "metadata": meta,
        "status": status
    }


def get_reference_images(
    file_path: str,
    manual_dir: Optional[str] = None,
    part_number: Optional[str] = None,
    scan_images: Optional[bool] = None
) -> List[str]:
    """Compatibility wrapper around resolve_part_document."""
    resolved = resolve_part_document(
        part_or_path=part_number or file_path,
        scan_images=scan_images,
        manual_images_dir=manual_dir
    )
    return resolved["images"]


def normalize_pdf_standard(std: str) -> str:
    """Normalize tolerances such as '25 + 0 0.2' -> '25 + 0.2 / 0'."""
    if not std:
        return ""
    s = std.replace("\n", " / ").strip()
    # Normalize spaced decimals like '1 0 .4' -> '1.4' or '0 . 2' -> '0.2'
    s = re.sub(r"(\d)\s+0\s*\.\s*(\d)", r"\1.\2", s)
    # 25 + 0 0.2 -> 25 + 0.2 / 0
    m1 = re.match(r"^([Øø]?\s*\d+(?:\.\d+)?)\s*\+\s*0\s*(\d+\.\d+)$", s)
    if m1:
        s = f"{m1.group(1)} + {m1.group(2)} / 0"
    m2 = re.match(r"^([Øø]?\s*\d+(?:\.\d+)?)\s*\+\s*0\s*0\.(\d+)$", s)
    if m2:
        s = f"{m2.group(1)} + 0.{m2.group(2)} / 0"
    m_pm = re.match(r"^([Øø]?\s*\d+(?:\.\d+)?)\s*±\s*(\d+(?:\.\d+)?)$", s)
    if m_pm:
        s = f"{m_pm.group(1)} ± {m_pm.group(2)}"
    s = re.sub(r"\s*\/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return SemanticStandardParser.clean_format(s)


def extract_pdf_inspection_points(file_path: str) -> List[Dict[str, str]]:
    """
    Extract inspection points from PDF checksheets using table structure first,
    falling back to textual stream analysis if tables are absent.
    Accurately maps balloon numbers, inspection item descriptions, standards, and methods.
    """
    if not pdfplumber:
        print("[Warning] pdfplumber not installed, cannot extract PDF inspection points.")
        return []

    all_points = []

    # Try table extraction first (primary and most accurate for vector checksheets)
    try:
        with pdfplumber.open(file_path) as pdf:
            for p_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if not tables:
                    continue
                table = tables[0]
                header_idx = None
                no_col = item_col = std_col = method_col = None

                for r_idx, row in enumerate(table):
                    for c_idx, cell in enumerate(row):
                        if not cell:
                            continue
                        txt = str(cell).upper().replace("\n", " ").strip()
                        if txt == "NO" or txt.startswith("NO."):
                            no_col = c_idx
                        elif "INSPECTION ITEM" in txt:
                            item_col = c_idx
                        elif "ITEM" in txt and "INSPECTION" not in txt and item_col is None:
                            item_col = c_idx
                        elif "STD" in txt or "STANDARD" in txt:
                            std_col = c_idx
                        elif "METHOD" in txt or "INSPECTION METHOD" in txt:
                            method_col = c_idx
                    if (no_col is not None or item_col is not None) and (std_col is not None or method_col is not None):
                        header_idx = r_idx
                        break

                if header_idx is None:
                    continue

                h_row = table[header_idx]
                for c_idx, cell in enumerate(h_row):
                    if not cell:
                        continue
                    txt = str(cell).upper().replace("\n", " ").strip()
                    if no_col is None and ("ITEM" in txt or "NO" in txt) and c_idx < 5:
                        no_col = c_idx
                    if item_col is None and "ITEM" in txt:
                        item_col = c_idx
                    if std_col is None and ("STANDARD" in txt or "STD" in txt):
                        std_col = c_idx
                    if method_col is None and "METHOD" in txt:
                        method_col = c_idx

                last_balloon = ""
                last_item_name = ""
                last_method = ""

                for r_idx in range(header_idx + 1, len(table)):
                    row = table[r_idx]
                    row_all_str = " ".join([str(c) for c in row if c])
                    if any(term in row_all_str for term in ["OK POINT", "JUDGEMENT", "Dibuat", "Diperiksa", "PERCENTAGE"]):
                        break

                    cell_no = row[no_col] if no_col is not None and no_col < len(row) else None
                    cell_item = row[item_col] if item_col is not None and item_col < len(row) else None
                    cell_std = row[std_col] if std_col is not None and std_col < len(row) else None
                    cell_method = row[method_col] if method_col is not None and method_col < len(row) else None

                    # Check for sub-item tags in intermediate columns (e.g. col 7 between item and std for [ TL ] / [ BL ])
                    sub_tag = ""
                    if item_col is not None and std_col is not None and std_col > item_col + 1:
                        for mid_c in range(item_col + 1, std_col):
                            if mid_c < len(row) and row[mid_c]:
                                val = str(row[mid_c]).strip()
                                if val:
                                    sub_tag = val
                                    break

                    balloon = str(cell_no).strip() if cell_no else ""
                    m_b = re.match(r"^(\d+)", balloon)
                    if m_b:
                        balloon = m_b.group(1)
                        last_balloon = balloon
                    elif last_balloon:
                        balloon = last_balloon

                    item_name = str(cell_item).strip() if cell_item else ""
                    if "\n" in item_name:
                        item_name = item_name.split("\n")[0].strip()

                    if sub_tag and sub_tag.startswith("[") and sub_tag.endswith("]"):
                        if item_name:
                            item_name = f"{item_name} {sub_tag}"
                        elif last_item_name:
                            item_name = f"{last_item_name} {sub_tag}"
                        else:
                            item_name = sub_tag
                    elif not item_name and last_item_name:
                        item_name = last_item_name

                    if item_name:
                        last_item_name = item_name.split(" [")[0].strip()

                    std_raw = str(cell_std).strip() if cell_std else ""
                    method_raw = str(cell_method).strip() if cell_method else ""
                    if not method_raw and last_method and std_raw:
                        method_raw = last_method
                    if method_raw:
                        last_method = method_raw

                    if not std_raw and not item_name:
                        continue
                    if not std_raw and not method_raw:
                        continue

                    cleaned_std = normalize_pdf_standard(std_raw)
                    norm_method = FuzzyToolNormalizer.normalize(method_raw)

                    all_points.append({
                        "item_no": balloon or "1",
                        "inspection_item": item_name or last_item_name,
                        "standard": cleaned_std,
                        "method": norm_method,
                        "master_data": ""
                    })
    except Exception as e:
        print(f"[Warning] PDF table extraction failed: {e}, attempting line fallback.")

    if all_points:
        return all_points

    # Fallback to textual parser if table extraction returned nothing
    methods_list = [
        "Pin chk. / Caliper", "Pin chk.", "Insert Pin Datum", "Tapper Gauge", "Tapper Gg",
        "Feeler Gg", "Feeler Gauge", "Steel Ruler", "Steelrule", "Ruler Gg", "Caliper", "Visual", "Torque Wrench"
    ]
    header_skips = [
        "CUSTOMER :", "MODEL :", "DWG. No.", "DATE :", "PROD. SHIFT :",
        "FG. PART", "LEADER PROD", "LEAD PROD", "S E JUD", "INSPECTOR :",
        "CHECK SHEET", "FINAL CHECK", "REVISE NO", "REV NO :", "EFFECTIVE DATE"
    ]
    std_patterns = [
        r"(\d+(?:\.\d+)?\s*\+\s*0\s*\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?\s*\/\s*[\-\+]?\s*\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?\s*±\s*\d+(?:\.\d+)?)",
        r"(DEV\.WITHIN\s*\d+(?:\.\d+)?)",
        r"(OK\s*\/\s*NG)",
        r"([Øø]?\s*\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?(?:\s*X\s*\d+(?:\.\d+)?\s*\+\s*\d+(?:\.\d+)?)?)",
    ]

    current_balloon = "1"
    last_valid_item = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.split("\n")

            for line in lines:
                line = line.strip()
                if not line or any(h in line for h in header_skips):
                    continue

                if line.startswith("SKETCH"):
                    line = line.replace("SKETCH", "").strip()

                if re.match(r"^[\-\+0\s\/]+$", line) and all_points:
                    prev_std = all_points[-1]["standard"]
                    line_clean = line.strip()
                    if line_clean.startswith("-") or line_clean.startswith("0"):
                        all_points[-1]["standard"] = f"{prev_std} / {line_clean}".strip()
                        continue

                m_balloon = re.match(r"^(\d+)\s*(.*)", line)
                if m_balloon and int(m_balloon.group(1)) <= 400:
                    num_val = m_balloon.group(1)
                    rest = m_balloon.group(2).strip()
                    if rest:
                        current_balloon = num_val
                        line = rest
                    elif not rest and len(line) <= 3:
                        current_balloon = num_val
                        continue

                found_method = ""
                for m in methods_list:
                    if line.endswith(m):
                        found_method = m
                        line = line[:-len(m)].strip()
                        break
                    elif m.lower() in line.lower():
                        idx = line.lower().rfind(m.lower())
                        if idx >= len(line) - len(m) - 5:
                            found_method = line[idx:].strip()
                            line = line[:idx].strip()
                            break

                found_std = ""
                item_name = line
                for sp in std_patterns:
                    m_std = re.search(sp, line, re.IGNORECASE)
                    if m_std:
                        found_std = m_std.group(1).strip()
                        item_name = (line[:m_std.start()] + " " + line[m_std.end():]).strip()
                        break

                item_name = re.sub(r"\s+", " ", item_name).strip()
                if not item_name and last_valid_item:
                    item_name = last_valid_item
                elif item_name:
                    last_valid_item = item_name

                found_std = normalize_pdf_standard(found_std)
                norm_method = FuzzyToolNormalizer.normalize(found_method)

                if item_name or found_std:
                    if item_name in ["PAGE", "CHECK SHEET", "REVISE NO."]:
                        continue
                    all_points.append({
                        "item_no": current_balloon,
                        "inspection_item": item_name or "INSPECTION POINT",
                        "standard": found_std,
                        "method": norm_method,
                        "master_data": ""
                    })

    return all_points


def filter_inspection_sheets(sheetnames: List[str], filename: str = "") -> List[str]:
    """
    Filter workbook sheets to only include the active revision and valid inspection sheets.
    Excludes cover/drawing/eo sheets, superseded revisions (e.g. Rev.01 when Rev.02 exists),
    and empty sheets without inspection data.
    """
    valid_sheets = [s for s in sheetnames if not any(skip in s.lower() for skip in ["cover", "drawing", "eo"])]
    if not valid_sheets:
        return sheetnames

    # Check if filename specifies a revision e.g. Rev.02 -> '02'
    file_rev_m = re.search(r"rev\.?\s*(\d+)", filename, re.IGNORECASE)
    file_rev = file_rev_m.group(1) if file_rev_m else ""

    sheet_revs = {}
    for s in valid_sheets:
        m = re.search(r"rev\.?\s*(\d+)", s, re.IGNORECASE)
        if m:
            sheet_revs[s] = int(m.group(1))

    if sheet_revs:
        if file_rev and any(re.search(rf"rev\.?\s*0?{int(file_rev)}\b", s, re.IGNORECASE) for s in valid_sheets):
            target_int = int(file_rev)
        else:
            target_int = max(sheet_revs.values())

        filtered = [s for s in valid_sheets if sheet_revs.get(s) == target_int]
        if filtered:
            return filtered

    # Check for (rev) unnumbered revision sheets (e.g. IQC incoming files)
    rev_sheets = [s for s in valid_sheets if "(rev)" in s.lower()]
    if rev_sheets:
        if len(rev_sheets) > 1 and filename:
            fn_clean = re.sub(r"[^0-9A-Za-z]", "", filename).upper()
            matched = [s for s in rev_sheets if re.sub(r"[^0-9A-Za-z]", "", s).upper() in fn_clean]
            if matched:
                return matched
        return rev_sheets

    # If multiple sheets and filename contains a specific part number, prefer that sheet
    if len(valid_sheets) > 1 and filename:
        fn_clean = re.sub(r"[^0-9A-Za-z]", "", filename).upper()
        matched = [s for s in valid_sheets if re.sub(r"[^0-9A-Za-z]", "", s).upper() in fn_clean]
        if matched:
            return matched

    return valid_sheets


def parse_mmki_ir_sheet(ws, sheet_name: str) -> Optional[List[Dict[str, str]]]:
    """
    Dedicated parser for MMKI Multi-Page Inspection Reports (e.g. 743F4E000P, 73211E010P, 73231E000P).
    Handles merged B7:B12 item numbers, item name in C3, coordinate/position [TL],[BL],[WL] in C4,
    nominal in C5, upper/lower tolerances in C6 across split rows, and tool/method normalization.
    """
    header_row = None
    for r in range(1, min(ws.max_row + 1, 15)):
        v2 = str(ws.cell(r, 2).value or "").strip().upper()
        v5 = str(ws.cell(r, 5).value or "").strip().upper()
        if "INSPECTION ITEM" in v2 and "STANDARD" in v5:
            header_row = r
            break

    if not header_row:
        return None

    points = []
    current_balloon = "1"
    last_item_name = ""
    r = header_row + 1

    while r <= ws.max_row:
        c2 = ws.cell(r, 2).value
        c3 = ws.cell(r, 3).value
        c4 = ws.cell(r, 4).value
        c5 = ws.cell(r, 5).value
        c6 = ws.cell(r, 6).value

        # Update balloon number if present
        if c2 is not None and str(c2).strip():
            c2_str = str(c2).strip()
            if any(ch.isdigit() for ch in c2_str):
                m_no = re.search(r"\d+", c2_str)
                if m_no:
                    current_balloon = m_no.group(0)

        # Skip completely empty row
        if not any(x is not None for x in [c2, c3, c4, c5, c6]):
            r += 1
            continue

        raw_item = str(c3).strip() if c3 is not None else ""
        raw_pos = str(c4).strip() if c4 is not None else ""
        raw_std = str(c5).strip() if c5 is not None else ""
        raw_tol = str(c6).strip() if c6 is not None else ""

        # Stop if footer reached
        if any(f_kw in raw_item.upper() for f_kw in ["JUDGEMENT", "REMARK", "NOTE :"]):
            break

        # Peek next row
        nr_c2 = ws.cell(r + 1, 2).value if r + 1 <= ws.max_row else None
        nr_c3 = ws.cell(r + 1, 3).value if r + 1 <= ws.max_row else None
        nr_c4 = ws.cell(r + 1, 4).value if r + 1 <= ws.max_row else None
        nr_c5 = ws.cell(r + 1, 5).value if r + 1 <= ws.max_row else None
        nr_c6 = ws.cell(r + 1, 6).value if r + 1 <= ws.max_row else None

        item_name = raw_item or last_item_name
        if raw_item:
            last_item_name = raw_item

        # Extract method if embedded in item name (e.g. 'GAP\\n(SWING Gg.)')
        method = ""
        if "(SWING GG.)" in item_name.upper():
            method = "Swing Gauge"
            item_name = re.sub(r"(?i)\(SWING\s+GG\.?\)", "", item_name).strip()

        # Special Case 1: HOLE POSITION / INSERT PIN DATUM
        if "HOLE POSITION" in item_name.upper() or "INSERT PIN" in raw_std.upper():
            std_val = "OK / NG"
            if "MARKING CTR LINE" in raw_std.upper():
                std_val = "OK / NG (MARKING CTR LINE)"
                method = "Visual"
            elif "INSERT PIN" in raw_std.upper():
                method = "Insert Pin Datum"
                if nr_c5 and "OK" in str(nr_c5).upper():
                    r += 1  # consume 'OK / NG' subrow
            elif "OK" in raw_std.upper():
                std_val = raw_std

            points.append({
                "item_no": current_balloon,
                "inspection_item": "HOLE POSITION",
                "standard": std_val,
                "method": method or "Insert Pin Datum",
                "master_data": ""
            })
            r += 1
            continue

        # Special Case 2: Multi-row item with position in next row [TL], [BL], [WL]
        pos = raw_pos
        skip_next = False
        if not pos and nr_c4 and str(nr_c4).strip().startswith("["):
            pos = str(nr_c4).strip()
            if nr_c6 and not raw_tol:
                raw_tol = str(nr_c6).strip()
                skip_next = True
            elif nr_c6 and raw_tol and not nr_c3 and not nr_c5:
                lower_tol = str(nr_c6).strip()
                full_std, _ = SemanticStandardParser.compose_standard(
                    base_std=raw_std,
                    row_extra_tokens=[raw_tol],
                    next_row_tokens=[lower_tol]
                )
                raw_std = full_std
                raw_tol = ""
                skip_next = True

        # Special Case 3: Two-row asymmetric tolerance without pos (e.g. TRIM LINE or GAP)
        if not skip_next and nr_c6 and not nr_c2 and not nr_c3 and not nr_c5 and raw_tol:
            lower_tol = str(nr_c6).strip()
            full_std, _ = SemanticStandardParser.compose_standard(
                base_std=raw_std,
                row_extra_tokens=[raw_tol],
                next_row_tokens=[lower_tol]
            )
            raw_std = full_std
            raw_tol = ""
            skip_next = True

        # If raw_tol still present, compose with raw_std
        if raw_tol:
            full_std, _ = SemanticStandardParser.compose_standard(
                base_std=raw_std,
                row_extra_tokens=[raw_tol]
            )
            raw_std = full_std

        full_item_name = f"{item_name} {pos}".strip()
        full_item_name = re.sub(r"\[\s+", "[", full_item_name)
        full_item_name = re.sub(r"\s+\]", "]", full_item_name)

        if not method:
            if "GAP" in item_name.upper():
                method = "Tapper Gauge"
            elif "TRIM" in item_name.upper():
                method = "Caliper"
            elif "SHIM" in item_name.upper():
                method = "Feeler Gauge"
            elif "HOLE" in item_name.upper():
                method = "Caliper"
            elif "POSITION" in item_name.upper():
                method = "Caliper"
            else:
                method = "Caliper"

        if full_item_name and raw_std:
            points.append({
                "item_no": current_balloon,
                "inspection_item": full_item_name,
                "standard": raw_std,
                "method": method,
                "master_data": ""
            })

        if skip_next:
            r += 1
        r += 1

    return points


def parse_ipqc_sheet(ws, sheet_name: str) -> Optional[List[Dict[str, str]]]:
    """
    Dedicated parser for In Process Quality Control (IPQC) checksheets (e.g. 5220AB09, 5220AB10).
    Detects sheets with Appearance and Dimension sections, reading:
    - Column B: Item number / Balloon
    - Column C: Item specification / name
    - Column H: Standard / Nominal
    - Column J: Tolerance (e.g. +0.3 / -0)
    - Column L: Inspection / Method
    - Column A: Datum markers (e.g. I, II)
    Merges multi-row upper/lower tolerances into a single canonical row (e.g. '0 + 0.3 / - 0').
    """
    is_ipqc = False
    for r in range(1, min(ws.max_row + 1, 60)):
        c_val = str(ws.cell(r, 3).value or "").strip().upper()
        h_val = str(ws.cell(r, 8).value or "").strip().upper()
        l_val = str(ws.cell(r, 12).value or "").strip().upper()
        if ("APPEARANCE" in c_val or "DIMENSION" in c_val) and ("STANDARD" in h_val or "METHOD" in l_val):
            is_ipqc = True
            break

    if not is_ipqc:
        return None

    def _format_tolerance_str(s: str) -> str:
        s = s.strip()
        m = re.match(r'^([^\+\-\/±]+)?\s*[\+]+\s*([0-9\.]+)\s*\/\s*([\-\+])\s*([0-9\.]+)', s)
        if m:
            nom = (m.group(1) or "").strip()
            u = m.group(2).strip()
            sign2 = m.group(3).strip()
            l = m.group(4).strip()
            if nom:
                return f"{nom} + {u} / {sign2} {l}"
            else:
                return f"+ {u} / {sign2} {l}"
        return s

    points = []
    current_section = ""
    current_item_no = ""
    current_item_name = ""
    current_method = "Visual"
    r = 1

    while r <= ws.max_row:
        c_raw = ws.cell(r, 3).value
        c_val = "" if c_raw is None else str(c_raw).strip()
        h_raw = ws.cell(r, 8).value
        h_val = "" if h_raw is None else str(h_raw).strip()
        j_raw = ws.cell(r, 10).value
        j_val = "" if j_raw is None else str(j_raw).strip()
        l_raw = ws.cell(r, 12).value
        l_val = "" if l_raw is None else str(l_raw).strip()
        b_raw = ws.cell(r, 2).value
        b_val = "" if b_raw is None else str(b_raw).strip()
        a_raw = ws.cell(r, 1).value
        a_val = "" if a_raw is None else str(a_raw).strip()

        c_upper = c_val.upper()
        h_upper = h_val.upper()
        l_upper = l_val.upper()
        a_upper = a_val.upper()

        # Section headers
        if "APPEARANCE" in c_upper and ("STANDARD" in h_upper or "METHOD" in l_upper):
            current_section = "Appearance"
            current_method = "Visual"
            r += 1
            continue
        elif "DIMENSION" in c_upper and ("STANDARD" in h_upper or "METHOD" in l_upper):
            current_section = "Dimension"
            current_method = "Feeler Gauge"
            r += 1
            continue
        elif "JUDGEMENT" in c_upper or "JML. PROD." in a_upper or "KETERANGAN" in str(ws.cell(r, 6).value or "").upper():
            break

        if current_section:
            # Skip subheaders
            if any(k in c_upper for k in ["SPESIFIKASI", "WAKTU PENGECEKAN", "APPEARANCE", "DIMENSION"]) or any(k in h_upper for k in ["STANDARD", "AWAL PROSES", "AKHIR PROSES", "TGL", "SHIFT"]):
                r += 1
                continue

            if b_val and (b_val.isdigit() or not any(k in b_val.upper() for k in ["NO", "ITEM", "A", "B"])):
                current_item_no = b_val

            if c_val:
                current_item_name = c_val

            if l_val:
                current_method = l_val

            datum = ""
            if a_val and a_upper not in ["INSPECTOR", "SHIFT", "TGL", "PROSES", "JML. PROD.", "NO.", "NO", "JUDGEMENT"]:
                datum = a_val.strip()

            skip_next = False
            next_j_raw = ws.cell(r + 1, 10).value if r + 1 <= ws.max_row else None
            next_j = "" if next_j_raw is None else str(next_j_raw).strip()

            # Tolerance checking: merge row r and row r+1
            if j_val:
                if next_j and (next_j.startswith("-") or next_j.startswith("+")):
                    u_clean = j_val.lstrip("+").strip()
                    l_sign = "-" if next_j.startswith("-") else "+"
                    l_clean = next_j.lstrip("-+").strip()
                    std_str = f"{h_val} + {u_clean} / {l_sign} {l_clean}".strip()
                    skip_next = True
                else:
                    std_str = f"{h_val} {j_val}".strip()
            else:
                std_str = h_val

            std_formatted = _format_tolerance_str(std_str)

            # Discard orphan tolerance rows that have no nominal and start with - or +
            if not h_val and (std_formatted.startswith("-") or std_formatted.startswith("+")):
                r += 1
                continue

            if std_formatted and std_formatted.upper() not in ["STANDARD", "AWAL PROSES", "AKHIR PROSES"] and current_item_name:
                item_display = current_item_name
                if datum:
                    item_display = f"{current_item_name} [{datum}]"
                item_clean = " ".join(item_display.split())
                std_clean = " ".join(std_formatted.split())
                meth_clean = " ".join(current_method.split())

                points.append({
                    "item_no": current_item_no or "1",
                    "inspection_item": item_clean,
                    "standard": std_clean,
                    "method": meth_clean,
                    "master_data": ""
                })

            if skip_next:
                r += 1
        r += 1

    return points


def parse_iqc_incoming_sheet(ws, sheet_name: str = "") -> Optional[List[Dict[str, str]]]:
    """
    Dedicated parser for Incoming Material (IQC) checksheets (e.g. coil / raw material checks).
    Detects table header with NO, INSPECTION, STANDAR/LIMIT, ALAT/TOOLS.
    Extracts inspection points (Material Spec, Thickness, Length, Width, Appearance, Judgements).
    """
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
                elif "INSPECTION" in val and not "RESULT" in val:
                    c_item = c
                elif "STANDAR" in val or "LIMIT" in val:
                    c_std = c
                elif "ALAT" in val or "TOOL" in val:
                    c_tool = c
            break

    if not hdr_row:
        return None

    points = []
    balloon_counter = 1
    last_item = ""
    for r in range(hdr_row + 1, min(ws.max_row + 1, hdr_row + 35)):
        v_no = str(ws.cell(r, c_no).value or "").strip()
        v_item = str(ws.cell(r, c_item).value or "").strip()
        v_std = str(ws.cell(r, c_std).value or "").strip()
        v_tool = str(ws.cell(r, c_tool).value or "").strip()

        # Skip empty rows or inspection result subheaders (Date, Qty, Judg, numbers 1-5)
        if not v_item and not v_std:
            continue
        if any(skip in v_item.upper() for skip in ["DATE", "QTY", "JUDG", "JUDGEMENT"]):
            continue
        if v_item.isdigit() and len(v_item) <= 2:
            continue

        if not v_item and v_no and not v_no.isdigit():
            v_item = v_no
            v_no = ""

        # If v_item is empty but we have v_std, inherit from last_item (e.g. Conformity merged cells)
        if not v_item and last_item:
            v_item = last_item
        elif v_item:
            last_item = v_item

        item_no_str = v_no if v_no else str(balloon_counter)
        if v_no and v_no.isdigit():
            balloon_counter = int(v_no) + 1
        else:
            balloon_counter += 1

        points.append({
            "item_no": item_no_str,
            "inspection_item": " ".join(v_item.split()),
            "standard": " ".join(v_std.split()),
            "method": " ".join(v_tool.split()) if v_tool else "Visual",
            "master_data": ""
        })
    return points if points else None


def extract_inspection_points(file_path: str) -> List[Dict[str, str]]:
    """
    Extract inspection points dynamically for ANY checksheet document (Excel or PDF)
    using Hybrid Semantic Tokenizer & Spatial Adjacency Graph:
    - PDF documents (using pdfplumber & Semantic tokenizer)
    - Standard tabular Excel (Col 1: No, Col 2: Item, Col 3: Standard, Col 4: Method)
    - MMKI Final Checksheet layout (HAL 1..4, Col 18: NO, Col 20: ITEM, Col 26: STD, Col 30: Method)
    - MMKI Multi-page IR reports (PAGE 6..11)
    - MMKI IPQC Checksheets (Appearance & Dimension multi-page sheets)
    - Incoming Material (IQC) checksheets
    - Custom sheets with NO / ITEM / STANDARD headers
    """
    abs_p = os.path.abspath(file_path)
    try:
        mtime = os.path.getmtime(abs_p)
    except OSError:
        mtime = 0
    cache_key = (abs_p, mtime)
    if cache_key in _POINTS_CACHE:
        return [dict(it) for it in _POINTS_CACHE[cache_key]]

    if file_path.lower().endswith(".pdf"):
        res = extract_pdf_inspection_points(file_path)
        _POINTS_CACHE[cache_key] = res
        return [dict(it) for it in res]

    # Try specialized modular parser
    try:
        from parsers import get_parser_for_file
        mod_parser = get_parser_for_file(file_path)
        mod_points = mod_parser.extract_inspection_points(file_path)
        if mod_points:
            _POINTS_CACHE[cache_key] = mod_points
            return [dict(it) for it in mod_points]
    except Exception:
        pass

    wb = None
    all_items = []
    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        target_sheets = filter_inspection_sheets(wb.sheetnames, filename=os.path.basename(file_path))

        for sheet_name in target_sheets:
            # Skip cover or drawing-only sheets
            if any(skip in sheet_name.lower() for skip in ["cover", "drawing", "eo"]):
                continue

            ws = wb[sheet_name]

            # Specialized layout parser for MMKI Multi-page Inspection Reports (PAGE 6..11)
            mmki_points = parse_mmki_ir_sheet(ws, sheet_name)
            if mmki_points is not None:
                all_items.extend(mmki_points)
                continue

            # Specialized layout parser for In Process Quality Control (IPQC) checksheets
            ipqc_points = parse_ipqc_sheet(ws, sheet_name)
            if ipqc_points is not None:
                all_items.extend(ipqc_points)
                continue

            # Specialized layout parser for Incoming Inspection (IQC Material) checksheets
            iqc_points = parse_iqc_incoming_sheet(ws, sheet_name)
            if iqc_points is not None:
                all_items.extend(iqc_points)
                continue

            header_row = None
            col_no = None
            col_name = None
            col_std = None
            col_method = None
            col_master = None
            col_pos = None
    
            # Scan rows 1 to 60 across columns 1 to 70
            for r in range(1, min(ws.max_row + 1, 60)):
                c_no = None
                c_name = None
                c_std = None
                c_meth = None
                c_mast = None
    
                for c in range(1, min(ws.max_column + 1, 70)):
                    v = str(ws.cell(r, c).value or "").strip().upper()
                    if not v:
                        continue
    
                    if v in ["NO", "NO.", "ITEM", "NO. / ITEM", "ITEM NO"] and c_no is None:
                        c_no = c
                    elif ("INSPECTION ITEM" in v or v in ["ITEM", "ITEM NAME"]) and c_name is None and c != c_no:
                        c_name = c
                    elif ("STANDARD" in v or v in ["STD", "STANDAR"]) and c_std is None:
                        c_std = c
                    elif ("METHOD" in v or "INSPECTION" in v) and c_meth is None and c != c_name and c != c_no:
                        if "METHOD" in v or any("METHOD" in str(ws.cell(sub_r, c).value or "").upper() for sub_r in range(r, min(ws.max_row + 1, r + 6))):
                            c_meth = c
                    elif ("MASTER" in v) and c_mast is None:
                        c_mast = c
    
                if (c_name or c_no) and c_std:
                    header_row = r
                    col_no = c_no
                    col_name = c_name or (c_no + 1 if c_no else 2)
                    col_std = c_std
                    col_method = c_meth
                    col_master = c_mast
                    break
    
            # Fallback to PAGE check for multi-page IR format
            if not header_row and sheet_name.upper().startswith("PAGE") and any(ch.isdigit() for ch in sheet_name):
                for r in range(1, min(ws.max_row + 1, 15)):
                    row_vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, min(ws.max_column + 1, 20))]
                    if any("Inspection Item" in v for v in row_vals) and any("Standard" in v for v in row_vals):
                        header_row = r
                        col_no = 2
                        col_name = 3
                        col_pos = 4
                        for c in range(1, min(ws.max_column + 1, 15)):
                            hv = str(ws.cell(r, c).value or "").strip()
                            if "Standard" in hv:
                                col_std = c
                        break
    
            if not header_row:
                continue
    
            # Detect position column if between col_name and col_std
            if col_name and col_std and col_std > col_name + 1 and not col_pos:
                col_pos = col_std - 1
    
            current_balloon = "1"
            last_item_name = ""
            r = header_row + 1
    
            while r <= ws.max_row:
                c_no_val = ws.cell(r, col_no).value if col_no else None
                c_name_val = ws.cell(r, col_name).value if col_name else None
    
                # Check if this row is a judgement / remark / footer row
                if SpatialBlockDetector.is_footer_row([c_no_val, c_name_val]):
                    break
    
                if c_no_val is not None and str(c_no_val).strip():
                    raw_no = str(c_no_val).strip()
                    if any(ch.isdigit() for ch in raw_no) and len(raw_no) <= 12:
                        m = re.search(r"\d+", raw_no)
                        current_balloon = m.group(0) if m else raw_no
    
                raw_item_name = str(c_name_val).strip() if c_name_val is not None else ""
    
                # Check standard span across columns [col_std .. max_tol_c - 1]
                max_tol_c = col_method if col_method and col_method > col_std else (col_std + 4)
                std_cells = []
                for tc in range(col_std, min(ws.max_column + 1, max_tol_c)):
                    tv = ws.cell(r, tc).value
                    if tv is not None and str(tv).strip():
                        std_cells.append((tc, str(tv).strip()))
    
                std_raw = std_cells[0][1] if std_cells else ""
                extra_tokens = [v for _, v in std_cells[1:]] if len(std_cells) > 1 else []
    
                # Skip header rows if repeated
                if SpatialBlockDetector.is_header_noise(raw_item_name):
                    r += 1
                    continue
    
                raw_method = str(ws.cell(r, col_method).value or "").strip() if col_method else ""
    
                # Determine item name (inherits from last_item_name for multi-row items like APPEARANCE or NUT POSITION)
                item_name = ""
                if raw_item_name:
                    item_name = raw_item_name
                    last_item_name = raw_item_name
                elif (std_raw or raw_method or (col_pos and ws.cell(r, col_pos).value)) and last_item_name:
                    item_name = last_item_name
    
                # Process row if we have an item name and standard value or method
                if item_name and (std_raw or raw_method or (col_pos and ws.cell(r, col_pos).value)):
                    pos = ""
                    if col_pos:
                        pv = ws.cell(r, col_pos).value
                        next_pv = ws.cell(r + 1, col_pos).value if r + 1 <= ws.max_row else None
                        if pv and str(pv).strip():
                            pos = str(pv).strip()
                        elif next_pv and "[" in str(next_pv) and not raw_item_name:
                            pos = str(next_pv).strip()
    
                    full_name = f"{item_name} {pos}".strip()
                    full_name = re.sub(r"\[\s+", "[", full_name)
                    full_name = re.sub(r"\s+\]", "]", full_name)
    
                    # Vertical next row continuation tokens
                    next_row_tokens = []
                    is_hole_size_cont = False
                    if r + 1 <= ws.max_row:
                        next_name = str(ws.cell(r + 1, col_name).value or "").strip() if col_name else ""
                        next_no = str(ws.cell(r + 1, col_no).value or "").strip() if col_no else ""
                        next_meth = str(ws.cell(r + 1, col_method).value or "").strip() if col_method else ""

                        if "HOLE" in item_name.upper() and next_name.upper() == "HOLE SIZE":
                            next_std_val = ws.cell(r + 1, col_std).value if col_std else None
                            if not next_std_val:
                                is_hole_size_cont = True

                        # Only check continuation if next row is not an independent item and not a footer
                        if (not next_name or is_hole_size_cont) and not next_no and not next_meth and not SpatialBlockDetector.is_footer_row([next_no, next_name]):
                            if is_hole_size_cont:
                                full_name = f"{full_name} - {next_name}".strip()
                            for tc in range(col_std, min(ws.max_column + 1, max_tol_c)):
                                ntv = ws.cell(r + 1, tc).value
                                if ntv is not None and str(ntv).strip():
                                    next_row_tokens.append(str(ntv).strip())
    
                    # Semantic compose standard and tolerance
                    full_std, skip_next = SemanticStandardParser.compose_standard(
                        base_std=std_raw,
                        row_extra_tokens=extra_tokens,
                        next_row_tokens=next_row_tokens
                    )
    
                    meth_val = FuzzyToolNormalizer.normalize(raw_method)
                    mast_val = str(ws.cell(r, col_master).value or "").strip() if col_master else ""
    
                    all_items.append({
                        "item_no": current_balloon,
                        "inspection_item": full_name,
                        "standard": full_std,
                        "method": meth_val,
                        "master_data": mast_val
                    })
    
                    if skip_next or is_hole_size_cont:
                        r += 1
    
                r += 1
    
    finally:
        if wb:
            try:
                wb.close()
            except Exception:
                pass

    _POINTS_CACHE[cache_key] = all_items
    return all_items
