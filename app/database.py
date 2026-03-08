import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "/opt/dix/aspic/data/aspic.db")

def init_db():
    """Инициализация БД с правильными настройками"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Настройки для производительности
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA cache_size=-64000")

    # Таблица файлов
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            token TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            size INTEGER,
            mime_type TEXT,
            deleted_comment_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (deleted_comment_id) REFERENCES comments(id)
        )
    """)

    # Таблица комментариев/действий
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_token TEXT NOT NULL,
            action_type TEXT DEFAULT 'comment',
            author_name TEXT,
            author_ip TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_token) REFERENCES files(token) ON DELETE CASCADE
        )
    """)

    # Индексы
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(deleted_comment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_file ON comments(file_token)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_type ON comments(action_type)")

    conn.commit()
    conn.close()


@contextmanager
def get_db():
    """Контекстный менеджер для подключения к БД"""
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()