"""
Script 1-klik untuk upload semua gambar lokal ke Supabase Cloud.
Cukup jalankan: python sync.py
"""
import sys, os
from scripts.sync_local_images_to_cloud import sync_disk_to_cloud
import asyncio

if __name__ == "__main__":
    print("[*] Memulai sinkronisasi otomatis ke Supabase Cloud...")
    res = asyncio.run(sync_disk_to_cloud())
    print("\n[SELESAI]", res.get("message", "Berhasil!"))
