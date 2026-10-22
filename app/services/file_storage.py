"""
Сохранение загруженных PDF на диск (async).

Атомарная запись:
  1. Пишем в {uuid}.tmp через aiofiles (не блокирует event loop).
  2. os.replace → атомарная замена (мгновенная операция на одном разделе).
  Файл либо записан полностью, либо отсутствует — никаких частично записанных файлов.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from uuid import UUID

import aiofiles
import aiofiles.os

from app.core.config import settings
from app.core.exceptions import StorageError

logger = logging.getLogger("docmind.file_storage")


def get_upload_dir() -> Path:
    """Корень хранилища. Создаём при первом обращении."""
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_storage_path(document_id: UUID) -> Path:
    """Имя на диске = UUID.pdf — безопасно и уникально."""
    return get_upload_dir() / f"{document_id}.pdf"


async def save_upload(document_id: UUID, data: bytes) -> str:
    """
    Асинхронно сохраняет PDF и возвращает путь строкой.

    Raises:
        StorageError: если не удалось записать файл.
    """
    upload_dir = get_upload_dir()
    target = build_storage_path(document_id)
    tmp_path = upload_dir / f"{document_id}.tmp"

    try:
        async with aiofiles.open(tmp_path, "wb") as fh:
            await fh.write(data)
        # os.replace — атомарная операция; tmp и target на одном разделе
        os.replace(tmp_path, target)
    except OSError as exc:
        try:
            await aiofiles.os.remove(str(tmp_path))
        except Exception:
            pass
        logger.exception("Failed to save upload doc_id=%s path=%s", document_id, target)
        raise StorageError(f"Cannot save file {target}: {exc}") from exc

    logger.debug("Saved upload doc_id=%s path=%s size=%d", document_id, target, len(data))
    return str(target)


async def delete_upload(storage_path: str) -> None:
    """Удаляет файл с диска. Если файла нет — молча выходим."""
    try:
        await aiofiles.os.remove(storage_path)
        logger.debug("Deleted upload path=%s", storage_path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("Could not delete upload path=%s", storage_path, exc_info=True)
