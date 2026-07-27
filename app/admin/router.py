import json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.storage import documents as documents_storage

router = APIRouter()

# templates лежат в app/templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@router.get("/", response_class=HTMLResponse)
@router.get("/documents", response_class=HTMLResponse)
def documents_list(request: Request, db: Session = Depends(get_db)):
    docs = documents_storage.list_documents(db)
    return templates.TemplateResponse(
        request=request,
        name="admin/documents_list.html",
        context={"documents": docs},
    )


@router.get("/documents/{document_id}", response_class=HTMLResponse)
def document_detail(
    document_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
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
