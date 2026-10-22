"""
Интеграционные тесты пайплайна process_document.

process_document — синхронная функция (вызывается из worker).
Используем sync_db_session (psycopg2 + SAVEPOINT).
Реальные sample-PDF; LLM заменён на mock-экстрактор.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.models.document import Document, DocumentStatus, DocumentType
from app.services.processor import process_document

SAMPLES = Path(__file__).resolve().parents[2] / "samples"

pytestmark = pytest.mark.integration


def _add_sync(db, storage_path: str, *, status=DocumentStatus.QUEUED) -> Document:
    """Синхронно создаёт документ через ORM (без async storage layer)."""
    doc = Document(
        id=uuid4(),
        filename=Path(storage_path).name,
        storage_path=storage_path,
        status=status,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


class TestProcessDocumentSuccess:
    def test_discharge_pdf_reaches_done(self, sync_db_session, monkeypatch):
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_discharge.pdf"))
        process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.DONE
        assert updated.extracted_text
        assert updated.document_type is not None
        assert updated.error_message is None

    def test_discharge_extraction_result_is_jsonb(self, sync_db_session, monkeypatch):
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_discharge.pdf"))
        process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        result = updated.extraction_result

        assert isinstance(result, dict)
        assert result["extractor"] == "mock"
        assert "confidence" in result

    def test_prescription_classified_correctly(self, sync_db_session, monkeypatch):
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_prescription.pdf"))
        process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.DONE
        assert updated.document_type == DocumentType.PRESCRIPTION

    def test_all_sample_pdfs_process_without_error(self, sync_db_session, monkeypatch):
        """Дымовой тест: все sample-PDF обрабатываются без исключений."""
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        sample_pdfs = list(SAMPLES.glob("*.pdf"))
        assert len(sample_pdfs) >= 1, "Нет sample-PDF в директории samples/"

        for pdf in sample_pdfs:
            doc = _add_sync(sync_db_session, str(pdf))
            process_document(sync_db_session, doc.id)

            updated = sync_db_session.get(Document, doc.id)
            assert updated.status == DocumentStatus.DONE, (
                f"PDF {pdf.name} не обработан: {updated.error_message}"
            )


class TestProcessDocumentFailure:
    def test_missing_file_marks_failed(self, sync_db_session):
        doc = _add_sync(sync_db_session, "uploads/nonexistent-99999.pdf")

        with pytest.raises(FileNotFoundError):
            process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.FAILED
        assert updated.error_message

    def test_document_not_found_raises(self, sync_db_session):
        with pytest.raises(ValueError, match="not found"):
            process_document(sync_db_session, uuid4())

    def test_extractor_failure_marks_failed(self, sync_db_session, monkeypatch):
        from unittest.mock import MagicMock

        fake = MagicMock()
        fake.extract.side_effect = RuntimeError("LLM timeout")
        monkeypatch.setattr("app.services.processor.get_extractor", lambda: fake)

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_discharge.pdf"))

        with pytest.raises(RuntimeError, match="LLM timeout"):
            process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.FAILED
        assert "LLM timeout" in updated.error_message

    def test_failed_document_can_be_reprocessed(self, sync_db_session, monkeypatch):
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_discharge.pdf"), status=DocumentStatus.FAILED)
        doc.error_message = "previous error"
        sync_db_session.commit()

        process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.DONE
        assert updated.error_message is None


class TestProcessDocumentIdempotency:
    def test_processing_twice_stays_done(self, sync_db_session, monkeypatch):
        from app.services.extractors.mock import MockEntityExtractor

        monkeypatch.setattr("app.services.processor.get_extractor", lambda: MockEntityExtractor())

        doc = _add_sync(sync_db_session, str(SAMPLES / "test_discharge.pdf"))
        process_document(sync_db_session, doc.id)
        process_document(sync_db_session, doc.id)

        updated = sync_db_session.get(Document, doc.id)
        assert updated.status == DocumentStatus.DONE
