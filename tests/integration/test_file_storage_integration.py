"""
Интеграционные тесты файлового хранилища (async).

Все функции file_storage теперь async → тесты тоже async.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.services.file_storage import build_storage_path, delete_upload, save_upload

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def patch_upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.file_storage.settings.upload_dir", str(tmp_path))
    return tmp_path


# ── save_upload ───────────────────────────────────────────────────────────────


class TestSaveUpload:
    async def test_file_created_on_disk(self):
        path_str = await save_upload(uuid4(), b"%PDF-1.4 test")
        assert Path(path_str).exists()

    async def test_file_content_matches(self):
        data = b"%PDF-1.4 unique data " + uuid4().bytes
        path_str = await save_upload(uuid4(), data)
        assert Path(path_str).read_bytes() == data

    async def test_filename_is_uuid_pdf(self, tmp_path):
        doc_id = uuid4()
        path_str = await save_upload(doc_id, b"%PDF-1.4")
        assert Path(path_str).name == f"{doc_id}.pdf"

    async def test_upload_dir_created_if_missing(self, tmp_path, monkeypatch):
        nested = tmp_path / "a" / "b" / "uploads"
        monkeypatch.setattr("app.services.file_storage.settings.upload_dir", str(nested))
        await save_upload(uuid4(), b"%PDF-1.4")
        assert nested.exists()

    async def test_no_temp_files_left_after_save(self, tmp_path):
        await save_upload(uuid4(), b"%PDF-1.4 content")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == [], f"Найдены временные файлы: {tmp_files}"

    async def test_second_save_overwrites_first(self):
        doc_id = uuid4()
        await save_upload(doc_id, b"%PDF-1.4 version-one")
        await save_upload(doc_id, b"%PDF-1.4 version-two")

        path = build_storage_path(doc_id)
        assert path.read_bytes() == b"%PDF-1.4 version-two"

    async def test_returns_string_path(self):
        path_str = await save_upload(uuid4(), b"%PDF-1.4")
        assert isinstance(path_str, str)

    async def test_large_file_saves_correctly(self):
        data = b"%PDF-1.4 " + b"x" * (1024 * 1024)
        path_str = await save_upload(uuid4(), data)
        assert Path(path_str).stat().st_size == len(data)


# ── delete_upload ─────────────────────────────────────────────────────────────


class TestDeleteUpload:
    async def test_existing_file_deleted(self):
        path_str = await save_upload(uuid4(), b"%PDF-1.4")
        await delete_upload(path_str)
        assert not Path(path_str).exists()

    async def test_missing_file_no_error(self, tmp_path):
        await delete_upload(str(tmp_path / "no-such-file.pdf"))

    async def test_delete_twice_no_error(self):
        path_str = await save_upload(uuid4(), b"%PDF-1.4")
        await delete_upload(path_str)
        await delete_upload(path_str)


# ── round-trip ────────────────────────────────────────────────────────────────


class TestRoundTrip:
    async def test_save_then_delete_leaves_no_trace(self, tmp_path):
        files_before = set(tmp_path.iterdir())
        path_str = await save_upload(uuid4(), b"%PDF-1.4 data")
        await delete_upload(path_str)
        files_after = set(tmp_path.iterdir())
        assert files_before == files_after

    async def test_multiple_docs_independent(self):
        ids = [uuid4() for _ in range(5)]
        payloads = {doc_id: (b"%PDF " + doc_id.bytes) for doc_id in ids}

        for doc_id, data in payloads.items():
            await save_upload(doc_id, data)

        for doc_id, expected in payloads.items():
            path = build_storage_path(doc_id)
            assert path.read_bytes() == expected

    async def test_real_pdf_sample_saved_and_readable(self):
        sample = Path(__file__).resolve().parents[2] / "samples" / "test_discharge.pdf"
        if not sample.exists():
            pytest.skip("sample PDF not found")

        import fitz

        data = sample.read_bytes()
        doc_id = uuid4()
        path_str = await save_upload(doc_id, data)

        with fitz.open(path_str) as pdf:
            text = "".join(page.get_text() for page in pdf)

        assert len(text) > 0
        await delete_upload(path_str)
