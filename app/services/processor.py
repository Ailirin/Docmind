"""Пайплайн обработки документа: текст → тип → сущности → запись в БД."""

import logging
import time
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.metrics import DOCUMENTS_PROCESSED, PROCESS_DURATION
from app.models.document import DocumentStatus
from app.services.classifier import classify_document
from app.services.extractors.factory import get_extractor
from app.services.pdf_extractor import extract_text_from_pdf
from app.storage import documents as documents_storage

logger = logging.getLogger("docmind.processor")


def process_document(db: Session, document_id: UUID) -> None:
    """
    Синхронная обработка одного документа:
    queued/uploaded -> processing -> done | failed
    """
    document = documents_storage.get_document(db, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")

    logger.info("processing start doc_id=%s", document_id)
    document.status = DocumentStatus.PROCESSING
    document.error_message = None
    db.commit()

    started = time.perf_counter()
    try:
        text = extract_text_from_pdf(document.storage_path)
        if not text:
            raise ValueError("No text extracted from PDF")

        doc_type = classify_document(text)
        logger.info("classified doc_id=%s doc_type=%s", document_id, doc_type)
        extraction = get_extractor().extract(text, doc_type)

        document.extracted_text = text
        document.document_type = doc_type
        document.extraction_result = extraction.model_dump(mode="json")
        document.status = DocumentStatus.DONE
        logger.info("processing done doc_id=%s", document_id)
        db.commit()
        DOCUMENTS_PROCESSED.labels(status="done").inc()
        PROCESS_DURATION.observe(time.perf_counter() - started)

    except Exception as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)[:1000]
        db.commit()
        logger.exception("processing failed doc_id=%s error=%s", document_id, exc)
        DOCUMENTS_PROCESSED.labels(status="failed").inc()
        PROCESS_DURATION.observe(time.perf_counter() - started)
        raise
