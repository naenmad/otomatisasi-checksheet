"""
Catalog Service for FactoryHub Master Parts & Checksheets.
Provides in-memory caching, instant fuzzy matching, Supabase DB cross-referencing,
and live Playwright synchronization.
"""
import os
import re
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import Checksheet

CATALOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "factoryhub_catalog.json")

_CATALOG_CACHE: Optional[Dict[str, Any]] = None
_CACHE_MTIME: float = 0.0


def clean_code(s: str) -> str:
    """Normalize part number by stripping non-alphanumeric chars and uppercase."""
    return re.sub(r"[^0-9A-Za-z]", "", str(s or "")).upper()


def fuzzy_code(s: str) -> str:
    """Normalize part code with O/0 and I/1 visual interchangeability."""
    cleaned = clean_code(s)
    return cleaned.replace("O", "0").replace("I", "1")


def load_catalog(force_reload: bool = False) -> Dict[str, Any]:
    """Load local catalog cache from disk."""
    global _CATALOG_CACHE, _CACHE_MTIME

    if not os.path.exists(CATALOG_PATH):
        return {
            "synced_at": None,
            "stats": {"total_parts": 0, "total_regular": 0, "total_project": 0, "total_templates": 0},
            "parts": [],
            "templates": []
        }

    try:
        mtime = os.path.getmtime(CATALOG_PATH)
        if not force_reload and _CATALOG_CACHE is not None and mtime == _CACHE_MTIME:
            return _CATALOG_CACHE

        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            _CATALOG_CACHE = data
            _CACHE_MTIME = mtime
            return data
    except Exception as e:
        print(f"[Warning] Failed loading catalog cache: {e}")
        return {
            "synced_at": None,
            "stats": {"total_parts": 0, "total_regular": 0, "total_project": 0, "total_templates": 0},
            "parts": [],
            "templates": []
        }


def save_catalog(catalog_data: Dict[str, Any]) -> None:
    """Save catalog cache to disk."""
    global _CATALOG_CACHE, _CACHE_MTIME
    os.makedirs(os.path.dirname(CATALOG_PATH), exist_ok=True)
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, indent=2, ensure_ascii=False)
    _CATALOG_CACHE = catalog_data
    _CACHE_MTIME = os.path.getmtime(CATALOG_PATH)


def get_catalog_stats() -> Dict[str, Any]:
    """Return catalog metadata and counts."""
    cat = load_catalog()
    stats = cat.get("stats", {})
    return {
        "synced_at": cat.get("synced_at"),
        "elapsed_seconds": cat.get("elapsed_seconds", 0),
        "total_parts": stats.get("total_parts", len(cat.get("parts", []))),
        "total_regular": stats.get("total_regular", 0),
        "total_project": stats.get("total_project", 0),
        "total_templates": stats.get("total_templates", len(cat.get("templates", [])))
    }


def parse_part_input(raw: str) -> List[str]:
    """Split comma, newline, or tab separated parts."""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    parts = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split by comma or tab or semicolon
        items = re.split(r"[,;\t]+", line)
        for item in items:
            p = item.strip()
            if p:
                parts.append(p)
    return parts


async def search_and_match_parts(
    part_numbers: List[str],
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Search list of part numbers against FactoryHub catalog and Supabase database.
    """
    cat = load_catalog()
    parts_db = cat.get("parts", [])

    # Index catalog by clean number and fuzzy code
    clean_catalog: Dict[str, Dict[str, Any]] = {}
    fuzzy_catalog: Dict[str, Dict[str, Any]] = {}
    for p in parts_db:
        c_num = clean_code(p.get("part_number") or p.get("value", ""))
        f_num = fuzzy_code(c_num)
        if c_num and c_num not in clean_catalog:
            clean_catalog[c_num] = p
        if f_num and f_num not in fuzzy_catalog:
            fuzzy_catalog[f_num] = p

    # Fetch all checksheets from database to index them
    stmt = select(Checksheet)
    res = await db.execute(stmt)
    db_checksheets = res.scalars().all()
    db_map: Dict[str, Checksheet] = {}
    db_fuzzy_map: Dict[str, Checksheet] = {}
    for cs in db_checksheets:
        c_p = clean_code(cs.clean_part_number or cs.part_number)
        f_p = fuzzy_code(c_p)
        if c_p:
            db_map[c_p] = cs
        if f_p:
            db_fuzzy_map[f_p] = cs

    results = []
    total_found_fh = 0
    total_found_db = 0
    total_missing_fh = 0

    for query in part_numbers:
        q_clean = clean_code(query)
        q_fuzzy = fuzzy_code(query)

        # 1. Match against FactoryHub Catalog
        fh_match = clean_catalog.get(q_clean)
        match_type = "exact" if fh_match else None

        if not fh_match:
            fh_match = fuzzy_catalog.get(q_fuzzy)
            if fh_match:
                match_type = "fuzzy"

        # Check token matching if still not found
        if not fh_match and len(q_clean) >= 6:
            for c_key, item in clean_catalog.items():
                if q_clean in c_key or c_key in q_clean:
                    fh_match = item
                    match_type = "substring"
                    break

        # Check DB presence
        cs_item = db_map.get(q_clean) or db_fuzzy_map.get(q_fuzzy)
        db_info = None
        if cs_item:
            total_found_db += 1
            db_info = {
                "id": cs_item.id,
                "part_number": cs_item.part_number,
                "part_name": cs_item.part_name,
                "status": cs_item.status,
                "assigned_to": cs_item.assigned_to,
                "doc_number": cs_item.doc_number
            }

        if fh_match:
            total_found_fh += 1
            results.append({
                "query": query,
                "part_number": fh_match.get("part_number") or fh_match.get("value") or query,
                "part_name": fh_match.get("part_name", "-"),
                "category": fh_match.get("category", "REGULAR"),
                "status_master": "TERDAFTAR",
                "has_template": bool(fh_match.get("has_template")),
                "template_info": fh_match.get("template_info"),
                "match_type": match_type or "exact",
                "checksheet": db_info
            })
        else:
            total_missing_fh += 1
            # Find similar suggestions
            similar = []
            prefix = q_fuzzy[:5] if len(q_fuzzy) >= 5 else q_fuzzy
            if prefix:
                for f_key, item in fuzzy_catalog.items():
                    if prefix in f_key:
                        p_display = item.get("part_number") or item.get("value")
                        if p_display and p_display not in similar:
                            similar.append(p_display)
                    if len(similar) >= 3:
                        break

            results.append({
                "query": query,
                "part_number": query,
                "part_name": "-",
                "category": "-",
                "status_master": "BELUM TERDAFTAR",
                "has_template": False,
                "template_info": None,
                "match_type": "none",
                "similar": similar,
                "checksheet": db_info
            })

    return {
        "summary": {
            "total_queried": len(part_numbers),
            "found_in_master": total_found_fh,
            "missing_in_master": total_missing_fh,
            "found_in_database": total_found_db
        },
        "results": results
    }


async def sync_catalog_from_factoryhub(browser_channel: str = "chrome") -> Dict[str, Any]:
    """
    Sync FactoryHub Master Parts dropdowns in headless mode.
    Can be run by any team member.
    """
    from playwright.async_api import async_playwright
    from automator import login_factoryhub, CREATE_URL

    t0 = time.time()
    print("[*] Memulai sinkronisasi katalog FactoryHub...")

    channel = browser_channel.strip().lower()
    if channel in ["edge", "ms-edge"]:
        channel = "msedge"

    async with async_playwright() as p:
        browser = None
        for ch in [channel if channel in ["chrome", "msedge"] else None, None]:
            try:
                browser = await p.chromium.launch(headless=True, channel=ch)
                break
            except Exception as e:
                print(f"[!] Warning launch browser channel {ch}: {e}")

        if not browser:
            browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        try:
            # Login
            await login_factoryhub(page)

            # Scrape create page options
            await page.goto(CREATE_URL, wait_until="networkidle")

            raw_master = await page.evaluate("""() => {
                const regSelect = document.getElementById('part_num_select');
                const projSelect = document.getElementById('part_project_id');

                const regular = regSelect ? Array.from(regSelect.options).map(o => ({
                    value: o.value,
                    text: o.text
                })).filter(o => o.value && !o.text.includes('-- Choose')) : [];

                const project = projSelect ? Array.from(projSelect.options).map(o => ({
                    value: o.value,
                    text: o.text,
                    dataNum: o.getAttribute('data-num') || ''
                })).filter(o => o.value && !o.text.includes('-- Choose')) : [];

                return { regular, project };
            }""")

            regular_opts = raw_master.get("regular", [])
            project_opts = raw_master.get("project", [])

            # Preserve existing template mappings if any
            existing_cat = load_catalog()
            existing_parts = {clean_code(p.get("part_number") or p.get("value", "")): p for p in existing_cat.get("parts", [])}

            parts_list = []
            seen = set()

            # Process Regular Parts
            for opt in regular_opts:
                val = opt.get("value", "").strip()
                txt = opt.get("text", "").strip()
                c_num = clean_code(val)
                if not c_num or c_num in seen:
                    continue
                seen.add(c_num)

                # Extract name if format is 'NUMBER - NAME'
                p_name = ""
                if " - " in txt:
                    p_name = txt.split(" - ", 1)[1].strip()
                elif txt != val:
                    p_name = txt

                old = existing_parts.get(c_num, {})
                parts_list.append({
                    "part_number": val,
                    "clean_number": c_num,
                    "part_name": p_name or old.get("part_name", ""),
                    "category": "REGULAR",
                    "value": val,
                    "has_template": old.get("has_template", False),
                    "template_info": old.get("template_info")
                })

            # Process Project Parts
            for opt in project_opts:
                val = opt.get("value", "").strip()
                txt = opt.get("text", "").strip()
                data_num = opt.get("dataNum", "").strip()
                p_num = data_num or val
                c_num = clean_code(p_num)
                if not c_num or c_num in seen:
                    continue
                seen.add(c_num)

                p_name = ""
                if " - " in txt:
                    p_name = txt.split(" - ", 1)[1].strip()
                elif txt != p_num:
                    p_name = txt

                old = existing_parts.get(c_num, {})
                parts_list.append({
                    "part_number": p_num,
                    "clean_number": c_num,
                    "part_name": p_name or old.get("part_name", ""),
                    "category": "NEW PROJECT",
                    "value": val,
                    "has_template": old.get("has_template", False),
                    "template_info": old.get("template_info")
                })

            elapsed = round(time.time() - t0, 1)
            new_data = {
                "synced_at": datetime.now().isoformat(),
                "elapsed_seconds": elapsed,
                "stats": {
                    "total_parts": len(parts_list),
                    "total_regular": len(regular_opts),
                    "total_project": len(project_opts),
                    "total_templates": existing_cat.get("stats", {}).get("total_templates", 0)
                },
                "parts": parts_list,
                "templates": existing_cat.get("templates", [])
            }

            save_catalog(new_data)
            return {
                "status": "success",
                "synced_at": new_data["synced_at"],
                "elapsed_seconds": elapsed,
                "total_parts": len(parts_list),
                "total_regular": len(regular_opts),
                "total_project": len(project_opts)
            }
        finally:
            await browser.close()
