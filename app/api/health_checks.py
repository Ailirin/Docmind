"""Проверки зависимостей для readiness."""

import pika
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


def check_database() -> bool:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception:
        return False


def check_rabbitmq() -> bool:
    try:
        params = pika.URLParameters(settings.rabbitmq_url)
        connection = pika.BlockingConnection(params)
        connection.close()
        return True
    except Exception:
        return False
