"""
Фикстуры для интеграционных тестов.

Два типа сессий:
  db_session (AsyncSession) — для тестов storage-слоя и API.
    Изоляция через SAVEPOINT: каждый test commit() создаёт SAVEPOINT,
    после теста внешняя транзакция откатывается.

  sync_db_session (Session) — для тестов process_document,
    который работает синхронно (вызывается из worker).
    Та же стратегия SAVEPOINT через join_transaction_mode.

Один PostgreSQL-контейнер на всю тестовую сессию.
При недоступном Docker — тесты SKIPPED, не ERROR.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from testcontainers.postgres import PostgresContainer

from alembic import command as alembic_command
from alembic.config import Config as AlembicConfig
from app.db.session import get_db
from app.main import app

# ── Docker availability ───────────────────────────────────────────────────────


def _docker_available() -> bool:
    try:
        import docker as docker_lib  # type: ignore[import-untyped]

        docker_lib.from_env(timeout=3).ping()
        return True
    except Exception:
        return False


# ── Контейнер и URL (session-scope) ──────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_container():
    """PostgreSQL 16 в Docker. SKIP если Docker недоступен."""
    if not _docker_available():
        pytest.skip("Docker daemon недоступен. Запустите Docker Desktop и повторите: pytest -m integration")
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def pg_sync_url(pg_container) -> str:
    """psycopg2-URL для Alembic и sync-сессий."""
    raw = pg_container.get_connection_url()
    if "+asyncpg" in raw:
        return raw.replace("+asyncpg", "+psycopg2")
    if "psycopg2" not in raw:
        return raw.replace("postgresql://", "postgresql+psycopg2://", 1)
    return raw


@pytest.fixture(scope="session")
def pg_async_url(pg_sync_url) -> str:
    """asyncpg-URL для async-сессий."""
    return pg_sync_url.replace("+psycopg2", "+asyncpg")


# ── Движки (session-scope) ────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def integration_sync_engine(pg_sync_url):
    """Sync-engine с накатанными миграциями (один раз на сессию)."""
    engine = create_engine(pg_sync_url, pool_pre_ping=True)

    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", pg_sync_url)
    alembic_command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def integration_async_engine(pg_async_url, integration_sync_engine):
    """Async-engine (asyncpg). Миграции уже накатаны sync-engine'ом."""
    engine = create_async_engine(pg_async_url, pool_pre_ping=True, echo=False)
    yield engine
    await engine.dispose()


# ── Изолированные сессии на каждый тест ──────────────────────────────────────


@pytest_asyncio.fixture
async def db_session(integration_async_engine) -> AsyncSession:
    """
    AsyncSession с SAVEPOINT-изоляцией.
    Все изменения теста откатываются после его завершения.
    """
    async with integration_async_engine.connect() as connection:
        async with connection.begin() as transaction:
            factory = async_sessionmaker(
                bind=connection,
                class_=AsyncSession,
                autoflush=False,
                autocommit=False,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                yield session
            await transaction.rollback()


@pytest.fixture
def sync_db_session(integration_sync_engine) -> Session:
    """
    Синхронная Session с SAVEPOINT-изоляцией.
    Используется в тестах process_document (синхронный код).
    """
    connection = integration_sync_engine.connect()
    transaction = connection.begin()

    factory = sessionmaker(
        bind=connection,
        autoflush=False,
        autocommit=False,
        join_transaction_mode="create_savepoint",
    )
    session = factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── TestClient с реальной БД ──────────────────────────────────────────────────


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession, monkeypatch):
    """
    FastAPI TestClient с реальной async-БД и замоканной очередью.
    dependency_overrides[get_db] подставляет тестовую AsyncSession.
    """

    async def _override_get_db():
        yield db_session

    def _fake_publish(document_id, request_id=None):
        pass

    monkeypatch.setattr("app.api.v1.router.publish_document_process", _fake_publish)
    monkeypatch.setattr("app.api.deps.settings.api_key", "test-key")

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app, raise_server_exceptions=True) as client:
            client.headers["X-API-Key"] = "test-key"
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
