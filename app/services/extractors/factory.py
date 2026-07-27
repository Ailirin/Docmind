from app.core.config import settings
from app.services.extractors.base import EntityExtractor
from app.services.extractors.mock import MockEntityExtractor


def get_extractor() -> EntityExtractor:
    provider = settings.extractor_provider.lower()
    if provider == "mock":
        return MockEntityExtractor()
    if provider == "llm":
        from app.services.extractors.llm import LlmEntityExtractor

        return LlmEntityExtractor()
    raise ValueError(f"Unknown extractor_provider: {provider}")
