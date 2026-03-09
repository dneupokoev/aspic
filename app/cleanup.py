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
from dotenv import load_dotenv

load_dotenv()


async def cleanup():
    print("🔍 Поиск файлов, помеченных как удаленные...")
    deleted = await get_deleted_files()

    if not deleted:
        print("✅ Нет файлов для очистки")
        return

    print(f"📊 Найдено {len(deleted)} файлов для очистки:")
    cleaned = 0
    errors = 0
    empty_dirs = set()

    for file_info in deleted:
        try:
            file_path = Path(file_info['file_path'])
            token = file_info['token']
            delete_date = file_info['delete_date']
            reason = file_info['delete_reason'] or "без причины"

            print(f"  • {token} ({delete_date}) - {reason}")

            if file_path.exists():
                # Запоминаем родительскую папку для возможной очистки
                parent_dir = file_path.parent
                file_path.unlink()
                print(f"    ✅ Файл удален: {file_path}")
                empty_dirs.add(parent_dir)
            else:
                print(f"    ⚠️ Файл не найден на диске: {file_path}")

            await permanently_delete_file(token)
            cleaned += 1

        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            errors += 1

    # Удаляем пустые папки
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

    print(f"\n✅ Очистка завершена: {cleaned} файлов удалено, {errors} ошибок, {removed_dirs} папок очищено")


if __name__ == "__main__":
    asyncio.run(cleanup())