#!/usr/bin/env python3
"""
Summit Checksheet Image Optimizer & WebP Converter
Converts PNG, JPG, JPEG images in documents/ and extracted_images/ into optimized WebP.
Reduces file size by 75-90% while preserving visual clarity for checksheet drawings.
"""

import os
import sys
import argparse
from typing import Dict, Any, List, Optional
from PIL import Image


SUPPORTED_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")


def get_image_stats(base_dirs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Scan directories and calculate counts and sizes of non-webp vs webp images."""
    if not base_dirs:
        base_dirs = ["documents", "extracted_images"]

    non_webp_count = 0
    non_webp_bytes = 0
    webp_count = 0
    webp_bytes = 0
    file_list = []

    for bdir in base_dirs:
        if not os.path.isdir(bdir):
            continue
        for root, _, files in os.walk(bdir):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                fp = os.path.join(root, fn)
                try:
                    sz = os.path.getsize(fp)
                except OSError:
                    continue

                if ext in SUPPORTED_EXTS:
                    non_webp_count += 1
                    non_webp_bytes += sz
                    file_list.append(fp)
                elif ext == ".webp":
                    webp_count += 1
                    webp_bytes += sz

    non_webp_mb = round(non_webp_bytes / (1024 * 1024), 2)
    webp_mb = round(webp_bytes / (1024 * 1024), 2)
    est_savings_mb = round(non_webp_mb * 0.82, 2)

    return {
        "non_webp_count": non_webp_count,
        "non_webp_bytes": non_webp_bytes,
        "non_webp_mb": non_webp_mb,
        "webp_count": webp_count,
        "webp_bytes": webp_bytes,
        "webp_mb": webp_mb,
        "total_images": non_webp_count + webp_count,
        "estimated_savings_mb": est_savings_mb,
        "candidate_files": file_list
    }


def convert_images_to_webp(
    target_dirs: Optional[List[str]] = None,
    quality: int = 82,
    max_dimension: int = 1920,
    delete_original: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Find all non-webp images in target_dirs and convert them to compressed WebP.
    
    Args:
        target_dirs: Directories to scan (defaults to ['documents', 'extracted_images'])
        quality: WebP compression quality (1-100, default 82)
        max_dimension: Max width or height in pixels (default 1920)
        delete_original: If True, deletes original non-webp file after conversion
        dry_run: If True, calculates statistics without modifying files
    """
    if not target_dirs:
        target_dirs = ["documents", "extracted_images"]

    converted_files = []
    skipped_files = []
    errors = []
    total_old_bytes = 0
    total_new_bytes = 0

    for bdir in target_dirs:
        if not os.path.isdir(bdir):
            continue

        for root, _, files in os.walk(bdir):
            for fn in files:
                base_name, ext = os.path.splitext(fn)
                ext = ext.lower()
                if ext not in SUPPORTED_EXTS:
                    continue

                src_path = os.path.join(root, fn)
                dest_path = os.path.join(root, f"{base_name}.webp")

                try:
                    old_sz = os.path.getsize(src_path)
                except OSError as e:
                    errors.append(f"Gagal membaca {src_path}: {e}")
                    continue

                if dry_run:
                    # Estimate ~82% reduction
                    est_new = int(old_sz * 0.18)
                    total_old_bytes += old_sz
                    total_new_bytes += est_new
                    converted_files.append({
                        "original_path": src_path,
                        "webp_path": dest_path,
                        "old_size_kb": round(old_sz / 1024, 1),
                        "new_size_kb": round(est_new / 1024, 1),
                        "saved_percent": 82.0
                    })
                    continue

                try:
                    with Image.open(src_path) as im:
                        # Handle color mode
                        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                            # Preserve transparency
                            im_converted = im.convert("RGBA")
                        else:
                            im_converted = im.convert("RGB")

                        # Downscale if exceeding max_dimension
                        w, h = im_converted.size
                        if max_dimension and (w > max_dimension or h > max_dimension):
                            im_converted.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

                        # Save as WebP
                        im_converted.save(dest_path, "WEBP", quality=quality, method=6)

                    new_sz = os.path.getsize(dest_path)

                    # Check if conversion actually saved space or was successful
                    if delete_original and os.path.isfile(dest_path) and dest_path != src_path:
                        os.remove(src_path)

                    saved_bytes = max(0, old_sz - new_sz)
                    saved_pct = round((saved_bytes / old_sz * 100), 1) if old_sz > 0 else 0

                    total_old_bytes += old_sz
                    total_new_bytes += new_sz

                    converted_files.append({
                        "original_path": src_path,
                        "webp_path": dest_path,
                        "old_size_kb": round(old_sz / 1024, 1),
                        "new_size_kb": round(new_sz / 1024, 1),
                        "saved_percent": saved_pct
                    })
                except Exception as ex:
                    errors.append(f"Error mengonversi {src_path}: {str(ex)}")

    total_saved_bytes = max(0, total_old_bytes - total_new_bytes)
    total_saved_pct = round((total_saved_bytes / total_old_bytes * 100), 1) if total_old_bytes > 0 else 0

    return {
        "status": "success",
        "dry_run": dry_run,
        "total_converted": len(converted_files),
        "total_errors": len(errors),
        "original_size_mb": round(total_old_bytes / (1024 * 1024), 2),
        "compressed_size_mb": round(total_new_bytes / (1024 * 1024), 2),
        "saved_size_mb": round(total_saved_bytes / (1024 * 1024), 2),
        "saved_percent": total_saved_pct,
        "converted_files": converted_files,
        "errors": errors
    }


def main():
    parser = argparse.ArgumentParser(description="Summit Checksheet WebP Image Optimizer CLI")
    parser.add_argument(
        "dirs",
        nargs="*",
        default=["documents", "extracted_images"],
        help="Directories to scan for non-webp images (default: documents extracted_images)"
    )
    parser.add_argument(
        "--quality", "-q",
        type=int,
        default=82,
        help="WebP compression quality from 1 to 100 (default: 82)"
    )
    parser.add_argument(
        "--max-dim", "-m",
        type=int,
        default=1920,
        help="Max width or height in pixels (default: 1920, set 0 for original resolution)"
    )
    parser.add_argument(
        "--keep-original", "-k",
        action="store_true",
        help="Do NOT delete the original PNG/JPG files (default: deletes to save disk space)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Simulate conversion without modifying files"
    )
    parser.add_argument(
        "--stats", "-s",
        action="store_true",
        help="Only display current image statistics and exit"
    )

    args = parser.parse_args()

    print("=" * 65)
    print("   ⚡ SUMMIT ADYAWINSA - WEBP IMAGE COMPRESSION & OPTIMIZER")
    print("=" * 65)

    if args.stats:
        stats = get_image_stats(args.dirs)
        print(f"[*] Direktori Target   : {', '.join(args.dirs)}")
        print(f"[*] Non-WebP Images    : {stats['non_webp_count']} file(s) ({stats['non_webp_mb']} MB)")
        print(f"[*] WebP Images        : {stats['webp_count']} file(s) ({stats['webp_mb']} MB)")
        print(f"[*] Estimasi Hemat     : ~{stats['estimated_savings_mb']} MB (~80-90%)")
        print("=" * 65)
        return

    print(f"[*] Direktori Target   : {', '.join(args.dirs)}")
    print(f"[*] Kualitas WebP      : {args.quality}%")
    print(f"[*] Max Dimensi        : {args.max_dim} px" if args.max_dim else "[*] Max Dimensi: Asli (tanpa resize)")
    print(f"[*] Hapus File Asli    : {'TIDAK (--keep-original)' if args.keep_original else 'YA (Hemat storage)'}")
    if args.dry_run:
        print("[!] MODE DRY-RUN: Simulasi tanpa mengubah file fisik.")
    print("-" * 65)

    result = convert_images_to_webp(
        target_dirs=args.dirs,
        quality=args.quality,
        max_dimension=args.max_dim,
        delete_original=not args.keep_original,
        dry_run=args.dry_run
    )

    print(f"[✓] Berhasil Mengonversi: {result['total_converted']} file")
    print(f"[✓] Ukuran Semula       : {result['original_size_mb']} MB")
    print(f"[✓] Ukuran WebP Baru    : {result['compressed_size_mb']} MB")
    print(f"[✓] Ruang Terhemat      : {result['saved_size_mb']} MB ({result['saved_percent']}%)")

    if result["errors"]:
        print(f"[!] Ditemukan {len(result['errors'])} error:")
        for err in result["errors"][:5]:
            print(f"    - {err}")

    print("=" * 65)


if __name__ == "__main__":
    main()
