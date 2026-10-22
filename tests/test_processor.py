"""Unit-тесты пайплайна process_document."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import DocumentNotFoundError, EmptyDocumentError
from app.models.document import DocumentStatus, DocumentType
from app.schemas.extraction import ExtractionResult
from app.services.processor import process_document


def make_document(**overrides):
    doc = SimpleNamespace(
        id=uuid4(),
        filename="test.pdf",
        storage_path="uploads/test.pdf",
        status=DocumentStatus.QUEUED,
        document_type=None,
        extracted_text=None,
        extraction_result=None,
        error_message=None,
    )
    for key, value in overrides.items():
        setattr(doc, key, value)
    return doc


def test_process_document_not_found():
    """Если db.get возвращает None — бросается DocumentNotFoundError."""
    doc_id = uuid4()
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(DocumentNotFoundError) as exc_info:
        process_document(db, doc_id)

    assert exc_info.value.document_id == doc_id
    db.get.assert_called_once()
    db.commit.assert_not_called()


def test_process_document_success(monkeypatch, discharge_text):
    db = MagicMock()
    doc = make_document()
    db.get.return_value = doc

    fake_result = ExtractionResult(
        document_type="discharge",
        extractor="mock",
        confidence=0.9,
        data={"patient": {"full_name": "Ivan Ivanov"}},
    )
    fake_extractor = MagicMock()
    fake_extractor.extract.return_value = fake_result

    monkeypatch.setattr(
        "app.services.processor.extract_text_from_pdf",
        lambda path: discharge_text,
    )
    monkeypatch.setattr(
        "app.services.processor.classify_document",
        lambda text: DocumentType.DISCHARGE,
    )
    monkeypatch.setattr(
        "app.services.processor.get_extractor",
        lambda: fake_extractor,
    )

    process_document(db, doc.id)

    assert doc.status == DocumentStatus.DONE
    assert doc.document_type == DocumentType.DISCHARGE
    assert doc.extracted_text == discharge_text
    assert doc.extraction_result == fake_result.model_dump(mode="json")
    assert doc.error_message is None
    assert db.commit.call_count >= 2
    fake_extractor.extract.assert_called_once_with(discharge_text, DocumentType.DISCHARGE)


def test_process_document_empty_text_marks_failed(monkeypatch):
    db = MagicMock()
    doc = make_document()
    db.get.return_value = doc

    monkeypatch.setattr(
        "app.services.processor.extract_text_from_pdf",
        lambda path: "",
    )

    with pytest.raises(EmptyDocumentError) as exc_info:
        process_document(db, doc.id)

    assert exc_info.value.document_id == doc.id
    assert doc.status == DocumentStatus.FAILED
    assert "No text extracted" in doc.error_message
    assert db.commit.call_count >= 2


def test_process_document_extractor_error_marks_failed(monkeypatch, discharge_text):
    db = MagicMock()
    doc = make_document()
    db.get.return_value = doc

    fake_extractor = MagicMock()
    fake_extractor.extract.side_effect = RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.processor.extract_text_from_pdf",
        lambda path: discharge_text,
    )
    monkeypatch.setattr(
        "app.services.processor.classify_document",
        lambda text: DocumentType.DISCHARGE,
    )
    monkeypatch.setattr(
        "app.services.processor.get_extractor",
        lambda: fake_extractor,
    )

    with pytest.raises(RuntimeError, match="boom"):
        process_document(db, doc.id)

    assert doc.status == DocumentStatus.FAILED
    assert "boom" in doc.error_message
