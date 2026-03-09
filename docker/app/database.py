import os
import aiosqlite
from typing import Optional, Dict, List, Any
from datetime import datetime

# Путь к БД из окружения
DB_PATH = os.getenv('DB_PATH', '/opt/dix/aspic/data/aspic.db')


async def get_table_info(db, table_name: str) -> List[str]:
    """Получает список колонок таблицы."""
    cursor = await db.execute(f"PRAGMA table_info({table_name})")
    columns = await cursor.fetchall()
    return [col[1] for col in columns]


async def init_db(db_path: str = DB_PATH):
    """
    Инициализация базы данных.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute("PRAGMA journal_mode = WAL")

        # Проверяем существование таблицы files
        cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files'")
        table_exists = await cursor.fetchone()

        if not table_exists:
            print("🆕 Создание новой базы данных...")
            # Таблица файлов с полем deleted и downloads
            await db.execute('''
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    views INTEGER DEFAULT 0,
                    downloads INTEGER DEFAULT 0,
                    deleted BOOLEAN DEFAULT 0,
                    delete_date TIMESTAMP,
                    delete_reason TEXT
                )
            ''')

            # Таблица комментариев
            await db.execute('''
                CREATE TABLE comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_token TEXT NOT NULL,
                    author TEXT NOT NULL,
                    comment_text TEXT NOT NULL,
                    comment_type TEXT DEFAULT 'comment',
                    comment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_token) REFERENCES files (token) ON DELETE CASCADE
                )
            ''')

            await db.execute('CREATE INDEX idx_files_token ON files(token)')
            await db.execute('CREATE INDEX idx_comments_file_token ON comments(file_token)')
            await db.execute('CREATE INDEX idx_files_deleted ON files(deleted)')

            await db.commit()
            print("✅ Новая база данных создана")
        else:
            # Проверяем структуру таблицы files
            files_columns = await get_table_info(db, "files")

            # Добавляем недостающие поля
            if 'deleted' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле deleted...")
                await db.execute("ALTER TABLE files ADD COLUMN deleted BOOLEAN DEFAULT 0")

            if 'delete_date' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле delete_date...")
                await db.execute("ALTER TABLE files ADD COLUMN delete_date TIMESTAMP")

            if 'delete_reason' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле delete_reason...")
                await db.execute("ALTER TABLE files ADD COLUMN delete_reason TEXT")

            if 'downloads' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле downloads...")
                await db.execute("ALTER TABLE files ADD COLUMN downloads INTEGER DEFAULT 0")

            # Проверяем таблицу comments
            comments_columns = await get_table_info(db, "comments")
            if 'comment_type' not in comments_columns:
                print("🔄 Обновление таблицы comments: добавляем поле comment_type...")
                await db.execute("ALTER TABLE comments ADD COLUMN comment_type TEXT DEFAULT 'comment'")

            if 'author' not in comments_columns:
                print("🔄 Обновление таблицы comments: добавляем поле author...")
                await db.execute("ALTER TABLE comments ADD COLUMN author TEXT DEFAULT 'ЗЛОБНЫЙ_АНОНИМ'")

            await db.commit()
            print("✅ Таблицы обновлены")


async def save_file_metadata(
        token: str,
        filename: str,
        mime_type: str,
        size: int,
        file_path: str,
        db_path: str = DB_PATH
) -> None:
    """Сохраняет метаданные загруженного файла."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'filename' in columns:
            await db.execute('''
                INSERT INTO files (token, filename, mime_type, size, file_path, deleted, downloads)
                VALUES (?, ?, ?, ?, ?, 0, 0)
            ''', (token, filename, mime_type, size, file_path))
        elif 'original_name' in columns:
            await db.execute('''
                INSERT INTO files (token, original_name, mime_type, size, file_path, deleted, downloads)
                VALUES (?, ?, ?, ?, ?, 0, 0)
            ''', (token, filename, mime_type, size, file_path))

        await db.commit()


async def get_file_metadata(
        token: str,
        include_deleted: bool = False,
        db_path: str = DB_PATH
) -> Optional[Dict[str, Any]]:
    """
    Возвращает метаданные файла по токену.
    По умолчанию не возвращает удаленные файлы.
    """
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")
        name_field = 'filename' if 'filename' in columns else 'original_name'

        # Формируем запрос с учетом флага include_deleted
        if include_deleted:
            query = f'''
                SELECT token, {name_field}, mime_type, size, file_path, 
                       upload_date, views, downloads, deleted, delete_date, delete_reason
                FROM files 
                WHERE token = ?
            '''
            params = (token,)
        else:
            query = f'''
                SELECT token, {name_field}, mime_type, size, file_path, 
                       upload_date, views, downloads, deleted, delete_date, delete_reason
                FROM files 
                WHERE token = ? AND deleted = 0
            '''
            params = (token,)

        cursor = await db.execute(query, params)
        row = await cursor.fetchone()
        await db.commit()

        if row:
            result = {
                'token': row[0],
                'filename': row[1],
                'mime_type': row[2],
                'size': row[3],
                'file_path': row[4],
                'upload_date': row[5],
                'views': row[6] or 0,
                'downloads': row[7] or 0,
                'deleted': bool(row[8]) if len(row) > 8 else False
            }

            # Добавляем поля удаления, если они есть
            if len(row) > 9:
                result['delete_date'] = row[9]
                result['delete_reason'] = row[10]

            return result
        return None


async def increment_view_count(token: str, db_path: str = DB_PATH) -> None:
    """Увеличивает счетчик просмотров."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('UPDATE files SET views = views + 1 WHERE token = ? AND deleted = 0', (token,))
        await db.commit()


async def increment_download_count(token: str, db_path: str = DB_PATH) -> None:
    """Увеличивает счетчик скачиваний."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('UPDATE files SET downloads = downloads + 1 WHERE token = ? AND deleted = 0', (token,))
        await db.commit()


async def mark_file_as_deleted(
        token: str,
        delete_reason: str = None,
        db_path: str = DB_PATH
) -> bool:
    """
    Помечает файл как удаленный (soft delete).
    Возвращает True если успешно, False если файл не найден.
    """
    async with aiosqlite.connect(db_path) as db:
        # Проверяем существование файла
        cursor = await db.execute('SELECT 1 FROM files WHERE token = ?', (token,))
        exists = await cursor.fetchone()

        if not exists:
            return False

        # Помечаем как удаленный
        await db.execute('''
            UPDATE files 
            SET deleted = 1, 
                delete_date = CURRENT_TIMESTAMP,
                delete_reason = ?
            WHERE token = ?
        ''', (delete_reason, token))

        await db.commit()
        return True


async def get_deleted_files(
        limit: int = 100,
        db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """Возвращает список удаленных файлов для последующей очистки."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")
        name_field = 'filename' if 'filename' in columns else 'original_name'

        cursor = await db.execute(f'''
            SELECT token, {name_field}, file_path, delete_date, delete_reason
            FROM files
            WHERE deleted = 1
            ORDER BY delete_date ASC
            LIMIT ?
        ''', (limit,))

        rows = await cursor.fetchall()

        return [
            {
                'token': row[0],
                'filename': row[1],
                'file_path': row[2],
                'delete_date': row[3],
                'delete_reason': row[4]
            }
            for row in rows
        ]


async def permanently_delete_file(
        token: str,
        db_path: str = DB_PATH
) -> bool:
    """
    Полностью удаляет запись о файле из БД.
    Использовать только после физического удаления файла!
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute('DELETE FROM files WHERE token = ?', (token,))
        await db.commit()
        return True


async def add_comment(
        file_token: str,
        author: str,
        comment_text: str,
        comment_type: str = 'comment',
        db_path: str = DB_PATH
) -> None:
    """Добавляет комментарий к файлу."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            INSERT INTO comments (file_token, author, comment_text, comment_type)
            VALUES (?, ?, ?, ?)
        ''', (file_token, author, comment_text, comment_type))
        await db.commit()


async def get_comments(
        file_token: str,
        db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """Возвращает все комментарии для файла."""
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute('''
            SELECT id, author, comment_text, comment_type, comment_date
            FROM comments
            WHERE file_token = ?
            ORDER BY comment_date DESC
        ''', (file_token,))
        rows = await cursor.fetchall()

        return [
            {
                'id': row[0],
                'author': row[1],
                'text': row[2],
                'type': row[3],
                'date': row[4]
            }
            for row in rows
        ]