"""Экспорт ORM-моделей (нужно Alembic и удобным импортам)."""

from app.models.document import Document, DocumentStatus, DocumentType

__all__ = ["Document", "DocumentStatus", "DocumentType"]
