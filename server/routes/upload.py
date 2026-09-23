"""
File Upload API Router.
"""
import os
import shutil
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.parser_service import parse_and_save_checksheet

router = APIRouter(prefix="/api/upload", tags=["Upload"])

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("")
async def upload_checksheets(
    files: List[UploadFile] = File(...),
    assigned_to: str = Form("Zul"),
    custom_doc_no: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    results = []
    errors = []

    for file in files:
        if not file.filename.lower().endswith((".xlsx", ".xls", ".pdf")):
            errors.append({"file": file.filename, "error": "Format berkas tidak didukung (harus .xlsx, .xls, .pdf)"})
            continue

        file_path = os.path.join(UPLOAD_DIR, file.filename)
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            parsed = await parse_and_save_checksheet(
                session=db,
                file_path=file_path,
                assigned_to=assigned_to,
                custom_doc_no=custom_doc_no
            )
            results.append(parsed)
        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})

    return {
        "success_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors
    }
