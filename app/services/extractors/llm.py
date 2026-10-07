"""LLM-экстрактор: OpenAI-compatible API + валидация ответа через Pydantic."""

import json
import re

from openai import OpenAI
from pydantic import ValidationError

from app.core.config import settings
from app.core.metrics import LLM_EXTRACTIONS
from app.models.document import DocumentType
from app.schemas.extraction import ExtractionResult, MedicalExtraction
from app.services.extractors.base import EntityExtractor

SYSTEM_PROMPT = """
Ты извлекаешь сущности из медицинского текста.
Ответь ОДНИМ JSON-объектом. Без markdown, без текста до/после JSON.
Ключи строго такие:
{
  "patient": {"full_name": null},
  "diagnosis": {"code": null, "name": null},
  "treatment": {"medication": null, "dosage": null},
  "document_date": null,
  "raw_notes": null
}
Правила:
- только двойные кавычки
- нет trailing comma
- даты только строка YYYY-MM-DD или null (не объект)
- если поля нет — null (не "" и не [])
- patient / diagnosis / treatment — объекты или null, не списки и не строки
- name / medication / dosage бери из текста КАК ЕСТЬ, без перевода
- торговые названия НЕ заменяй на МНН (Нурофен остаётся Нурофен)

Диагноз — самое важное:
- строка вида "Diagnosis: J06.9 Acute URI" значит:
  diagnosis.code = "J06.9"
  diagnosis.name = "Acute URI"
- code: ТОЛЬКО код МКБ, шаблон буква + цифры, опционально точка и цифры
  примеры верно: "J06.9", "I10", "E11.9"
  примеры НЕВЕРНО: "J06.9 Acute URI", "J06.9 ОРВИ", "Acute URI"
- name: только текст названия БЕЗ кода
  верно: "Acute URI" / "Пневмония"
  неверно: "J06.9 Acute URI"
- если кода нет в тексте — code = null
- если названия нет — name = null

medication — название препарата, dosage — дозировка и режим.
Между словами сохраняй пробелы, ничего не додумывай.
""".strip()


def _extract_json_object(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


_ICD_RE = re.compile(r"\b([A-Z]\d{2}(?:\.\d+)?)\b", re.IGNORECASE)


def _normalize_diagnosis_fields(parsed: dict) -> dict:
    """Если code содержит 'J06.9 Acute URI' — разрезать на code/name."""
    diagnosis = parsed.get("diagnosis")
    if not isinstance(diagnosis, dict):
        return parsed

    code = diagnosis.get("code")
    name = diagnosis.get("name")
    if not isinstance(code, str):
        return parsed

    code_stripped = code.strip()
    match = _ICD_RE.search(code_stripped)
    if not match:
        return parsed

    only_code = match.group(1).upper()
    rest = code_stripped[match.end() :].strip(" :-–—\t")
    diagnosis["code"] = only_code
    if (not name) and rest:
        diagnosis["name"] = rest
    parsed["diagnosis"] = diagnosis
    return parsed


def _fill_from_text(parsed: dict, text: str) -> dict:
    """Добиваем поля, которые маленькая модель часто оставляет null."""
    diagnosis = parsed.get("diagnosis")
    if not isinstance(diagnosis, dict):
        diagnosis = {}
        parsed["diagnosis"] = diagnosis

    code = diagnosis.get("code")
    if not (isinstance(code, str) and _ICD_RE.search(code)):
        m = _ICD_RE.search(text)
        if m:
            diagnosis["code"] = m.group(1).upper()

    treatment = parsed.get("treatment")
    if not isinstance(treatment, dict):
        treatment = {}
        parsed["treatment"] = treatment

    med = treatment.get("medication")
    if not isinstance(med, str) or not med.strip():
        m = re.search(
            r"Medication:\s*(.+?)(?:\n|Dosage:|Date:|Rp:|$)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            treatment["medication"] = m.group(1).strip()

    if isinstance(treatment.get("medication"), dict):
        treatment["medication"] = treatment["medication"].get("name") or treatment[
            "medication"
        ].get("value")
    if isinstance(treatment.get("dosage"), dict):
        treatment["dosage"] = treatment["dosage"].get("value") or treatment["dosage"].get("name")

    patient = parsed.get("patient")
    if not isinstance(patient, dict):
        patient = {}
        parsed["patient"] = patient
    m = re.search(r"Patient:\s*(.+)", text, flags=re.IGNORECASE)
    if m:
        patient["full_name"] = m.group(1).strip()

    return parsed


class LlmEntityExtractor(EntityExtractor):
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=settings.llm_api_key or "unused",
            base_url=settings.llm_base_url,
        )
        self.model = settings.llm_model

    def extract(self, text: str, document_type: DocumentType) -> ExtractionResult:
        kwargs = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Тип документа: {document_type.value}\n\nТекст:\n{text}",
                },
            ],
        }

        try:
            try:
                response = self.client.chat.completions.create(
                    **kwargs,
                    response_format={"type": "json_object"},
                )
            except Exception:
                response = self.client.chat.completions.create(**kwargs)

            raw = (response.choices[0].message.content or "").strip()
            parsed = _extract_json_object(raw)
            parsed = _normalize_diagnosis_fields(parsed)
            parsed = _fill_from_text(parsed, text)
            payload = MedicalExtraction.model_validate(parsed)
            LLM_EXTRACTIONS.labels(result="success").inc()
        except (ValidationError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            LLM_EXTRACTIONS.labels(result="validation_error").inc()
            raise
        except Exception:
            LLM_EXTRACTIONS.labels(result="request_error").inc()
            raise

        return ExtractionResult(
            document_type=document_type.value,
            data=payload.model_dump(mode="json"),
            extractor="llm",
            confidence=0.8,
        )
