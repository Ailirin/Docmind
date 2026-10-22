"""Async-проверки зависимостей для readiness-эндпоинта."""

from __future__ import annotations

import anyio
import pika
from sqlalchemy import text

from app.core.config import settings


async def check_database() -> bool:
    """Проверяет доступность PostgreSQL через async engine."""
    try:
        from app.db.session import async_engine

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _rabbitmq_ping() -> bool:
    """Sync-проверка RabbitMQ (выполняется в пуле потоков)."""
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        connection = pika.BlockingConnection(params)
        connection.close()
        return True
    except Exception:
        return False


async def check_rabbitmq() -> bool:
    """Проверяет доступность RabbitMQ без блокировки event loop."""
    return await anyio.to_thread.run_sync(_rabbitmq_ping)
