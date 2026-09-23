"""
CRUD operations for database models.
"""
import re
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Checksheet, InspectionPoint, PartImage, SubmissionQueue


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
    status: str = "DRAFT",
    assigned_to: str = "Unassigned",
    keterangan: str = "",
    raw_file_path: str = "",
    points: Optional[List[Dict[str, str]]] = None,
    images: Optional[List[str]] = None
) -> Checksheet:
    clean_pno = clean_str(part_number)

    # Check if part already exists
    stmt = select(Checksheet).where(Checksheet.clean_part_number == clean_pno)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        # Update existing
        existing.part_name = part_name or existing.part_name
        existing.model = model or existing.model
        existing.customer = customer or existing.customer
        existing.doc_number = doc_number or existing.doc_number
        existing.template_type = template_type or existing.template_type
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

        for idx, pt in enumerate(points):
            ip = InspectionPoint(
                checksheet_id=target.id,
                item_no=pt.get("item_no") or str(idx + 1),
                inspection_item=pt.get("inspection_item") or f"Point {idx + 1}",
                standard=pt.get("standard") or "-",
                method=pt.get("method") or "Visual",
                master_data=pt.get("master_data") or "",
                order_index=idx
            )
            session.add(ip)

    # Add images
    if images:
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
    search: Optional[str] = None,
    limit: int = 150,
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
        query = query.where(Checksheet.status == status)
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
    cs = await get_checksheet_by_id(session, checksheet_id)
    if cs:
        cs.status = status
        if factoryhub_url:
            cs.factoryhub_url = factoryhub_url
        if keterangan:
            cs.keterangan = keterangan
        await session.commit()
        await session.refresh(cs)
    return cs
