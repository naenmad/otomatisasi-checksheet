"""
Parser service that orchestrates file parsing, catalog matching, and database persistence.
"""
import os
import json
import re
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from parsers import get_parser_for_file
from database.crud import create_checksheet

# Load FactoryHub catalog cache
CATALOG_PATH = "data/factoryhub_catalog.json"
_mp_cache = {}
_tpl_cache = {}

if os.path.exists(CATALOG_PATH):
    try:
        with open(CATALOG_PATH, "r") as f:
            cat = json.load(f)

        def _clean(s: str) -> str:
            return re.sub(r"[^a-zA-Z0-9]", "", str(s)).upper()

        _mp_cache = {_clean(p["part_number"]): p for p in cat.get("parts", [])}
        _tpl_cache = {_clean(t["part_number"]): t for t in cat.get("templates", [])}
    except Exception as e:
        print(f"[Warning] Failed loading catalog cache: {e}")


def match_catalog_status(part_number: str) -> Dict[str, str]:
    """Determine checksheet status based on FactoryHub catalog."""
    clean_pno = re.sub(r"[^a-zA-Z0-9]", "", str(part_number)).upper()

    if clean_pno in _tpl_cache:
        t_info = _tpl_cache[clean_pno]
        return {
            "status": "Checksheet Done",
            "keterangan": f"Sudah ada template di FactoryHub ({t_info.get('status', 'ACTIVE')})"
        }

    if clean_pno in _mp_cache:
        p_info = _mp_cache[clean_pno]
        if p_info.get("has_template"):
            return {
                "status": "Checksheet Done",
                "keterangan": "Sudah ada template di FactoryHub"
            }
        else:
            return {
                "status": "Belum Di Input",
                "keterangan": "Part terdaftar di Master Part, siap diinput template"
            }

    return {
        "status": "Tidak Ada Part",
        "keterangan": "Part belum terdaftar di Master Part FactoryHub"
    }


async def parse_and_save_checksheet(
    session: AsyncSession,
    file_path: str,
    assigned_to: str = "Zul",
    custom_doc_no: Optional[str] = None
) -> Dict[str, Any]:
    """Parse checksheet file and persist directly into database."""
    parser = get_parser_for_file(file_path)
    meta = parser.extract_metadata(file_path)

    part_no = meta.get("part_number") or os.path.splitext(os.path.basename(file_path))[0]
    part_name = meta.get("part_name", "")
    model = meta.get("model", "-")
    customer = meta.get("customer", "PT. HPM")
    doc_no = custom_doc_no or meta.get("doc_number", "Form 1")

    # Extract points and images
    points = parser.extract_inspection_points(file_path)
    images = parser.extract_images(file_path, part_number=part_no)

    # Determine status
    cat_match = match_catalog_status(part_no)

    # Save to database
    cs = await create_checksheet(
        session=session,
        part_number=part_no,
        part_name=part_name,
        model=model,
        customer=customer,
        doc_number=doc_no,
        template_type=parser.__class__.__name__,
        status=cat_match["status"],
        assigned_to=assigned_to,
        keterangan=cat_match["keterangan"],
        raw_file_path=file_path,
        points=points,
        images=images
    )

    return {
        "id": cs.id,
        "part_number": cs.part_number,
        "part_name": cs.part_name,
        "model": cs.model,
        "customer": cs.customer,
        "status": cs.status,
        "keterangan": cs.keterangan,
        "points_count": len(points),
        "images_count": len(images),
        "assigned_to": cs.assigned_to
    }
