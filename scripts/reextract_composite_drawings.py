"""
Re-extract composite DrawingML drawings from Excel checksheets.
Properly merges Excel overlay shapes (1, 2, 3, 4, thickness rectangle, arrows)
with the base image into a single complete sketch drawing, then uploads to Supabase.
"""
import io
import os
import re
import glob
import zipfile
import asyncio
from PIL import Image, ImageDraw, ImageFont
import xml.etree.ElementTree as ET

from database.connection import AsyncSessionLocal
from database.models import Checksheet, PartImage
from database.crud import clean_str
from services.supabase_storage_service import upload_file_to_supabase
from sqlalchemy import select
from sqlalchemy.orm import selectinload


def render_drawingml_composite(xlsx_path: str) -> Image.Image:
    """Render composite drawing from Excel if grpSp or drawing shapes are present."""
    if not os.path.exists(xlsx_path):
        return None

    try:
        with zipfile.ZipFile(xlsx_path, 'r') as z:
            drawing_files = [n for n in z.namelist() if n.startswith('xl/drawings/drawing') and not n.endswith('.rels')]
            if not drawing_files:
                return None

            for d_file in drawing_files:
                rels_file = d_file.replace('drawings/', 'drawings/_rels/') + '.rels'
                media_map = {}
                if rels_file in z.namelist():
                    r_root = ET.fromstring(z.read(rels_file))
                    for rel in r_root.findall('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                        if 'image' in rel.attrib.get('Type', ''):
                            media_map[rel.attrib['Id']] = rel.attrib['Target'].replace('../', 'xl/')

                content = z.read(d_file).decode('utf-8', errors='ignore')
                root = ET.fromstring(content)

                # Look for grpSp containing pic
                grp = root.find('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}grpSp')
                if grp is None:
                    continue

                pic = grp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}pic')
                if pic is None:
                    continue

                blip = pic.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}blip')
                if blip is None:
                    continue
                embed = blip.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                media_file = media_map.get(embed)
                if not media_file or media_file not in z.namelist():
                    continue

                base_img = Image.open(io.BytesIO(z.read(media_file))).convert('RGBA')

                # Group coordinate space
                grpPr = grp.find('{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}grpSpPr')
                xfrm = grpPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
                chOff = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}chOff')
                chExt = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}chExt')

                ox = int(chOff.attrib['x'])
                oy = int(chOff.attrib['y'])
                ow = int(chExt.attrib['cx'])
                oh = int(chExt.attrib['cy'])

                pic_xfrm = pic.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
                pic_ext = pic_xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
                pic_w_emu = int(pic_ext.attrib['cx'])
                pic_h_emu = int(pic_ext.attrib['cy'])

                scale_x = base_img.width / pic_w_emu
                scale_y = base_img.height / pic_h_emu
                scale = (scale_x + scale_y) / 2

                pad = 20
                canvas_w = int(ow * scale) + pad * 2
                canvas_h = int(oh * scale) + pad * 2
                canvas = Image.new('RGBA', (canvas_w, canvas_h), (255, 255, 255, 255))
                draw = ImageDraw.Draw(canvas)

                # Paste base image
                pic_off = pic_xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
                px = int((int(pic_off.attrib['x']) - ox) * scale) + pad
                py = int((int(pic_off.attrib['y']) - oy) * scale) + pad
                canvas.paste(base_img, (px, py), base_img if base_img.mode == 'RGBA' else None)

                # Fonts
                try:
                    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 14)
                except Exception:
                    try:
                        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 14)
                    except Exception:
                        font = ImageFont.load_default()

                # Iterate all shapes in group
                for sp in grp.findall('{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}sp'):
                    sp_xfrm = sp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm')
                    if sp_xfrm is None: continue
                    off = sp_xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
                    ext = sp_xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
                    if off is None or ext is None: continue

                    sx = int((int(off.attrib['x']) - ox) * scale) + pad
                    sy = int((int(off.attrib['y']) - oy) * scale) + pad
                    sw = int(int(ext.attrib['cx']) * scale)
                    sh = int(int(ext.attrib['cy']) * scale)

                    geom = sp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}prstGeom')
                    geom_type = geom.attrib.get('prst') if geom is not None else ''

                    text_nodes = sp.findall('.//{http://schemas.openxmlformats.org/drawingml/2006/main}t')
                    text_str = ''.join([t.text for t in text_nodes if t.text])

                    head_end = sp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}headEnd')
                    tail_end = sp.find('.//{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd')
                    has_head_arrow = head_end is not None and head_end.attrib.get('type') == 'triangle'
                    has_tail_arrow = tail_end is not None and tail_end.attrib.get('type') == 'triangle'

                    if geom_type == 'ellipse':
                        draw.ellipse([sx, sy, sx + sw, sy + sh], fill='white', outline='black', width=2)
                        if text_str:
                            bbox = draw.textbbox((0, 0), text_str, font=font)
                            tw = bbox[2] - bbox[0]
                            th = bbox[3] - bbox[1]
                            draw.text((sx + (sw - tw) / 2, sy + (sh - th) / 2 - 1), text_str, fill='black', font=font)
                    elif geom_type == 'rect':
                        draw.rectangle([sx, sy, sx + sw, sy + sh], fill='white', outline='black', width=2)
                    elif geom_type == 'line':
                        x1, y1 = sx, sy
                        x2, y2 = sx + sw, sy + sh
                        draw.line([(x1, y1), (x2, y2)], fill='black', width=1)
                        if has_head_arrow:
                            if x1 == x2:
                                draw.polygon([(x1, y1), (x1 - 3, y1 + 7), (x1 + 3, y1 + 7)], fill='black')
                            else:
                                draw.polygon([(x1, y1), (x1 + 7, y1 - 3), (x1 + 7, y1 + 3)], fill='black')
                        if has_tail_arrow:
                            if x1 == x2:
                                draw.polygon([(x2, y2), (x2 - 3, y2 - 7), (x2 + 3, y2 - 7)], fill='black')
                            else:
                                draw.polygon([(x2, y2), (x2 - 7, y2 - 3), (x2 - 7, y2 + 3)], fill='black')

                return canvas

    except Exception as e:
        print(f"Error rendering composite for {xlsx_path}: {e}")

    return None


async def process_all():
    async with AsyncSessionLocal() as session:
        stmt = select(Checksheet).options(selectinload(Checksheet.images))
        res = await session.execute(stmt)
        checksheets = res.scalars().all()
        print(f"Found {len(checksheets)} checksheets in database.")

        updated_count = 0

        for cs in checksheets:
            if not cs.raw_file_path or not cs.raw_file_path.endswith('.xlsx'):
                continue
            if not os.path.exists(cs.raw_file_path):
                continue

            composite = render_drawingml_composite(cs.raw_file_path)
            if not composite:
                continue

            clean_p = clean_str(cs.part_number) or "default"
            save_dir = os.path.join("storage", "images", clean_p)
            os.makedirs(save_dir, exist_ok=True)
            out_file = os.path.join(save_dir, "sketch_1.webp")

            composite.save(out_file, "WEBP", quality=88, method=6)

            # Upload to Supabase Storage
            remote_path = f"{clean_p}/sketch_1.webp"
            remote_url = upload_file_to_supabase(out_file, remote_path)
            if not remote_url:
                remote_url = f"/media/images/{clean_p}/sketch_1.webp"

            # Update or create PartImage record
            if cs.images:
                # Update existing first image
                first_img = cs.images[0]
                first_img.image_path = os.path.abspath(out_file)
                first_img.image_url = remote_url
            else:
                new_img = PartImage(
                    checksheet_id=cs.id,
                    image_path=os.path.abspath(out_file),
                    image_url=remote_url
                )
                session.add(new_img)

            updated_count += 1
            if updated_count % 20 == 0:
                print(f"Rendered & uploaded {updated_count} composite drawings...")

        await session.commit()
        print(f"DONE! Total {updated_count} checksheets updated with complete composite drawings!")


if __name__ == "__main__":
    asyncio.run(process_all())
