from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class DocumentType(str, Enum):
    DISCHARGE = "discharge"
    PRESCRIPTION = "prescription"
    DIAGNOSIS = "diagnosis"
    UNKNOWN = "unknown"


class DocumentCreateResponse(BaseModel):
    id: UUID
    status: DocumentStatus
    message: str = "Document accepted for processing"

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    filename: str
    storage_path: str | None = None
    status: DocumentStatus
    document_type: DocumentType | None = None
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None
    extracted_text: str | None = None
    extraction_result: dict | None = None

class HealthResponse(BaseModel):
    status: str = "ok"
    app: str
    version: str

