"""
Engine, сессии и FastAPI-dependency get_db.

Два движка:
  async_engine  — asyncpg, используется API (async endpoints).
  sync_engine   — psycopg2, используется worker и Alembic-миграции.

URL-соглашение: DATABASE_URL задаётся с драйвером +asyncpg.
Синхронный URL выводится заменой драйвера на +psycopg2.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _to_sync_url(url: str) -> str:
    """Преобразует asyncpg-URL в psycopg2-URL для синхронных операций."""
    if "+asyncpg" in url:
        return url.replace("+asyncpg", "+psycopg2")
    # Голый postgresql:// без драйвера → добавляем psycopg2
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


# ── Async engine (API) ────────────────────────────────────────────────────────
async_engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,  # объекты не инвалидируются после commit
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: одна AsyncSession на запрос."""
    async with AsyncSessionLocal() as session:
        yield session


# ── Sync engine (Worker + Alembic) ───────────────────────────────────────────
sync_engine = create_engine(
    _to_sync_url(settings.database_url),
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_recycle=settings.db_pool_recycle,
    connect_args={"options": "-c timezone=utc"}
    if "postgresql" in settings.database_url
    else {},
)

SessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)
