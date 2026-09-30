#!/usr/bin/env python3
"""
Reassign checksheets in 'Butuh Revisi' status equally among Zul, Iqbal, and Rama.
Total: 116 checksheets -> Zul (39), Iqbal (39), Rama (38).
"""
import asyncio
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sqlalchemy import select
from database.connection import AsyncSessionLocal
from database.models import Checksheet, User, ActivityLog


async def reassign_need_review():
    async with AsyncSessionLocal() as session:
        # 1. Fetch operators
        users_res = await session.execute(
            select(User).filter(User.username.in_(["zul", "iqbal", "rama"]))
        )
        user_map = {u.username.lower(): u for u in users_res.scalars().all()}
        
        operators = [
            {"username": "zul", "name": "Zul", "id": user_map["zul"].id if "zul" in user_map else 2},
            {"username": "iqbal", "name": "Iqbal", "id": user_map["iqbal"].id if "iqbal" in user_map else 3},
            {"username": "rama", "name": "Rama", "id": user_map["rama"].id if "rama" in user_map else 4},
        ]

        # 2. Fetch checksheets with status 'Butuh Revisi'
        cs_res = await session.execute(
            select(Checksheet)
            .filter(Checksheet.status == "Butuh Revisi")
            .order_by(Checksheet.raw_file_path.asc(), Checksheet.part_number.asc(), Checksheet.id.asc())
        )
        checksheets = cs_res.scalars().all()
        total = len(checksheets)
        print(f"[*] Total checksheet 'Butuh Revisi': {total}")

        # 3. Calculate equal splits: e.g. 116 -> 39, 39, 38
        base_count = total // len(operators)
        remainder = total % len(operators)

        counts = []
        for i in range(len(operators)):
            counts.append(base_count + (1 if i < remainder else 0))

        plan_str = ", ".join(f"{op['name']}: {c}" for op, c in zip(operators, counts))
        print(f"[*] Rencana pembagian: {plan_str}")

        # 4. Assign
        idx = 0
        operator_batches = {}
        for op, count in zip(operators, counts):
            operator_batches[op["name"]] = []
            for _ in range(count):
                if idx < total:
                    cs = checksheets[idx]
                    cs.assigned_to = op["name"]
                    cs.assigned_user_id = op["id"]
                    operator_batches[op["name"]].append(cs)
                    idx += 1

        # 5. Log activity
        log = ActivityLog(
            action="REASSIGN_NEED_REVIEW",
            operator="Admin",
            status="SUCCESS",
            details=f"Reassigned {total} Need Review checksheets evenly: Zul ({counts[0]}), Iqbal ({counts[1]}), Rama ({counts[2]})",
            created_at=datetime.utcnow()
        )
        session.add(log)
        await session.commit()

        print("\n" + "=" * 65)
        print("[✓] PEMBAGIAN TUGAS SELESAI & TERSIMPAN DI DATABASE!")
        print("=" * 65)
        for op_name, batch in operator_batches.items():
            print(f"\n▶ {op_name} ({len(batch)} checksheet):")
            for cs in batch[:4]:
                print(f"    - [{cs.part_number}] {cs.part_name} (ID: {cs.id})")
            if len(batch) > 4:
                print(f"    ... dan {len(batch) - 4} part lainnya")


if __name__ == "__main__":
    asyncio.run(reassign_need_review())
