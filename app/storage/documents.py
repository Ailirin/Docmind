"""Репозиторий документов (POstgreSQL)"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document


def add_document(db: Session, document: Document) -> Document:
    db.add(document)
    db.commit()
    db.refresh(document)  # подтянуть server_default(created_at)
    return document


def get_document(db: Session, document_id: UUID) -> Document | None:
    return db.get(Document, document_id)


def list_documents(db: Session) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc())
    return list(db.scalars(stmt).all())
