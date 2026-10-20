"""
Fast Batch Updater: Fix all 58 misclassified IR checksheets to 'IR MONTHLY REPORT'.
"""
import os
import sys
import asyncio
from playwright.async_api import async_playwright
from sqlalchemy import update, select

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.automator import login_factoryhub, INDEX_URL
from database.connection import AsyncSessionLocal
from database.models import Checksheet
from database.crud import get_checksheets_summary_list
import json

TARGET_PARTS = [
    '51138E000P', '65140E000P', '65141E000P', '65612E000P', '67148E000P', '67148E020P',
    '73210E000P', '73211E010P', '73230E000P', '73231E000P', '73234E000P', '73235E000P',
    '73242E000P', '73252E000P', '73272E000P', '73282E000P', '73944E000P', '743F4E000P',
    '745A2E050P', '745A3E000P', '745C0E020P', '75424E000P', '76654E000P', '76655E000P',
    '76714E000P', '76715E000P', '76742E010P', '76743E010P', '76750E000P', '76751E000P',
    '76756E010P', '76756E020P', '76757E010P', '76757E020P', '76758E000P', '76762E000P',
    '76763E000P', '767E6E000P', '767E7E000P', '80119E000P', '80126E010P', '80127E010P',
    '80148E000P', '80149E000P', '80182E000P', '80182E050P', '80183E000P', '80183E070P',
    '801G4E000P', '801G5E000P', '82118E000P', '82119E000P', '82126E010P', '82127E010P',
    '82198E000P', '82199E000P', '90149E000P', '96991E010P'
]

async def main():
    print("=" * 70)
    print("  BATCH FIX: 58 TEMPLATE IR -> 'IR MONTHLY REPORT' & 'monthly_mmki'")
    print("=" * 70)

    # 1. Fetch existing known URLs from DB
    db_urls = {}
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(Checksheet.part_number, Checksheet.factoryhub_url)
            .where(Checksheet.part_number.in_(TARGET_PARTS))
        )
        for pn, url in res.all():
            if url:
                db_urls[pn] = url

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await login_factoryhub(page)

        success = 0
        failed = 0

        for idx, pn in enumerate(TARGET_PARTS, 1):
            print(f"\n[{idx}/{len(TARGET_PARTS)}] Memproses: {pn}...")
            edit_url = db_urls.get(pn)

            # If no direct URL, search on FactoryHub
            if not edit_url or "/edit" not in edit_url:
                search_url = f"{INDEX_URL}?search={pn}"
                await page.goto(search_url, wait_until='networkidle')
                found_url = await page.evaluate(r"""(part) => {
                    const trs = document.querySelectorAll('table tbody tr');
                    for (let tr of trs) {
                        const nameCell = tr.cells[0] ? tr.cells[0].innerText.trim() : '';
                        if (nameCell === part || nameCell.includes(part)) {
                            const a = tr.querySelector('a[href*="/edit"]');
                            if (a) return a.href;
                        }
                    }
                    return null;
                }""", pn)

                if found_url:
                    edit_url = found_url
                    db_urls[pn] = edit_url
                else:
                    print(f"  [!] Tidak ditemukan di FactoryHub: {pn}")
                    failed += 1
                    continue

            try:
                await page.goto(edit_url, wait_until='networkidle')

                # Update Category & Format
                res = await page.evaluate(r"""() => {
                    const catSel = document.querySelector('select[name="category"]');
                    if (!catSel) return { ok: false, msg: 'No category select' };

                    // Category -> IR MONTHLY REPORT
                    let catMatched = false;
                    for (let i = 0; i < catSel.options.length; i++) {
                        const opt = catSel.options[i];
                        if (opt.value === 'IR MONTHLY REPORT' || opt.text.includes('IR MONTHLY')) {
                            catSel.selectedIndex = i;
                            catSel.dispatchEvent(new Event('input', { bubbles: true }));
                            catSel.dispatchEvent(new Event('change', { bubbles: true }));
                            catMatched = true;
                            break;
                        }
                    }

                    // Format -> monthly_mmki
                    const fmtSel = document.querySelector('select[name="format"]');
                    if (fmtSel) {
                        fmtSel.value = 'monthly_mmki';
                        fmtSel.dispatchEvent(new Event('input', { bubbles: true }));
                        fmtSel.dispatchEvent(new Event('change', { bubbles: true }));
                    }

                    return { ok: catMatched };
                }""")

                if not res.get("ok"):
                    print(f"  [!] Gagal memilih kategori IR MONTHLY REPORT pada {pn}")
                    failed += 1
                    continue

                # Submit Form
                submit_btn = await page.query_selector('button[type="submit"]:has-text("Update Template"), button[type="submit"]:has-text("Save"), button[type="submit"]')
                if submit_btn:
                    await submit_btn.click()
                    try:
                        await page.wait_for_load_state('networkidle', timeout=8000)
                    except Exception:
                        await page.wait_for_timeout(1500)

                    print(f"  [+] SUKSES: {pn} -> IR MONTHLY REPORT (Format: monthly_mmki)")
                    success += 1

                    # Update local database
                    try:
                        async with AsyncSessionLocal() as db_session:
                            stmt = (
                                update(Checksheet)
                                .where(Checksheet.part_number == pn)
                                .values(category="IR MONTHLY REPORT", factoryhub_url=edit_url)
                            )
                            await db_session.execute(stmt)
                            await db_session.commit()
                    except Exception as de:
                        pass
                else:
                    print(f"  [!] Tombol submit tidak ditemukan.")
                    failed += 1

            except Exception as e:
                print(f"  [!] Error saat update {pn}: {e}")
                failed += 1

        print("\n" + "=" * 70)
        print(f"  SELESAI! Sukses: {success} | Gagal: {failed} (Total: {len(TARGET_PARTS)})")
        print("=" * 70)

        # Refresh local summary cache
        try:
            print("[*] Merefresh cache ringkasan lokal...")
            async with AsyncSessionLocal() as db_session:
                summary = await get_checksheets_summary_list(db_session)
                cache_path = os.path.join(PROJECT_ROOT, "data", "checksheets_summary_cache.json")
                with open(cache_path, "w", encoding="utf-8") as f:
                    json.dump(summary, f, ensure_ascii=False)
            print("[+] Cache ringkasan lokal berhasil disinkronkan!")
        except Exception as ce:
            print(f"[!] Warning: Gagal refresh cache lokal: {ce}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
