"""Unit-тесты фабрики экстракторов."""

from unittest.mock import MagicMock

import pytest

from app.services.extractors.factory import get_extractor
from app.services.extractors.fallback import FallbackEntityExtractor
from app.services.extractors.llm import LlmEntityExtractor
from app.services.extractors.mock import MockEntityExtractor


def test_get_extractor_mock(monkeypatch):
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "mock",
    )

    extractor = get_extractor()

    assert isinstance(extractor, MockEntityExtractor)


def test_get_extractor_llm_returns_fallback_wrapper(monkeypatch):
    """При provider=llm возвращается FallbackEntityExtractor, а не голый LLM."""
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "llm",
    )
    monkeypatch.setattr(
        "app.services.extractors.llm.OpenAI",
        MagicMock,
    )

    extractor = get_extractor()

    assert isinstance(extractor, FallbackEntityExtractor)
    assert isinstance(extractor.primary, LlmEntityExtractor)
    assert isinstance(extractor.secondary, MockEntityExtractor)


def test_get_extractor_unknown(monkeypatch):
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "weird",
    )

    with pytest.raises(ValueError, match="Unknown extractor_provider"):
        get_extractor()


def test_get_extractor_mock_case_insensitive(monkeypatch):
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "MOCK",
    )

    extractor = get_extractor()

    assert isinstance(extractor, MockEntityExtractor)
