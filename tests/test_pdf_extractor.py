from pathlib import Path

import pytest

from app.services.pdf_extractor import extract_text_from_pdf


def test_extract_text_from_sample(sample_discharge_pdf: Path):
    text = extract_text_from_pdf(str(sample_discharge_pdf))

    assert "DocMind" in text
    assert "discharge" in text.lower()
    assert "Ivan Ivanov" in text


def test_extract_missing_file():
    with pytest.raises(FileNotFoundError):
        extract_text_from_pdf("uploads/definitely-missing.pdf")
