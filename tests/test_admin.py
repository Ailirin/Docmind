"""Unit-тесты HTML-админки: list, detail, 401 без авторизации."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.document import Document, DocumentStatus, DocumentType

ADMIN_AUTH = ("admin", "admin")  # default credentials from settings


def _make_doc(
    doc_id: UUID | None = None,
    status: DocumentStatus = DocumentStatus.UPLOADED,
    extraction_result: dict | None = None,
) -> Document:
    now = datetime.now(UTC)
    return Document(
        id=doc_id or uuid4(),
        filename="report.pdf",
        document_type=DocumentType.DISCHARGE,
        status=status,
        storage_path="/uploads/report.pdf",
        created_at=now,
        updated_at=now,
        extraction_result=extraction_result,
    )


@pytest.fixture
def admin_client(monkeypatch):
    """TestClient с замоканным storage и правильными кред. для Basic Auth."""
    store: dict[UUID, Document] = {}

    async def fake_list(db, *, limit=50, offset=0, status=None):
        docs = list(store.values())
        if status is not None:
            docs = [d for d in docs if d.status == status]
        return docs[offset : offset + limit]

    async def fake_count(db, *, status=None):
        docs = list(store.values())
        if status is not None:
            docs = [d for d in docs if d.status == status]
        return len(docs)

    async def fake_get(db, document_id):
        return store.get(document_id)

    monkeypatch.setattr("app.admin.router.documents_storage.list_documents", fake_list)
    monkeypatch.setattr("app.admin.router.documents_storage.count_documents", fake_count)
    monkeypatch.setattr("app.admin.router.documents_storage.get_document", fake_get)
    monkeypatch.setattr("app.admin.auth.settings.admin_username", "admin")
    monkeypatch.setattr("app.admin.auth.settings.admin_password", "admin")

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, store


# ── /admin/ — список документов ──────────────────────────────────────────────


def test_admin_list_returns_200(admin_client):
    client, store = admin_client
    store[uuid4()] = _make_doc()

    response = client.get("/admin/", auth=ADMIN_AUTH)

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_list_redirects_to_documents(admin_client):
    client, _ = admin_client
    response = client.get("/admin/documents", auth=ADMIN_AUTH)
    assert response.status_code == 200


def test_admin_list_without_auth_returns_401(admin_client):
    client, _ = admin_client
    response = client.get("/admin/")
    assert response.status_code == 401


def test_admin_list_wrong_password_returns_401(admin_client):
    client, _ = admin_client
    response = client.get("/admin/", auth=("admin", "wrong"))
    assert response.status_code == 401


def test_admin_list_shows_documents(admin_client):
    client, store = admin_client
    doc = _make_doc()
    store[doc.id] = doc

    response = client.get("/admin/", auth=ADMIN_AUTH)

    assert response.status_code == 200
    assert "report.pdf" in response.text


# ── /admin/documents/{id} — карточка документа ──────────────────────────────


def test_admin_detail_returns_200(admin_client):
    client, store = admin_client
    doc = _make_doc(extraction_result={"diagnosis": {"code": "J06.9"}})
    store[doc.id] = doc

    response = client.get(f"/admin/documents/{doc.id}", auth=ADMIN_AUTH)

    assert response.status_code == 200
    assert "J06.9" in response.text


def test_admin_detail_returns_404_for_unknown_id(admin_client):
    client, _ = admin_client
    response = client.get(f"/admin/documents/{uuid4()}", auth=ADMIN_AUTH)
    assert response.status_code == 404


def test_admin_detail_without_auth_returns_401(admin_client):
    client, store = admin_client
    doc = _make_doc()
    store[doc.id] = doc

    response = client.get(f"/admin/documents/{doc.id}")
    assert response.status_code == 401


def test_admin_detail_no_extraction_result(admin_client):
    """Документ без extraction_result отображается без ошибок (показывает '-')."""
    client, store = admin_client
    doc = _make_doc(extraction_result=None)
    store[doc.id] = doc

    response = client.get(f"/admin/documents/{doc.id}", auth=ADMIN_AUTH)

    assert response.status_code == 200
    assert "-" in response.text
