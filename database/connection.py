"""
Database connection and session factory.
Connects to PostgreSQL (Neon/Supabase) via DATABASE_URL or falls back to local SQLite.
"""
import os
from typing import AsyncGenerator
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

load_dotenv()

raw_url = os.getenv("DATABASE_URL", "").strip()

# Format URL for async SQLAlchemy driver
if raw_url:
    if raw_url.startswith("postgres://"):
        db_url = raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw_url.startswith("postgresql://") and not raw_url.startswith("postgresql+asyncpg://"):
        db_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        db_url = raw_url
else:
    # Local SQLite fallback
    os.makedirs("storage", exist_ok=True)
    db_url = "sqlite+aiosqlite:///storage/checksheets.db"

# Engine configuration
connect_args = {}
if "sqlite" in db_url:
    connect_args["check_same_thread"] = False
elif "postgresql" in db_url:
    # Clean query parameters for asyncpg compatibility
    if "?" in db_url:
        base_db_url, query_part = db_url.split("?", 1)
        db_url = base_db_url
    # Supabase requires SSL
    import ssl
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Create all tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
