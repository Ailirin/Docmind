"""Unit-тесты фабрики экстракторов."""

from unittest.mock import MagicMock

import pytest

from app.services.extractors.factory import get_extractor
from app.services.extractors.llm import LlmEntityExtractor
from app.services.extractors.mock import MockEntityExtractor


def test_get_extractor_mock(monkeypatch):
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "mock",
    )

    extractor = get_extractor()

    assert isinstance(extractor, MockEntityExtractor)


def test_get_extractor_llm(monkeypatch):
    monkeypatch.setattr(
        "app.services.extractors.factory.settings.extractor_provider",
        "llm",
    )
    monkeypatch.setattr(
        "app.services.extractors.llm.OpenAI",
        MagicMock,
    )

    extractor = get_extractor()

    assert isinstance(extractor, LlmEntityExtractor)


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
