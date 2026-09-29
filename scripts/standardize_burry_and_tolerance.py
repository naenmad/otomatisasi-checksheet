"""
Migration script to standardize:
1. Burr -> Burry
2. Max. : 0.3mm (and variations) -> ≤ 0.3 mm
Applied across all inspection points in the database.
"""
import asyncio
import re
from datetime import datetime
from database.connection import AsyncSessionLocal
from database.models import InspectionPoint, ActivityLog
from sqlalchemy import select

async def run_standardization():
    print("[*] Memulai standarisasi 'Burr' -> 'Burry' dan 'Max. : 0.3mm' -> '≤ 0.3 mm' di Database...")
    
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(InspectionPoint))
        points = res.scalars().all()
        
        item_updated_count = 0
        std_updated_count = 0
        updated_points_count = 0
        
        for p in points:
            orig_item = p.inspection_item or ""
            orig_std = p.standard or ""
            
            new_item = orig_item
            new_std = orig_std
            
            item_lower = orig_item.strip().lower()
            
            # 1. Standardize Burr -> Burry
            if item_lower in ("burr", "burry", "burrs", "burry max 0.3", "burry max. : 0.3mm", "burrs max 0,3 mm"):
                if orig_item.strip() != "Burry":
                    new_item = "Burry"
            
            # If item field originally held the tolerance criteria
            if item_lower in ("burry max 0.3", "burry max. : 0.3mm", "burrs max 0,3 mm"):
                if orig_std.strip() in ("", "-", "OK / NG"):
                    new_std = "≤ 0.3 mm"
            
            # 2. Standardize Max. : 0.3mm -> ≤ 0.3 mm
            std_lower = orig_std.strip().lower()
            if re.search(r"^(?:burry\s+|burrs\s+|burr\s+)?(?:max\.?\s*:?\s*0[.,]3(?:\s*mm)?|0[.,]3\s*max|<=?\s*0[.,]3(?:\s*mm)?|≤\s*0[.,]3(?:\s*mm)?)$", std_lower):
                if orig_std.strip() != "≤ 0.3 mm":
                    new_std = "≤ 0.3 mm"
            
            is_changed = False
            if new_item != orig_item:
                p.inspection_item = new_item
                item_updated_count += 1
                is_changed = True
                
            if new_std != orig_std:
                p.standard = new_std
                std_updated_count += 1
                is_changed = True
                
            if is_changed:
                updated_points_count += 1
                
        # Log to activity log
        log = ActivityLog(
            action="STANDARDIZATION",
            operator="System Migration",
            status="SUCCESS",
            details=f"Standardized {item_updated_count} Burr->Burry items and {std_updated_count} tolerance->≤ 0.3 mm points across {updated_points_count} points",
            created_at=datetime.utcnow()
        )
        session.add(log)
        
        await session.commit()
        print(f"[✓] Berhasil memperbarui database:")
        print(f"    - Item Inspeksi diubah menjadi 'Burry': {item_updated_count} baris")
        print(f"    - Standar diubah menjadi '≤ 0.3 mm': {std_updated_count} baris")
        print(f"    - Total titik inspeksi yang diperbarui: {updated_points_count} titik")

if __name__ == "__main__":
    asyncio.run(run_standardization())
