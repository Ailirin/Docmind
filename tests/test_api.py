"""API-тесты: TestClient + моки диска/БД/очереди."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.models.document import Document
from app.models.document import DocumentStatus as ModelDocumentStatus


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


def test_upload_rejects_non_pdf_content(client):
    test_client, _ = client
    files = {"file": ("fake.pdf", b"not-a-pdf-content", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid PDF file"


def test_upload_rejects_too_large_file(client, monkeypatch):
    test_client, _ = client
    # для теста ставим маленький лимит, чтобы не слать 20 МБ
    monkeypatch.setattr(
        "app.api.v1.router.settings.max_upload_bytes",
        10,
    )
    files = {"file": ("big.pdf", b"%PDF-1134567890", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()


def test_upload_rejects_missing_api_key(client):
    test_client, _ = client
    # убираем ключ, который фикстура поставила по умолчанию
    test_client.headers.pop("X-API-Key", None)
    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_upload_rejects_invalid_api_key(client):
    test_client, _ = client
    test_client.headers.update({"X-API-Key": "wrong-key"})
    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}

    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"


def test_health_without_api_key(client):
    test_client, _ = client
    test_client.headers.pop("X-API-Key", None)

    response = test_client.get("/api/v1/health")

    assert response.status_code == 200


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
    assert "storage_path" not in body
    assert body["id"] == doc_id
    assert body["filename"] == "test.pdf"
    assert body["status"] == "queued"


def test_upload_returns_503_when_queue_fails(client, monkeypatch, tmp_path):
    test_client, store = client

    def broken_publish(document_id: UUID, request_id: str | None = None) -> None:
        raise RuntimeError("rabbit down")

    monkeypatch.setattr("app.api.v1.router.publish_document_process", broken_publish)

    files = {"file": ("test.pdf", b"%PDF-1.4 fake", "application/pdf")}
    response = test_client.post("/api/v1/documents", files=files)

    assert response.status_code == 503
    assert response.json()["detail"] == "Queue unavailable"
    # документ в store уже есть и помечен failed
    doc = next(iter(store.values()))
    assert doc.status == ModelDocumentStatus.FAILED

    # файл с диска убран
    assert not Path(doc.storage_path).exists()


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
    assert "storage_path" not in body
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
