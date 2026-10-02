"""
Database Restore Utility for Summit FactoryHub Checksheet System.

Restores a JSON or JSON.GZ backup file into the target database:
    python scripts/restore_database.py [path_to_backup_file]

If no file is provided, it defaults to storage/backups/latest_backup.json
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

from database.connection import AsyncSessionLocal, init_db
from database.models import User, Checksheet, InspectionPoint, PartImage, ActivityLog
from sqlalchemy import text, delete


def parse_date(v):
    if not v:
        return None
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v)
        except Exception:
            return None
    return v


async def restore_database(backup_file: str = None):
    t0 = time.time()
    backup_dir = os.path.join(ROOT_DIR, "storage", "backups")
    if not backup_file:
        backup_file = os.path.join(backup_dir, "latest_backup.json")

    if not os.path.isfile(backup_file):
        print(f"[ERROR] File backup tidak ditemukan: {backup_file}")
        sys.exit(1)

    print(f"[*] Membaca file backup: {backup_file}...")
    if backup_file.endswith(".gz"):
        with gzip.open(backup_file, "rt", encoding="utf-8") as f:
            payload = json.load(f)
    else:
        with open(backup_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

    data = payload.get("data", {})
    users = data.get("users", [])
    checksheets = data.get("checksheets", [])
    points = data.get("inspection_points", [])
    images = data.get("part_images", [])
    logs = data.get("activity_logs", [])

    print(f"[*] Menyiapkan tabel database tujuan...")
    await init_db()

    async with AsyncSessionLocal() as session:
        print("[*] Mengimpor data users...")
        for u in users:
            row = User(
                id=u["id"],
                username=u["username"],
                name=u["name"],
                nik=u.get("nik"),
                password_hash=u["password_hash"],
                role=u.get("role", "operator"),
                is_active=u.get("is_active", True),
                created_at=parse_date(u.get("created_at"))
            )
            session.add(row)
        await session.commit()

        print(f"[*] Mengimpor {len(checksheets)} checksheets...")
        for cs in checksheets:
            row = Checksheet(
                id=cs["id"],
                part_number=cs["part_number"],
                clean_part_number=cs["clean_part_number"],
                part_name=cs.get("part_name", ""),
                model=cs.get("model", "-"),
                customer=cs.get("customer", "PT. HPM"),
                doc_number=cs.get("doc_number", "FO-45-01"),
                template_type=cs.get("template_type", "GENERIC"),
                status=cs.get("status", "DRAFT"),
                keterangan=cs.get("keterangan", ""),
                assigned_to=cs.get("assigned_to", "Unassigned"),
                assigned_user_id=cs.get("assigned_user_id"),
                locked_by=cs.get("locked_by"),
                locked_at=parse_date(cs.get("locked_at")),
                factoryhub_id=cs.get("factoryhub_id"),
                factoryhub_url=cs.get("factoryhub_url"),
                raw_file_path=cs.get("raw_file_path", ""),
                created_at=parse_date(cs.get("created_at")),
                updated_at=parse_date(cs.get("updated_at"))
            )
            session.add(row)
        await session.commit()

        print(f"[*] Mengimpor {len(points)} inspection points (batch)...")
        # Insert in chunks of 500
        for i in range(0, len(points), 500):
            chunk = points[i:i + 500]
            for p in chunk:
                row = InspectionPoint(
                    id=p["id"],
                    checksheet_id=p["checksheet_id"],
                    item_no=p["item_no"],
                    inspection_item=p["inspection_item"],
                    standard=p.get("standard", "-"),
                    method=p.get("method", "Visual"),
                    master_data=p.get("master_data", ""),
                    order_index=p.get("order_index", 0)
                )
                session.add(row)
            await session.commit()
            print(f"    - Tersimpan {min(i + 500, len(points))}/{len(points)} titik ukur...")

        print(f"[*] Mengimpor {len(images)} part images...")
        for img in images:
            row = PartImage(
                id=img["id"],
                checksheet_id=img["checksheet_id"],
                image_path=img["image_path"],
                image_url=img.get("image_url", ""),
                image_base64=img.get("image_base64")
            )
            session.add(row)
        await session.commit()

        print(f"[*] Mengimpor {len(logs)} activity logs...")
        for l in logs:
            row = ActivityLog(
                id=l["id"],
                action=l["action"],
                part_number=l.get("part_number", "-"),
                operator=l.get("operator", "System"),
                status=l.get("status", "SUCCESS"),
                details=l.get("details", ""),
                link=l.get("link"),
                created_at=parse_date(l.get("created_at") or l.get("timestamp"))
            )
            session.add(row)
        await session.commit()

        # Update PostgreSQL sequence to prevent PK collisions
        try:
            for tbl in ["users", "checksheets", "inspection_points", "part_images", "activity_logs"]:
                await session.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {tbl};"))
            await session.commit()
        except Exception:
            pass

    print("\n" + "=" * 55)
    print(" [✓] RESTORE SELESAI DENGAN SUKSES!")
    print(f" Waktu Proses: {round(time.time() - t0, 2)} detik")
    print("=" * 55)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(restore_database(target))
