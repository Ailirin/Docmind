"""
Интеграционные тесты API v1 с реальным PostgreSQL (async).

Очередь RabbitMQ замокана. Файловая система — tmp_path.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.models.document import Document, DocumentStatus

SAMPLES = Path(__file__).resolve().parents[2] / "samples"

pytestmark = pytest.mark.integration


def _upload(client, filename: str = "test.pdf", content: bytes = b"%PDF-1.4 sample") -> dict:
    resp = client.post(
        "/api/v1/documents",
        files={"file": (filename, content, "application/pdf")},
    )
    assert resp.status_code == 202, resp.text
    return resp.json()


# ── Upload ────────────────────────────────────────────────────────────────────


class TestUpload:
    async def test_upload_creates_db_record(self, api_client, db_session, tmp_path, monkeypatch):
        async def _fake_save(doc_id, data):
            p = tmp_path / f"{doc_id}.pdf"
            p.write_bytes(data)
            return str(p)

        monkeypatch.setattr("app.api.v1.router.save_upload", _fake_save)

        body = _upload(api_client)
        doc_id = UUID(body["id"])

        from app.storage import documents as storage_mod

        doc = await storage_mod.get_document(db_session, doc_id)
        assert doc is not None
        assert doc.filename == "test.pdf"
        assert doc.status == DocumentStatus.QUEUED

    async def test_upload_returns_queued_status(self, api_client, tmp_path, monkeypatch):
        async def _fake_save(doc_id, data):
            p = tmp_path / f"{doc_id}.pdf"
            p.write_bytes(data)
            return str(p)

        monkeypatch.setattr("app.api.v1.router.save_upload", _fake_save)

        body = _upload(api_client)
        assert body["status"] == "queued"
        assert "id" in body

    def test_upload_rejects_non_pdf_extension(self, api_client):
        resp = api_client.post(
            "/api/v1/documents",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400

    def test_upload_rejects_fake_pdf_bytes(self, api_client):
        resp = api_client.post(
            "/api/v1/documents",
            files={"file": ("fake.pdf", b"not-a-pdf", "application/pdf")},
        )
        assert resp.status_code == 400

    def test_upload_rejects_empty_file(self, api_client):
        resp = api_client.post(
            "/api/v1/documents",
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )
        assert resp.status_code == 400


# ── Get document ──────────────────────────────────────────────────────────────


class TestGetDocument:
    async def test_get_existing_document(self, api_client, db_session, tmp_path, monkeypatch):
        async def _fake_save(doc_id, data):
            p = tmp_path / f"{doc_id}.pdf"
            p.write_bytes(data)
            return str(p)

        monkeypatch.setattr("app.api.v1.router.save_upload", _fake_save)

        body = _upload(api_client)
        doc_id = body["id"]

        resp = api_client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert data["status"] == "queued"
        assert "storage_path" not in data

    def test_get_missing_document_returns_404(self, api_client):
        resp = api_client.get(f"/api/v1/documents/{uuid4()}")
        assert resp.status_code == 404

    async def test_get_done_document_has_extraction_result(self, api_client, db_session):
        from app.storage import documents as storage_mod

        doc = Document(
            id=uuid4(),
            filename="done.pdf",
            storage_path="uploads/done.pdf",
            status=DocumentStatus.DONE,
            extracted_text="some text",
            extraction_result={"patient": {"full_name": "Тест Тестов"}},
        )
        await storage_mod.add_document(db_session, doc)

        resp = api_client.get(f"/api/v1/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "done"
        assert data["extraction_result"]["patient"]["full_name"] == "Тест Тестов"


# ── List documents ────────────────────────────────────────────────────────────


class TestListDocuments:
    def test_list_empty_db(self, api_client):
        resp = api_client.get("/api/v1/documents")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0
        assert body["has_next"] is False

    async def test_list_after_multiple_uploads(self, api_client, db_session):
        from app.storage import documents as storage_mod

        for i in range(3):
            doc = Document(
                id=uuid4(),
                filename=f"doc{i}.pdf",
                storage_path=f"uploads/doc{i}.pdf",
                status=DocumentStatus.QUEUED,
            )
            await storage_mod.add_document(db_session, doc)

        resp = api_client.get("/api/v1/documents")
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3

    async def test_list_pagination_limit(self, api_client, db_session):
        from app.storage import documents as storage_mod

        for i in range(4):
            doc = Document(
                id=uuid4(),
                filename=f"p{i}.pdf",
                storage_path=f"uploads/p{i}.pdf",
                status=DocumentStatus.QUEUED,
            )
            await storage_mod.add_document(db_session, doc)

        resp = api_client.get("/api/v1/documents?limit=2&offset=0")
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 4
        assert body["has_next"] is True

    async def test_list_filter_by_status(self, api_client, db_session):
        from app.storage import documents as storage_mod

        for status in (DocumentStatus.DONE, DocumentStatus.DONE, DocumentStatus.FAILED):
            doc = Document(
                id=uuid4(),
                filename="f.pdf",
                storage_path="uploads/f.pdf",
                status=status,
            )
            await storage_mod.add_document(db_session, doc)

        assert api_client.get("/api/v1/documents?status=done").json()["total"] == 2
        assert api_client.get("/api/v1/documents?status=failed").json()["total"] == 1
        assert api_client.get("/api/v1/documents?status=queued").json()["total"] == 0

    def test_list_invalid_status_returns_422(self, api_client):
        resp = api_client.get("/api/v1/documents?status=nonexistent")
        assert resp.status_code == 422

    def test_list_requires_api_key(self, api_client):
        api_client.headers.pop("X-API-Key", None)
        resp = api_client.get("/api/v1/documents")
        assert resp.status_code == 401
        api_client.headers["X-API-Key"] = "test-key"
