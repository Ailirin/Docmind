"""REST API v1: health, загрузка PDF, список/получение документа, ручной process."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import anyio
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_api_key
from app.api.health_checks import check_database, check_rabbitmq
from app.core.config import settings
from app.core.exceptions import DocumentNotFoundError
from app.core.metrics import DOCUMENTS_UPLOADED
from app.db.session import SessionLocal, get_db
from app.models.document import Document
from app.models.document import DocumentStatus as ModelDocumentStatus
from app.queue.publisher import publish_document_process
from app.schemas.document import (
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatus,
    HealthResponse,
    ReadyResponse,
)
from app.services.file_storage import delete_upload, save_upload
from app.services.processor import process_document
from app.storage import documents as documents_storage

logger = logging.getLogger("docmind.api.v1")

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(app=settings.app_name, version=settings.app_version)


@router.get("/health/ready", response_model=ReadyResponse)
async def health_ready(response: Response) -> ReadyResponse:
    # Параллельно проверяем оба сервиса через task group
    results: list[bool] = [False, False]

    async def _check_db() -> None:
        results[0] = await check_database()

    async def _check_mq() -> None:
        results[1] = await check_rabbitmq()

    async with anyio.create_task_group() as tg:
        tg.start_soon(_check_db)
        tg.start_soon(_check_mq)

    db_ok, mq_ok = results[0], results[1]

    if db_ok and mq_ok:
        return ReadyResponse(
            status="ok",
            app=settings.app_name,
            version=settings.app_version,
            database="ok",
            rabbitmq="ok",
        )

    response.status_code = 503
    return ReadyResponse(
        status="unavailable",
        app=settings.app_name,
        version=settings.app_version,
        database="ok" if db_ok else "error",
        rabbitmq="ok" if mq_ok else "error",
    )


@router.post("/documents", response_model=DocumentCreateResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> DocumentCreateResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    doc_id = uuid4()
    logger.info("upload accepted doc_id=%s filename=%s", doc_id, file.filename)

    data = await file.read()  # async чтение из upload stream
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size is {settings.max_upload_bytes} bytes",
        )
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    # 1) сначала диск (async)
    storage_path = await save_upload(doc_id, data)
    logger.info("uploaded to storage doc_id=%s path=%s", doc_id, storage_path)

    # 2) потом БД (async)
    document = Document(
        id=doc_id,
        filename=file.filename,
        storage_path=storage_path,
        status=ModelDocumentStatus.QUEUED,
        document_type=None,
    )
    await documents_storage.add_document(db, document)

    # 3) очередь (sync pika — запускаем в пуле потоков)
    try:
        await anyio.to_thread.run_sync(lambda: publish_document_process(doc_id))
        logger.info("document enqueued doc_id=%s", doc_id)
    except Exception as exc:
        document.status = ModelDocumentStatus.FAILED
        document.error_message = f"Failed to enqueue: {exc}"[:1000]
        await db.commit()
        await delete_upload(storage_path)
        logger.exception("failed to enqueue doc_id=%s error=%s", doc_id, exc)
        raise HTTPException(status_code=503, detail="Queue unavailable") from exc

    DOCUMENTS_UPLOADED.inc()
    return DocumentCreateResponse(id=doc_id, status=DocumentStatus.QUEUED)


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
    limit: int = Query(default=50, ge=1, le=200, description="Количество записей на страницу"),
    offset: int = Query(default=0, ge=0, description="Смещение для пагинации"),
    status: DocumentStatus | None = Query(default=None, description="Фильтр по статусу"),
) -> DocumentListResponse:
    """Возвращает список документов с пагинацией и опциональным фильтром по статусу."""
    model_status: ModelDocumentStatus | None = (
        ModelDocumentStatus(status.value) if status is not None else None
    )

    docs = await documents_storage.list_documents(
        db, limit=limit, offset=offset, status=model_status
    )
    total = await documents_storage.count_documents(db, status=model_status)

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in docs],
        total=total,
        limit=limit,
        offset=offset,
        has_next=(offset + limit) < total,
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> DocumentResponse:
    document = await documents_storage.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.post("/documents/{document_id}/process", response_model=DocumentResponse)
async def process_document_endpoint(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> DocumentResponse:
    document = await documents_storage.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    logger.info("manual process start doc_id=%s status=%s", document_id, document.status)

    # process_document — синхронная функция (используется также из воркера).
    # Запускаем в пуле потоков со своей sync-сессией, чтобы не блокировать event loop.
    def _run_sync() -> None:
        with SessionLocal() as sync_db:
            process_document(sync_db, document_id)

    try:
        await anyio.to_thread.run_sync(_run_sync)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Обновляем состояние документа через async-сессию
    document = await documents_storage.get_document(db, document_id)
    logger.info("manual process done doc_id=%s status=%s", document_id, document.status)
    return DocumentResponse.model_validate(document)
