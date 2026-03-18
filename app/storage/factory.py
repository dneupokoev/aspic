from . import StorageBackend
from .local import LocalStorage


def get_storage_backend(config: dict) -> StorageBackend:
    """Создать экземпляр бэкенда по конфигу.

    Сейчас поддерживает только 'local', но интерфейс позволяет добавить другие.

    ============================================
    КАК ДОБАВИТЬ НОВЫЙ ТИП ХРАНИЛИЩА
    ============================================

    Шаг 1: Создайте новый файл в app/storage/
    ------------------------------------------
    Например: app/storage/s3.py

    Шаг 2: Реализуйте класс, наследующий StorageBackend
    ---------------------------------------------------
    from . import StorageBackend
    from typing import Optional, BinaryIO

    class S3Storage(StorageBackend):
        def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
            self.endpoint = endpoint
            self.bucket = bucket
            # ... инициализация клиента ...

        async def save(self, token: str, file_content: bytes, filename: str, mime_type: str) -> str:
            # Логика сохранения файла
            # Вернуть публичный путь: f"/file/{token}"
            pass

        async def get(self, token: str, filename: str) -> Optional[BinaryIO]:
            # Логика получения файла
            # Вернуть файловый объект или None
            pass

        async def delete(self, token: str, filename: str) -> bool:
            # Логика удаления файла
            # Вернуть True если успешно
            pass

        async def exists(self, token: str, filename: str) -> bool:
            # Проверка существования файла
            pass

        def get_public_path(self, token: str, filename: str) -> str:
            # Вернуть публичный путь для эндпоинтов
            return f"/file/{token}"

    Шаг 3: Импортируйте класс в factory.py
    --------------------------------------
    from .s3 import S3Storage  # добавьте в начало файла

    Шаг 4: Добавьте ветку в get_storage_backend()
    --------------------------------------------
    if backend_type == 's3':
        return S3Storage(
            endpoint=config['S3_ENDPOINT'],
            bucket=config['S3_BUCKET'],
            access_key=config['S3_ACCESS_KEY'],
            secret_key=config['S3_SECRET_KEY']
        )

    Шаг 5: Добавьте настройки в config.py и .env
    -------------------------------------------
    # В config.py:
    S3_ENDPOINT = os.getenv('S3_ENDPOINT', '')
    S3_BUCKET = os.getenv('S3_BUCKET', '')
    # ... и т.д.

    # В .env:
    STORAGE_BACKEND=s3
    S3_ENDPOINT=https://s3.yandexcloud.net
    S3_BUCKET=my-bucket
    S3_ACCESS_KEY=your_key
    S3_SECRET_KEY=your_secret

    Шаг 6: Протестируйте
    -------------------
    - Загрузите файл через веб-интерфейс
    - Проверьте, что файл появился в новом хранилище
    - Проверьте скачивание и удаление

    ============================================
    ВАЖНО: Методы, которые нужно реализовать
    ============================================

    • save() — сохраняет файл, возвращает публичный путь
    • get() — возвращает файловый объект для отдачи клиенту
    • delete() — удаляет файл, возвращает статус
    • exists() — проверяет наличие файла
    • get_public_path() — возвращает путь для эндпоинтов (/file/{token})

    Все методы, кроме get_public_path(), — асинхронные.
    """
    backend_type = config.get('STORAGE_BACKEND', 'local').lower()

    if backend_type == 'local':
        return LocalStorage(base_path=config['UPLOAD_DIR'])

    raise ValueError(f"Unknown storage backend: {backend_type}")