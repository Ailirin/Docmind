"""Репозиторий документов в PostgreSQL: add / get / list / count (async)."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentStatus


async def count_documents(db: AsyncSession, *, status: DocumentStatus | None = None) -> int:
    """Возвращает кол-во документов, опционально с фильтром по статусу."""
    stmt = select(func.count()).select_from(Document)
    if status is not None:
        stmt = stmt.where(Document.status == status)
    return int(await db.scalar(stmt) or 0)


async def add_document(db: AsyncSession, document: Document) -> Document:
    db.add(document)
    await db.commit()
    await db.refresh(document)  # подтянуть server_default(created_at)
    return document


async def get_document(db: AsyncSession, document_id: UUID) -> Document | None:
    return await db.get(Document, document_id)


async def list_documents(
    db: AsyncSession,
    *,
    limit: int = 50,
    offset: int = 0,
    status: DocumentStatus | None = None,
) -> list[Document]:
    """
    Возвращает список документов.

    Args:
        limit: максимальное кол-во записей.
        offset: смещение для пагинации.
        status: если задан — фильтруем только по этому статусу.
    """
    stmt = select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        stmt = stmt.where(Document.status == status)
    result = await db.scalars(stmt)
    return list(result.all())
