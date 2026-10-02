"""
Database Backup Utility for Summit FactoryHub Checksheet System.

Exports all data from Supabase/PostgreSQL into a compressed JSON backup file:
    python scripts/backup_database.py
"""
import os
import sys
import json
import gzip
import time
import asyncio
from datetime import datetime

# Setup path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from database.connection import AsyncSessionLocal
from database.models import User, Checksheet, InspectionPoint, PartImage, ActivityLog, SubmissionQueue
from sqlalchemy import select


def serialize_val(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v


async def backup_database(output_path: str = None):
    t0 = time.time()
    print("[*] Memulai backup seluruh database Supabase...")

    backup_dir = os.path.join(ROOT_DIR, "storage", "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not output_path:
        output_file = os.path.join(backup_dir, f"backup_checksheets_{timestamp}.json.gz")
    else:
        output_file = output_path

    async with AsyncSessionLocal() as session:
        # 1. Users
        print("  - Mengambil data users...")
        res_users = await session.execute(select(User).order_by(User.id.asc()))
        users_data = [
            {col.name: serialize_val(getattr(u, col.name)) for col in User.__table__.columns}
            for u in res_users.scalars().all()
        ]

        # 2. Checksheets
        print("  - Mengambil data checksheets master...")
        res_cs = await session.execute(select(Checksheet).order_by(Checksheet.id.asc()))
        cs_data = [
            {col.name: serialize_val(getattr(c, col.name)) for col in Checksheet.__table__.columns}
            for c in res_cs.scalars().all()
        ]

        # 3. Inspection Points
        print("  - Mengambil data titik ukur (inspection points)...")
        res_pts = await session.execute(select(InspectionPoint).order_by(InspectionPoint.id.asc()))
        pts_data = [
            {col.name: serialize_val(getattr(p, col.name)) for col in InspectionPoint.__table__.columns}
            for p in res_pts.scalars().all()
        ]

        # 4. Part Images
        print("  - Mengambil data gambar part (part images)...")
        res_imgs = await session.execute(select(PartImage).order_by(PartImage.id.asc()))
        imgs_data = [
            {col.name: serialize_val(getattr(img, col.name)) for col in PartImage.__table__.columns}
            for img in res_imgs.scalars().all()
        ]

        # 5. Activity Logs
        print("  - Mengambil data audit log aktivitas...")
        res_logs = await session.execute(select(ActivityLog).order_by(ActivityLog.id.asc()))
        logs_data = [
            {col.name: serialize_val(getattr(l, col.name)) for col in ActivityLog.__table__.columns}
            for l in res_logs.scalars().all()
        ]

    backup_payload = {
        "version": "2.0.0",
        "created_at": datetime.now().isoformat(),
        "stats": {
            "users_count": len(users_data),
            "checksheets_count": len(cs_data),
            "points_count": len(pts_data),
            "images_count": len(imgs_data),
            "logs_count": len(logs_data)
        },
        "data": {
            "users": users_data,
            "checksheets": cs_data,
            "inspection_points": pts_data,
            "part_images": imgs_data,
            "activity_logs": logs_data
        }
    }

    # Write compressed
    if output_file.endswith(".gz"):
        with gzip.open(output_file, "wt", encoding="utf-8") as f:
            json.dump(backup_payload, f, ensure_ascii=False)
    else:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(backup_payload, f, ensure_ascii=False, indent=2)

    # Also keep a readable non-gzip JSON as 'latest_backup.json' for easy manual inspection
    latest_plain = os.path.join(backup_dir, "latest_backup.json")
    with open(latest_plain, "w", encoding="utf-8") as f:
        json.dump(backup_payload, f, ensure_ascii=False, indent=2)

    elapsed = round(time.time() - t0, 2)
    file_size_kb = round(os.path.getsize(output_file) / 1024, 2)
    print("\n" + "=" * 55)
    print(" [✓] BACKUP SELESAI DENGAN SUKSES!")
    print(f" File Target : {output_file} ({file_size_kb} KB)")
    print(f" File Plain  : {latest_plain}")
    print(f" Waktu Proses: {elapsed} detik")
    print(f" Ringkasan   :")
    print(f"   • Users             : {len(users_data)} akun")
    print(f"   • Checksheets       : {len(cs_data)} part")
    print(f"   • Inspection Points : {len(pts_data)} baris titik ukur")
    print(f"   • Part Images       : {len(imgs_data)} sketsa gambar")
    print(f"   • Activity Logs     : {len(logs_data)} riwayat aktivitas")
    print("=" * 55)
    return output_file


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(backup_database(out))
