from pathlib import Path
import aiofiles
from typing import Optional
from . import StorageBackend
from datetime import datetime


class LocalStorage(StorageBackend):
    """Хранение файлов на локальном диске (текущая логика)."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, token: str, filename: str) -> Path:
        """Получить путь к файлу на диске с подпапками по дате."""
        now = datetime.now()
        year = str(now.year)
        month = f"{now.month:02d}"
        return self.base_path / year / month / f"{token}{Path(filename).suffix}"

    async def save(self, token: str, file_content: bytes, filename: str, mime_type: str) -> str:
        file_path = self._get_file_path(token, filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Проверка наличия места происходит в main.py, но добавим обработку ошибок
        try:
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)
        except OSError as e:
            # Пробрасываем ошибку для обработки в main.py
            raise e

        return f"/file/{token}"

    async def get(self, token: str, filename: str) -> Optional[str]:
        """Возвращает путь к файлу как строку, или None если файл не найден."""
        file_path = self._get_file_path(token, filename)
        if file_path.exists():
            return str(file_path)
        return None

    async def delete(self, token: str, filename: str) -> bool:
        file_path = self._get_file_path(token, filename)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    async def exists(self, token: str, filename: str) -> bool:
        file_path = self._get_file_path(token, filename)
        return file_path.exists()

    def get_public_path(self, token: str, filename: str) -> str:
        return f"/file/{token}"
