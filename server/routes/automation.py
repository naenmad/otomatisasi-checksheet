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
