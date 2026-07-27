import json
import re

from openai import OpenAI

from app.core.config import settings
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
- даты только YYYY-MM-DD или null
- если поля нет — null
- name/medication/dosage бери из текста как есть, без перевода
- code — только код МКБ (например J03.9)
- medication — название препарата, dosage — дозировка и режим
- между словами сохраняй пробелы, ничего не додумывай
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
        # Ollama / совместимые API часто принимают json_object
        try:
            response = self.client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
        except Exception:
            response = self.client.chat.completions.create(**kwargs)

        raw = (response.choices[0].message.content or "").strip()
        parsed = _extract_json_object(raw)
        payload = MedicalExtraction.model_validate(parsed)

        return ExtractionResult(
            document_type=document_type.value,
            data=payload.model_dump(mode="json"),
            extractor="llm",
            confidence=0.8,
        )
