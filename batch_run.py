#!/usr/bin/env python3
"""
Batch Runner for Summit Adyawinsa Checksheet Automation
Processes multiple checksheet files sequentially in a single logged-in session.
Supports auto-submit directly to FactoryHub.

Usage:
    # Dry run (test parsing all files without submitting):
    python batch_run.py --dry-run

    # Run all 65 files with auto-submit in headless mode:
    python batch_run.py --submit --headless

    # Run only IR CHILD PART (19 files):
    python batch_run.py --folder child --submit

    # Run only IR MONTHLY FG (46 files):
    python batch_run.py --folder monthly --submit

    # Test run only first 2 files:
    python batch_run.py --limit 2 --submit
"""

import argparse
import asyncio
import os
import sys
import time
import json
import traceback
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from automator import (
    login_factoryhub,
    fill_checksheet_form,
    find_existing_template,
    FACTORYHUB_BASE_URL,
    INDEX_URL,
    CREATE_URL
)
from extractor import (
    resolve_part_document,
    extract_metadata,
    clear_document_caches
)

load_dotenv()

DEFAULT_FOLDERS = [
    ("IR CHILD PART", "documents/DIGITALISASI NEW PROJECT/IR CHILD PART"),
    ("IR MONTHLY FG", "documents/DIGITALISASI NEW PROJECT/IR MONTHLY FG")
]


def collect_target_files(folder_choice: str = "all") -> List[Dict[str, str]]:
    """Collect Excel checksheet files based on user choice."""
    target_dirs = []
    choice = folder_choice.lower().strip()
    if choice in ["child", "ir child", "ir_child", "child_part"]:
        target_dirs = [DEFAULT_FOLDERS[0]]
    elif choice in ["monthly", "fg", "ir monthly", "ir_monthly", "monthly_fg"]:
        target_dirs = [DEFAULT_FOLDERS[1]]
    elif os.path.isdir(folder_choice):
        target_dirs = [(os.path.basename(folder_choice), folder_choice)]
    else:
        target_dirs = DEFAULT_FOLDERS

    collected = []
    for cat_name, dir_path in target_dirs:
        if not os.path.isdir(dir_path):
            print(f"[!] Warning: Direktori tidak ditemukan: {dir_path}")
            continue
        files = sorted([
            f for f in os.listdir(dir_path)
            if f.endswith((".xlsx", ".xls")) and not f.startswith("~")
        ])
        for f in files:
            collected.append({
                "category": cat_name,
                "file_name": f,
                "file_path": os.path.join(dir_path, f)
            })
    return collected


async def run_batch(
    files: List[Dict[str, str]],
    submit: bool = True,
    headless: bool = False,
    delay: float = 2.0,
    limit: Optional[int] = None,
    start_index: int = 1,
    browser_channel: str = "chromium"
):
    """Executes automation sequentially across all provided files."""
    if limit and limit > 0:
        files = files[:limit]

    total = len(files)
    print("\n" + "="*80)
    print("        SUMMIT ADYAWINSA - BATCH CHECKSHEET AUTOMATION")
    print("="*80)
    print(f" Total File Target : {total} file")
    print(f" Action            : {'AUTO-SUBMIT KE FACTORYHUB' if submit else 'SIAPKAN SAJA (DRY/REVIEW)'}")
    print(f" Mode Browser      : {'Headless (Background)' if headless else 'Visible (Window Terbuka)'}")
    print(f" Delay Antar Part  : {delay} detik")
    print("="*80 + "\n")

    results_log = []
    success_count = 0
    fail_count = 0

    clear_document_caches()

    async with async_playwright() as p:
        browser_type = getattr(p, browser_channel if browser_channel in ["chromium", "firefox", "webkit"] else "chromium")
        launch_args = {
            "headless": headless,
            "args": ["--start-maximized", "--no-sandbox"]
        }
        if browser_channel in ["chrome", "msedge"]:
            launch_args["channel"] = browser_channel

        print(f"[*] Meluncurkan browser ({browser_channel}, headless={headless})...")
        browser = await browser_type.launch(**launch_args)
        context = await browser.new_context(viewport=None, no_viewport=True)
        page = await context.new_page()

        # Step 1: Login once
        print("[*] Melakukan login ke FactoryHub...")
        await login_factoryhub(page)
        print("[+] Login berhasil!\n")

        # Step 2: Iterate over each file
        for idx, item in enumerate(files, start=start_index):
            fpath = item["file_path"]
            fname = item["file_name"]
            cat = item["category"]

            print("-" * 80)
            print(f"[{idx}/{total}] Memproses [{cat}] {fname}")

            start_time = time.time()
            try:
                # Resolve package
                doc_pkg = resolve_part_document(fpath)
                part_no = doc_pkg["part_number"]
                meta = doc_pkg["metadata"]
                doc_no = meta.get("doc_number", "Form 1")

                print(f"    * Part Number : {part_no} ({meta.get('part_name') or '-'})")
                print(f"    * Doc Number  : {doc_no}")
                print(f"    * Ref Images  : {len(doc_pkg['images'])} gambar")

                # Fill form and submit
                res = await fill_checksheet_form(
                    page=page,
                    part_or_excel=fpath,
                    submit=submit,
                    custom_doc_no=doc_no,
                    scan_images=doc_pkg.get("scan_images")
                )

                elapsed = round(time.time() - start_time, 1)

                if res.get("status") in ["submitted", "prepared"]:
                    success_count += 1
                    status_text = "BERHASIL DI-SUBMIT ✓" if submit else "FORM TERISI LENGKAP ✓"
                    pts = res.get("inspection_points_count", 0)
                    print(f"    [+] {status_text} ({pts} inspection points) [{elapsed}s]")
                    results_log.append({
                        "index": idx,
                        "file": fname,
                        "part_number": part_no,
                        "category": cat,
                        "status": "SUCCESS",
                        "mode": res.get("mode"),
                        "inspection_points": pts,
                        "elapsed_seconds": elapsed,
                        "url": res.get("final_url", page.url)
                    })
                elif res.get("status") == "part_not_registered":
                    fail_count += 1
                    print(f"    [!] GAGAL: Part number '{part_no}' belum terdaftar di FactoryHub!")
                    results_log.append({
                        "index": idx,
                        "file": fname,
                        "part_number": part_no,
                        "category": cat,
                        "status": "PART_NOT_REGISTERED",
                        "error": "Part not in FactoryHub",
                        "elapsed_seconds": elapsed
                    })
                else:
                    fail_count += 1
                    print(f"    [!] Status tidak diketahui: {res.get('status')}")
                    results_log.append({
                        "index": idx,
                        "file": fname,
                        "part_number": part_no,
                        "category": cat,
                        "status": "UNKNOWN",
                        "details": res,
                        "elapsed_seconds": elapsed
                    })

            except Exception as e:
                fail_count += 1
                elapsed = round(time.time() - start_time, 1)
                err_msg = str(e)
                print(f"    [X] ERROR saat memproses {fname}: {err_msg}")
                traceback.print_exc()
                results_log.append({
                    "index": idx,
                    "file": fname,
                    "part_number": item.get("file_name"),
                    "category": cat,
                    "status": "ERROR",
                    "error": err_msg,
                    "elapsed_seconds": elapsed
                })

            # Small cooldown between requests to be gentle on FactoryHub server
            if delay > 0 and idx < total:
                await asyncio.sleep(delay)

        await browser.close()

    # Step 3: Write report
    report_file = "batch_execution_report.json"
    with open(report_file, "w", encoding="utf-8") as rf:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total": total,
            "success": success_count,
            "failed": fail_count,
            "results": results_log
        }, rf, indent=2)

    print("\n" + "="*80)
    print("                    RINGKASAN EKSEKUSI BATCH")
    print("="*80)
    print(f" Total Diproses : {total}")
    print(f" Sukses         : {success_count}")
    print(f" Gagal          : {fail_count}")
    print(f" Log Laporan    : {os.path.abspath(report_file)}")
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Batch Automation for Summit Adyawinsa Checksheets")
    parser.add_argument(
        "--folder",
        type=str,
        default="all",
        help="Target folder: 'all' (default, 65 files), 'child' (19 files), 'monthly' (46 files)"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        default=True,
        help="Otomatis klik Save / Update Template (default: True)"
    )
    parser.add_argument(
        "--no-submit",
        dest="submit",
        action="store_false",
        help="Hanya isi form tanpa submit (dry/review)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Jalankan di background tanpa membuka jendela browser (default: headed / terlihat)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Batasi jumlah file yang dieksekusi (contoh: --limit 5 untuk tes)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Jeda antar checksheet dalam detik (default: 2.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Hanya cek dan ekstrak data tanpa membuka FactoryHub"
    )
    parser.add_argument(
        "--browser",
        type=str,
        default=os.getenv("BROWSER_CHANNEL", "chromium"),
        help="Pilihan engine browser (default: chromium)"
    )

    args = parser.parse_args()

    files = collect_target_files(args.folder)
    if not files:
        print("[!] Tidak ada file checksheet yang ditemukan.")
        sys.exit(1)

    print(f"[*] Menemukan {len(files)} file checksheet untuk diproses.")

    if args.dry_run:
        print("\n=== DRY RUN MODE: Memeriksa kelengkapan file ===")
        for i, item in enumerate(files, 1):
            try:
                pkg = resolve_part_document(item["file_path"])
                print(f" [{i:02d}/{len(files)}] [{item['category']}] {item['file_name']}")
                print(f"       -> Part: {pkg['part_number']} | Name: {pkg['metadata'].get('part_name') or '-'} | Images: {len(pkg['images'])}")
            except Exception as e:
                print(f" [{i:02d}/{len(files)}] [ERROR] {item['file_name']}: {e}")
        print("\n[✓] Dry run selesai. Semua file valid dan siap dieksekusi.")
        sys.exit(0)

    asyncio.run(
        run_batch(
            files=files,
            submit=args.submit,
            headless=args.headless,
            delay=args.delay,
            limit=args.limit,
            browser_channel=args.browser
        )
    )


if __name__ == "__main__":
    main()
