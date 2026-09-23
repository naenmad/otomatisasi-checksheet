"""
Catalog API router for FactoryHub Master Parts search, statistics, and live synchronization.
"""
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from services.catalog_service import (
    get_catalog_stats,
    search_and_match_parts,
    sync_catalog_from_factoryhub,
    parse_part_input
)

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])


class CatalogSearchRequest(BaseModel):
    query: Optional[str] = None
    parts: Optional[List[str]] = None


@router.get("/stats")
async def get_stats():
    """Return catalog metadata, total counts, and last sync timestamp."""
    return get_catalog_stats()


@router.post("/search")
async def search_parts(
    payload: CatalogSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search part numbers (single query or batch list) against FactoryHub master
    and Supabase checksheet database.
    """
    to_check = []
    if payload.parts:
        for p in payload.parts:
            p_clean = p.strip()
            if p_clean:
                to_check.append(p_clean)
    elif payload.query:
        to_check = parse_part_input(payload.query)

    if not to_check:
        return {
            "summary": {
                "total_queried": 0,
                "found_in_master": 0,
                "missing_in_master": 0,
                "found_in_database": 0
            },
            "results": []
        }

    return await search_and_match_parts(to_check[:100], db)


@router.post("/sync")
async def trigger_catalog_sync(
    browser_channel: str = Query("chrome", description="Browser channel: chrome or msedge")
):
    """
    Trigger live Playwright scraping of FactoryHub Master Parts dropdowns
    and update server's catalog cache.
    """
    try:
        res = await sync_catalog_from_factoryhub(browser_channel=browser_channel)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal melakukan sinkronisasi: {str(e)}")
