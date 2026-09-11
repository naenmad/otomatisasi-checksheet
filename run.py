#!/usr/bin/env python3
"""
CLI Runner for Summit Adyawinsa Checksheet Automation
Usage:
    python run.py [part_number] [scan_image: yes/no]
    python run.py 75511b040p no
    python run.py 51138e000p yes
    python run.py --part 75511b040p --no-scan-image
    python run.py --excel "path/to/file.xlsx"
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
            "     Contoh: run.py 51138e000p yes\n"
        )
    )
    parser.add_argument(
        "-p", "--part",
        type=str,
        default=None,
        help="Part number atau nama folder di documents/ (contoh: 75511b040p, 51138e000p)"
    )
    parser.add_argument(
        "--scan-image",
        dest="scan_image",
        action="store_const",
        const=True,
        default=None,
        help="Paksa ekstrak gambar tersemat dari file Excel (mode Excel mentah)"
    )
    parser.add_argument(
        "--no-scan-image",
        dest="scan_image",
        action="store_const",
        const=False,
        help="Jangan scan Excel; gunakan file gambar dari folder part (mode hasil scan data)"
    )
    parser.add_argument(
        "--excel",
        type=str,
        default=None,
        help="Path langsung ke file Excel (.xlsx) jika tidak menggunakan struktur documents/"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Jalankan browser di background tanpa membuka jendela (default: headed / jendela terbuka)"
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Otomatis klik 'Save Template' (default: pause untuk review manual)"
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
            mode_desc = "Hasil Scan Data (gambar lokal)" if p["is_scan_data"] else "Excel Mentah (gambar di excel)"
            print(f" [{i}] {p['folder_name']} | Part: {p['part_number']} | Excel: {p['excel_file']} | {p['image_count']} gambar | {mode_desc}")
        sys.exit(0)

    # Resolve positional arguments
    target_part = args.part
    scan_images = args.scan_image

    pos_args = args.part_or_scan or []
    if len(pos_args) == 1:
        # Could be part or boolean flag
        bool_val = parse_scan_image_value(pos_args[0])
        if bool_val is not None:
            if scan_images is None:
                scan_images = bool_val
        else:
            if not target_part:
                target_part = pos_args[0]
    elif len(pos_args) >= 2:
        # Check which is bool and which is part
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
                type_label = f"Hasil Scan Data ({p['image_count']} gambar)" if p["is_scan_data"] else "Excel Mentah (scan dari excel)"
                print(f"  [{i}] {p['folder_name']} (Part No: {p['part_number']}) -> {type_label}")
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
                # Default to first available part if non-interactive
                target_part = available_parts[0]["folder_name"]
                print(f"[*] Non-interaktif: Menggunakan part pertama: {target_part}")
        else:
            print("[!] Error: Tidak ada part yang ditemukan di folder documents/ dan opsi --excel tidak diberikan.")
            print("[!] Harap letakkan dokumen di folder documents/<part_number>/ atau tentukan path file.")
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
    excel_path = doc_pkg["excel_path"]
    images = doc_pkg["images"]
    actual_scan_mode = doc_pkg["scan_images"]
    meta = doc_pkg["metadata"]
    doc_no = args.doc_number or meta.get("doc_number", "Form 1")

    print("\n==================================================")
    print("   FactoryHub Checksheet Master Automation")
    print("==================================================")
    print(f" Part Number : {part_no}")
    print(f" Folder      : {doc_pkg['folder_path']}")
    print(f" Excel File  : {os.path.basename(excel_path)}")
    print(f" Doc Number  : {doc_no}")
    print(f" Part Name   : {meta.get('part_name') or '-'}")
    print(f" Model       : {meta.get('model') or '-'}")
    print(f" Scan Excel  : {'YA (Ekstrak dari sheet Excel)' if actual_scan_mode else 'TIDAK (Ambil gambar dari folder)'}")
    print(f" Ref Images  : {len(images)} file gambar")
    print(f" Browser     : {'Headless' if args.headless else 'Visible (Siap Review)'}")
    print(f" Action      : {'AUTO-SUBMIT' if args.submit else 'REVIEW & SAVE MANUAL'}")
    print("==================================================\n")

    if args.dry_run:
        print("[*] DRY RUN MODE: Membaca titik inspeksi...")
        items = extract_inspection_points(excel_path)
        print(f"[+] Berhasil mengekstrak {len(items)} titik inspeksi.")
        print("[*] Sampel 5 titik inspeksi pertama:")
        for idx, it in enumerate(items[:5], 1):
            print(f"    {idx}. Balloon #{it['item_no']} | {it['inspection_item']} | Std: {it['standard']}")
        print("\n[*] Daftar Gambar Referensi:")
        for idx, img in enumerate(images, 1):
            print(f"    {idx}. {os.path.basename(img)} ({img})")
        print("\n[✓] Dry-run selesai. Semua data siap diproses ke FactoryHub.")
        sys.exit(0)

    result = asyncio.run(
        run_automation(
            part_or_excel=part_or_excel,
            headless=args.headless,
            submit=args.submit,
            doc_number=doc_no,
            manual_images_dir=args.images_dir,
            scan_images=actual_scan_mode
        )
    )

    if result and result.get("status") == "part_not_registered":
        sys.exit(1)

if __name__ == "__main__":
    main()
