"""Сохранение загруженных PDF на диск под именем {uuid}.pdf."""

from pathlib import Path
from uuid import UUID

from app.core.config import settings


def get_upload_dir() -> Path:
    """Корень хранилища. Создаем при первом обращении."""
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_storage_path(document_id: UUID) -> Path:
    """Имя на диске = UUID.pdf - безопасно и уникально."""
    return get_upload_dir() / f"{document_id}.pdf"


async def save_upload(document_id: UUID, data: bytes) -> str:
    """
    Сохраняет PDF и возвращает путь строкой для метаданных.
    sync-запись через Path.write_bytes здесь допустима для небольших файлов.
    Для очень больших PDF на проде чаще в S3 / пишут через aiofiles.
    """
    path = build_storage_path(document_id)
    path.write_bytes(data)
    return str(path)
