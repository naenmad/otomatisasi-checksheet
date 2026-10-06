"""
Sync Checksheet Categories from Supabase Database to FactoryHub.

Iterates over checksheets with existing factoryhub_url where category != 'Accuracy',
navigates to the edit page on FactoryHub, selects the correct category dropdown option,
and submits the update.

Usage:
    python scripts/sync_factoryhub_categories.py --limit 5 --dry-run
    python scripts/sync_factoryhub_categories.py --limit 10
    python scripts/sync_factoryhub_categories.py --part 1530A303
    python scripts/sync_factoryhub_categories.py --all
"""

import os
import sys
import argparse
import asyncio
from typing import Optional, List
from playwright.async_api import async_playwright

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import AsyncSessionLocal
from database.models import Checksheet
from core.automator import login_factoryhub
from sqlalchemy import select


CATEGORY_OPTIONS_MAP = {
    "subcont": "Incomming Subcont Part",
    "material": "Incomming Material",
    "std": "Incomming Std Part",
    "ssw": "Accuracy SSW",
    "accuracy": "Accuracy",
    "general": "General"
}


def resolve_factoryhub_category(cat: Optional[str]) -> str:
    s = (cat or "Accuracy").lower().strip()
    if "subcont" in s:
        return "Incomming Subcont Part"
    if "material" in s:
        return "Incomming Material"
    if "std" in s:
        return "Incomming Std Part"
    if "ssw" in s:
        return "Accuracy SSW"
    if "accuracy" in s:
        return "Accuracy"
    if "general" in s:
        return "General"
    return cat or "Accuracy"


async def sync_categories(limit: Optional[int] = None, dry_run: bool = False, target_part: Optional[str] = None):
    async with AsyncSessionLocal() as session:
        query = (
            select(Checksheet)
            .where(
                Checksheet.factoryhub_url.isnot(None),
                Checksheet.factoryhub_url != "",
                Checksheet.category != "Accuracy"
            )
            .order_by(Checksheet.id)
        )
        if target_part:
            query = select(Checksheet).where(Checksheet.part_number == target_part)

        if limit and limit > 0:
            query = query.limit(limit)

        checksheets = (await session.scalars(query)).all()
        total = len(checksheets)
        print(f"[*] Ditemukan {total} checksheet dengan FactoryHub URL yang perlu dicek kategorinya.")

        if not total:
            return

        async with async_playwright() as p:
            browser = None
            context = None
            page = None

            async def ensure_page():
                nonlocal browser, context, page
                if page and not page.is_closed():
                    return page
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                page.on("dialog", lambda d: asyncio.create_task(d.accept()))
                await login_factoryhub(page)
                return page

            page = await ensure_page()

            updated_count = 0
            skipped_count = 0
            failed_count = 0

            for idx, cs in enumerate(checksheets, 1):
                target_cat = resolve_factoryhub_category(cs.category)
                url = cs.factoryhub_url

                # Ensure URL is edit URL
                if "/edit" not in url:
                    print(f"[{idx}/{total}] [SKIP] {cs.part_number}: URL bukan edit URL ({url})")
                    skipped_count += 1
                    continue

                for attempt in range(2):
                    try:
                        page = await ensure_page()
                        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
                        await asyncio.sleep(0.3)

                        # Check current category selected on FactoryHub
                        current_cat = await page.evaluate("""() => {
                            const sel = document.querySelector('select[name="category"]');
                            if (!sel || sel.selectedIndex < 0) return null;
                            return sel.options[sel.selectedIndex].text.trim();
                        }""")

                        if not current_cat:
                            print(f"[{idx}/{total}] [WARN] {cs.part_number}: Elemen select[name='category'] tidak ditemukan di {url}")
                            failed_count += 1
                            break

                        if current_cat.lower() == target_cat.lower():
                            print(f"[{idx}/{total}] [OK] {cs.part_number}: Kategori sudah sesuai ('{current_cat}')")
                            skipped_count += 1
                            break

                        print(f"[{idx}/{total}] [UPDATE] {cs.part_number}: '{current_cat}' -> '{target_cat}'")

                        if dry_run:
                            print(f"         [DRY RUN] Lewati submit untuk {cs.part_number}")
                            updated_count += 1
                            break

                        # Select new category
                        set_res = await page.evaluate("""(target) => {
                            const sel = document.querySelector('select[name="category"]');
                            if (!sel) return false;
                            for (let i = 0; i < sel.options.length; i++) {
                                const opt = sel.options[i];
                                if (opt.value.toLowerCase().trim() === target.toLowerCase().trim() ||
                                    opt.text.toLowerCase().trim() === target.toLowerCase().trim()) {
                                    sel.selectedIndex = i;
                                    sel.dispatchEvent(new Event('input', { bubbles: true }));
                                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                                    return true;
                                }
                            }
                            return false;
                        }""", target_cat)

                        if not set_res:
                            print(f"         [FAIL] Opsi '{target_cat}' tidak ditemukan dalam dropdown FactoryHub.")
                            failed_count += 1
                            break

                        # Submit form
                        submit_btn = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]')
                        if submit_btn:
                            await submit_btn.click()
                            try:
                                await page.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                pass
                            await asyncio.sleep(0.5)
                            print(f"         [✓] Berhasil diupdate di FactoryHub!")
                            updated_count += 1
                        else:
                            print(f"         [FAIL] Tombol submit tidak ditemukan.")
                            failed_count += 1
                        break

                    except Exception as e:
                        if attempt == 0:
                            print(f"[{idx}/{total}] [RETRY] {cs.part_number}: Browser reload karena error: {e}")
                            page = None  # Force ensure_page to re-create browser
                            await asyncio.sleep(1)
                        else:
                            print(f"[{idx}/{total}] [ERROR] {cs.part_number} ({url}): {e}")
                            failed_count += 1

            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

            print("\n" + "=" * 50)
            print("RINGKASAN SINKRONISASI KATEGORI FACTORYHUB:")
            print(f"Total Dicek : {total}")
            print(f"Diupdate    : {updated_count}")
            print(f"Dilewati    : {skipped_count}")
            print(f"Gagal       : {failed_count}")
            print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description="Sync Checksheet categories to FactoryHub")
    parser.add_argument("--limit", type=int, default=None, help="Maksimal jumlah checksheet yang diproses")
    parser.add_argument("--dry-run", action="store_true", help="Cek tanpa menyimpan perubahan di FactoryHub")
    parser.add_argument("--part", type=str, default=None, help="Part number tertentu")
    parser.add_argument("--all", action="store_true", help="Proses semua checksheet yang memenuhi syarat")

    args = parser.parse_args()
    asyncio.run(sync_categories(limit=args.limit, dry_run=args.dry_run, target_part=args.part))


if __name__ == "__main__":
    main()
