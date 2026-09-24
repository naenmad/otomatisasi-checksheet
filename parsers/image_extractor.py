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

# Known dimensions of non-sketch elements (Summit logo, Customer badges, ISO stamps)
KNOWN_LOGO_DIMENSIONS = {
    (115, 60),    # Small logo badge
    (245, 65),    # Summit Adyawinsa header banner
    (180, 50),    # HPM header stamp
    (120, 120),   # Circular ISO certification logo
    (90, 90),     # Small approval box stamp
    (64, 64),     # Generic small icon
}


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

                            # 3. File type check (exclude vector stamp formats like EMF/WMF)
                            if not media_file.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                                continue

                            # 4. Check file size
                            data = z.read(media_file)
                            if len(data) < 2000:
                                continue

                            # 5. Check image dimensions with PIL
                            is_logo = False
                            if Image:
                                try:
                                    with Image.open(io.BytesIO(data)) as im:
                                        w, h = im.size
                                        if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                            is_logo = True
                                        elif w < 80 or h < 40:
                                            is_logo = True
                                        # Only consider top-left a logo if dimensions are small like a banner/badge
                                        elif f_r <= 4 and f_c <= 3 and w <= 200 and h <= 80:
                                            is_logo = True
                                except Exception:
                                    pass

                            if is_logo:
                                continue

                            if media_file not in seen_media:
                                seen_media.add(media_file)
                                anchored_sketches.append(media_file)

            # Fallback: if no anchored sketches identified, look directly at xl/media/
            if not anchored_sketches:
                for n in z.namelist():
                    if "media/" in n and n.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                        data = z.read(n)
                        if len(data) < 2500:
                            continue
                        if Image:
                            try:
                                with Image.open(io.BytesIO(data)) as im:
                                    w, h = im.size
                                    if (w, h) in KNOWN_LOGO_DIMENSIONS:
                                        continue
                                    if w < 100 or h < 50:
                                        continue
                            except Exception:
                                pass
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
