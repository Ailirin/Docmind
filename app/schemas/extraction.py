from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PatientInfo(BaseModel):
    full_name: str | None = None


class DiagnosisInfo(BaseModel):
    code: str | None = Field(default=None, description="Код МКБ, например J06.9")
    name: str | None = None


class TreatmentInfo(BaseModel):
    """Лечение по диагнозу."""

    medication: str | None = Field(default=None, description="Название препарата")
    dosage: str | None = Field(default=None, description="Дозировка")


class MedicalExtraction(BaseModel):
    """Общая нормализованная структура для выписки/рецепта/диагноза."""

    patient: PatientInfo | None = None
    diagnosis: DiagnosisInfo | None = None
    treatment: TreatmentInfo | None = None
    document_date: date | None = None
    raw_notes: str | None = None


class ExtractionResult(BaseModel):
    document_type: str
    data: dict[str, Any]
    extractor: str = Field(description="mock | llm")
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float | None) -> float | None:
        if v is None:
            return v
        return round(v, 3)
