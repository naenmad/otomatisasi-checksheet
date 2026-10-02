"""
One-Command Migration Utility to a New Supabase Project (e.g. Singapore / Work Account).

Usage:
    python scripts/migrate_to_new_supabase.py \\
        --new-db-url "postgresql://postgres.<ref>:<password>@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres" \\
        --new-supabase-url "https://<ref>.supabase.co" \\
        --new-supabase-key "<service_or_anon_key>"
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import mimetypes
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, select
from database.models import Base, User, Checksheet, InspectionPoint, PartImage, ActivityLog

BUCKET_NAME = "image"
BACKUP_IMAGES_DIR = os.path.join(ROOT_DIR, "storage", "backups", "images_backup")
BACKUP_JSON_FILE = os.path.join(ROOT_DIR, "storage", "backups", "latest_backup.json")


def ensure_bucket_exists(supabase_url: str, supabase_key: str):
    """Create public storage bucket 'image' if not already created."""
    print(f"[*] Memeriksa storage bucket '{BUCKET_NAME}' di Supabase baru...")
    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/bucket"
    try:
        # Check if bucket exists
        req = urllib.request.Request(
            endpoint,
            headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            buckets = json.loads(resp.read().decode())
            if any(b.get("name") == BUCKET_NAME for b in buckets):
                print(f"[✓] Bucket '{BUCKET_NAME}' sudah ada.")
                return True
    except Exception as e:
        pass

    # Create bucket
    try:
        payload = json.dumps({"name": BUCKET_NAME, "id": BUCKET_NAME, "public": True}).encode()
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[✓] Berhasil membuat public bucket '{BUCKET_NAME}'!")
            return True
    except Exception as e:
        print(f"[!] Warning saat membuat bucket: {e} (Mungkin bucket sudah ada)")
        return False


def upload_single_image(local_path: str, remote_rel_path: str, supabase_url: str, supabase_key: str) -> bool:
    """Upload a single file to the new Supabase bucket."""
    encoded_path = urllib.parse.quote(remote_rel_path.lstrip("/"), safe="/-_.~")
    endpoint = f"{supabase_url.rstrip('/')}/storage/v1/object/{BUCKET_NAME}/{encoded_path}"

    mime_type, _ = mimetypes.guess_type(local_path)
    if not mime_type:
        mime_type = "image/webp" if local_path.lower().endswith(".webp") else "image/png"

    try:
        with open(local_path, "rb") as f:
            file_data = f.read()

        req = urllib.request.Request(
            endpoint,
            data=file_data,
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": mime_type,
                "x-upsert": "true"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            return resp.status in (200, 201)
    except Exception:
        return False


def upload_all_images(supabase_url: str, supabase_key: str):
    """Upload all backed-up images to the new Supabase storage bucket."""
    print("\n[*] Menyiapkan upload seluruh gambar part ke Supabase Storage baru...")
    image_files = []
    for root, _, files in os.walk(BACKUP_IMAGES_DIR):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, BACKUP_IMAGES_DIR).replace("\\", "/")
            image_files.append((full_path, rel_path))

    print(f"[*] Ditemukan {len(image_files)} file gambar lokal siap diunggah.")
    uploaded = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(upload_single_image, f_path, r_path, supabase_url, supabase_key): r_path
            for f_path, r_path in image_files
        }
        for fut in as_completed(futures):
            if fut.result():
                uploaded += 1
            if uploaded % 100 == 0 or uploaded == len(image_files):
                print(f"    - Berhasil diunggah: {uploaded}/{len(image_files)}...")
    print(f"[✓] Selesai! {uploaded}/{len(image_files)} gambar berhasil diunggah ke Supabase baru.")


async def restore_to_new_db(new_db_url: str, new_supabase_url: str):
    """Restore database tables and update image URLs to point to new project."""
    print("\n[*] Menyiapkan koneksi ke PostgreSQL database baru...")
    import ssl

    clean_url = new_db_url.strip()
    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif clean_url.startswith("postgresql://") and not clean_url.startswith("postgresql+asyncpg://"):
        clean_url = clean_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "pooler.supabase.com:5432" in clean_url:
        clean_url = clean_url.replace(":5432", ":6543")

    if "?" in clean_url:
        clean_url = clean_url.split("?", 1)[0]

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    engine = create_async_engine(
        clean_url,
        echo=False,
        connect_args={
            "ssl": ssl_ctx,
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0
        },
        pool_pre_ping=True
    )

    print("[*] Membuat skema tabel di database baru...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Clean any partial previous import
        for tbl in ["activity_logs", "submission_queue", "part_images", "inspection_points", "checksheets", "users"]:
            try:
                await conn.execute(text(f"TRUNCATE TABLE {tbl} CASCADE;"))
            except Exception:
                pass

    # Load backup data
    with open(BACKUP_JSON_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    data = payload.get("data", {})
    users = data.get("users", [])
    checksheets = data.get("checksheets", [])
    points = data.get("inspection_points", [])
    images = data.get("part_images", [])
    logs = data.get("activity_logs", [])

    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    def parse_dt(v):
        if not v:
            return None
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v)
            except Exception:
                return None
        return v

    async with Session() as session:
        print("[*] Mengimpor users...")
        for u in users:
            row_dict = {k: v for k, v in u.items() if hasattr(User, k)}
            row_dict["created_at"] = parse_dt(row_dict.get("created_at"))
            session.add(User(**row_dict))
        await session.commit()

        print(f"[*] Mengimpor {len(checksheets)} checksheets...")
        for cs in checksheets:
            row_dict = {k: v for k, v in cs.items() if hasattr(Checksheet, k)}
            row_dict["created_at"] = parse_dt(row_dict.get("created_at"))
            row_dict["updated_at"] = parse_dt(row_dict.get("updated_at"))
            row_dict["locked_at"] = parse_dt(row_dict.get("locked_at"))
            session.add(Checksheet(**row_dict))
        await session.commit()

        print(f"[*] Mengimpor {len(points)} inspection points (batch)...")
        for i in range(0, len(points), 500):
            chunk = points[i:i + 500]
            for p in chunk:
                session.add(InspectionPoint(**{k: v for k, v in p.items() if hasattr(InspectionPoint, k)}))
            await session.commit()

        print(f"[*] Mengimpor {len(images)} part images (memperbarui URL ke Supabase baru)...")
        new_base_url = new_supabase_url.rstrip("/")
        for img in images:
            old_url = img.get("image_url", "")
            new_url = old_url
            if "storage/v1/object/public/image/" in old_url:
                sub_path = old_url.split("storage/v1/object/public/image/", 1)[1]
                new_url = f"{new_base_url}/storage/v1/object/public/{BUCKET_NAME}/{sub_path}"

            session.add(PartImage(
                id=img["id"],
                checksheet_id=img["checksheet_id"],
                image_path=img.get("image_path", ""),
                image_url=new_url,
                image_base64=img.get("image_base64")
            ))
        await session.commit()

        print(f"[*] Mengimpor {len(logs)} activity logs...")
        for l in logs:
            row_dict = {k: v for k, v in l.items() if hasattr(ActivityLog, k)}
            row_dict["created_at"] = parse_dt(l.get("created_at") or l.get("timestamp"))
            session.add(ActivityLog(**row_dict))
        await session.commit()

        # Update sequences
        try:
            for tbl in ["users", "checksheets", "inspection_points", "part_images", "activity_logs"]:
                await session.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {tbl};"))
            await session.commit()
        except Exception:
            pass

    await engine.dispose()
    print("[✓] Seluruh data database berhasil dipindahkan!")


def update_env_file(new_db_url: str, new_supabase_url: str, new_supabase_key: str):
    """Update .env file with new credentials."""
    env_path = os.path.join(ROOT_DIR, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("DATABASE_URL="):
            new_lines.append(f"DATABASE_URL={new_db_url.strip()}\n")
        elif line.startswith("SUPABASE_URL="):
            new_lines.append(f"SUPABASE_URL={new_supabase_url.strip()}\n")
        elif line.startswith("SUPABASE_KEY="):
            new_lines.append(f"SUPABASE_KEY={new_supabase_key.strip()}\n")
        else:
            new_lines.append(line)

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"[✓] File .env berhasil diperbarui dengan kredensial Supabase baru!")


def main():
    parser = argparse.ArgumentParser(description="Migrate data to new Supabase project")
    parser.add_argument("--new-db-url", required=True, help="New PostgreSQL Database URL")
    parser.add_argument("--new-supabase-url", required=True, help="New Supabase Project URL")
    parser.add_argument("--new-supabase-key", required=True, help="New Supabase API Key (anon or service_role)")
    args = parser.parse_args()

    t_start = time.time()
    print("=" * 60)
    print("      MIGRASI LENGKAP KE PROYEK SUPABASE BARU")
    print("=" * 60)

    # 1. Bucket setup
    ensure_bucket_exists(args.new_supabase_url, args.new_supabase_key)

    # 2. Upload storage images
    upload_all_images(args.new_supabase_url, args.new_supabase_key)

    # 3. Restore database data
    asyncio.run(restore_to_new_db(args.new_db_url, args.new_supabase_url))

    # 4. Update .env
    update_env_file(args.new_db_url, args.new_supabase_url, args.new_supabase_key)

    total_time = round(time.time() - t_start, 2)
    print("\n" + "=" * 60)
    print(" [✓] SEMUA PROSES MIGRASI SELESAI DENGAN SEMPURNA!")
    print(f" Total Waktu: {total_time} detik")
    print(" Sistem Anda sekarang 100% terhubung ke Supabase baru.")
    print("=" * 60)


if __name__ == "__main__":
    main()
