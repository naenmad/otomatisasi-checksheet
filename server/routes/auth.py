"""
Authentication API endpoints for login, profile verification, and session logout.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import User
from server.auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user with username and password, returning an HMAC token."""
    username_clean = payload.username.strip().lower()
    stmt = select(User).where(User.username == username_clean, User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah."
        )

    token = create_token(user_id=user.id, username=user.username, role=user.role)

    return {
        "token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "nik": user.nik,
            "role": user.role
        }
    }


@router.get("/me")
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Return the profile and role of the currently logged in user."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "name": current_user.name,
        "nik": current_user.nik,
        "role": current_user.role
    }


@router.post("/logout")
async def logout():
    """Client clears local session token."""
    return {"status": "success", "message": "Berhasil logout."}
