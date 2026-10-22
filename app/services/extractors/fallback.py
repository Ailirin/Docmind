"""FallbackEntityExtractor: пробует primary (LLM), при сбое — secondary (regex).

Паттерн graceful degradation:
- при недоступности LLM документ всё равно обрабатывается (не падает в FAILED);
- результат помечается extractor="regex_fallback" и confidence снижается;
- каждый fallback-вызов инкрементирует счётчик Prometheus для алертинга.
"""

import logging

from app.core.metrics import EXTRACTOR_FALLBACK_TOTAL
from app.models.document import DocumentType
from app.schemas.extraction import ExtractionResult
from app.services.extractors.base import EntityExtractor

logger = logging.getLogger("docmind.extractor.fallback")


class FallbackEntityExtractor(EntityExtractor):
    """Обёртка над двумя экстракторами: primary → secondary при любом исключении."""

    def __init__(self, primary: EntityExtractor, secondary: EntityExtractor) -> None:
        self.primary = primary
        self.secondary = secondary

    def extract(self, text: str, document_type: DocumentType) -> ExtractionResult:
        try:
            return self.primary.extract(text, document_type)
        except Exception as exc:
            logger.warning(
                "Primary extractor failed, switching to fallback. primary=%s error=%s: %s",
                type(self.primary).__name__,
                type(exc).__name__,
                exc,
            )
            EXTRACTOR_FALLBACK_TOTAL.inc()

            result = self.secondary.extract(text, document_type)

            # Явно помечаем, что извлечение выполнено резервным экстрактором,
            # и снижаем confidence — потребитель может учесть это при обработке.
            return ExtractionResult(
                document_type=result.document_type,
                data=result.data,
                extractor="regex_fallback",
                confidence=min(result.confidence or 0.4, 0.5),
            )
