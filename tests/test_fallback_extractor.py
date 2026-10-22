"""Unit-тесты FallbackEntityExtractor."""

from unittest.mock import MagicMock, patch

from app.models.document import DocumentType
from app.schemas.extraction import ExtractionResult
from app.services.extractors.fallback import FallbackEntityExtractor


def _make_result(extractor: str = "llm", confidence: float = 0.8) -> ExtractionResult:
    return ExtractionResult(
        document_type="discharge",
        data={"patient": {"full_name": "Test User"}},
        extractor=extractor,
        confidence=confidence,
    )


def test_fallback_uses_primary_on_success():
    """Если primary отрабатывает без ошибок — secondary не вызывается."""
    primary = MagicMock()
    primary.extract.return_value = _make_result(extractor="llm")
    secondary = MagicMock()

    result = FallbackEntityExtractor(primary, secondary).extract("text", DocumentType.DISCHARGE)

    assert result.extractor == "llm"
    secondary.extract.assert_not_called()


def test_fallback_switches_to_secondary_on_error():
    """При сбое primary — вызывается secondary, extractor меняется на regex_fallback."""
    primary = MagicMock()
    primary.extract.side_effect = RuntimeError("LLM unavailable")
    secondary = MagicMock()
    secondary.extract.return_value = _make_result(extractor="mock", confidence=0.6)

    result = FallbackEntityExtractor(primary, secondary).extract("text", DocumentType.DISCHARGE)

    assert result.extractor == "regex_fallback"
    secondary.extract.assert_called_once()


def test_fallback_caps_confidence():
    """Confidence результата fallback не превышает 0.5."""
    primary = MagicMock()
    primary.extract.side_effect = ConnectionError("timeout")
    secondary = MagicMock()
    secondary.extract.return_value = _make_result(extractor="mock", confidence=0.9)

    result = FallbackEntityExtractor(primary, secondary).extract("text", DocumentType.DISCHARGE)

    assert result.confidence is not None
    assert result.confidence <= 0.5


def test_fallback_increments_prometheus_counter():
    """Каждый fallback-вызов инкрементирует docmind_extractor_fallback_total."""
    primary = MagicMock()
    primary.extract.side_effect = OSError("no route to host")
    secondary = MagicMock()
    secondary.extract.return_value = _make_result(extractor="mock", confidence=0.4)

    with patch("app.services.extractors.fallback.EXTRACTOR_FALLBACK_TOTAL") as mock_counter:
        FallbackEntityExtractor(primary, secondary).extract("text", DocumentType.DISCHARGE)
        mock_counter.inc.assert_called_once()


def test_fallback_preserves_data_from_secondary():
    """Данные из secondary передаются без изменений."""
    primary = MagicMock()
    primary.extract.side_effect = Exception("boom")
    secondary = MagicMock()
    expected_data = {"patient": {"full_name": "Anna"}, "diagnosis": {"code": "J06.9"}}
    secondary.extract.return_value = ExtractionResult(
        document_type="prescription",
        data=expected_data,
        extractor="mock",
        confidence=0.6,
    )

    result = FallbackEntityExtractor(primary, secondary).extract("text", DocumentType.PRESCRIPTION)

    assert result.data == expected_data
    assert result.document_type == "prescription"
