"""
Batch submit all ready-to-push checksheets to FactoryHub.
Uses single browser session with one-time login for maximum speed and reliability.
Supports optional --limit argument to avoid command timeout.
"""
import os
import sys
import asyncio
import argparse

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database.connection import AsyncSessionLocal
from database.models import User, Checksheet
from services.automation_service import execute_batch_submission
from sqlalchemy import select

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max checksheets to process in this run")
    args = parser.parse_args()

    print("=" * 65)
    print("  SUMMIT QC FACTORYHUB BATCH AUTOMATION PUSH")
    print("=" * 65)

    async with AsyncSessionLocal() as session:
        admin_user = (await session.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if not admin_user:
            print("[ERROR] Admin user not found in database.")
            return

        stmt = select(Checksheet.id, Checksheet.part_number, Checksheet.assigned_to, Checksheet.category)\
            .where(Checksheet.status.in_(["Siap Kirim", "Reviewed"]))\
            .order_by(Checksheet.id)
        if args.limit:
            stmt = stmt.limit(args.limit)

        res = await session.execute(stmt)
        ready_items = res.all()

        total = len(ready_items)
        print(f"[*] Ditemukan {total} checksheet berstatus 'Siap Kirim' siap di-push ke FactoryHub.")
        if total == 0:
            print("[+] Tidak ada checksheet yang perlu dikirim saat ini.")
            return

        print(f"[*] Menjalankan batch submission otomatis untuk {total} checksheet...")
        ready_ids = [item[0] for item in ready_items]

        async for log_line in execute_batch_submission(
            checksheet_ids=ready_ids,
            session=session,
            submit=True,
            headless=True,
            browser_channel="chrome",
            requesting_user=admin_user
        ):
            print(log_line, end="", flush=True)

    print("\n" + "=" * 65)
    print("  BATCH AUTOMATION PUSH COMPLETED")
    print("=" * 65)

if __name__ == "__main__":
    asyncio.run(main())
