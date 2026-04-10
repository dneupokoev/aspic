# app/config.py

import os
import ipaddress
import shutil
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# ============================================
# КОНФИГУРАЦИЯ ИЗ .ENV
# ============================================
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 15191))

# ============================================
# НАСТРОЙКИ ВЕБ-ИНТЕРФЕЙСА
# ============================================
ENABLE_WEB_UI = os.getenv('ENABLE_WEB_UI', 'True').lower() == 'true'

# ============================================
# НАСТРОЙКИ ПУТЕЙ К ДАННЫМ
# ============================================
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/opt/dix/aspic/data/files')
PREVIEW_DIR = os.getenv('PREVIEW_DIR', '/opt/dix/aspic/data/preview')
DB_PATH = os.getenv('DB_PATH', '/opt/dix/aspic/data/aspic.db')
PREVIEW_TTL = int(os.getenv('PREVIEW_TTL_SECONDS', 3600))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))  # 100 MB
TOKEN_LENGTH = int(os.getenv('TOKEN_LENGTH', 8))

# ============================================
# НАСТРОЙКИ ДИСКОВОГО ПРОСТРАНСТВА
# ============================================
# Минимальное свободное место на диске (в байтах), по умолчанию 20 ГБ
MIN_DISK_SPACE = int(os.getenv('MIN_DISK_SPACE', 20 * 1024 * 1024 * 1024))  # 20 GB in bytes

# ============================================
# НАСТРОЙКИ АВТОМАТИЧЕСКОГО УДАЛЕНИЯ
# ============================================
# Количество дней до автоматического удаления по умолчанию (365 дней = 1 год)
DEFAULT_EXPIRE_DAYS = int(os.getenv('DEFAULT_EXPIRE_DAYS', 365))
# Количество часов хранения после последнего обращения по умолчанию (8760 часов = 1 год)
DEFAULT_TTL_HOURS = int(os.getenv('DEFAULT_TTL_HOURS', 8760))


def get_default_expire_date() -> str:
    """
    Возвращает дату удаления по умолчанию: текущая дата + DEFAULT_EXPIRE_DAYS дней.
    Формат: YYYY-MM-DD
    """
    default_date = datetime.now() + timedelta(days=DEFAULT_EXPIRE_DAYS)
    return default_date.strftime("%Y-%m-%d")


def get_default_ttl_hours() -> int:
    """
    Возвращает значение TTL в часах по умолчанию.
    """
    return DEFAULT_TTL_HOURS


def format_ttl_hours(ttl_hours: int) -> str:
    """Форматирует TTL в часах для отображения с правильным склонением."""
    if not ttl_hours or ttl_hours == 0:
        return "Без ограничения"

    if ttl_hours < 24:
        # Часы: 1 час, 2-4 часа, 5-20 часов
        if ttl_hours == 1:
            return "через 1 час"
        elif ttl_hours in (2, 3, 4):
            return f"через {ttl_hours} часа"
        else:
            return f"через {ttl_hours} часов"

    if ttl_hours < 168:  # 7 дней
        days = ttl_hours // 24
        remaining_hours = ttl_hours % 24

        # Дни: 1 день, 2-4 дня, 5-20 дней
        if days == 1:
            days_str = "1 день"
        elif days in (2, 3, 4):
            days_str = f"{days} дня"
        else:
            days_str = f"{days} дней"

        if remaining_hours == 0:
            return f"через {days_str}"
        else:
            # Часы
            if remaining_hours == 1:
                hours_str = "1 час"
            elif remaining_hours in (2, 3, 4):
                hours_str = f"{remaining_hours} часа"
            else:
                hours_str = f"{remaining_hours} часов"
            return f"через {days_str} {hours_str}"

    if ttl_hours < 8760:  # 1 год
        days = ttl_hours // 24
        # Дни
        if days == 1:
            return "через 1 день"
        elif days in (2, 3, 4):
            return f"через {days} дня"
        else:
            return f"через {days} дней"

    # Годы
    years = ttl_hours // 8760
    remaining_days = (ttl_hours % 8760) // 24

    if years == 1:
        years_str = "1 год"
    elif years in (2, 3, 4):
        years_str = f"{years} года"
    else:
        years_str = f"{years} лет"

    if remaining_days == 0:
        return f"через {years_str}"
    else:
        # Дни
        if remaining_days == 1:
            days_str = "1 день"
        elif remaining_days in (2, 3, 4):
            days_str = f"{remaining_days} дня"
        else:
            days_str = f"{remaining_days} дней"
        return f"через {years_str} {days_str}"


# ============================================
# НАСТРОЙКИ ДЛЯ ВЕБХУКОВ
# ============================================
# Таймаут в секундах
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', 5))
# Время кэширования ответов (5 минут)
WEBHOOK_CACHE_TTL = int(os.getenv('WEBHOOK_CACHE_TTL', 300))

# ============================================
# RATE LIMITING ДЛЯ ВЕБХУКОВ
# ============================================
# Лимит вызовов одного вебхука в минуту
WEBHOOK_RATE_LIMIT_PER_URL = int(os.getenv('WEBHOOK_RATE_LIMIT_PER_URL', 10))
# Лимит вызовов вебхуков с одного IP в минуту
WEBHOOK_RATE_LIMIT_PER_IP = int(os.getenv('WEBHOOK_RATE_LIMIT_PER_IP', 30))

# ============================================
# БЕЗОПАСНОСТЬ ВЕБХУКОВ
# ============================================
# Блокировка внутренних/приватных IP (защита от SSRF)
BLOCKED_IP_RANGES = [
    '127.0.0.0/8',  # localhost
    '10.0.0.0/8',  # private networks
    '172.16.0.0/12',  # private networks
    '192.168.0.0/16',  # private networks
    '169.254.0.0/16',  # link-local
    '::1',  # IPv6 localhost
    'fc00::/7',  # IPv6 unique local
    'fe80::/10',  # IPv6 link-local
    '0.0.0.0/8',  # invalid addresses
    '100.64.0.0/10',  # carrier-grade NAT
    '198.18.0.0/15',  # network benchmark
]
# Опасные порты, которые нельзя использовать для вебхуков
BLOCKED_PORTS = {
    22,  # SSH
    23,  # Telnet
    25,  # SMTP
    3306,  # MySQL
    5432,  # PostgreSQL
    6379,  # Redis
    27017,  # MongoDB
    9200,  # Elasticsearch
    11211,  # Memcached
    5984,  # CouchDB
    7000,  # Cassandra
    8086,  # InfluxDB
    9042,  # Cassandra CQL
}

# Разрешённые протоколы (только HTTPS в продакшене)
if DEBUG:
    ALLOWED_WEBHOOK_SCHEMES = ['http', 'https']
else:
    ALLOWED_WEBHOOK_SCHEMES = ['https']  # В продакшене только HTTPS

# Максимальный размер ответа вебхука (1 MB)
WEBHOOK_MAX_RESPONSE_SIZE = int(os.getenv('WEBHOOK_MAX_RESPONSE_SIZE', 1024 * 1024))  # 1 MB по умолчанию

# Максимальное количество одновременных запросов к вебхукам от одного IP
WEBHOOK_MAX_CONCURRENT_PER_IP = int(os.getenv('WEBHOOK_MAX_CONCURRENT_PER_IP', 5))

# Таймауты для разных этапов
WEBHOOK_CONNECT_TIMEOUT = int(os.getenv('WEBHOOK_CONNECT_TIMEOUT', 3))  # Таймаут подключения
WEBHOOK_READ_TIMEOUT = int(os.getenv('WEBHOOK_READ_TIMEOUT', 5))  # Таймаут чтения

# Ограничения на размеры данных
WEBHOOK_MAX_HEADERS_SIZE = int(os.getenv('WEBHOOK_MAX_HEADERS_SIZE', 8192))  # 8 KB

# ============================================
# НАСТРОЙКИ ХРАНЕНИЯ ФАЙЛОВ
# ============================================
# Бэкенд хранения: local (пока только локальный диск)
STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local').lower()

# ============================================
# ОБХОД ЛИМИТА РАЗМЕРА ФАЙЛА
# ============================================
# Секретный ключ для обхода лимита размера файла
UNLIMITED_UPLOAD_SECRET = os.getenv('UNLIMITED_UPLOAD_SECRET', '')
# Максимальный размер файла при использовании секрета (4 ГБ по умолчанию)
MAX_UNLIMITED_FILE_SIZE = int(os.getenv('MAX_UNLIMITED_FILE_SIZE', 4294967296))


# ============================================
# ФУНКЦИИ ДЛЯ ПРОВЕРКИ ДИСКОВОГО ПРОСТРАНСТВА
# ============================================
def check_disk_space(required_bytes: int, path: str = None) -> Tuple[bool, int, str]:
    """
    Проверяет, достаточно ли свободного места на диске.

    Args:
        required_bytes: Требуемое количество байт
        path: Путь для проверки (по умолчанию UPLOAD_DIR)

    Returns:
        Tuple[bool, int, str]: (достаточно ли места, свободно байт, человекочитаемая строка)
    """
    if path is None:
        path = UPLOAD_DIR

    try:
        # Создаем директорию, если её нет
        Path(path).mkdir(parents=True, exist_ok=True)

        # Получаем информацию о диске
        stat = shutil.disk_usage(path)
        free_bytes = stat.free

        # Форматируем для вывода
        free_formatted = format_bytes(free_bytes)
        required_formatted = format_bytes(required_bytes)

        # Проверяем, хватит ли места с учетом минимального порога
        # Нужно, чтобы после загрузки осталось MIN_DISK_SPACE
        will_remain = free_bytes - required_bytes
        enough = will_remain >= MIN_DISK_SPACE

        if not enough:
            print(f"⚠️ Недостаточно места: свободно {free_formatted}, требуется {required_formatted}, минимальный порог {format_bytes(MIN_DISK_SPACE)}")

        return enough, free_bytes, free_formatted

    except Exception as e:
        print(f"⚠️ Ошибка проверки дискового пространства: {e}")
        # В случае ошибки лучше пропустить проверку, чем блокировать загрузку
        return True, 0, "неизвестно"


def format_bytes(bytes_count: int) -> str:
    """Форматирует байты в человекочитаемый вид."""
    if bytes_count < 1024:
        return f"{bytes_count} Б"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} КБ"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} МБ"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.1f} ГБ"


def get_disk_space_warning() -> str:
    """Возвращает предупреждение о минимальном свободном месте."""
    return f"На сервере должно оставаться минимум {format_bytes(MIN_DISK_SPACE)} свободного места"


# ============================================
# ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ПУТИ С ДАТОЙ
# ============================================
def get_dated_upload_path(filename: str = None) -> Path:
    """
    Возвращает путь для сохранения файла с подпапками YYYY/MM.
    Если передан filename, возвращает полный путь с именем файла.
    """
    now = datetime.now()
    year = str(now.year)
    month = f"{now.month:02d}"
    # Базовый путь с годом и месяцем
    dated_path = Path(UPLOAD_DIR) / year / month

    # Создаем директорию, если её нет
    dated_path.mkdir(parents=True, exist_ok=True)

    if filename:
        return dated_path / filename
    return dated_path


# ============================================
# МАППИНГ РАСШИРЕНИЙ -> MIME-ТИПЫ (единый источник истины)
# ============================================
# Используется в main.py для определения MIME-типа при загрузке
EXT_TO_MIME: Dict[str, str] = {
    # Документы
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc': 'application/msword',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls': 'application/vnd.ms-excel',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pdf': 'application/pdf',
    '.txt': 'text/plain',
    '.rtf': 'application/rtf',
    '.odt': 'application/vnd.oasis.opendocument.text',
    '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
    '.odp': 'application/vnd.oasis.opendocument.presentation',
    '.csv': 'text/csv',
    '.md': 'text/markdown',
    '.html': 'text/html', '.htm': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.xml': 'application/xml',
    '.yaml': 'application/x-yaml', '.yml': 'application/x-yaml',
    # Код
    '.py': 'text/x-python',
    '.sql': 'text/x-sql',
    '.java': 'text/x-java-source',
    '.c': 'text/x-c', '.h': 'text/x-c',
    '.cpp': 'text/x-c++', '.hpp': 'text/x-c++', '.cc': 'text/x-c++',
    '.php': 'text/x-php',
    '.rb': 'text/x-ruby',
    '.go': 'text/x-go',
    '.rs': 'text/x-rust',
    '.swift': 'text/x-swift',
    '.ts': 'application/typescript',
    '.sh': 'application/x-sh', '.bash': 'application/x-bash',
    '.pl': 'application/x-perl',
    # Изображения
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.svg': 'image/svg+xml', '.svgz': 'image/svg+xml',
    '.bmp': 'image/bmp',
    '.tiff': 'image/tiff', '.tif': 'image/tiff',
    '.ico': 'image/x-icon',
    '.heic': 'image/heic', '.heif': 'image/heif',
    '.avif': 'image/avif',
    # Видео
    '.mp4': 'video/mp4', '.m4v': 'video/mp4',
    '.webm': 'video/webm',
    '.ogg': 'video/ogg', '.ogv': 'video/ogg',
    '.mov': 'video/quicktime',
    '.avi': 'video/x-msvideo',
    '.mkv': 'video/x-matroska',
    '.mpeg': 'video/mpeg', '.mpg': 'video/mpeg', '.mpe': 'video/mpeg',
    '.3gp': 'video/3gpp', '.3g2': 'video/3gpp',
    '.wmv': 'video/x-ms-wmv',
    '.flv': 'video/x-flv',
    # Аудио
    '.mp3': 'audio/mpeg',
    '.ogg': 'audio/ogg',
    '.wav': 'audio/wav',
    '.webm': 'audio/webm',
    '.aac': 'audio/aac',
    '.flac': 'audio/flac',
    '.m4a': 'audio/mp4', '.mp4': 'audio/mp4',
    '.midi': 'audio/x-midi', '.mid': 'audio/x-midi',
    # Архивы
    '.zip': 'application/zip',
    '.rar': 'application/x-rar-compressed',
    '.7z': 'application/x-7z-compressed',
    '.tar': 'application/x-tar',
    '.gz': 'application/gzip', '.tgz': 'application/gzip',
    '.bz2': 'application/x-bzip2',
    '.xz': 'application/x-xz',
    '.zst': 'application/zstd',
    '.br': 'application/x-brotli',
    # Электронные книги
    '.epub': 'application/epub+zip',
    '.mobi': 'application/x-mobipocket-ebook',
    '.azw': 'application/vnd.amazon.ebook', '.azw3': 'application/vnd.amazon.ebook',
    '.fb2': 'application/x-fictionbook+xml',
    # Чертежи и 3D
    '.dwg': 'application/x-dwg',
    '.dxf': 'application/x-dxf',
    '.stl': 'model/stl',
    '.step': 'application/x-step', '.stp': 'application/x-step',
    '.obj': 'model/obj',
    '.3mf': 'model/3mf',
    # Другое
    '.bin': 'application/octet-stream',
}

# Маппинг для предпросмотра в браузере (только поддерживаемые форматы)
# Используется в main.py для эндпоинта /preview/{filename}
# И может быть экспортирован в frontend через /api/mime-map
PREVIEW_MIME_MAP: Dict[str, str] = {
    # Изображения
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
    '.bmp': 'image/bmp', '.tiff': 'image/tiff', '.tif': 'image/tiff',
    '.ico': 'image/x-icon', '.heic': 'image/heic', '.avif': 'image/avif',
    # Видео
    '.mp4': 'video/mp4', '.webm': 'video/webm', '.ogg': 'video/ogg', '.ogv': 'video/ogg',
    '.mov': 'video/quicktime', '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska',
    # Аудио
    '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.ogg': 'audio/ogg',
    '.aac': 'audio/aac', '.flac': 'audio/flac', '.m4a': 'audio/mp4',
    # Документы (только те, что браузер может отобразить)
    '.pdf': 'application/pdf',
    '.txt': 'text/plain', '.html': 'text/html', '.htm': 'text/html',
    '.css': 'text/css', '.js': 'application/javascript',
    '.json': 'application/json', '.xml': 'application/xml',
    '.md': 'text/markdown', '.csv': 'text/csv', '.rtf': 'application/rtf',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.ppt': 'application/vnd.ms-powerpoint',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    # Архивы (только для скачивания, без предпросмотра)
    '.zip': 'application/zip', '.rar': 'application/x-rar-compressed',
    '.7z': 'application/x-7z-compressed', '.tar': 'application/x-tar',
    '.gz': 'application/gzip', '.bz2': 'application/x-bzip2',
    # Электронные книги
    '.epub': 'application/epub+zip', '.mobi': 'application/x-mobipocket-ebook',
    '.fb2': 'application/x-fictionbook+xml',
}

RATE_LIMIT_UPLOAD = os.getenv('RATE_LIMIT_UPLOAD', '5/minute')
RATE_LIMIT_COMMENT = os.getenv('RATE_LIMIT_COMMENT', '3/minute')
RATE_LIMIT_DELETE = os.getenv('RATE_LIMIT_DELETE', '2/minute')


# ============================================
# ДИНАМИЧЕСКИЕ СООБЩЕНИЯ
# ============================================
def get_file_size_limit_text(max_size: int = None) -> str:
    """Возвращает текст с ограничением по размеру файла (автоматический выбор единиц измерения)."""
    size = max_size if max_size is not None else MAX_FILE_SIZE

    # Определяем подходящую единицу измерения
    units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
    unit_index = 0
    temp_size = size

    while temp_size >= 1024 and unit_index < len(units) - 1:
        temp_size /= 1024
        unit_index += 1

    # Форматируем с нужной точностью
    if unit_index == 0:  # Байты
        return f"{int(temp_size)} {units[unit_index]}"
    elif temp_size < 10:  # Для маленьких чисел показываем с десятыми
        return f"{temp_size:.1f} {units[unit_index]}"
    elif temp_size < 100:  # Для средних чисел - с одной десятой или целое
        if temp_size - int(temp_size) < 0.1:
            return f"{int(temp_size)} {units[unit_index]}"
        else:
            return f"{temp_size:.1f} {units[unit_index]}"
    else:  # Для больших чисел - целое
        return f"{int(temp_size)} {units[unit_index]}"


def get_upload_hint_text(max_size: int = None) -> str:
    """Возвращает полный текст подсказки для загрузки."""
    size_text = get_file_size_limit_text(max_size)
    return f"Поддерживаются любые файлы до {size_text}"


def get_not_found_message() -> str:
    """Возвращает сообщение о ненайденном файле."""
    return "Файл не найден или был удален"


def get_api_only_message() -> str:
    """Возвращает сообщение для режима API-only."""
    return "Веб-интерфейс ЗАГРУЗКИ ФАЙЛОВ отключен."
