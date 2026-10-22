"""Фабрика экстракторов.

Стратегия выбора:
- mock  → MockEntityExtractor (стабильный regex, для тестов и демо)
- llm   → FallbackEntityExtractor(LlmEntityExtractor, MockEntityExtractor)
          LLM — основной провайдер; при сбое автоматически деградирует
          до regex-экстрактора (extractor="regex_fallback"), вместо того
          чтобы перевести документ в статус FAILED.
"""

from app.core.config import settings
from app.services.extractors.base import EntityExtractor
from app.services.extractors.mock import MockEntityExtractor


def get_extractor() -> EntityExtractor:
    provider = settings.extractor_provider.lower()

    if provider == "mock":
        return MockEntityExtractor()

    if provider == "llm":
        from app.services.extractors.fallback import FallbackEntityExtractor
        from app.services.extractors.llm import LlmEntityExtractor

        return FallbackEntityExtractor(
            primary=LlmEntityExtractor(),
            secondary=MockEntityExtractor(),
        )

    raise ValueError(f"Unknown extractor_provider: {provider}")
