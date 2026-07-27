"""Unit-тесты Pydantic-схем extraction (confidence и валидация)."""

import pytest
from pydantic import ValidationError

from app.schemas.extraction import ExtractionResult


def test_confidence_must_be_in_range():
    with pytest.raises(ValidationError):
        ExtractionResult(
            document_type="discharge",
            data={},
            extractor="mock",
            confidence=1.5,
        )


def test_confidence_rounded():
    result = ExtractionResult(
        document_type="discharge",
        data={},
        extractor="mock",
        confidence=0.80001,
    )
    assert result.confidence == 0.8
