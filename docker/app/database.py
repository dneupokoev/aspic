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
            await db.execute('''
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    views INTEGER DEFAULT 0, -- Количество просмотров
                    downloads INTEGER DEFAULT 0, -- Количество скачиваний
                    deleted BOOLEAN DEFAULT 0, -- 1 = Помечено на удаление
                    delete_date TIMESTAMP, -- Дата и время пометки на удаление 
                    delete_reason TEXT, -- Причина удаления (заполняется в интерфейсе или через api) 
                    last_view_date DATE, -- Дата последнего просмотра (без времени для производительности)
                    last_download_date DATE, -- Дата последнего скачивания (без времени для производительности)
                    webhook_url TEXT DEFAULT '', -- URL вебхука для вызова при попытке доступа к файлу
                    delete_password TEXT DEFAULT '', -- Пароль для удаления файла
                    expire_date TIMESTAMP, -- Дата и время автоматического удаления файла (абсолютная дата)
                    ttl_minutes INTEGER DEFAULT 0 -- Время жизни после последнего обращения (в минутах, 0 = без ограничения)
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

            # Оптимизированные индексы для новой БД
            await db.execute('CREATE INDEX idx_files_token ON files(token)')
            await db.execute('CREATE INDEX idx_files_deleted ON files(deleted)')
            await db.execute('CREATE INDEX idx_files_cleanup ON files(delete_date) WHERE deleted = 1')
            await db.execute('CREATE INDEX idx_files_active_view ON files(last_view_date) WHERE deleted = 0')
            await db.execute('CREATE INDEX idx_files_active_download ON files(last_download_date) WHERE deleted = 0')
            await db.execute('CREATE INDEX idx_files_webhook ON files(webhook_url) WHERE webhook_url != ""')
            await db.execute('CREATE INDEX idx_files_expire ON files(expire_date) WHERE deleted = 0 AND expire_date IS NOT NULL')
            await db.execute('CREATE INDEX idx_comments_file_token ON comments(file_token)')

            await db.commit()
            print("✅ Новая база данных создана с оптимизированными индексами")
        else:
            # Проверяем структуру таблицы files
            files_columns = await get_table_info(db, "files")

            # Добавляем недостающие поля (если их нет)
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

            if 'last_view_date' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле last_view_date...")
                await db.execute("ALTER TABLE files ADD COLUMN last_view_date DATE")

            if 'last_download_date' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле last_download_date...")
                await db.execute("ALTER TABLE files ADD COLUMN last_download_date DATE")

            if 'webhook_url' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле webhook_url...")
                await db.execute("ALTER TABLE files ADD COLUMN webhook_url TEXT DEFAULT ''")

            if 'delete_password' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле delete_password...")
                await db.execute("ALTER TABLE files ADD COLUMN delete_password TEXT DEFAULT ''")

            # Добавляем новые поля для автоматического удаления
            if 'expire_date' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле expire_date...")
                await db.execute("ALTER TABLE files ADD COLUMN expire_date TIMESTAMP")

            if 'ttl_minutes' not in files_columns:
                print("🔄 Обновление таблицы files: добавляем поле ttl_minutes...")
                await db.execute("ALTER TABLE files ADD COLUMN ttl_minutes INTEGER DEFAULT 0")

            # === ОПТИМИЗАЦИЯ ИНДЕКСОВ ===

            # 1. Удаляем старые неоптимальные индексы (если они есть)
            old_indexes = [
                'idx_files_last_view_date',
                'idx_files_last_download_date'
            ]

            for index_name in old_indexes:
                cursor = await db.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
                index_exists = await cursor.fetchone()
                if index_exists:
                    print(f"🔄 Удаляем старый индекс {index_name}...")
                    await db.execute(f"DROP INDEX {index_name}")

            # 2. Создаем новые оптимизированные индексы (если их нет)

            # Индекс для очистки удаленных файлов (только для deleted=1)
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_cleanup'")
            index_exists = await cursor.fetchone()
            if not index_exists and 'delete_date' in files_columns:
                print("🔄 Создаем индекс для очистки idx_files_cleanup...")
                await db.execute("CREATE INDEX idx_files_cleanup ON files(delete_date) WHERE deleted = 1")

            # Индекс для просмотров активных файлов (только для deleted=0)
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_active_view'")
            index_exists = await cursor.fetchone()
            if not index_exists and 'last_view_date' in files_columns:
                print("🔄 Создаем индекс для просмотров idx_files_active_view...")
                await db.execute("CREATE INDEX idx_files_active_view ON files(last_view_date) WHERE deleted = 0")

            # Индекс для скачиваний активных файлов (только для deleted=0)
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_active_download'")
            index_exists = await cursor.fetchone()
            if not index_exists and 'last_download_date' in files_columns:
                print("🔄 Создаем индекс для скачиваний idx_files_active_download...")
                await db.execute("CREATE INDEX idx_files_active_download ON files(last_download_date) WHERE deleted = 0")

            # Индекс для вебхуков (только если URL не пустой)
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_webhook'")
            index_exists = await cursor.fetchone()
            if not index_exists and 'webhook_url' in files_columns:
                print("🔄 Создаем индекс для вебхуков idx_files_webhook...")
                await db.execute("CREATE INDEX idx_files_webhook ON files(webhook_url) WHERE webhook_url != ''")

            # Индекс для автоматического удаления по дате
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_expire'")
            index_exists = await cursor.fetchone()
            if not index_exists and 'expire_date' in files_columns:
                print("🔄 Создаем индекс для автоудаления idx_files_expire...")
                await db.execute("CREATE INDEX idx_files_expire ON files(expire_date) WHERE deleted = 0 AND expire_date IS NOT NULL")

            # Проверяем старые индексы на всякий случай (могли остаться)
            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_last_view_date'")
            if await cursor.fetchone():
                print("⚠️ Старый индекс idx_files_last_view_date все еще существует")

            cursor = await db.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_files_last_download_date'")
            if await cursor.fetchone():
                print("⚠️ Старый индекс idx_files_last_download_date все еще существует")

            # Проверяем таблицу comments
            comments_columns = await get_table_info(db, "comments")
            if 'comment_type' not in comments_columns:
                print("🔄 Обновление таблицы comments: добавляем поле comment_type...")
                await db.execute("ALTER TABLE comments ADD COLUMN comment_type TEXT DEFAULT 'comment'")

            if 'author' not in comments_columns:
                print("🔄 Обновление таблицы comments: добавляем поле author...")
                await db.execute("ALTER TABLE comments ADD COLUMN author TEXT DEFAULT 'ЗЛОБНЫЙ_АНОНИМ'")

            await db.commit()
            print("✅ Таблицы обновлены, индексы оптимизированы")


async def save_file_metadata(
        token: str,
        filename: str,
        mime_type: str,
        size: int,
        file_path: str,
        webhook_url: str = '',
        delete_password: str = '',
        expire_date: str = None,  # дата удаления
        ttl_minutes: int = 0,      # TTL после последнего обращения
        db_path: str = DB_PATH
) -> None:
    """Сохраняет метаданные загруженного файла."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        # Получаем текущую дату для last_view_date и last_download_date
        current_date = datetime.now().strftime('%Y-%m-%d')

        if 'filename' in columns:
            # Проверяем наличие всех полей и формируем запрос динамически
            fields = ['token', 'filename', 'mime_type', 'size', 'file_path', 'deleted', 'downloads']
            values = [token, filename, mime_type, size, file_path, 0, 0]
            placeholders = ['?', '?', '?', '?', '?', '?', '?']

            if 'webhook_url' in columns:
                fields.append('webhook_url')
                values.append(webhook_url)
                placeholders.append('?')

            if 'delete_password' in columns:
                fields.append('delete_password')
                values.append(delete_password)
                placeholders.append('?')

            if 'last_view_date' in columns:
                fields.append('last_view_date')
                values.append(current_date)
                placeholders.append('?')

            if 'last_download_date' in columns:
                fields.append('last_download_date')
                values.append(current_date)
                placeholders.append('?')

            if 'expire_date' in columns and expire_date:
                fields.append('expire_date')
                values.append(expire_date)
                placeholders.append('?')

            if 'ttl_minutes' in columns and ttl_minutes:
                fields.append('ttl_minutes')
                values.append(ttl_minutes)
                placeholders.append('?')

            query = f'''
                INSERT INTO files ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            '''
            await db.execute(query, values)

        elif 'original_name' in columns:
            # Аналогично для старой схемы
            fields = ['token', 'original_name', 'mime_type', 'size', 'file_path', 'deleted', 'downloads']
            values = [token, filename, mime_type, size, file_path, 0, 0]
            placeholders = ['?', '?', '?', '?', '?', '?', '?']

            if 'webhook_url' in columns:
                fields.append('webhook_url')
                values.append(webhook_url)
                placeholders.append('?')

            if 'delete_password' in columns:
                fields.append('delete_password')
                values.append(delete_password)
                placeholders.append('?')

            if 'last_view_date' in columns:
                fields.append('last_view_date')
                values.append(current_date)
                placeholders.append('?')

            if 'last_download_date' in columns:
                fields.append('last_download_date')
                values.append(current_date)
                placeholders.append('?')

            if 'expire_date' in columns and expire_date:
                fields.append('expire_date')
                values.append(expire_date)
                placeholders.append('?')

            if 'ttl_minutes' in columns and ttl_minutes:
                fields.append('ttl_minutes')
                values.append(ttl_minutes)
                placeholders.append('?')

            query = f'''
                INSERT INTO files ({', '.join(fields)})
                VALUES ({', '.join(placeholders)})
            '''
            await db.execute(query, values)

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

        # Формируем запрос с учетом всех возможных полей
        base_fields = ['token', name_field, 'mime_type', 'size', 'file_path',
                       'upload_date', 'views', 'downloads', 'deleted',
                       'delete_date', 'delete_reason']

        # Добавляем новые поля, если они существуют
        optional_fields = ['last_view_date', 'last_download_date', 'webhook_url', 'delete_password',
                           'expire_date', 'ttl_minutes']
        for field in optional_fields:
            if field in columns:
                base_fields.append(field)

        fields_str = ', '.join(base_fields)

        # Формируем запрос с учетом флага include_deleted
        if include_deleted:
            query = f'''
                SELECT {fields_str}
                FROM files 
                WHERE token = ?
            '''
            params = (token,)
        else:
            query = f'''
                SELECT {fields_str}
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

            # Добавляем новые поля, если они есть
            field_index = 11
            if 'last_view_date' in columns and len(row) > field_index:
                result['last_view_date'] = row[field_index]
                field_index += 1
            if 'last_download_date' in columns and len(row) > field_index:
                result['last_download_date'] = row[field_index]
                field_index += 1
            if 'webhook_url' in columns and len(row) > field_index:
                result['webhook_url'] = row[field_index]
                field_index += 1
            if 'delete_password' in columns and len(row) > field_index:
                result['delete_password'] = row[field_index]
                field_index += 1
            if 'expire_date' in columns and len(row) > field_index:
                result['expire_date'] = row[field_index]
                field_index += 1
            if 'ttl_minutes' in columns and len(row) > field_index:
                result['ttl_minutes'] = row[field_index]

            return result
        return None


async def increment_view_count(token: str, db_path: str = DB_PATH) -> None:
    """Увеличивает счетчик просмотров и обновляет дату последнего просмотра."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'last_view_date' in columns:
            # Используем текущую дату в формате YYYY-MM-DD
            current_date = datetime.now().strftime('%Y-%m-%d')
            await db.execute('''
                UPDATE files 
                SET views = views + 1,
                    last_view_date = ?
                WHERE token = ? AND deleted = 0
            ''', (current_date, token))
        else:
            await db.execute('UPDATE files SET views = views + 1 WHERE token = ? AND deleted = 0', (token,))

        await db.commit()


async def increment_download_count(token: str, db_path: str = DB_PATH) -> None:
    """Увеличивает счетчик скачиваний и обновляет дату последнего скачивания."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'last_download_date' in columns:
            # Используем текущую дату в формате YYYY-MM-DD
            current_date = datetime.now().strftime('%Y-%m-%d')
            await db.execute('''
                UPDATE files 
                SET downloads = downloads + 1,
                    last_download_date = ?
                WHERE token = ? AND deleted = 0
            ''', (current_date, token))
        else:
            await db.execute('UPDATE files SET downloads = downloads + 1 WHERE token = ? AND deleted = 0', (token,))

        await db.commit()


async def update_webhook_url(
        token: str,
        webhook_url: str,
        db_path: str = DB_PATH
) -> bool:
    """Обновляет URL вебхука для файла."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'webhook_url' not in columns:
            return False

        await db.execute('''
            UPDATE files 
            SET webhook_url = ?
            WHERE token = ? AND deleted = 0
        ''', (webhook_url, token))

        await db.commit()
        return True


async def set_delete_password(
        token: str,
        password: str,
        db_path: str = DB_PATH
) -> bool:
    """Устанавливает пароль для удаления файла."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'delete_password' not in columns:
            return False

        await db.execute('''
            UPDATE files 
            SET delete_password = ?
            WHERE token = ? AND deleted = 0
        ''', (password, token))

        await db.commit()
        return True


async def verify_delete_password(
        token: str,
        password: str,
        db_path: str = DB_PATH
) -> bool:
    """Проверяет пароль для удаления файла."""
    async with aiosqlite.connect(db_path) as db:
        columns = await get_table_info(db, "files")

        if 'delete_password' not in columns:
            return True  # Если поля нет, считаем что пароль не требуется

        cursor = await db.execute('''
            SELECT delete_password 
            FROM files 
            WHERE token = ? AND deleted = 0
        ''', (token,))

        row = await cursor.fetchone()

        if not row or not row[0]:  # Если пароль не установлен
            return True

        return row[0] == password


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