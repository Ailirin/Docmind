from app.models.document import DocumentType
from app.services.classifier import classify_document

def test_classify_document(discharge_text: str):
   assert classify_document(discharge_text) == DocumentType.DISCHARGE

def test_classify_prescription(prescription_text: str):
    assert classify_document(prescription_text) == DocumentType.PRESCRIPTION

def test_classify_unknown():
    assert classify_document("hello world nothung medical") == DocumentType.UNKNOWN

def test_classify_diagnosis_keywords():
    text = "Заключение врача: диагноз по МКБ подтвержден"
    assert classify_document(text) == DocumentType.DIAGNOSIS    