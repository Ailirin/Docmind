"""Общие фикстуры pytest: тексты документов, sample PDF и HTTP-клиент."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import Document

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


@pytest.fixture
def discharge_text() -> str:
    return (
        "DocMind test PDF Document type: discharge summary "
        "Patient: Ivan Ivanov Diagnosis: J06.9 Acute upper respiratory infection "
        "Date: 2026-07-20"
    )


@pytest.fixture
def prescription_text() -> str:
    return (
        "Document type: prescription Patient: Anna Smirnova "
        "Diagnosis: J03.9 Острый тонзиллит "
        "Medication: Ibuprofen Dosage: 200 mg tablets, twice daily "
        "Rp: Ibuprofen 200mg Date: 2026-05-01"
    )


@pytest.fixture
def sample_discharge_pdf() -> Path:
    path = SAMPLES / "test_discharge.pdf"
    assert path.exists(), f"Missing sample: {path}"
    return path


@pytest.fixture
def client(monkeypatch, tmp_path):
    """
    FastAPI TestClient с замоканными зависимостями.

    Подменяем:
      - файловую систему (tmp_path вместо uploads/)
      - хранилище документов (in-memory dict вместо PostgreSQL)
      - очередь RabbitMQ (noop вместо pika)

    Все fake-функции — async, т.к. реальные функции теперь async.
    TestClient от Starlette внутренне запускает anyio и корректно
    обрабатывает async-эндпоинты и async-зависимости.
    """
    store: dict[UUID, Document] = {}

    async def fake_save_upload(document_id: UUID, data: bytes) -> str:
        path = tmp_path / f"{document_id}.pdf"
        path.write_bytes(data)
        return str(path)

    async def fake_delete_upload(storage_path: str) -> None:
        Path(storage_path).unlink(missing_ok=True)

    async def fake_add_document(db, document: Document) -> Document:
        now = datetime.now(UTC)
        document.created_at = now
        document.updated_at = now
        store[document.id] = document
        return document

    async def fake_get_document(db, document_id: UUID) -> Document | None:
        return store.get(document_id)

    async def fake_list_documents(
        db, *, limit: int = 50, offset: int = 0, status=None
    ) -> list[Document]:
        docs = list(store.values())
        if status is not None:
            docs = [d for d in docs if d.status == status]
        return docs[offset : offset + limit]

    async def fake_count_documents(db, *, status=None) -> int:
        docs = list(store.values())
        if status is not None:
            docs = [d for d in docs if d.status == status]
        return len(docs)

    def fake_publish(document_id: UUID, request_id: str | None = None) -> None:
        pass  # pika остаётся sync — фейк тоже sync

    monkeypatch.setattr("app.api.v1.router.save_upload", fake_save_upload)
    monkeypatch.setattr("app.api.v1.router.delete_upload", fake_delete_upload)
    monkeypatch.setattr("app.api.v1.router.documents_storage.add_document", fake_add_document)
    monkeypatch.setattr("app.api.v1.router.documents_storage.get_document", fake_get_document)
    monkeypatch.setattr("app.api.v1.router.documents_storage.list_documents", fake_list_documents)
    monkeypatch.setattr("app.api.v1.router.documents_storage.count_documents", fake_count_documents)
    monkeypatch.setattr("app.api.v1.router.publish_document_process", fake_publish)
    monkeypatch.setattr("app.api.deps.settings.api_key", "test-key")

    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": "test-key"})
        yield test_client, store
