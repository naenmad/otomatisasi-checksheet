"""
Authentication and security utilities for the Checksheet system.
Provides password hashing (PBKDF2-HMAC-SHA256), session tokens, and FastAPI dependencies.
"""
import os
import hmac
import hashlib
import secrets
import json
import base64
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.connection import get_db
from database.models import User

# Secret key for HMAC token signing
AUTH_SECRET = os.getenv("AUTH_SECRET", "summit-quality-checksheet-secret-key-2026")
TOKEN_EXPIRY_SECONDS = 7 * 24 * 3600  # 7 days

security_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Generate a secure PBKDF2 hash with a random salt."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations=100_000
    ).hex()
    return f"{salt}${pw_hash}"


def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verify a password against the stored salt$hash."""
    try:
        salt, expected_hash = stored_hash.split("$", 1)
        computed_hash = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations=100_000
        ).hex()
        return hmac.compare_digest(computed_hash, expected_hash)
    except Exception:
        return False


def create_token(user_id: int, username: str, role: str) -> str:
    """Generate a signed HMAC token containing user metadata and expiry."""
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": int(time.time()) + TOKEN_EXPIRY_SECONDS
    }
    raw_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    b64_payload = base64.urlsafe_b64encode(raw_json).decode('utf-8').rstrip('=')

    signature = hmac.new(
        AUTH_SECRET.encode('utf-8'),
        b64_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return f"{b64_payload}.{signature}"


def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """Verify a signed token and return the payload if valid."""
    try:
        b64_payload, signature = token.split(".", 1)
        expected_sig = hmac.new(
            AUTH_SECRET.encode('utf-8'),
            b64_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Pad base64 if needed
        padding = 4 - (len(b64_payload) % 4)
        if padding != 4:
            b64_payload += "=" * padding

        raw_json = base64.urlsafe_b64decode(b64_payload.encode('utf-8'))
        payload = json.loads(raw_json)

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """FastAPI dependency to extract and validate the authenticated user."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Otentikasi diperlukan. Silakan login terlebih dahulu.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesi login tidak valid atau telah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    stmt = select(User).where(User.id == user_id, User.is_active.is_(True))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Akun pengguna tidak ditemukan atau tidak aktif."
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency to enforce admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak: Aksi ini memerlukan hak akses Administrator."
        )
    return current_user
