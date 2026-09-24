"""HTML-админка: список документов и карточка с текстом/JSON результата."""

import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.admin.auth import require_admin
from app.db.session import get_db
from app.storage import documents as documents_storage

router = APIRouter()

# templates лежат в app/templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
@router.get("/documents", response_class=HTMLResponse)
def documents_list(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    docs = documents_storage.list_documents(db, limit=limit, offset=offset)
    total = documents_storage.count_documents(db)

    prev_offset = max(offset - limit, 0)
    next_offset = offset + limit
    has_prev = offset > 0
    has_next = next_offset < total

    return templates.TemplateResponse(
        request=request,
        name="admin/documents_list.html",
        context={
            "documents": docs,
            "total": total,
            "limit": limit,
            "offset": offset,
            "prev_offset": prev_offset,
            "next_offset": next_offset,
            "has_prev": has_prev,
            "has_next": has_next,
        },
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document_detail(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    document = documents_storage.get_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    extraction_json = (
        json.dumps(
            document.extraction_result,
            ensure_ascii=False,
            indent=2,
        )
        if document.extraction_result
        else "-"
    )

    return templates.TemplateResponse(
        request=request,
        name="admin/document_detail.html",
        context={
            "document": document,
            "extraction_json": extraction_json,
        },
    )
