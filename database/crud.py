"""
CRUD operations for database models.
"""
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, desc, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Checksheet, InspectionPoint, PartImage, SubmissionQueue, ActivityLog
from parsers.smart_parser import TextNormalizer


def clean_str(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", str(s)).upper()


async def get_or_create_user(session: AsyncSession, name: str, nik: Optional[str] = None) -> User:
    stmt = select(User).where(User.name == name)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(name=name, nik=nik)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def create_checksheet(
    session: AsyncSession,
    part_number: str,
    part_name: str = "",
    model: str = "-",
    customer: str = "PT. HPM",
    doc_number: str = "Form 1",
    template_type: str = "GENERIC",
    category: str = "Accuracy",
    status: str = "DRAFT",
    assigned_to: str = "Unassigned",
    keterangan: str = "",
    raw_file_path: str = "",
    points: Optional[List[Dict[str, str]]] = None,
    images: Optional[List[str]] = None
) -> Checksheet:
    clean_pno = clean_str(part_number)
    category_val = (category or "Accuracy").strip()

    # Check if a template for this part number and category already exists
    query_filters = [
        Checksheet.clean_part_number == clean_pno,
        Checksheet.category == category_val
    ]
    if doc_number and doc_number not in ("Form 1", "-"):
        query_filters.append(Checksheet.doc_number == doc_number)

    stmt = select(Checksheet).where(*query_filters)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing template
        existing.part_name = part_name or existing.part_name
        existing.model = model or existing.model
        existing.customer = customer or existing.customer
        existing.doc_number = doc_number or existing.doc_number
        existing.template_type = template_type or existing.template_type
        existing.category = category_val or existing.category
        if existing.status != "Reviewed":
            if status != "DRAFT" or existing.status == "DRAFT":
                existing.status = status
        if keterangan:
            existing.keterangan = keterangan
        target = existing
    else:
        target = Checksheet(
            part_number=part_number,
            clean_part_number=clean_pno,
            part_name=part_name,
            model=model,
            customer=customer,
            doc_number=doc_number,
            template_type=template_type,
            category=category_val,
            status=status,
            assigned_to=assigned_to,
            keterangan=keterangan,
            raw_file_path=raw_file_path
        )
        session.add(target)
        await session.flush()

    # Add points
    if points:
        # Clear old points if updating
        if existing:
            await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == target.id))

        # Normalize + expand (splits combined appearance rows into individual defect checks)
        expanded_points = TextNormalizer.expand_points(points)

        for idx, pt in enumerate(expanded_points):
            ip = InspectionPoint(
                checksheet_id=target.id,
                item_no=pt.get("item_no") or str(idx + 1),
                inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                standard=pt.get("standard") or "",
                method=pt.get("method") or "Visual",
                master_data=pt.get("master_data") or "",
                order_index=idx
            )
            session.add(ip)

    # Add images
    if images:
        if existing:
            await session.execute(delete(PartImage).where(PartImage.checksheet_id == target.id))

        for img_idx, img_path in enumerate(images):
            pimg = PartImage(
                checksheet_id=target.id,
                image_path=img_path,
                image_url=img_path
            )
            session.add(pimg)

    await session.commit()
    await session.refresh(target)
    return target


async def list_checksheets(
    session: AsyncSession,
    assigned_to: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0
) -> List[Checksheet]:
    query = select(Checksheet).options(selectinload(Checksheet.inspection_points), selectinload(Checksheet.images))

    if assigned_to and assigned_to.upper() != "ALL":
        if assigned_to.upper() in ("UNASSIGNED", "BELUM DITUGASKAN"):
            query = query.where(
                (Checksheet.assigned_to.is_(None)) |
                (Checksheet.assigned_to == "") |
                (Checksheet.assigned_to == "Unassigned") |
                (Checksheet.assigned_to == "Belum Ditugaskan")
            )
        else:
            query = query.where(Checksheet.assigned_to == assigned_to)
    if status and status.upper() != "ALL":
        st_clean = status.strip().lower()
        if st_clean in ("belum dikerjakan", "belum di review", "belum di input", "belum_dikerjakan", "belum_di_review", "belum_di_input"):
            query = query.where(Checksheet.status.in_(["Belum Dikerjakan", "Belum Di Input", "Belum di review"]))
        elif st_clean in ("siap kirim", "siap_kirim", "reviewed"):
            query = query.where(Checksheet.status.in_(["Siap Kirim", "Reviewed", "reviewed"]))
        elif st_clean in ("perlu revisi isi", "revisi isi", "butuh revisi", "butuh_revisi"):
            query = query.where(Checksheet.status.in_(["Perlu Revisi Isi", "Butuh Revisi", "butuh revisi"]))
        elif st_clean in ("perlu revisi gambar", "revisi gambar"):
            query = query.where(Checksheet.status == "Perlu Revisi Gambar")
        elif st_clean in ("checksheet done", "checksheet_done"):
            query = query.where(Checksheet.status.ilike("Checksheet Done"))
        else:
            query = query.where(Checksheet.status.ilike(status))
    if category and category.upper() != "ALL":
        query = query.where(Checksheet.category.ilike(category.strip()))
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Checksheet.part_number.ilike(search_pattern)) |
            (Checksheet.part_name.ilike(search_pattern)) |
            (Checksheet.model.ilike(search_pattern))
        )

    query = query.order_by(Checksheet.id.asc()).offset(offset).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()


def _normalize_thumbnail_url(url: Optional[str], path: Optional[str], cache_version: Optional[str] = None) -> Optional[str]:
    raw = url or path or ""
    if not raw:
        return None
    raw = raw.strip().replace("\\", "/")
    res = raw
    if raw.startswith("http://") or raw.startswith("https://"):
        res = raw
    elif "storage/images" in raw:
        sub = raw.split("storage/images", 1)[1].lstrip("/")
        res = f"/media/images/{sub}"
    elif "extracted_images" in raw:
        sub = raw.split("extracted_images", 1)[1].lstrip("/")
        res = f"/media/extracted/{sub}"
    elif raw.startswith("/media/"):
        res = raw

    if cache_version and "?" not in res:
        res = f"{res}?v={cache_version}"
    return res


def extract_process_label(raw_path: Optional[str], doc_number: Optional[str] = None) -> str:
    """Helper to determine the exact manufacturing/inspection stage badge from file path."""
    if not raw_path:
        return ""
    p = raw_path.upper().replace("\\", "/")
    if "1. STAMPING" in p or "/STAMPING/" in p:
        return "IPQC Stamping"
    if "2. SSW" in p or "SPOT NUT" in p or "SPOT_NUT" in p:
        return "IPQC Spot Nut"
    if "3. FINAL" in p or "/FINAL/" in p:
        return "IPQC Final Assy"
    if "2. IR CHILD PART" in p or "CHILD PART" in p:
        return "IR Child Part"
    if "3. IR MONTHLY FG" in p or "MONTHLY FG" in p:
        if "REV#NEW EO" in p or "NEW EO" in p:
            return "IR Monthly FG (EO)"
        import re
        m = re.search(r"REV#([0-9A-Z]+)", p)
        if m:
            return f"IR Monthly FG (Rev {m.group(1)})"
        return "IR Monthly FG"
    if "CS IQC SUBCONT" in p:
        return "IQC Subcont"
    if "CS IQC MATERIAL" in p or "CS MATERIAL" in p:
        return "IQC Material"
    return ""


async def get_checksheets_summary_list(
    session: AsyncSession,
    assigned_to: Optional[str] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 5000,
    offset: int = 0
) -> List[dict]:
    """High-performance checksheet summary query using SQL aggregates instead of 80,000+ ORM model loads."""
    pts_sub = (
        select(InspectionPoint.checksheet_id, func.count(InspectionPoint.id).label("cnt"))
        .group_by(InspectionPoint.checksheet_id)
        .subquery()
    )
    imgs_sub = (
        select(
            PartImage.checksheet_id,
            func.count(PartImage.id).label("cnt"),
            func.min(PartImage.id).label("first_img_id")
        )
        .group_by(PartImage.checksheet_id)
        .subquery()
    )
    first_img = (
        select(
            PartImage.id,
            PartImage.image_url,
            PartImage.image_path
        )
        .subquery()
    )

    query = (
        select(
            Checksheet.id,
            Checksheet.part_number,
            Checksheet.part_name,
            Checksheet.model,
            Checksheet.customer,
            Checksheet.doc_number,
            Checksheet.template_type,
            Checksheet.category,
            Checksheet.status,
            Checksheet.assigned_to,
            Checksheet.keterangan,
            Checksheet.factoryhub_url,
            Checksheet.updated_at,
            Checksheet.raw_file_path,
            func.coalesce(pts_sub.c.cnt, 0).label("points_count"),
            func.coalesce(imgs_sub.c.cnt, 0).label("images_count"),
            first_img.c.image_url.label("first_image_url"),
            first_img.c.image_path.label("first_image_path"),
        )
        .outerjoin(pts_sub, Checksheet.id == pts_sub.c.checksheet_id)
        .outerjoin(imgs_sub, Checksheet.id == imgs_sub.c.checksheet_id)
        .outerjoin(first_img, imgs_sub.c.first_img_id == first_img.c.id)
    )

    if assigned_to and assigned_to.upper() != "ALL":
        if assigned_to.upper() in ("UNASSIGNED", "BELUM DITUGASKAN"):
            query = query.where(
                (Checksheet.assigned_to.is_(None)) |
                (Checksheet.assigned_to == "") |
                (Checksheet.assigned_to == "Unassigned") |
                (Checksheet.assigned_to == "Belum Ditugaskan")
            )
        else:
            query = query.where(Checksheet.assigned_to == assigned_to)
    if status and status.upper() != "ALL":
        st_clean = status.strip().lower()
        if st_clean in ("belum dikerjakan", "belum di review", "belum di input", "belum_dikerjakan", "belum_di_review", "belum_di_input"):
            query = query.where(Checksheet.status.in_(["Belum Dikerjakan", "Belum Di Input", "Belum di review"]))
        elif st_clean in ("siap kirim", "siap_kirim", "reviewed"):
            query = query.where(Checksheet.status.in_(["Siap Kirim", "Reviewed", "reviewed"]))
        elif st_clean in ("perlu revisi isi", "revisi isi", "butuh revisi", "butuh_revisi"):
            query = query.where(Checksheet.status.in_(["Perlu Revisi Isi", "Butuh Revisi", "butuh revisi"]))
        elif st_clean in ("perlu revisi gambar", "revisi gambar"):
            query = query.where(Checksheet.status == "Perlu Revisi Gambar")
        elif st_clean in ("checksheet done", "checksheet_done"):
            query = query.where(Checksheet.status.ilike("Checksheet Done"))
        else:
            query = query.where(Checksheet.status.ilike(status))
    if category and category.upper() != "ALL":
        query = query.where(Checksheet.category.ilike(category.strip()))
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (Checksheet.part_number.ilike(search_pattern)) |
            (Checksheet.part_name.ilike(search_pattern)) |
            (Checksheet.model.ilike(search_pattern)) |
            (Checksheet.category.ilike(search_pattern))
        )

    query = query.order_by(Checksheet.id.asc()).offset(offset).limit(limit)
    res = await session.execute(query)
    rows = res.all()

    # Pre-fetch all images for these checksheets so multiple drawings can be previewed/scrolled directly in the row
    cs_ids = [r.id for r in rows]
    cs_images_map: Dict[int, List[str]] = {}
    # Build lookup: checksheet_id -> updated_at for cache-busting CDN URLs
    cs_updated_map: Dict[int, str] = {}
    for r in rows:
        cs_updated_map[r.id] = str(int(r.updated_at.timestamp())) if r.updated_at else ""
    if cs_ids:
        imgs_res = await session.execute(
            select(PartImage.checksheet_id, PartImage.image_url, PartImage.image_path)
            .where(PartImage.checksheet_id.in_(cs_ids))
            .order_by(PartImage.id.asc())
        )
        for p_cs_id, p_url, p_path in imgs_res.all():
            cv = cs_updated_map.get(p_cs_id, "")
            norm_url = _normalize_thumbnail_url(p_url, p_path, cache_version=cv)
            if norm_url:
                cs_images_map.setdefault(p_cs_id, []).append(norm_url)

    items = []
    for r in rows:
        cv = cs_updated_map.get(r.id, "")
        thumb = _normalize_thumbnail_url(r.first_image_url, r.first_image_path, cache_version=cv)
        all_imgs = cs_images_map.get(r.id)
        if not all_imgs and thumb:
            all_imgs = [thumb]
        elif not all_imgs:
            all_imgs = []

        items.append({
            "id": r.id,
            "part_number": r.part_number,
            "part_name": r.part_name,
            "model": r.model,
            "customer": r.customer,
            "doc_number": r.doc_number,
            "template_type": r.template_type,
            "category": r.category or "Accuracy",
            "status": r.status,
            "assigned_to": r.assigned_to,
            "keterangan": r.keterangan,
            "points_count": r.points_count,
            "images_count": max(r.images_count or 0, len(all_imgs)),
            "thumbnail_url": thumb or (all_imgs[0] if all_imgs else None),
            "image_urls": all_imgs,
            "factoryhub_url": r.factoryhub_url,
            "raw_file_path": r.raw_file_path,
            "process_label": extract_process_label(r.raw_file_path, r.doc_number),
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        })
    return items


async def get_checksheet_base_by_id(session: AsyncSession, checksheet_id: int) -> Optional[Checksheet]:
    """Fast single checksheet lookup without loading inspection points and images."""
    query = select(Checksheet).where(Checksheet.id == checksheet_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_checksheet_by_id(session: AsyncSession, checksheet_id: int) -> Optional[Checksheet]:
    query = (
        select(Checksheet)
        .options(selectinload(Checksheet.inspection_points), selectinload(Checksheet.images))
        .where(Checksheet.id == checksheet_id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def update_checksheet_status(
    session: AsyncSession,
    checksheet_id: int,
    status: str,
    factoryhub_url: Optional[str] = None,
    keterangan: Optional[str] = None
) -> Optional[Checksheet]:
    cs = await get_checksheet_base_by_id(session, checksheet_id)
    if cs:
        cs.status = status
        if factoryhub_url:
            cs.factoryhub_url = factoryhub_url
        if keterangan:
            cs.keterangan = keterangan
        await session.commit()
    return cs


async def log_activity(
    session: AsyncSession,
    action: str,
    part_number: str = "-",
    operator: str = "System",
    status: str = "SUCCESS",
    details: str = "",
    link: Optional[str] = None
) -> ActivityLog:
    """Create a new chronological audit log entry."""
    entry = ActivityLog(
        action=action,
        part_number=part_number or "-",
        operator=operator or "System",
        status=status or "SUCCESS",
        details=details or "",
        link=link
    )
    session.add(entry)
    await session.commit()
    return entry


async def list_activity_logs(session: AsyncSession, limit: int = 500) -> List[ActivityLog]:
    """Retrieve all activity logs sorted from oldest to newest (or newest first)."""
    stmt = select(ActivityLog).order_by(ActivityLog.id.asc()).limit(limit)
    res = await session.execute(stmt)
    return res.scalars().all()
