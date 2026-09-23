"""
Database seeding script with authentication and initial team accounts.
Creates Admin and Operator accounts, then seeds the 91 checksheet parts.
"""
import asyncio
from pathlib import Path
import openpyxl
from sqlalchemy import select

from database.connection import init_db, AsyncSessionLocal
from database.models import User, Checksheet
from server.auth import hash_password


INITIAL_USERS = [
    {
        "username": "admin",
        "name": "Administrator QC",
        "nik": "070817-001",
        "password": "admin123",
        "role": "admin"
    },
    {
        "username": "zul",
        "name": "Zul",
        "nik": "070817-033",
        "password": "zul123",
        "role": "operator"
    },
    {
        "username": "iqbal",
        "name": "Iqbal",
        "nik": "070817-034",
        "password": "iqbal123",
        "role": "operator"
    },
    {
        "username": "rama",
        "name": "Rama",
        "nik": "070817-035",
        "password": "rama123",
        "role": "operator"
    },
    {
        "username": "yogi",
        "name": "Yogi",
        "nik": "070817-036",
        "password": "yogi123",
        "role": "operator"
    }
]


async def seed_auth_and_data():
    print("[*] Menginisialisasi tabel database...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # 1. Seed Users
        print("[*] Membuat akun pengguna awal...")
        created_users = {}
        for u in INITIAL_USERS:
            stmt = select(User).where(User.username == u["username"])
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()

            if not existing:
                user_obj = User(
                    username=u["username"],
                    name=u["name"],
                    nik=u["nik"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True
                )
                session.add(user_obj)
                await session.flush()
                created_users[u["name"]] = user_obj.id
                print(f" [+] User dibuat: {u['username']} ({u['name']} - Role: {u['role']})")
            else:
                created_users[u["name"]] = existing.id
                print(f" [=] User sudah ada: {u['username']}")

        await session.commit()

        # 2. Seed 91 Parts Checksheet from Rekap Excel
        rekap_path = Path("documents/rekap/REKAP_ALL_91_PARTS_HPM.xlsx")
        if not rekap_path.exists():
            rekap_path = Path("REKAP_ALL_91_PARTS_HPM.xlsx")

        if rekap_path.exists():
            print(f"[*] Membaca data checksheet dari {rekap_path}...")
            wb = openpyxl.load_workbook(rekap_path, data_only=True)
            ws = wb.active

            operators = ["Zul", "Iqbal", "Rama", "Yogi"]
            count = 0

            for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True)):
                p_no = str(row[4] or "").strip()
                if not p_no:
                    continue

                p_name = str(row[5] or "").strip()
                model = str(row[6] or "").strip()
                cust = str(row[7] or "PT. HPM").strip()
                status = str(row[8] or "Tidak Ada Part").strip()
                ket = str(row[9] or "").strip()

                # Distribute parts across the 4 operators
                assignee_name = operators[count % len(operators)]
                assignee_id = created_users.get(assignee_name)

                cs = Checksheet(
                    part_number=p_no,
                    clean_part_number=p_no.replace("-", "").replace(" ", "").upper(),
                    part_name=p_name,
                    model=model,
                    customer=cust,
                    doc_number="Form 1",
                    status=status,
                    assigned_to=assignee_name,
                    assigned_user_id=assignee_id,
                    keterangan=ket
                )
                session.add(cs)
                count += 1

            await session.commit()
            print(f"[+] Berhasil menyemai {count} data checksheet ke Supabase!")
        else:
            print("[!] File rekap checksheet tidak ditemukan, lewati seeding checksheet.")

    print("[*] Selesai!")


if __name__ == "__main__":
    asyncio.run(seed_auth_and_data())
