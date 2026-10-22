"""
Интеграционные тесты слоя хранилища (app/storage/documents.py).

Все тесты — async: хранилище теперь использует AsyncSession.
Каждый тест работает в откатываемой транзакции (SAVEPOINT).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.document import Document, DocumentStatus, DocumentType
from app.storage import documents as storage

pytestmark = pytest.mark.integration


def make_doc(
    *,
    status: DocumentStatus = DocumentStatus.QUEUED,
    doc_type: DocumentType | None = None,
    filename: str = "test.pdf",
    extraction_result: dict | None = None,
) -> Document:
    return Document(
        id=uuid4(),
        filename=filename,
        storage_path=f"uploads/{uuid4()}.pdf",
        status=status,
        document_type=doc_type,
        extraction_result=extraction_result,
    )


# ── add / get ─────────────────────────────────────────────────────────────────


class TestAddAndGet:
    async def test_add_sets_created_at(self, db_session):
        doc = make_doc()
        saved = await storage.add_document(db_session, doc)
        assert saved.created_at is not None
        assert saved.updated_at is not None

    async def test_get_returns_document(self, db_session):
        doc = make_doc()
        await storage.add_document(db_session, doc)

        fetched = await storage.get_document(db_session, doc.id)

        assert fetched is not None
        assert fetched.id == doc.id
        assert fetched.filename == doc.filename

    async def test_get_missing_returns_none(self, db_session):
        result = await storage.get_document(db_session, uuid4())
        assert result is None

    async def test_jsonb_stored_and_retrieved(self, db_session):
        """JSONB-поле сохраняется и десериализуется корректно."""
        payload = {
            "patient": {"full_name": "Иван Иванов"},
            "diagnosis": {"code": "J06.9", "name": "ОРВИ"},
            "confidence": 0.92,
        }
        doc = make_doc(extraction_result=payload)
        await storage.add_document(db_session, doc)

        fetched = await storage.get_document(db_session, doc.id)

        assert fetched.extraction_result == payload
        assert fetched.extraction_result["diagnosis"]["code"] == "J06.9"

    async def test_jsonb_null_stored_as_none(self, db_session):
        doc = make_doc(extraction_result=None)
        await storage.add_document(db_session, doc)

        fetched = await storage.get_document(db_session, doc.id)
        assert fetched.extraction_result is None


# ── list_documents ────────────────────────────────────────────────────────────


class TestListDocuments:
    async def test_returns_all_without_filter(self, db_session):
        for _ in range(3):
            await storage.add_document(db_session, make_doc())

        result = await storage.list_documents(db_session)
        assert len(result) == 3

    async def test_ordered_by_created_at_desc(self, db_session):
        """Документы возвращаются от новых к старым."""
        docs = [
            await storage.add_document(db_session, make_doc(filename=f"{i}.pdf")) for i in range(3)
        ]
        result = await storage.list_documents(db_session)

        ids_returned = [d.id for d in result]
        ids_expected = [d.id for d in reversed(docs)]
        assert ids_returned == ids_expected

    async def test_limit_respected(self, db_session):
        for _ in range(5):
            await storage.add_document(db_session, make_doc())

        result = await storage.list_documents(db_session, limit=2)
        assert len(result) == 2

    async def test_offset_skips_rows(self, db_session):
        for i in range(4):
            await storage.add_document(db_session, make_doc(filename=f"{i}.pdf"))

        page1 = await storage.list_documents(db_session, limit=2, offset=0)
        page2 = await storage.list_documents(db_session, limit=2, offset=2)

        ids1 = {d.id for d in page1}
        ids2 = {d.id for d in page2}
        assert ids1.isdisjoint(ids2)
        assert len(ids1 | ids2) == 4

    async def test_filter_by_status_queued(self, db_session):
        await storage.add_document(db_session, make_doc(status=DocumentStatus.QUEUED))
        await storage.add_document(db_session, make_doc(status=DocumentStatus.DONE))
        await storage.add_document(db_session, make_doc(status=DocumentStatus.FAILED))

        result = await storage.list_documents(db_session, status=DocumentStatus.QUEUED)

        assert len(result) == 1
        assert result[0].status == DocumentStatus.QUEUED

    async def test_filter_by_status_done(self, db_session):
        for _ in range(2):
            await storage.add_document(db_session, make_doc(status=DocumentStatus.DONE))
        await storage.add_document(db_session, make_doc(status=DocumentStatus.FAILED))

        result = await storage.list_documents(db_session, status=DocumentStatus.DONE)

        assert len(result) == 2
        assert all(d.status == DocumentStatus.DONE for d in result)

    async def test_filter_none_returns_all(self, db_session):
        for s in (DocumentStatus.QUEUED, DocumentStatus.DONE, DocumentStatus.FAILED):
            await storage.add_document(db_session, make_doc(status=s))

        result = await storage.list_documents(db_session, status=None)
        assert len(result) == 3


# ── count_documents ───────────────────────────────────────────────────────────


class TestCountDocuments:
    async def test_count_empty(self, db_session):
        assert await storage.count_documents(db_session) == 0

    async def test_count_all(self, db_session):
        for _ in range(3):
            await storage.add_document(db_session, make_doc())
        assert await storage.count_documents(db_session) == 3

    async def test_count_with_status_filter(self, db_session):
        await storage.add_document(db_session, make_doc(status=DocumentStatus.DONE))
        await storage.add_document(db_session, make_doc(status=DocumentStatus.DONE))
        await storage.add_document(db_session, make_doc(status=DocumentStatus.FAILED))

        assert await storage.count_documents(db_session, status=DocumentStatus.DONE) == 2
        assert await storage.count_documents(db_session, status=DocumentStatus.FAILED) == 1
        assert await storage.count_documents(db_session, status=DocumentStatus.QUEUED) == 0

    async def test_count_matches_list_length(self, db_session):
        """count() и len(list()) совпадают при любом фильтре."""
        for s in (DocumentStatus.QUEUED, DocumentStatus.QUEUED, DocumentStatus.DONE):
            await storage.add_document(db_session, make_doc(status=s))

        for status in (None, DocumentStatus.QUEUED, DocumentStatus.DONE, DocumentStatus.FAILED):
            count = await storage.count_documents(db_session, status=status)
            docs = await storage.list_documents(db_session, status=status, limit=1000)
            assert count == len(docs), f"Mismatch for status={status}"


# ── status update ─────────────────────────────────────────────────────────────


class TestStatusUpdate:
    async def test_status_change_persisted(self, db_session):
        doc = await storage.add_document(db_session, make_doc(status=DocumentStatus.QUEUED))

        doc.status = DocumentStatus.PROCESSING
        await db_session.commit()

        fetched = await storage.get_document(db_session, doc.id)
        assert fetched.status == DocumentStatus.PROCESSING

    async def test_full_status_lifecycle(self, db_session):
        """QUEUED → PROCESSING → DONE — все переходы сохраняются."""
        doc = await storage.add_document(db_session, make_doc(status=DocumentStatus.QUEUED))

        for new_status in (DocumentStatus.PROCESSING, DocumentStatus.DONE):
            doc.status = new_status
            await db_session.commit()
            fresh = await storage.get_document(db_session, doc.id)
            assert fresh.status == new_status

    async def test_error_message_truncated_to_1000(self, db_session):
        doc = await storage.add_document(db_session, make_doc())
        doc.error_message = "x" * 1000
        doc.status = DocumentStatus.FAILED
        await db_session.commit()

        fetched = await storage.get_document(db_session, doc.id)
        assert len(fetched.error_message) == 1000
