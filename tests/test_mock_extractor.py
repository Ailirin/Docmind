from app.models.document import DocumentType
from app.services.extractors.mock import MockEntityExtractor


def test_mock_extracts_discharge_fields(discharge_text: str):
    result = MockEntityExtractor().extract(discharge_text, DocumentType.DISCHARGE)

    assert result.extractor == "mock"
    assert result.document_type == "discharge"
    assert result.data["patient"]["full_name"] == "Ivan Ivanov"
    assert result.data["diagnosis"]["code"] == "J06.9"
    assert result.data["document_date"] == "2026-07-20"


def test_mock_extracts_prescription_with_treatment(prescription_text: str):
    result = MockEntityExtractor().extract(prescription_text, DocumentType.PRESCRIPTION)

    assert result.data["patient"]["full_name"] == "Anna Smirnova"
    assert result.data["diagnosis"]["code"] == "J03.9"
    assert result.data["treatment"]["medication"] == "Ibuprofen"
    assert "200 mg" in (result.data["treatment"]["dosage"] or "")
    assert result.confidence >= 0.8
