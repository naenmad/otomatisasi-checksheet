"""
User management API endpoints for listing, creating, editing, and deleting team members.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from database.connection import get_db
from database.models import User
from server.auth import hash_password, get_current_user, require_admin

router = APIRouter(prefix="/api/users", tags=["Users"])


class UserCreateSchema(BaseModel):
    username: str
    name: str
    nik: Optional[str] = ""
    password: str
    role: Optional[str] = "operator"  # "admin" or "operator"


class UserUpdateSchema(BaseModel):
    name: Optional[str] = None
    nik: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("")
async def list_users(db: AsyncSession = Depends(get_db)):
    """
    List all active users.
    Open to all users to dynamically populate frontend tabs and assignee selectors.
    """
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.id)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "nik": u.nik or "-",
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateSchema,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Create a new user account."""
    username_clean = payload.username.strip().lower()

    # Check if username already exists
    existing = await db.execute(select(User).where(User.username == username_clean))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{username_clean}' sudah digunakan."
        )

    new_user = User(
        username=username_clean,
        name=payload.name.strip(),
        nik=payload.nik.strip() if payload.nik else "",
        password_hash=hash_password(payload.password),
        role=payload.role if payload.role in ("admin", "operator") else "operator",
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return {
        "status": "success",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "name": new_user.name,
            "nik": new_user.nik,
            "role": new_user.role
        }
    }


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    payload: UserUpdateSchema,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Update user profile, role, or reset password."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")

    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.nik is not None:
        user.nik = payload.nik.strip()
    if payload.role is not None and payload.role in ("admin", "operator"):
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.password:
        user.password_hash = hash_password(payload.password)

    await db.commit()
    return {"status": "success", "message": f"User '{user.username}' berhasil diperbarui."}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Admin-only: Deactivate a user account."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User tidak ditemukan.")

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak dapat menonaktifkan akun admin sendiri."
        )

    user.is_active = False
    await db.commit()
    return {"status": "success", "message": f"Akun '{user.username}' telah dinonaktifkan."}
