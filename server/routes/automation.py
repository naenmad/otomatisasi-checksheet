"""
Automation execution and SSE log streaming API router.
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.automation_service import execute_checksheet_submission

router = APIRouter(prefix="/api/automation", tags=["Automation"])


@router.get("/stream/{checksheet_id}")
async def stream_automation_logs(
    checksheet_id: int,
    submit: bool = Query(True, description="Submit to FactoryHub or dry-run review"),
    headless: bool = Query(False, description="Run browser headless or visible"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute Playwright automation and stream logs live to browser via Server-Sent Events (SSE).
    """
    async def event_generator():
        yield f"data: [*] Inisialisasi otomasi untuk Checksheet ID #{checksheet_id}...\n\n"
        async for line in execute_checksheet_submission(
            checksheet_id=checksheet_id,
            session=db,
            submit=submit,
            headless=headless,
            browser_channel=browser_channel
        ):
            # Clean SSE format
            safe_line = line.strip().replace("\n", " ")
            yield f"data: {safe_line}\n\n"
        yield "data: [DONE] Selesai.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/batch/stream")
async def stream_batch_automation_logs(
    ids: str = Query(..., description="Comma-separated checksheet IDs (e.g. 1,2,3)"),
    submit: bool = Query(True, description="Submit to FactoryHub or dry-run review"),
    headless: bool = Query(False, description="Run browser headless or visible"),
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge"),
    db: AsyncSession = Depends(get_db)
):
    """
    Execute batch checksheet submission sequentially and stream logs live via SSE.
    """
    from services.automation_service import execute_batch_submission

    cs_ids = [int(i.strip()) for i in ids.split(",") if i.strip().isdigit()]

    async def event_generator():
        yield f"data: [*] Inisialisasi Batch Submission untuk {len(cs_ids)} part...\n\n"
        async for line in execute_batch_submission(
            checksheet_ids=cs_ids,
            session=db,
            submit=submit,
            headless=headless,
            browser_channel=browser_channel
        ):
            safe_line = line.strip().replace("\n", " ")
            if safe_line:
                yield f"data: {safe_line}\n\n"
        yield "data: [DONE] Seluruh batch selesai.\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
