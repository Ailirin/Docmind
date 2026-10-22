"""Unit-тесты LLM-экстрактора: парсинг JSON, нормализация, retry."""

import json
from unittest.mock import MagicMock, patch

import pytest
from openai import APIConnectionError

from app.models.document import DocumentType
from app.services.extractors.llm import (
    LlmEntityExtractor,
    _extract_json_object,
    _fill_from_text,
    _normalize_diagnosis_fields,
)

# ── _extract_json_object ─────────────────────────────────────────────────────

def test_extract_clean_json():
    raw = '{"patient": {"full_name": "Ivan"}}'
    result = _extract_json_object(raw)
    assert result["patient"]["full_name"] == "Ivan"


def test_extract_json_in_markdown_block():
    raw = '```json\n{"diagnosis": {"code": "J06.9"}}\n```'
    result = _extract_json_object(raw)
    assert result["diagnosis"]["code"] == "J06.9"


def test_extract_json_with_surrounding_text():
    raw = 'Here is the result:\n{"raw_notes": "headache"}\nEnd.'
    result = _extract_json_object(raw)
    assert result["raw_notes"] == "headache"


def test_extract_json_raises_on_garbage():
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object("no json here at all!!!")


# ── _normalize_diagnosis_fields ──────────────────────────────────────────────

def test_normalize_splits_code_and_name():
    parsed = {"diagnosis": {"code": "J06.9 Acute URI", "name": None}}
    result = _normalize_diagnosis_fields(parsed)
    assert result["diagnosis"]["code"] == "J06.9"
    assert result["diagnosis"]["name"] == "Acute URI"


def test_normalize_preserves_correct_code():
    parsed = {"diagnosis": {"code": "I10", "name": "Hypertension"}}
    result = _normalize_diagnosis_fields(parsed)
    assert result["diagnosis"]["code"] == "I10"
    assert result["diagnosis"]["name"] == "Hypertension"


def test_normalize_no_diagnosis_key():
    parsed = {"patient": {"full_name": "Test"}}
    result = _normalize_diagnosis_fields(parsed)
    assert "diagnosis" not in result


def test_normalize_diagnosis_is_not_dict():
    parsed = {"diagnosis": "J06.9"}
    result = _normalize_diagnosis_fields(parsed)
    assert result["diagnosis"] == "J06.9"


# ── _fill_from_text ──────────────────────────────────────────────────────────

def test_fill_icd_code_from_text():
    text = "Diagnosis: J03.9 Tonsillitis Medication: Amoxicillin"
    parsed: dict = {"diagnosis": {}, "treatment": {}, "patient": {}}
    result = _fill_from_text(parsed, text)
    assert result["diagnosis"]["code"] == "J03.9"


def test_fill_medication_from_text():
    text = "Medication: Ibuprofen\nDosage: 200mg"
    parsed: dict = {"diagnosis": {}, "treatment": {"medication": None}, "patient": {}}
    result = _fill_from_text(parsed, text)
    assert result["treatment"]["medication"] == "Ibuprofen"


def test_fill_patient_from_text():
    text = "Patient: Anna Petrova\nDate: 2026-01-15"
    parsed: dict = {"diagnosis": {}, "treatment": {}, "patient": {}}
    result = _fill_from_text(parsed, text)
    assert result["patient"]["full_name"] == "Anna Petrova"


# ── LlmEntityExtractor.extract ───────────────────────────────────────────────

def _make_extractor(response_content: str) -> LlmEntityExtractor:
    """Создаёт экстрактор с замоканным OpenAI-клиентом."""
    with patch("app.services.extractors.llm.OpenAI"):
        extractor = LlmEntityExtractor()

    mock_response = MagicMock()
    mock_response.choices[0].message.content = response_content
    extractor.client = MagicMock()
    extractor.client.chat.completions.create.return_value = mock_response
    return extractor


_GOOD_RESPONSE = json.dumps({
    "patient": {"full_name": "Ivan Ivanov"},
    "diagnosis": {"code": "J06.9", "name": "Acute URI"},
    "treatment": {"medication": "Ibuprofen", "dosage": "200mg"},
    "document_date": "2026-07-20",
    "raw_notes": None,
})


def test_extract_success():
    extractor = _make_extractor(_GOOD_RESPONSE)
    result = extractor.extract("text", DocumentType.DISCHARGE)

    assert result.extractor == "llm"
    assert result.document_type == "discharge"
    assert result.data["patient"]["full_name"] == "Ivan Ivanov"
    assert result.data["diagnosis"]["code"] == "J06.9"
    assert result.confidence == 0.8


def test_extract_increments_success_metric():
    extractor = _make_extractor(_GOOD_RESPONSE)
    with patch("app.services.extractors.llm.LLM_EXTRACTIONS") as mock_metric:
        extractor.extract("text", DocumentType.DISCHARGE)
        mock_metric.labels.assert_called_with(result="success")
        mock_metric.labels.return_value.inc.assert_called_once()


def test_extract_raises_on_invalid_json():
    extractor = _make_extractor("not json at all")
    with pytest.raises(json.JSONDecodeError):
        extractor.extract("text", DocumentType.DISCHARGE)


def test_extract_raises_on_validation_error():
    """Дата в неверном формате → Pydantic ValidationError."""
    from pydantic import ValidationError

    bad = json.dumps({
        "patient": None,
        "diagnosis": None,
        "treatment": None,
        "document_date": "not-a-date",
        "raw_notes": None,
    })
    extractor = _make_extractor(bad)
    with pytest.raises(ValidationError):
        extractor.extract("text", DocumentType.DISCHARGE)


def test_extract_retries_on_connection_error():
    """При APIConnectionError tenacity делает retry; если все 3 исчерпаны — reraise."""
    with patch("app.services.extractors.llm.OpenAI"):
        extractor = LlmEntityExtractor()

    extractor.client = MagicMock()
    extractor.client.chat.completions.create.side_effect = APIConnectionError.__new__(
        APIConnectionError
    )

    # tenacity reraise=True → пробрасывает последнее исключение после 3 попыток
    with pytest.raises(APIConnectionError):
        extractor.extract("text", DocumentType.DISCHARGE)

    # Должно было 3 попытки (+ 1 fallback без json_object = 2 вызова на попытку)
    assert extractor.client.chat.completions.create.call_count >= 3
