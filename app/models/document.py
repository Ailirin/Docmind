"""ORM-модель Document и enum статусов/типов документа."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DocumentType(str, enum.Enum):
    DISCHARGE = "discharge"
    PRESCRIPTION = "prescription"
    DIAGNOSIS = "diagnosis"
    UNKNOWN = "unknown"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus, name="document_status", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=DocumentStatus.UPLOADED,
        index=True,  # фильтр по статусу
    )
    document_type: Mapped[DocumentType | None] = mapped_column(
        Enum(DocumentType, name="document_type", values_callable=lambda x: [e.value for e in x]),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,  # сортировка ленты
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
