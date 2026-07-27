"""Абстрактный интерфейс экстрактора сущностей из текста документа."""

from abc import ABC, abstractmethod

from app.models.document import DocumentType
from app.schemas.extraction import ExtractionResult


class EntityExtractor(ABC):
    @abstractmethod
    def extract(self, text: str, document_type: DocumentType) -> ExtractionResult:
        """Извлекает сущности из текста документа."""
