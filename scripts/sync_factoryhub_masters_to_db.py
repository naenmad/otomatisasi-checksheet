"""
Sync FactoryHub Master Checksheets (Drawings & Inspection Points) to Local Database.
Pulls the official drawing image and inspection points from FactoryHub for checksheets
that already have a factoryhub_url, resolving any missing drawings or points discrepancy.
"""
import os
import re
import sys
import asyncio
from typing import List, Optional
from playwright.async_api import async_playwright

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import AsyncSessionLocal
from database.models import Checksheet, InspectionPoint, PartImage
from database.crud import clean_str
from core.automator import login_factoryhub
from sqlalchemy import select, delete


async def sync_single_checksheet_from_factoryhub(page, cs: Checksheet, session, download_images: bool = True) -> dict:
    """Scrapes drawing and points from FactoryHub edit page and updates local DB."""
    if not cs.factoryhub_url:
        return {"status": "skipped", "reason": "No factoryhub_url"}

    print(f"[*] Navigating to FactoryHub for {cs.part_number}: {cs.factoryhub_url}")
    await page.goto(cs.factoryhub_url, wait_until="networkidle")

    # 1. Scrape drawing image URLs
    img_urls = await page.evaluate(r"""() => {
        return Array.from(document.querySelectorAll('img'))
            .map(i => i.src)
            .filter(s => s && (s.includes('/storage/checksheets/') || s.includes('/masters/')));
    }""")

    # 2. Scrape inspection points table
    points_data = await page.evaluate(r"""() => {
        const rows = Array.from(document.querySelectorAll('table tbody tr')).map(tr => {
            const inputs = Array.from(tr.querySelectorAll('input, select, textarea'));
            const cells = Array.from(tr.querySelectorAll('td, th'));
            
            // Try extracting from form inputs first
            let no = '', item = '', std = '', method = '', master = '';
            for (let inp of inputs) {
                const name = (inp.name || '').toLowerCase();
                const val = inp.value ? inp.value.trim() : '';
                if (name.includes('no') || name.includes('item_no')) no = val;
                else if (name.includes('item') || name.includes('inspection')) item = val;
                else if (name.includes('standard') || name.includes('limit')) std = val;
                else if (name.includes('method') || name.includes('tool')) method = val;
                else if (name.includes('master') || name.includes('data')) master = val;
            }
            
            // Fallback to text inside cells
            if (!item && cells.length >= 3) {
                no = cells[0] ? cells[0].innerText.trim() : '';
                item = cells[1] ? cells[1].innerText.trim() : '';
                std = cells[2] ? cells[2].innerText.trim() : '';
                method = cells[3] ? cells[3].innerText.trim() : '';
            }
            
            return { item_no: no, inspection_item: item, standard: std, method: method, master_data: master };
        }).filter(r => r.inspection_item || r.standard);
        return rows;
    }""")

    # 3. Download image and attach to part_images
    downloaded_images = 0
    clean_p = clean_str(cs.part_number)
    folder_dir = os.path.join(PROJECT_ROOT, "storage", "images", clean_p)
    os.makedirs(folder_dir, exist_ok=True)

    if img_urls and download_images:
        for idx, img_url in enumerate(img_urls):
            try:
                resp = await page.request.get(img_url)
                if resp.status == 200:
                    body = await resp.body()
                    ext = os.path.splitext(img_url.split("?")[0])[1] or ".png"
                    local_filename = f"fh_master_{idx + 1}{ext}"
                    local_path = os.path.join(folder_dir, local_filename)
                    with open(local_path, "wb") as f:
                        f.write(body)

                    rel_url = f"/media/images/{clean_p}/{local_filename}"
                    
                    # Check if already in PartImage
                    existing_img = (await session.scalars(
                        select(PartImage).where(
                            PartImage.checksheet_id == cs.id,
                            PartImage.image_url == rel_url
                        )
                    )).first()

                    if not existing_img:
                        pimg = PartImage(
                            checksheet_id=cs.id,
                            image_path=local_path,
                            image_url=rel_url
                        )
                        session.add(pimg)
                        downloaded_images += 1
            except Exception as e:
                print(f"    [!] Failed to download image {img_url}: {e}")

    # 4. Update inspection points if FactoryHub has more or if local points are empty
    existing_points = (await session.scalars(
        select(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id).order_by(InspectionPoint.order_index)
    )).all()

    points_updated = False
    if len(points_data) > 0 and (len(existing_points) == 0 or len(points_data) > len(existing_points)):
        print(f"  [+] Updating {len(points_data)} inspection points from FactoryHub (was {len(existing_points)})")
        await session.execute(delete(InspectionPoint).where(InspectionPoint.checksheet_id == cs.id))
        for idx, pt in enumerate(points_data):
            new_pt = InspectionPoint(
                checksheet_id=cs.id,
                item_no=pt.get("item_no") or str(idx + 1),
                inspection_item=pt.get("inspection_item") or "-",
                standard=pt.get("standard") or "-",
                method=pt.get("method") or "Visual",
                master_data=pt.get("master_data") or "",
                order_index=idx
            )
            session.add(new_pt)
        points_updated = True

    await session.commit()
    return {
        "status": "success",
        "part_number": cs.part_number,
        "images_found": len(img_urls),
        "images_downloaded": downloaded_images,
        "points_found": len(points_data),
        "points_updated": points_updated
    }


async def sync_checksheets_list(part_numbers: Optional[List[str]] = None):
    async with AsyncSessionLocal() as session:
        if part_numbers:
            query = select(Checksheet).where(Checksheet.part_number.in_(part_numbers))
        else:
            # Sync checksheets that have a FactoryHub URL but 0 images in DB
            pts_sub = (
                select(PartImage.checksheet_id)
                .distinct()
                .subquery()
            )
            query = (
                select(Checksheet)
                .where(
                    Checksheet.factoryhub_url.isnot(None),
                    ~Checksheet.id.in_(select(pts_sub.c.checksheet_id))
                )
            )

        checksheets = (await session.scalars(query)).all()
        print(f"[*] Found {len(checksheets)} checksheets to sync from FactoryHub.")

        if not checksheets:
            print("[*] No checksheets need synchronization.")
            return

        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="msedge", headless=True)
            context = await browser.new_context(ignore_https_errors=True)
            page = await context.new_page()
            await login_factoryhub(page)

            for cs in checksheets:
                try:
                    res = await sync_single_checksheet_from_factoryhub(page, cs, session)
                    print(f"[+] Result for {cs.part_number}: {res}")
                except Exception as e:
                    print(f"[-] Error syncing {cs.part_number}: {e}")

            await browser.close()

        print("[*] Synchronization complete!")


if __name__ == "__main__":
    target_parts = sys.argv[1:] if len(sys.argv) > 1 else None
    asyncio.run(sync_checksheets_list(target_parts))
