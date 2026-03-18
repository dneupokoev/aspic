#!/usr/bin/env python3
"""
Скрипт для физического удаления файлов, помеченных как удаленные.
Запускать отдельно: python cleanup.py
"""

import os
import sys
import asyncio
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from app.database import get_deleted_files, permanently_delete_file
from app.storage.factory import get_storage_backend
from app.config import UPLOAD_DIR, STORAGE_BACKEND
from dotenv import load_dotenv

load_dotenv()


async def cleanup():
    print("🔍 Поиск файлов, помеченных как удаленные...")
    deleted = await get_deleted_files()

    if not deleted:
        print("✅ Нет файлов для очистки")
        return

    # Инициализируем хранилище для удаления файлов
    storage_config = {
        'STORAGE_BACKEND': STORAGE_BACKEND,
        'UPLOAD_DIR': UPLOAD_DIR,
    }
    storage = get_storage_backend(storage_config)

    print(f"📊 Найдено {len(deleted)} файлов для очистки:")
    cleaned = 0
    errors = 0
    empty_dirs = set()

    for file_info in deleted:
        try:
            token = file_info['token']
            filename = file_info['filename']
            delete_date = file_info['delete_date']
            reason = file_info['delete_reason'] or "без причины"

            print(f"  • {token} ({delete_date}) - {reason}")

            # Используем абстракцию хранилища для удаления
            deleted_from_storage = await storage.delete(token, filename)

            if deleted_from_storage:
                print(f"    ✅ Файл удален из хранилища: {token}")
                # Для локального хранилища можно попробовать очистить пустые папки
                if STORAGE_BACKEND == 'local':
                    file_path = Path(file_info['file_path'])
                    empty_dirs.add(file_path.parent)
            else:
                print(f"    ⚠️ Файл не найден в хранилище: {token}")

            await permanently_delete_file(token)
            cleaned += 1

        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            errors += 1

    # Удаляем пустые папки (только для локального хранилища)
    if STORAGE_BACKEND == 'local' and empty_dirs:
        print("\n🗑️  Очистка пустых папок...")
        removed_dirs = 0
        for dir_path in sorted(empty_dirs, key=lambda x: str(x), reverse=True):
            try:
                if dir_path.exists() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    print(f"   ✅ Удалена пустая папка: {dir_path}")
                    removed_dirs += 1
            except Exception as e:
                print(f"   ⚠️ Не удалось удалить папку {dir_path}: {e}")
        print(f"   📁 Очищено папок: {removed_dirs}")

    print(f"\n✅ Очистка завершена: {cleaned} файлов удалено, {errors} ошибок")


if __name__ == "__main__":
    asyncio.run(cleanup())