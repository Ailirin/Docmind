"""Доменные исключения DocMind.

Использование кастомных классов позволяет:
- точечно ловить ошибки на нужном уровне (API vs processor vs worker);
- не пробрасывать голые ValueError/RuntimeError через слои;
- легко добавлять структурированные поля (doc_id, field_name и т.п.).
"""

from uuid import UUID


class DocMindError(Exception):
    """Базовый класс для всех доменных ошибок."""


class DocumentNotFoundError(DocMindError):
    """Документ с указанным ID не найден в БД."""

    def __init__(self, document_id: UUID) -> None:
        self.document_id = document_id
        super().__init__(f"Document {document_id} not found")


class DocumentProcessingError(DocMindError):
    """Ошибка во время обработки документа (PDF → текст → экстракция)."""

    def __init__(self, document_id: UUID, reason: str) -> None:
        self.document_id = document_id
        self.reason = reason
        super().__init__(f"Processing failed for {document_id}: {reason}")


class EmptyDocumentError(DocumentProcessingError):
    """PDF не содержит извлекаемого текста."""

    def __init__(self, document_id: UUID) -> None:
        super().__init__(document_id, "No text extracted from PDF")


class StorageError(DocMindError):
    """Ошибка работы с файловым хранилищем."""


class QueueError(DocMindError):
    """Ошибка публикации сообщения в очередь."""


class ExtractionError(DocMindError):
    """Ошибка извлечения сущностей из текста (LLM или mock)."""

    def __init__(self, extractor: str, reason: str) -> None:
        self.extractor = extractor
        self.reason = reason
        super().__init__(f"[{extractor}] Extraction failed: {reason}")
