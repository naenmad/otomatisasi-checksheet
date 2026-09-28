"""
Image extraction and filtering utility for checksheet drawings.
Extracts sketch drawings from Excel/PDF documents while aggressively filtering out
company logos, stamps, datum markers, and non-sketch graphics, then converts to WebP.
"""
import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Optional

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imagecodecs
except ImportError:
    imagecodecs = None

# Known dimensions of non-sketch elements (Summit logo, Customer badges, ISO stamps)
KNOWN_LOGO_DIMENSIONS = {
    (115, 60),    # Small logo badge
    (245, 65),    # Summit Adyawinsa header banner
    (323, 126),   # Summit Adyawinsa large header logo with URS badge
    (180, 50),    # HPM header stamp
    (120, 120),   # Circular ISO certification logo
    (90, 90),     # Small approval box stamp
    (64, 64),     # Generic small icon
    (461, 201),   # Header logo banner in SIM/TMMIN checksheets
}


import struct


def decode_emf_bytes(data: bytes):
    """Safely extract embedded bitmap/jpeg/png from EMF format."""
    if not Image or not data:
        return None
    # 1. Scan for embedded JPEG
    j_start = data.find(b'\xff\xd8\xff')
    if j_start != -1:
        j_end = data.find(b'\xff\xd9', j_start)
        if j_end != -1:
            try:
                return Image.open(io.BytesIO(data[j_start:j_end+2]))
            except Exception:
                pass

    # 2. Scan for embedded PNG
    p_start = data.find(b'\x89PNG\r\n\x1a\n')
    if p_start != -1:
        p_end = data.find(b'IEND', p_start)
        if p_end != -1:
            try:
                return Image.open(io.BytesIO(data[p_start:p_end+8]))
            except Exception:
                pass

    # 3. Parse EMF records for EMR_STRETCHDIBITS (81) and EMR_BITBLT (76)
    offset = 0
    while offset + 8 <= len(data):
        rec_type, rec_size = struct.unpack('<II', data[offset:offset+8])
        if rec_size < 8 or offset + rec_size > len(data):
            break
        rec_data = data[offset:offset+rec_size]

        if rec_type == 81 and rec_size >= 64:  # EMR_STRETCHDIBITS
            off_bmi, cb_bmi, off_bits, cb_bits = struct.unpack('<IIII', rec_data[48:64])
            if off_bmi + cb_bmi <= rec_size and off_bits + cb_bits <= rec_size and cb_bmi > 0 and cb_bits > 0:
                bmi = rec_data[off_bmi:off_bmi+cb_bmi]
                bits = rec_data[off_bits:off_bits+cb_bits]
                bmp_header = struct.pack('<2sIHHI', b'BM', 14 + len(bmi) + len(bits), 0, 0, 14 + len(bmi))
                try:
                    return Image.open(io.BytesIO(bmp_header + bmi + bits))
                except Exception:
                    pass

        elif rec_type == 76 and rec_size >= 100:  # EMR_BITBLT
            off_bmi, cb_bmi, off_bits, cb_bits = struct.unpack('<IIII', rec_data[84:100])
            if off_bmi + cb_bmi <= rec_size and off_bits + cb_bits <= rec_size and cb_bmi > 0 and cb_bits > 0:
                bmi = rec_data[off_bmi:off_bmi+cb_bmi]
                bits = rec_data[off_bits:off_bits+cb_bits]
                bmp_header = struct.pack('<2sIHHI', b'BM', 14 + len(bmi) + len(bits), 0, 0, 14 + len(bmi))
                try:
                    return Image.open(io.BytesIO(bmp_header + bmi + bits))
                except Exception:
                    pass

        offset += rec_size

    return None


def decode_image_bytes(raw_data: bytes, ext: str):
    """Safely decode image bytes from PNG, JPEG, WEBP, WDP (JPEG-XR), or EMF/WMF."""
    if not Image:
        return None
    ext = ext.lower().lstrip(".")
    if ext in ("emf", "wmf"):
        return decode_emf_bytes(raw_data)
    if ext in ("wdp", "jxr", "hdp"):
        if imagecodecs:
            try:
                arr = imagecodecs.jpegxr_decode(raw_data)
                return Image.fromarray(arr)
            except Exception:
                return None
        return None
    try:
        return Image.open(io.BytesIO(raw_data))
    except Exception:
        return None


def extract_excel_images(file_path: str, output_dir: Optional[str] = None, part_number: str = "") -> List[str]:
    """
    Extract ONLY part sketch drawings from Excel checksheets (.xlsx).
    Strictly filters out company logos, header icons, stamp marks, and non-sketch graphics.
    """
    if not output_dir:
        sub = part_number or os.path.splitext(os.path.basename(file_path))[0]
        sub = re.sub(r"[^0-9A-Za-z_-]", "_", sub)
        output_dir = os.path.join("storage", "images", sub)

    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []

    # First check if the workbook has DrawingML composite group shapes (drawings with vector annotations)
    try:
        from scripts.reextract_composite_drawings import render_drawingml_composite
        composite_im = render_drawingml_composite(file_path)
        if composite_im is not None:
            out_file = os.path.join(output_dir, "sketch_1.webp")
            composite_im.save(out_file, "WEBP", quality=85, method=6)
            extracted_paths.append(os.path.abspath(out_file))
            return extracted_paths
    except Exception as e:
        pass

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

            for sheet_target, _ in sheet_targets.items():
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
                            rel_type = d_r.attrib.get("Type", "").lower()
                            if any(k in rel_type for k in ("image", "hdphoto", "picture")):
                                t = d_r.attrib.get("Target", "").replace("../", "xl/")
                                if not t.startswith("xl/"):
                                    t = "xl/" + t.lstrip("/")
                                media_map[d_r.attrib["Id"]] = t

                        d_xml = ET.fromstring(z.read(d_path))
                        for child in d_xml:
                            for blip in child.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                                embed = (
                                    blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                                    or blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link")
                                )
                                media_file = media_map.get(embed)
                                if not media_file or media_file not in z.namelist():
                                    continue

                                from_c = child.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}from")
                                f_r = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row").text) + 1 if from_c is not None else 1
                                f_c = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}col").text) + 1 if from_c is not None else 1

                                # 3. File type check (supports raster and EMF/WMF with embedded bitmaps)
                                ext = media_file.lower().split(".")[-1]
                                if ext not in ("png", "jpg", "jpeg", "webp", "wdp", "jxr", "hdp", "emf", "wmf"):
                                    continue

                                # 4. Check file size
                                data = z.read(media_file)
                                if len(data) < 1500:
                                    continue

                                # Header logo filter: top 4 rows and left 4 columns unconditionally
                                if f_r <= 4 and f_c <= 4:
                                    continue

                                # 5. Check image dimensions with PIL
                                is_logo = False
                                im = decode_image_bytes(data, ext)
                                if not im:
                                    continue
                                w, h = im.size
                                if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                    is_logo = True
                                elif w < 80 or h < 40:
                                    is_logo = True
                                elif f_r <= 4 and f_c <= 4 and (w < 480 and h < 220):
                                    is_logo = True

                                if is_logo:
                                    continue

                                if media_file not in seen_media:
                                    seen_media.add(media_file)
                                    anchored_sketches.append(media_file)

            # Fallback: if no anchored sketches identified, look directly at xl/media/
            if not anchored_sketches:
                for n in z.namelist():
                    ext = n.lower().split(".")[-1]
                    if "media/" in n and ext in ("png", "jpg", "jpeg", "webp", "wdp", "jxr", "hdp", "emf", "wmf"):
                        data = z.read(n)
                        if len(data) < 2000:
                            continue
                        im = decode_image_bytes(data, ext)
                        if im:
                            w, h = im.size
                            if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                continue
                            if w < 100 or h < 50:
                                continue
                        if n not in seen_media:
                            seen_media.add(n)
                            anchored_sketches.append(n)

            # Clean existing files in output_dir
            for old_f in os.listdir(output_dir):
                if old_f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    try:
                        os.remove(os.path.join(output_dir, old_f))
                    except Exception:
                        pass

            # Write only valid sketches to output_dir
            for idx, media_file in enumerate(anchored_sketches, start=1):
                ext = media_file.lower().split(".")[-1]
                raw_data = z.read(media_file)
                im = decode_image_bytes(raw_data, ext)
                if im:
                    try:
                        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                            im_c = im.convert("RGBA")
                        else:
                            im_c = im.convert("RGB")
                        out_file = os.path.join(output_dir, f"sketch_{idx}.webp")
                        im_c.save(out_file, "WEBP", quality=85, method=6)
                        extracted_paths.append(os.path.abspath(out_file))
                        continue
                    except Exception:
                        pass

                out_name = f"sketch_{idx}.{ext}"
                out_file = os.path.join(output_dir, out_name)
                with open(out_file, "wb") as f:
                    f.write(raw_data)
                extracted_paths.append(os.path.abspath(out_file))

    except Exception as e:
        print(f"[Warning] Error extracting Excel reference images: {e}")

    return extracted_paths


def get_workbook_sheet_drawing_map(z: zipfile.ZipFile) -> Dict[str, str]:
    """
    Precomputes mapping from clean sheet name to drawing XML path in xl/drawings/.
    Parses workbook relationships once per workbook in ~2ms.
    """
    sheet_drawings = {}
    if "xl/workbook.xml" not in z.namelist() or "xl/_rels/workbook.xml.rels" not in z.namelist():
        return sheet_drawings

    wb_xml = ET.fromstring(z.read("xl/workbook.xml"))
    wb_rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "pr": "http://schemas.openxmlformats.org/package/2006/relationships"
    }

    rel_to_target = {}
    for rel in wb_rels.findall("pr:Relationship", ns):
        t = rel.attrib.get("Target", "")
        if not t.startswith("xl/"):
            t = "xl/" + t
        rel_to_target[rel.attrib.get("Id")] = t

    sheet_to_target = {}
    for s in wb_xml.findall("main:sheets/main:sheet", ns):
        sname = s.attrib.get("name", "").strip().lower()
        rid = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        if rid in rel_to_target:
            sheet_to_target[sname] = rel_to_target[rid]

    for sname, sheet_path in sheet_to_target.items():
        srel_file = sheet_path.replace("worksheets/", "worksheets/_rels/") + ".rels"
        if srel_file in z.namelist():
            srels = ET.fromstring(z.read(srel_file))
            for rel in srels.findall("pr:Relationship", ns):
                if "drawing" in rel.attrib.get("Type", ""):
                    dt = rel.attrib.get("Target", "").replace("../", "xl/")
                    drawing_target = dt if dt.startswith("xl/") else "xl/" + dt
                    sheet_drawings[sname] = drawing_target
                    break

    return sheet_drawings


def extract_sheet_images(
    file_path: str,
    sheet_name: str,
    part_number: str = "",
    output_dir: Optional[str] = None,
    z: Optional[zipfile.ZipFile] = None,
    drawing_target: Optional[str] = None
) -> List[str]:
    """
    Extract ONLY the reference sketch drawings that belong specifically to `sheet_name`
    in a multi-sheet or single-sheet Excel workbook (.xlsx).
    Guarantees drawings from different sheets do not bleed across parts.
    Properly decodes PNG, JPEG, and Windows HD Photo (.wdp / JPEG-XR),
    filters out header logos, and converts to optimized WebP.
    """
    if not output_dir:
        sub = part_number or sheet_name or os.path.splitext(os.path.basename(file_path))[0]
        sub = re.sub(r"[^0-9A-Za-z_-]", "_", sub)
        output_dir = os.path.join("storage", "images", sub)

    os.makedirs(output_dir, exist_ok=True)
    extracted_paths = []

    if not z and (not file_path.lower().endswith(".xlsx") or not zipfile.is_zipfile(file_path)):
        return []

    ns = {
        "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "pr": "http://schemas.openxmlformats.org/package/2006/relationships"
    }

    def _process_zip(z_obj):
        nonlocal drawing_target
        if not drawing_target:
            if "xl/workbook.xml" not in z_obj.namelist() or "xl/_rels/workbook.xml.rels" not in z_obj.namelist():
                return []

            wb_xml = ET.fromstring(z_obj.read("xl/workbook.xml"))

            sheet_rid = None
            clean_sname = sheet_name.strip().lower()
            for s in wb_xml.findall("main:sheets/main:sheet", ns):
                curr_name = s.attrib.get("name", "").strip().lower()
                if curr_name == clean_sname:
                    sheet_rid = s.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                    break

            if not sheet_rid:
                return []

            wb_rels = ET.fromstring(z_obj.read("xl/_rels/workbook.xml.rels"))
            sheet_target = None
            for rel in wb_rels.findall("pr:Relationship", ns):
                if rel.attrib.get("Id") == sheet_rid:
                    sheet_target = rel.attrib.get("Target", "")
                    if not sheet_target.startswith("xl/"):
                        sheet_target = "xl/" + sheet_target
                    break

            if not sheet_target:
                return []

            srel_file = sheet_target.replace("worksheets/", "worksheets/_rels/") + ".rels"
            if srel_file not in z_obj.namelist():
                return []

            srels = ET.fromstring(z_obj.read(srel_file))
            for rel in srels.findall("pr:Relationship", ns):
                if "drawing" in rel.attrib.get("Type", ""):
                    dt = rel.attrib.get("Target", "").replace("../", "xl/")
                    drawing_target = dt if dt.startswith("xl/") else "xl/" + dt
                    break

        if not drawing_target or drawing_target not in z_obj.namelist():
            return []

        drel_file = drawing_target.replace("drawings/", "drawings/_rels/") + ".rels"
        media_map = {}
        if drel_file in z_obj.namelist():
            drels = ET.fromstring(z_obj.read(drel_file))
            for rel in drels.findall("pr:Relationship", ns):
                rel_type = rel.attrib.get("Type", "").lower()
                if any(k in rel_type for k in ("image", "hdphoto", "picture")):
                    t = rel.attrib.get("Target", "").replace("../", "xl/")
                    if not t.startswith("xl/"):
                        t = "xl/" + t.lstrip("/")
                    media_map[rel.attrib["Id"]] = t

        dxml = ET.fromstring(z_obj.read(drawing_target))
        seen_media = set()
        valid_media_list = []

        for child in dxml:
            for blip in child.findall(".//{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
                embed = (
                    blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
                    or blip.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}link")
                )
                media_file = media_map.get(embed)
                if not media_file or media_file not in z_obj.namelist():
                    continue

                if media_file in seen_media:
                    continue

                ext = media_file.lower().split(".")[-1]
                if ext in ("bin",):
                    continue

                from_c = child.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}from")
                f_r = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}row").text) + 1 if from_c is not None else 1
                f_c = int(from_c.find("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}col").text) + 1 if from_c is not None else 1

                raw_data = z_obj.read(media_file)
                if len(raw_data) < 1500:
                    continue

                im = decode_image_bytes(raw_data, ext)
                if not im:
                    continue

                w, h = im.size
                if (w, h) in KNOWN_LOGO_DIMENSIONS:
                    continue
                if w < 80 or h < 40:
                    continue
                if f_r <= 4 and f_c <= 4 and (w < 480 and h < 220):
                    continue

                seen_media.add(media_file)
                valid_media_list.append((media_file, ext, raw_data, im))

        # Clean existing image files in output_dir
        for old_f in os.listdir(output_dir):
            if old_f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".wdp")):
                try:
                    os.remove(os.path.join(output_dir, old_f))
                except Exception:
                    pass

        # Write converted sketches
        for idx, (m_path, ext, raw_bytes, im) in enumerate(valid_media_list, start=1):
            if im:
                try:
                    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                        im_c = im.convert("RGBA")
                    else:
                        im_c = im.convert("RGB")
                    out_file = os.path.join(output_dir, f"sketch_{idx}.webp")
                    im_c.save(out_file, "WEBP", quality=85, method=6)
                    extracted_paths.append(os.path.abspath(out_file))
                    continue
                except Exception as e:
                    print(f"[Warning] Failed to save webp for {m_path}: {e}")

            out_file = os.path.join(output_dir, f"sketch_{idx}.{ext}")
            with open(out_file, "wb") as f:
                f.write(raw_bytes)
            extracted_paths.append(os.path.abspath(out_file))

    try:
        if z is not None:
            _process_zip(z)
        else:
            with zipfile.ZipFile(file_path, "r") as z_local:
                _process_zip(z_local)
    except Exception as e:
        print(f"[Warning] Error extracting sheet images for {sheet_name} in {file_path}: {e}")

    return extracted_paths
