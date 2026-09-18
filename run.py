#!/usr/bin/env python3
"""
CLI Runner for Summit Adyawinsa Checksheet Automation
Supports Excel (.xlsx) and PDF (.pdf) checksheets.
Usage:
    python run.py [part_number] [scan_image: yes/no]
    python run.py 75510W050P
    python run.py 75511b040p no
    python run.py 51138e000p yes
    python run.py --part 75510W050P --dry-run
"""

import argparse
import asyncio
import os
import sys
from typing import Optional
from dotenv import load_dotenv

from extractor import resolve_part_document, list_available_parts, extract_inspection_points
from automator import run_automation

load_dotenv()


def parse_scan_image_value(val: Optional[str]) -> Optional[bool]:
    """Parse string representation of scan_images flag."""
    if val is None:
        return None
    v = str(val).strip().lower()
    if v in ["true", "1", "yes", "y", "ya", "scan", "scan-image", "scan_image"]:
        return True
    if v in ["false", "0", "no", "n", "tidak", "no-scan", "noscan", "no-scan-image", "no_scan_image"]:
        return False
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Summit Adyawinsa Checksheet Master Automation",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "part_or_scan",
        nargs="*",
        help=(
            "Argumen posisi fleksibel:\n"
            "  1. <part_number> [scan_image]\n"
            "     Contoh: run.py 75511b040p no\n"
            "     Contoh: run.py 75510W050P\n"
        )
    )
    parser.add_argument(
        "-p", "--part",
        type=str,
        default=None,
        help="Part number atau nama folder di documents/ (contoh: 75510W050P, 51138e000p)"
    )
    parser.add_argument(
        "--scan-image",
        dest="scan_image",
        action="store_const",
        const=True,
        default=None,
        help="Paksa ekstrak gambar tersemat dari file Excel/PDF"
    )
    parser.add_argument(
        "--no-scan-image",
        dest="scan_image",
        action="store_const",
        const=False,
        help="Gunakan file gambar dari folder part (hasil scan data)"
    )
    parser.add_argument(
        "--excel", "--file",
        dest="excel",
        type=str,
        default=None,
        help="Path langsung ke file dokumen (.xlsx / .pdf)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Jalankan browser di background tanpa membuka jendela (default: headed / jendela terbuka)"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Otomatis klik 'Save / Update Template' (default: pause untuk review manual)"
    )
    parser.add_argument(
        "--doc-number",
        type=str,
        default=None,
        help="Custom Doc Number (contoh: 'Form 6'). Jika kosong, diambil dari nama file/folder."
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help="Folder kustom untuk gambar manual"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Tampilkan daftar part yang tersedia di folder documents/ lalu keluar"
    )
    parser.add_argument(
        "--browser",
        type=str,
        default=os.getenv("BROWSER_CHANNEL", "chromium"),
        help="Pilihan engine browser: chromium (Chrome Testing, default), chrome (Google Chrome), msedge (Microsoft Edge)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Uji coba parsing data dan gambar tanpa membuka browser/FactoryHub"
    )

    args = parser.parse_args()

    available_parts = list_available_parts("documents")

    if args.list:
        print("\n=== Daftar Part Tersedia di folder documents/ ===")
        if not available_parts:
            print(" (Belum ada part di folder documents/)")
        for i, p in enumerate(available_parts, 1):
            status_tag = f"[{p.get('status', 'belum').upper()}]"
            type_tag = p.get('file_type', 'excel').upper()
            mode_desc = f"Scan Data ({p['image_count']} gambar)" if p["is_scan_data"] else f"{type_tag} Mentah"
            print(f" {status_tag:<8} [{i:<2}] {p['folder_name']} | Part: {p['part_number']} | File: {p['excel_file']} | {mode_desc}")
        sys.exit(0)

    # Resolve positional arguments
    target_part = args.part
    scan_images = args.scan_image

    pos_args = args.part_or_scan or []
    if len(pos_args) == 1:
        bool_val = parse_scan_image_value(pos_args[0])
        if bool_val is not None:
            if scan_images is None:
                scan_images = bool_val
        else:
            if not target_part:
                target_part = pos_args[0]
    elif len(pos_args) >= 2:
        b0 = parse_scan_image_value(pos_args[0])
        b1 = parse_scan_image_value(pos_args[1])
        if b0 is not None and b1 is None:
            if scan_images is None:
                scan_images = b0
            if not target_part:
                target_part = pos_args[1]
        elif b1 is not None and b0 is None:
            if scan_images is None:
                scan_images = b1
            if not target_part:
                target_part = pos_args[0]
        else:
            if not target_part:
                target_part = pos_args[0]

    # If neither target_part nor --excel is specified, prompt or show available parts
    if not target_part and not args.excel:
        if available_parts:
            print("\n==================================================")
            print("   FactoryHub Checksheet Master Automation")
            print("==================================================")
            print("Tersedia dokumen part di folder documents/:")
            for i, p in enumerate(available_parts, 1):
                status_tag = f"[{p.get('status', 'belum').upper()}]"
                type_label = f"Hasil Scan Data ({p['image_count']} gambar)" if p["is_scan_data"] else f"{p.get('file_type','excel').upper()} Mentah"
                print(f"  {status_tag:<8} [{i:<2}] {p['folder_name']} (Part No: {p['part_number']}) -> {type_label}")
            print("==================================================")

            if sys.stdin.isatty():
                try:
                    choice = input(f"Pilih nomor [1-{len(available_parts)}] atau ketik part number [1]: ").strip()
                    if not choice:
                        choice = "1"
                    if choice.isdigit() and 1 <= int(choice) <= len(available_parts):
                        target_part = available_parts[int(choice) - 1]["folder_name"]
                    else:
                        target_part = choice
                except (KeyboardInterrupt, EOFError):
                    print("\nDibatalkan.")
                    sys.exit(0)
            else:
                target_part = available_parts[0]["folder_name"]
                print(f"[*] Non-interaktif: Menggunakan part pertama: {target_part}")
        else:
            print("[!] Error: Tidak ada part yang ditemukan di folder documents/ dan opsi --excel tidak diberikan.")
            sys.exit(1)

    part_or_excel = args.excel if args.excel else target_part

    # Resolve document package
    try:
        doc_pkg = resolve_part_document(
            part_or_path=part_or_excel,
            scan_images=scan_images,
            manual_images_dir=args.images_dir
        )
    except FileNotFoundError as e:
        print(f"[!] Error: {e}")
        sys.exit(1)

    part_no = doc_pkg["part_number"]
    file_path = doc_pkg["file_path"]
    file_type = doc_pkg["file_type"]
    images = doc_pkg["images"]
    actual_scan_mode = doc_pkg["scan_images"]
    meta = doc_pkg["metadata"]
    doc_no = args.doc_number or meta.get("doc_number", "Form 1")
    status = doc_pkg.get("status", "belum")

    print("\n==================================================")
    print("   FactoryHub Checksheet Master Automation")
    print("==================================================")
    print(f" Part Number : {part_no}")
    print(f" Status      : {status.upper()}")
    print(f" Folder      : {doc_pkg['folder_path']}")
    print(f" Document    : {os.path.basename(file_path)} ({file_type.upper()})")
    print(f" Doc Number  : {doc_no}")
    print(f" Part Name   : {meta.get('part_name') or '-'}")
    print(f" Model       : {meta.get('model') or '-'}")
    print(f" Scan Mode   : {'YA (Ekstrak dari dokumen)' if actual_scan_mode else 'TIDAK (Ambil gambar dari folder)'}")
    print(f" Ref Images  : {len(images)} file gambar")
    print(f" Browser     : {'Headless' if args.headless else 'Visible (Siap Review)'}")
    print(f" Action      : {'AUTO-SUBMIT' if args.submit else 'REVIEW & SAVE MANUAL'}")
    print("==================================================\n")

    if args.dry_run:
        print(f"[*] DRY RUN MODE: Membaca titik inspeksi dari {file_type.upper()}...")
        items = extract_inspection_points(file_path)
        print(f"[+] Berhasil mengekstrak {len(items)} titik inspeksi.")
        print("[*] Sampel 5 titik inspeksi pertama:")
        for idx, it in enumerate(items[:5], 1):
            print(f"    {idx}. Balloon #{it['item_no']} | {it['inspection_item']} | Std: {it['standard']} | Method: {it['method']}")
        print(f"\n[*] Daftar Gambar Referensi ({len(images)} file):")
        for idx, img in enumerate(images[:5], 1):
            print(f"    {idx}. {os.path.basename(img)}")
        if len(images) > 5:
            print(f"    ... dan {len(images) - 5} gambar lainnya")
        print("\n[✓] Dry-run selesai. Semua data siap diproses ke FactoryHub.")
        sys.exit(0)

    result = asyncio.run(
        run_automation(
            part_or_excel=part_or_excel,
            headless=args.headless,
            submit=args.submit,
            doc_number=doc_no,
            manual_images_dir=args.images_dir,
            scan_images=actual_scan_mode,
            browser_channel=args.browser
        )
    )

    if result and result.get("status") == "part_not_registered":
        sys.exit(1)


if __name__ == "__main__":
    main()
