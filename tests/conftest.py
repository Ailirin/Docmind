from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples"


@pytest.fixture
def discharge_text() -> str:
    return (
        "DocMind test PDF Document type: discharge summary "
        "Patient: Ivan Ivanov Diagnosis: J06.9 Acute upper respiratory infection "
        "Date: 2026-07-20"
    )


@pytest.fixture
def prescription_text() -> str:
    return (
        "Document type: prescription Patient: Anna Smirnova "
        "Diagnosis: J03.9 Острый тонзиллит "
        "Medication: Ibuprofen Dosage: 200 mg tablets, twice daily "
        "Rp: Ibuprofen 200mg Date: 2026-05-01"
    )


@pytest.fixture
def sample_discharge_pdf() -> Path:
    path = SAMPLES / "test_discharge.pdf"
    assert path.exists(), f"Missing sample: {path}"
    return path
