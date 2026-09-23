"""
Seeding script to populate database with existing checksheets.
"""
import asyncio
import openpyxl
from database.connection import init_db, AsyncSessionLocal
from database.crud import get_or_create_user, create_checksheet

async def seed_data():
    print("[*] Initializing database...")
    await init_db()
    
    async with AsyncSessionLocal() as session:
        # Create users
        for name, nik in [("Zul", "070817-033"), ("Iqbal", "070817-034"), ("Rama", "070817-035"), ("Yogi", "070817-036")]:
            await get_or_create_user(session, name, nik)
        print("[+] Users seeded.")
        
        # Load from REKAP_ALL_91_PARTS_HPM.xlsx if exists
        try:
            wb = openpyxl.load_workbook("REKAP_ALL_91_PARTS_HPM.xlsx", data_only=True)
            ws = wb.active
            count = 0
            for row in ws.iter_rows(min_row=2, values_only=True):
                p_no = str(row[4] or "").strip()
                if not p_no:
                    continue
                p_name = str(row[5] or "").strip()
                model = str(row[6] or "").strip()
                cust = str(row[7] or "PT. HPM").strip()
                status = str(row[8] or "Tidak Ada Part").strip()
                ket = str(row[9] or "").strip()
                
                await create_checksheet(
                    session=session,
                    part_number=p_no,
                    part_name=p_name,
                    model=model,
                    customer=cust,
                    doc_number="Form 1",
                    status=status,
                    assigned_to="Zul",
                    keterangan=ket
                )
                count += 1
            print(f"[+] Seeded {count} parts from REKAP_ALL_91_PARTS_HPM.xlsx")
        except Exception as e:
            print(f"[!] Error reading rekap file: {e}")

if __name__ == "__main__":
    asyncio.run(seed_data())
