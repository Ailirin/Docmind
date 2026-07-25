import re
from datetime import date

from app.models.document import DocumentType
from app.schemas.extraction import (
    DiagnosisInfo,
    ExtractionResult,
    MedicalExtraction,
    PatientInfo,
    TreatmentInfo,
)
from app.services.extractors.base import EntityExtractor

_STOP = r"(?:\s+(?:Diagnosis|Medication|Dosage|Treatment|Date|Rp):|$)"


class MockEntityExtractor(EntityExtractor):
    def extract(self, text: str, document_type: DocumentType) -> ExtractionResult:
        payload = MedicalExtraction(
            patient=self._patient(text),
            diagnosis=self._diagnosis(text),
            treatment=self._treatment(text),
            document_date=self._date(text),
        )
        has_dx = bool(payload.diagnosis and payload.diagnosis.code)
        has_rx = bool(payload.treatment and payload.treatment.medication)
        confidence = 0.8 if has_dx and has_rx else 0.6 if has_dx or has_rx else 0.4

        return ExtractionResult(
            document_type=document_type.value,
            data=payload.model_dump(mode="json"),
            extractor="mock",
            confidence=confidence,
        )

    def _patient(self, text: str) -> PatientInfo | None:
        match = re.search(rf"Patient:\s*(.+?){_STOP}", text, re.IGNORECASE)
        if not match:
            return None
        return PatientInfo(full_name=match.group(1).strip())

    def _diagnosis(self, text: str) -> DiagnosisInfo | None:
        match = re.search(
            rf"Diagnosis:\s*([A-Z]\d{{2}}(?:\.\d+)?)\s*(.+?){_STOP}",
            text,
            re.IGNORECASE,
        )
        if not match:
            return None
        return DiagnosisInfo(code=match.group(1).upper(), name=match.group(2).strip())

    def _treatment(self, text: str) -> TreatmentInfo | None:
        med = re.search(rf"Medication:\s*(.+?){_STOP}", text, re.IGNORECASE)
        dose = re.search(rf"Dosage:\s*(.+?){_STOP}", text, re.IGNORECASE)
        if not med and not dose:
            rp = re.search(rf"Rp:\s*(.+?){_STOP}", text, re.IGNORECASE)
            if not rp:
                return None
            return TreatmentInfo(medication=rp.group(1).strip(), dosage=None)
        return TreatmentInfo(
            medication=med.group(1).strip() if med else None,
            dosage=dose.group(1).strip() if dose else None,
        )

    def _date(self, text: str) -> date | None:
        match = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
        if not match:
            return None
        return date.fromisoformat(match.group(1))
