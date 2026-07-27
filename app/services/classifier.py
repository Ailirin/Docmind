from app.models.document import DocumentType

RULES: list[tuple[DocumentType, tuple[str, ...]]] = [
    (
        DocumentType.PRESCRIPTION,
        ("рецепт", "prescription", "rp:", "dosage", "дозировка", "mg", "таблет"),
    ),
    (
        DocumentType.DIAGNOSIS,
        ("диагноз", "diagnosis", "мкб", "icd", "заключени"),
    ),
    (
        DocumentType.DISCHARGE,
        ("выписка", "discharge", "эпикриз", "госпитализац", "выписан"),
    ),
]


def classify_document(text: str) -> DocumentType:
    """Эвристическая классификация по ключевым словам"""
    normalized = text.lower()

    scores: dict[DocumentType, int] = {t: 0 for t in DocumentType if t != DocumentType.UNKNOWN}

    for doc_type, keyword in RULES:
        for kw in keyword:
            if kw in normalized:
                scores[doc_type] += 1

    best_type, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return DocumentType.UNKNOWN
    return best_type
