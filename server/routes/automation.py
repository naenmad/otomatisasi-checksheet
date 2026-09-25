"""
Automation execution and SSE log streaming API router.
Supports both single and batch execution via REST and SSE real-time streaming.
"""
import asyncio
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.crud import get_checksheet_by_id
from database.models import User
from server.auth import verify_token
from services.automation_service import (
    execute_checksheet_submission,
    execute_batch_submission,
    cancel_batch,
    is_batch_cancelled
)

router = APIRouter(prefix="/api/automation", tags=["Automation"])


async def resolve_user_from_request(
    db: AsyncSession,
    token: Optional[str] = None,
    authorization: Optional[str] = None
) -> Optional[User]:
    raw_token = token
    if not raw_token and authorization:
        if authorization.startswith("Bearer "):
            raw_token = authorization.split("Bearer ", 1)[1].strip()
    if not raw_token:
        return None
    payload = verify_token(raw_token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


class BatchAutomationRequest(BaseModel):
    checksheet_ids: List[int]
    submit: bool = True
    headless: bool = True
    browser_channel: str = "chrome"


class CancelBatchRequest(BaseModel):
    batch_id: Optional[str] = "current"


@router.post("/batch/cancel")
async def cancel_batch_route(payload: Optional[CancelBatchRequest] = None):
    """Cancel any active batch automation immediately."""
    b_id = payload.batch_id if (payload and payload.batch_id) else "current"
    cancel_batch(b_id)
    return {"status": "success", "message": f"Batalkan batch {b_id} berhasil dikirim."}


@router.post("/submit/{checksheet_id}")
async def submit_checksheet(
    checksheet_id: int,
    headless: bool = Query(False, description="Run browser headless or visible"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute Playwright automation and SUBMIT officially to FactoryHub.
    Updates checksheet status to 'Checksheet Done' upon success.
    """
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail=f"Checksheet ID {checksheet_id} tidak ditemukan.")

    logs = []
    final_url = ""
    is_success = False

    async for line in execute_checksheet_submission(
        checksheet_id=checksheet_id,
        session=db,
        submit=True,
        headless=headless,
        browser_channel=browser_channel
    ):
        clean_l = line.strip()
        if clean_l:
            logs.append(clean_l)
        if "[✓] Sukses submit" in clean_l:
            is_success = True
            # Extract URL if present
            parts = clean_l.split("ke FactoryHub:")
            if len(parts) > 1:
                final_url = parts[1].strip()

    # Reload fresh record from database
    await db.refresh(cs)

    return {
        "status": "success" if is_success else "completed",
        "submitted": is_success,
        "message": "Berhasil submit checksheet ke FactoryHub!" if is_success else "Proses otomatisasi selesai.",
        "checksheet_id": cs.id,
        "part_number": cs.part_number,
        "checksheet_status": cs.status,
        "factoryhub_url": cs.factoryhub_url or final_url,
        "logs": logs
    }


@router.post("/dry-run/{checksheet_id}")
async def dry_run_checksheet(
    checksheet_id: int,
    headless: bool = Query(False, description="Run browser headless or visible"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute Playwright automation in DRY-RUN mode.
    Fills form and inspection points on FactoryHub WITHOUT clicking the final submit button.
    Does NOT modify database checksheet status.
    """
    cs = await get_checksheet_by_id(db, checksheet_id)
    if not cs:
        raise HTTPException(status_code=404, detail=f"Checksheet ID {checksheet_id} tidak ditemukan.")

    logs = []
    async for line in execute_checksheet_submission(
        checksheet_id=checksheet_id,
        session=db,
        submit=False,
        headless=headless,
        browser_channel=browser_channel
    ):
        clean_l = line.strip()
        if clean_l:
            logs.append(clean_l)

    return {
        "status": "success",
        "submitted": False,
        "is_dry_run": True,
        "message": "Dry-run selesai! Seluruh form dan poin inspeksi terisi untuk pratinjau (tidak disimpan ke database FactoryHub).",
        "checksheet_id": cs.id,
        "part_number": cs.part_number,
        "checksheet_status": cs.status,
        "logs": logs
    }


@router.post("/batch")
async def run_batch_automation(
    payload: BatchAutomationRequest,
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute batch checksheet submission sequentially via POST.
    """
    if not payload.checksheet_ids:
        raise HTTPException(status_code=400, detail="Daftar checksheet_ids tidak boleh kosong.")

    req_user = await resolve_user_from_request(db, None, authorization)

    logs = []
    success_count = 0
    fail_count = 0

    async for line in execute_batch_submission(
        checksheet_ids=payload.checksheet_ids,
        session=db,
        submit=payload.submit,
        headless=payload.headless,
        browser_channel=payload.browser_channel,
        batch_id="post_batch",
        requesting_user=req_user
    ):
        clean_l = line.strip()
        if clean_l:
            logs.append(clean_l)
            if "[✓] Sukses submit" in clean_l:
                success_count += 1
            elif "[ERROR]" in clean_l or "gagal" in clean_l.lower():
                fail_count += 1

    return {
        "status": "success",
        "total": len(payload.checksheet_ids),
        "success_count": success_count,
        "fail_count": fail_count,
        "message": f"Batch selesai: {success_count} sukses, {fail_count} gagal dari {len(payload.checksheet_ids)} part.",
        "logs": logs
    }


@router.get("/stream/{checksheet_id}")
async def stream_automation_logs(
    checksheet_id: int,
    submit: bool = Query(True, description="Submit to FactoryHub or dry-run review"),
    headless: bool = Query(True, description="Run browser headless in background"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    token: Optional[str] = Query(None, description="Auth token"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute Playwright automation and stream logs live to browser via Server-Sent Events (SSE).
    """
    req_user = await resolve_user_from_request(db, token, authorization)
    mode_label = "SUBMIT RESMI" if submit else "DRY-RUN (UJI COBA)"

    async def event_generator():
        yield f"data: [*] Inisialisasi Otomasi [{mode_label}] untuk Checksheet ID #{checksheet_id}...\n\n"
        async for line in execute_checksheet_submission(
            checksheet_id=checksheet_id,
            session=db,
            submit=submit,
            headless=headless,
            browser_channel=browser_channel,
            requesting_user=req_user
        ):
            safe_line = line.strip().replace("\n", " ")
            if safe_line:
                yield f"data: {safe_line}\n\n"
        yield f"data: [DONE] Selesai ({mode_label}).\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/batch/stream")
async def stream_batch_automation_logs(
    request: Request,
    ids: str = Query(..., description="Comma-separated checksheet IDs (e.g. 1,2,3)"),
    submit: bool = Query(True, description="Submit to FactoryHub or dry-run review"),
    headless: bool = Query(True, description="Run browser headless in background"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    token: Optional[str] = Query(None, description="Auth token"),
    authorization: Optional[str] = Header(None),
    batch_id: str = Query("current", description="Batch session ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute batch checksheet submission sequentially and stream logs live via SSE
    with single browser session, one-time login, permission checking, and instant cancellation.
    """
    req_user = await resolve_user_from_request(db, token, authorization)
    cs_ids = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]

    async def event_generator():
        yield f"data: [*] Inisialisasi Batch Otomasi untuk {len(cs_ids)} part...\n\n"
        try:
            async for line in execute_batch_submission(
                checksheet_ids=cs_ids,
                session=db,
                submit=submit,
                headless=headless,
                browser_channel=browser_channel,
                batch_id=batch_id,
                requesting_user=req_user
            ):
                if await request.is_disconnected():
                    cancel_batch(batch_id)
                    break
                safe_line = line.strip().replace("\n", " ")
                if safe_line:
                    yield f"data: {safe_line}\n\n"
        except asyncio.CancelledError:
            cancel_batch(batch_id)
        yield "data: [DONE] Seluruh batch otomasi selesai.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
