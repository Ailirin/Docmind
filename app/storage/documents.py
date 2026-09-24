"""Репозиторий документов в PostgreSQL: add / get / list."""

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.document import Document

def count_documents(db: Session) -> int:
    stmt = select(func.count()).select_from(Document)
    return int(db.scalar(stmt) or 0)

def add_document(db: Session, document: Document) -> Document:
    db.add(document)
    db.commit()
    db.refresh(document)  # подтянуть server_default(created_at)
    return document


def get_document(db: Session, document_id: UUID) -> Document | None:
    return db.get(Document, document_id)


def list_documents(
    db: Session,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    stmt = (
        select(Document)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())
