from abc import ABC, abstractmethod
from typing import Optional
from pathlib import Path


class StorageBackend(ABC):
    """Абстрактный интерфейс для хранения файлов."""

    @abstractmethod
    async def save(self, token: str, file_content: bytes, filename: str, mime_type: str) -> str:
        """Сохранить файл, вернуть публичный путь/URL."""
        pass

    @abstractmethod
    async def get(self, token: str, filename: str) -> Optional[str]:
        """Получить путь к файлу как строку, или None если файл не найден."""
        pass

    @abstractmethod
    async def delete(self, token: str, filename: str) -> bool:
        """Удалить файл по токену."""
        pass

    @abstractmethod
    async def exists(self, token: str, filename: str) -> bool:
        """Проверить существование файла."""
        pass

    @abstractmethod
    def get_public_path(self, token: str, filename: str) -> str:
        """Получить публичный путь для файла."""
        pass