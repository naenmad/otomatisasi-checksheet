#!/usr/bin/env python3
"""
FactoryHub Master Parts & Checksheet Catalog Synchronizer
Scrapes:
1. Master Parts list (Regular + Project parts) from /quality/checksheet-master/create
2. Checksheet Templates from /quality/checksheet-master
And saves the consolidated database to data/factoryhub_catalog.json.
"""

import os
import re
import time
import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from playwright.async_api import async_playwright
from dotenv import load_dotenv

from automator import login_factoryhub, CREATE_URL, INDEX_URL
from catalog_manager import clean_code, save_catalog

load_dotenv()


async def sync_factoryhub_catalog(browser_channel: Optional[str] = None) -> Dict[str, Any]:
    """
    Perform full synchronization of FactoryHub Master Parts and Templates.
    Saves results to data/factoryhub_catalog.json and returns summary stats.
    """
    channel = (browser_channel or os.getenv("BROWSER_CHANNEL", "chromium")).strip().lower()
    if channel in ["edge", "ms-edge"]:
        channel = "msedge"

    t0 = time.time()
    print(f"[*] Memulai sinkronisasi Katalog FactoryHub...")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                headless=True,
                channel=channel if channel in ["msedge", "chrome"] else None
            )
        except Exception as e:
            print(f"[!] Gagal menggunakan channel {channel}: {e}. Menggunakan Chromium standar...")
            browser = await p.chromium.launch(headless=True)

        page = await browser.new_page()

        # Step 1: Login
        await login_factoryhub(page)

        # Step 2: Fetch Master Parts (Regular & New Project) from create page
        print(f"[*] Mengambil Master Parts dari {CREATE_URL}...")
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
        print(f"[+] Ditemukan {len(regular_opts)} Regular Parts dan {len(project_opts)} Project Parts.")

        # Step 3: Fetch Checksheet Templates
        print(f"[*] Mengambil template checksheet dari {INDEX_URL}...")
        all_templates = []
        for p_idx in range(1, 30):
            await page.goto(f"{INDEX_URL}?page={p_idx}", wait_until="domcontentloaded")
            rows = await page.evaluate("""() => {
                const trs = Array.from(document.querySelectorAll('table tbody tr'));
                return trs.map(tr => {
                    const tds = Array.from(tr.querySelectorAll('td')).map(td => td.innerText.trim());
                    const editLink = tr.querySelector('a[href*="/edit"]');
                    return {
                        part_number: tds[0] || '',
                        type: tds[1] || '',
                        part_name: tds[2] || '',
                        items_count: tds[3] || '',
                        doc_number: tds[4] || '',
                        status: tds[5] || '',
                        edit_url: editLink ? editLink.href : ''
                    };
                }).filter(item => item.part_number && !item.part_number.includes('No data'));
            }""")

            if not rows:
                break

            for r in rows:
                r["clean_number"] = clean_code(r["part_number"])
                all_templates.append(r)

            # Check if this was the last page
            has_next = await page.evaluate("""() => {
                const nextBtn = document.querySelector('nav a[rel="next"], .pagination a[rel="next"]');
                return !!nextBtn;
            }""")
            if not has_next and p_idx > 1:
                break

        print(f"[+] Ditemukan {len(all_templates)} Template Checksheet Master.")
        await browser.close()

    # Step 4: Index Templates by Clean Part Number
    template_map: Dict[str, Dict[str, Any]] = {}
    for t in all_templates:
        c_num = t.get("clean_number")
        if c_num and c_num not in template_map:
            template_map[c_num] = t

        # Step 4b: Index local documents for name enrichment
        local_name_map: Dict[str, str] = {}
        try:
            from extractor import list_available_parts
            for ld in list_available_parts("documents"):
                c = clean_code(ld.get("part_number") or ld.get("folder") or "")
                pn = ld.get("part_name", "").strip()
                if c and pn and pn != ld.get("part_number"):
                    local_name_map[c] = pn
        except Exception:
            pass

        # Step 5: Process Master Parts
        parts_list: List[Dict[str, Any]] = []
        seen_parts = set()

        # 5a. Regular Parts
        for opt in regular_opts:
            val = opt["value"].strip()
            text = opt["text"].strip()
            c_num = clean_code(val)

            if not c_num or c_num in seen_parts:
                continue
            seen_parts.add(c_num)

            # Parse part name from text: e.g. "11198-61J02-000 - COVER IGNITION COIL"
            if " - " in text:
                p_name = text.split(" - ", 1)[1].strip()
            else:
                p_name = text.replace(val, "").strip(" -:()")

            tmpl = template_map.get(c_num)
            tmpl_name = tmpl.get("part_name", "").strip() if tmpl else ""
            local_name = local_name_map.get(c_num, "").strip()

            final_p_name = p_name or (tmpl_name if tmpl_name != val else "") or local_name or ""

            parts_list.append({
                "part_number": val,
                "clean_number": c_num,
                "part_name": final_p_name,
                "category": "REGULAR",
                "value": val,
                "has_template": tmpl is not None,
                "template_info": tmpl
            })

        # 5b. Project Parts
        for opt in project_opts:
            val = opt["value"].strip()
            text = opt["text"].strip()
            data_num = opt.get("dataNum", "").strip()
            p_num = data_num or (text.split("(")[0].strip() if "(" in text else text)
            c_num = clean_code(p_num)

            if not c_num or c_num in seen_parts:
                continue
            seen_parts.add(c_num)

            # Extract project description e.g. "51138E000P (5P45)" -> "5P45"
            m_proj = re.search(r'\((.*?)\)', text)
            proj_name = m_proj.group(1).strip() if m_proj else text

            tmpl = template_map.get(c_num)
            tmpl_name = tmpl.get("part_name", "").strip() if tmpl else ""
            local_name = local_name_map.get(c_num, "").strip()

            final_p_name = proj_name or (tmpl_name if tmpl_name != p_num else "") or local_name or ""

            parts_list.append({
                "part_number": p_num,
                "clean_number": c_num,
                "part_name": final_p_name,
                "category": "NEW PROJECT",
                "value": val,
                "data_num": data_num,
                "has_template": tmpl is not None,
                "template_info": tmpl
            })

    # 5c. Include any existing templates whose part wasn't in create options
    for t in all_templates:
        c_num = t.get("clean_number")
        if c_num and c_num not in seen_parts:
            seen_parts.add(c_num)
            parts_list.append({
                "part_number": t["part_number"],
                "clean_number": c_num,
                "part_name": t.get("part_name", ""),
                "category": "REGULAR",
                "value": t["part_number"],
                "has_template": True,
                "template_info": t
            })

    elapsed = round(time.time() - t0, 2)
    now_iso = datetime.now().isoformat()

    catalog_data = {
        "synced_at": now_iso,
        "elapsed_seconds": elapsed,
        "stats": {
            "total_parts": len(parts_list),
            "total_regular": sum(1 for p in parts_list if p["category"] == "REGULAR"),
            "total_project": sum(1 for p in parts_list if p["category"] == "NEW PROJECT"),
            "total_templates": len(all_templates)
        },
        "parts": parts_list,
        "templates": all_templates
    }

    save_catalog(catalog_data)
    print(f"[✓] Sinkronisasi selesai dalam {elapsed}s! Total: {len(parts_list)} Parts, {len(all_templates)} Templates tersimpan.")
    return catalog_data["stats"]


if __name__ == "__main__":
    asyncio.run(sync_factoryhub_catalog())
