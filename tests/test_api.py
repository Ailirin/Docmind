"""API-тесты: TestClient + моки диска/БД/очереди."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import Document
from app.models.document import DocumentStatus as ModelDocumentStatus


@pytest.fixture
def client(monkeypatch, tmp_path):
    """
    Подменяем диск, БД и очередь — тестируем только API.
    """
    store: dict[UUID, Document] = {}

    async def fake_save_upload(document_id, data: bytes) -> str:
        path = tmp_path / f"{document_id}.pdf"
        path.write_bytes(data)
        return str(path)

    def fake_add_document(db, document: Document) -> Document:
        now = datetime.now(UTC)
        document.created_at = now
        document.updated_at = now
        store[document.id] = document
        return document

    def fake_get_document(db, document_id: UUID) -> Document | None:
        return store.get(document_id)

    def fake_publish(document_id: UUID) -> None:
        return None  # очередь «успешна»

    monkeypatch.setattr("app.api.v1.router.save_upload", fake_save_upload)
    monkeypatch.setattr("app.api.v1.router.documents_storage.add_document", fake_add_document)
    monkeypatch.setattr("app.api.v1.router.documents_storage.get_document", fake_get_document)
    monkeypatch.setattr("app.api.v1.router.publish_document_process", fake_publish)

    with TestClient(app) as test_client:
        yield test_client, store


def test_health(client):
    test_client, _ = client
    response = test_client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app" in body
    assert "version" in body


def test_upload_pdf_returns_202(client):
    test_client, store = client
    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert "id" in body
    doc_id = UUID(body["id"])
    assert doc_id in store
    assert store[doc_id].status == ModelDocumentStatus.QUEUED


def test_upload_rejects_non_pdf(client):
    test_client, _ = client
    files = {"file": ("note.txt", b"hello", "text/plain")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_rejects_empty_pdf(client):
    test_client, _ = client
    files = {"file": ("empty.pdf", b"", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 400
    assert response.json()["detail"] == "Empty file"


def test_get_document_not_found(client):
    test_client, _ = client
    missing_id = uuid4()

    response = test_client.get(f"/api/v1/documents/{missing_id}")

    assert response.status_code == 404


def test_get_document_after_upload(client):
    test_client, _ = client
    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
    upload = test_client.post("/api/v1/documents", files=files)
    doc_id = upload.json()["id"]

    response = test_client.get(f"/api/v1/documents/{doc_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == doc_id
    assert body["filename"] == "test.pdf"
    assert body["status"] == "queued"


def test_upload_returns_503_when_queue_fails(client, monkeypatch):
    test_client, store = client

    def broken_publish(document_id: UUID) -> None:
        raise RuntimeError("rabbit down")

    monkeypatch.setattr("app.api.v1.router.publish_document_process", broken_publish)

    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 503
    assert response.json()["detail"] == "Queue unavailable"
    # документ в store уже есть и помечен failed
    doc = next(iter(store.values()))
    assert doc.status == ModelDocumentStatus.FAILED

def test_process_document_endpoint_success(client, monkeypatch):
    test_client, store = client
    doc_id = uuid4()
    now = datetime.now(UTC)
    store[doc_id] = Document(
        id=doc_id,
        filename="test.pdf",
        storage_path="uploads/test.pdf",
        status=ModelDocumentStatus.QUEUED,
        created_at=now,
        updated_at=now,
    )

    def fake_process(db, document_id: UUID) -> None:
        store[document_id].status = ModelDocumentStatus.DONE
        store[document_id].extracted_text = "extracted"

    monkeypatch.setattr("app.api.v1.router.process_document", fake_process)

    response = test_client.post(f"/api/v1/documents/{doc_id}/process")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(doc_id)
    assert body["status"] == "done"
    assert body["extracted_text"] == "extracted"

def test_process_document_endpoint_not_found(client):
    test_client, _ = client

    response = test_client.post(f"/api/v1/documents/{uuid4()}/process")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"

def test_process_document_endpoint_value_error(client, monkeypatch):
    test_client, store = client
    doc_id = uuid4()
    now = datetime.now(UTC)
    store[doc_id] = Document(
        id=doc_id,
        filename="test.pdf",
        storage_path="uploads/test.pdf",
        status=ModelDocumentStatus.QUEUED,
        created_at=now,
        updated_at=now,
    )

    def fake_process(db, document_id: UUID) -> None:
        raise ValueError("No text extracted from PDF")

    monkeypatch.setattr("app.api.v1.router.process_document", fake_process)

    response = test_client.post(f"/api/v1/documents/{doc_id}/process")

    assert response.status_code == 422
    assert "No text extracted" in response.json()["detail"]
