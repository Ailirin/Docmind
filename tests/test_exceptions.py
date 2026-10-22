"""Unit-тесты доменных исключений DocMind."""

from uuid import UUID

import pytest

from app.core.exceptions import (
    DocMindError,
    DocumentNotFoundError,
    DocumentProcessingError,
    EmptyDocumentError,
    ExtractionError,
    QueueError,
    StorageError,
)

DOC_ID = UUID("12345678-1234-5678-1234-567812345678")


# ── базовый класс ────────────────────────────────────────────────────────────


def test_docmind_error_is_exception():
    exc = DocMindError("something went wrong")
    assert isinstance(exc, Exception)
    assert str(exc) == "something went wrong"


# ── DocumentNotFoundError ────────────────────────────────────────────────────


def test_document_not_found_message():
    exc = DocumentNotFoundError(DOC_ID)
    assert str(DOC_ID) in str(exc)


def test_document_not_found_stores_id():
    exc = DocumentNotFoundError(DOC_ID)
    assert exc.document_id == DOC_ID


def test_document_not_found_is_docmind_error():
    assert isinstance(DocumentNotFoundError(DOC_ID), DocMindError)


# ── DocumentProcessingError ──────────────────────────────────────────────────


def test_document_processing_error_fields():
    exc = DocumentProcessingError(DOC_ID, "PDF is corrupted")
    assert exc.document_id == DOC_ID
    assert exc.reason == "PDF is corrupted"
    assert "PDF is corrupted" in str(exc)
    assert str(DOC_ID) in str(exc)


# ── EmptyDocumentError ───────────────────────────────────────────────────────


def test_empty_document_error_is_processing_error():
    exc = EmptyDocumentError(DOC_ID)
    assert isinstance(exc, DocumentProcessingError)
    assert exc.document_id == DOC_ID


def test_empty_document_error_message():
    exc = EmptyDocumentError(DOC_ID)
    assert "No text extracted" in str(exc)


# ── StorageError ─────────────────────────────────────────────────────────────


def test_storage_error_is_docmind_error():
    exc = StorageError("disk full")
    assert isinstance(exc, DocMindError)
    assert str(exc) == "disk full"


# ── QueueError ───────────────────────────────────────────────────────────────


def test_queue_error_is_docmind_error():
    exc = QueueError("connection refused")
    assert isinstance(exc, DocMindError)


# ── ExtractionError ──────────────────────────────────────────────────────────


def test_extraction_error_fields():
    exc = ExtractionError("llm", "bad response")
    assert exc.extractor == "llm"
    assert exc.reason == "bad response"
    assert "[llm]" in str(exc)
    assert "bad response" in str(exc)


def test_extraction_error_is_docmind_error():
    assert isinstance(ExtractionError("mock", "empty"), DocMindError)


# ── catch-by-base ────────────────────────────────────────────────────────────


def test_can_catch_all_via_base():
    """Все исключения ловятся через DocMindError."""
    errors = [
        DocumentNotFoundError(DOC_ID),
        DocumentProcessingError(DOC_ID, "r"),
        EmptyDocumentError(DOC_ID),
        StorageError("s"),
        QueueError("q"),
        ExtractionError("llm", "e"),
    ]
    for exc in errors:
        with pytest.raises(DocMindError):
            raise exc
