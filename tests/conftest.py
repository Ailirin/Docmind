"""Общие фикстуры pytest: тексты документов и путь к sample PDF."""

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

    def fake_publish(document_id: UUID, request_id: str | None = None) -> None:
        return None  # очередь «успешна»

    monkeypatch.setattr("app.api.v1.router.save_upload", fake_save_upload)
    monkeypatch.setattr("app.api.v1.router.documents_storage.add_document", fake_add_document)
    monkeypatch.setattr("app.api.v1.router.documents_storage.get_document", fake_get_document)
    monkeypatch.setattr("app.api.v1.router.publish_document_process", fake_publish)
    monkeypatch.setattr("app.api.deps.settings.api_key", "test-key")

    with TestClient(app) as test_client:
        test_client.headers.update({"X-API-Key": "test-key"})
        yield test_client, store
