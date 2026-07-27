from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.document import Document
from app.models.document import DocumentStatus as ModelDocumentStatus
from app.queue.publisher import publish_document_process
from app.schemas.document import (
    DocumentCreateResponse,
    DocumentResponse,
    DocumentStatus,
    HealthResponse,
)
from app.services.file_storage import save_upload
from app.services.processor import process_document
from app.storage import documents as documents_storage

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(app=settings.app_name, version=settings.app_version)


@router.post("/documents", response_model=DocumentCreateResponse, status_code=202)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentCreateResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    doc_id = uuid4()

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    # 1) сначала диск
    storage_path = await save_upload(doc_id, data)

    # 2) потом БД
    document = Document(
        id=doc_id,
        filename=file.filename,
        storage_path=storage_path,
        status=ModelDocumentStatus.QUEUED,  # файл есть - готов к обработке
        document_type=None,
    )
    documents_storage.add_document(db, document)

    try:
        publish_document_process(doc_id)
    except Exception as exc:
        document.status = ModelDocumentStatus.FAILED
        document.error_message = f"Failed to enqueue: {exc}"[:1000]
        db.commit()
        raise HTTPException(status_code=503, detail="Queue unavailable") from exc

    return DocumentCreateResponse(id=doc_id, status=DocumentStatus.QUEUED)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = documents_storage.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.post("/documents/{document_id}/process", response_model=DocumentResponse)
def process_document_endpoint(
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = documents_storage.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        process_document(db, document_id)
    except ValueError as exc:
        # нет файла / пустой текст и т.п. - уже записано как  failed в processor
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    document = documents_storage.get_document(db, document_id)
    return DocumentResponse.model_validate(document)
