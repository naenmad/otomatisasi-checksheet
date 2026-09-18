#!/usr/bin/env python3
"""
duplicate.py - Duplikasi Data Part & Dokumen Checksheet

Modul ini memungkinkan duplikasi seluruh data checksheet (file dokumen Excel/PDF,
sketsa gambar inspeksi, dan info metadata) dari suatu nomor part sumber ke nomor
part target baru (misal: 76750B040P -> 76750B040PQ).
"""

import os
import sys
import re
import json
import shutil
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

from catalog_manager import load_catalog, clean_code
from extractor import resolve_part_document, clear_document_caches


def duplicate_part(
    source_part_or_folder: str,
    target_part_number: str,
    target_status: str = "belum",
    rename_files: bool = True
) -> Dict[str, Any]:
    """
    Duplikasi seluruh dokumen, sketsa gambar, dan metadata dari part sumber ke part target.

    Args:
        source_part_or_folder: Part number asal atau nama folder asal (misal: '76750B040P')
        target_part_number: Part number tujuan baru (misal: '76750B040PQ')
        target_status: Kategori folder tujuan ('belum', 'tidak_ada_part', 'done'). Default: 'belum'
        rename_files: Jika True, ganti kemunculan part lama pada nama file dokumen menjadi part baru.

    Returns:
        Dict berisi informasi hasil duplikasi.
    """
    src_target = source_part_or_folder.strip()
    target_part = target_part_number.strip().upper()

    if not src_target:
        raise ValueError("Nomor part sumber tidak boleh kosong.")
    if not target_part:
        raise ValueError("Nomor part target tidak boleh kosong.")

    if target_status not in ["belum", "tidak_ada_part", "done"]:
        target_status = "belum"

    # 1. Cari dan verifikasi folder sumber
    src_folder_path = None
    src_status = "belum"
    src_part_number = src_target

    # Cek apakah source_part_or_folder adalah path langsung
    if os.path.isdir(src_target):
        src_folder_path = os.path.abspath(src_target)
        if "tidak_ada_part" in src_folder_path:
            src_status = "tidak_ada_part"
        elif "done" in src_folder_path:
            src_status = "done"
        else:
            src_status = "belum"
    else:
        # Coba resolve lewat resolve_part_document
        try:
            resolved = resolve_part_document(src_target)
            src_folder_path = resolved["folder_path"]
            src_status = resolved.get("status", "belum")
            src_part_number = resolved.get("part_number") or src_target
        except Exception:
            # Cari manual di documents/<status>/<src_target>
            for st in ["belum", "done", "tidak_ada_part"]:
                cand = os.path.join("documents", st, src_target)
                if os.path.isdir(cand):
                    src_folder_path = os.path.abspath(cand)
                    src_status = st
                    break

    if not src_folder_path or not os.path.isdir(src_folder_path):
        raise FileNotFoundError(f"Folder atau part sumber '{src_target}' tidak ditemukan di documents/.")

    # 2. Siapkan folder target
    safe_target_name = re.sub(r'[\\/:*?"<>|]', '_', target_part)
    target_folder_path = os.path.abspath(os.path.join("documents", target_status, safe_target_name))

    if os.path.exists(target_folder_path) and os.listdir(target_folder_path):
        raise FileExistsError(
            f"Folder target 'documents/{target_status}/{safe_target_name}' sudah ada dan tidak kosong. "
            f"Gunakan nomor part lain atau hapus folder tersebut terlebih dahulu."
        )

    os.makedirs(target_folder_path, exist_ok=True)

    # 3. Cari info resmi dari katalog master FactoryHub jika ada
    catalog = load_catalog()
    clean_target = clean_code(target_part)
    catalog_part_info = None
    for p in catalog.get("parts", []):
        if (p.get("clean_number") or clean_code(p.get("part_number", ""))) == clean_target:
            catalog_part_info = p
            break

    # Baca metadata lama dari info.json sumber jika ada
    src_info_path = os.path.join(src_folder_path, "info.json")
    src_info = {}
    if os.path.isfile(src_info_path):
        try:
            with open(src_info_path, "r", encoding="utf-8") as f:
                src_info = json.load(f)
        except Exception:
            src_info = {}

    # 4. Salin seluruh file dari folder sumber ke folder target
    files_copied = 0
    images_copied = 0
    doc_copied = 0
    image_exts = (".png", ".jpg", ".jpeg", ".webp")

    # Siapkan pola regex untuk rename file
    src_clean = clean_code(src_part_number)

    def get_renamed_filename(orig_name: str) -> str:
        if not rename_files:
            return orig_name

        # Jika nama file mengandung part number lama, ganti dengan yang baru
        if src_part_number in orig_name:
            return orig_name.replace(src_part_number, target_part)
        elif src_clean and src_clean in orig_name:
            return orig_name.replace(src_clean, target_part)
        elif src_target in orig_name:
            return orig_name.replace(src_target, target_part)
        return orig_name

    for root, dirs, files in os.walk(src_folder_path):
        # Hitung relative path terhadap src_folder_path
        rel_dir = os.path.relpath(root, src_folder_path)
        dest_dir = target_folder_path if rel_dir == "." else os.path.join(target_folder_path, rel_dir)
        os.makedirs(dest_dir, exist_ok=True)

        for f in files:
            # Lewati file sementara OS dan Office lockfiles
            if f.startswith("~$") or f.startswith(".") or f == "info.json":
                continue

            src_file_path = os.path.join(root, f)
            new_filename = get_renamed_filename(f)
            dest_file_path = os.path.join(dest_dir, new_filename)

            shutil.copy2(src_file_path, dest_file_path)
            files_copied += 1

            lower_f = f.lower()
            if lower_f.endswith(image_exts):
                images_copied += 1
            elif lower_f.endswith((".xlsx", ".xls", ".pdf")):
                doc_copied += 1

    # 5. Buat file info.json resmi untuk target part
    new_info_path = os.path.join(target_folder_path, "info.json")
    part_name = ""
    category = "REGULAR"
    has_template = False
    template_info = None

    if catalog_part_info:
        part_name = catalog_part_info.get("part_name", "")
        category = catalog_part_info.get("category", "REGULAR")
        has_template = catalog_part_info.get("has_template", False)
        template_info = catalog_part_info.get("template_info")
    elif src_info:
        part_name = src_info.get("part_name", "")
        category = src_info.get("category", "REGULAR")

    snippet_data = {
        "part_number": target_part,
        "part_name": part_name,
        "category": category,
        "duplicated_from": {
            "source_part": src_part_number,
            "source_status": src_status,
            "duplicated_at": datetime.now().isoformat()
        },
        "has_template_in_factoryhub": has_template,
        "template_details": template_info,
        "created_at": datetime.now().isoformat(),
        "notes": f"Diduplikasi dari part {src_part_number} (Status: {src_status})"
    }

    with open(new_info_path, "w", encoding="utf-8") as f:
        json.dump(snippet_data, f, indent=2, ensure_ascii=False)
    files_copied += 1

    # 6. Bersihkan cache dokumen agar dashboard langsung mendeteksi part baru
    clear_document_caches()

    # 7. Catat ke activity.log
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    activity_log_path = os.path.join(log_dir, "activity.log")
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = (
        f"[{timestamp_str}] DUPLICATE: From={src_part_number} ({src_status}) -> "
        f"To={target_part} ({target_status}) | Files={files_copied} (Docs={doc_copied}, Images={images_copied}) | "
        f"Notes=Duplikasi part berhasil\n"
    )
    try:
        with open(activity_log_path, "a", encoding="utf-8") as lf:
            lf.write(log_line)
    except Exception:
        pass

    return {
        "success": True,
        "source_part": src_part_number,
        "source_status": src_status,
        "target_part": target_part,
        "target_status": target_status,
        "target_folder": os.path.relpath(target_folder_path),
        "files_copied": files_copied,
        "images_copied": images_copied,
        "doc_copied": doc_copied,
        "part_name": part_name,
        "category": category,
        "message": (
            f"Part {target_part} berhasil diduplikasi dari {src_part_number} "
            f"ke documents/{target_status}/{safe_target_name} ({files_copied} file disalin)."
        )
    }


def main():
    parser = argparse.ArgumentParser(
        description="Duplikasi checksheet master dan gambar: mendukung mode Lokal dan mode Server FactoryHub."
    )
    parser.add_argument("--server", action="store_true", help="Mode Server: Scrape dari server FactoryHub dan buat template part baru di server")
    parser.add_argument("--from", "-f", dest="src", required=True, help="Nomor part asal (misal: 76750B040P)")
    parser.add_argument("--to", "-t", dest="target", required=True, help="Nomor part baru tujuan (misal: 76750B040PQ)")
    parser.add_argument(
        "--status", "-s", default="belum", choices=["belum", "done", "tidak_ada_part"],
        help="Kategori folder tujuan (default: belum)"
    )
    parser.add_argument(
        "--no-rename", action="store_true",
        help="Mode Lokal: Jangan otomatis rename nama file dokumen sesuai part baru"
    )
    parser.add_argument("--submit", action="store_true", help="Mode Server: Otomatis klik submit/save di FactoryHub")
    parser.add_argument("--headless", action="store_true", help="Mode Server: Jalankan tanpa membuka jendela browser")

    args = parser.parse_args()

    try:
        if args.server:
            import asyncio
            from server_duplicator import duplicate_server_to_server
            print(f"[*] Menjalankan Duplikasi Server-ke-Server: {args.src} ➔ {args.target}...")
            res = asyncio.run(duplicate_server_to_server(
                source_part=args.src,
                target_part=args.target,
                submit=args.submit,
                headless=args.headless,
                target_status=args.status
            ))
            print("\n[✓] DUPLIKASI SERVER SUKSES:")
            print(f"    - Part Sumber : {res['source_part']}")
            print(f"    - Part Target : {res['target_part']}")
            print(f"    - Folder      : {res['target_folder']}")
            print(f"    - Excel File  : {res.get('excel_path', '-')}")
            print(f"    - Poin Inspeksi: {res['points_count']} baris")
            print(f"    - Gambar      : {res['images_count']} file")
            print(f"\n[+] {res['message']}\n")
        else:
            res = duplicate_part(
                source_part_or_folder=args.src,
                target_part_number=args.target,
                target_status=args.status,
                rename_files=not args.no_rename
            )
            print("\n[✓] DUPLIKASI LOKAL SUKSES:")
            print(f"    - Part Sumber : {res['source_part']} ({res['source_status']})")
            print(f"    - Part Target : {res['target_part']} ({res['target_status']})")
            print(f"    - Folder      : {res['target_folder']}")
            print(f"    - Total File  : {res['files_copied']} (Dokumen: {res['doc_copied']}, Gambar: {res['images_copied']})")
            if res.get("part_name"):
                print(f"    - Part Name   : {res['part_name']}")
            print(f"\n[+] {res['message']}\n")
    except Exception as e:
        print(f"\n[!] Gagal menduplikasi part: {e}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
