import os
import ipaddress
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ============================================
# КОНФИГУРАЦИЯ ИЗ .ENV
# ============================================
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 15191))
UPLOAD_DIR = os.getenv('UPLOAD_DIR', '/opt/dix/aspic/data/files')
PREVIEW_DIR = os.getenv('PREVIEW_DIR', '/opt/dix/aspic/data/preview')
DB_PATH = os.getenv('DB_PATH', '/opt/dix/aspic/data/aspic.db')
PREVIEW_TTL = int(os.getenv('PREVIEW_TTL_SECONDS', 3600))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 104857600))  # 100 MB
TOKEN_LENGTH = int(os.getenv('TOKEN_LENGTH', 8))

# ============================================
# НАСТРОЙКИ ДЛЯ ВЕБХУКОВ
# ============================================
WEBHOOK_TIMEOUT = int(os.getenv('WEBHOOK_TIMEOUT', 5))  # Таймаут в секундах
WEBHOOK_CACHE_TTL = int(os.getenv('WEBHOOK_CACHE_TTL', 300))  # Время кэширования ответов (5 минут)
WEBHOOK_RATE_LIMIT = os.getenv('WEBHOOK_RATE_LIMIT', '10/minute')  # Лимит вызовов вебхуков

# ============================================
# БЕЗОПАСНОСТЬ ВЕБХУКОВ
# ============================================

# Блокировка внутренних/приватных IP (защита от SSRF)
BLOCKED_IP_RANGES = [
    '127.0.0.0/8',      # localhost
    '10.0.0.0/8',       # private networks
    '172.16.0.0/12',    # private networks
    '192.168.0.0/16',   # private networks
    '169.254.0.0/16',   # link-local
    '::1',              # IPv6 localhost
    'fc00::/7',         # IPv6 unique local
    'fe80::/10',        # IPv6 link-local
    '0.0.0.0/8',        # invalid addresses
    '100.64.0.0/10',    # carrier-grade NAT
    '198.18.0.0/15',    # network benchmark
]

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
WEBHOOK_READ_TIMEOUT = int(os.getenv('WEBHOOK_READ_TIMEOUT', 5))        # Таймаут чтения

# Ограничения на размеры данных
WEBHOOK_MAX_HEADERS_SIZE = int(os.getenv('WEBHOOK_MAX_HEADERS_SIZE', 8192))  # 8 KB

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
# РАСШИРЕННЫЙ СПИСОК ПОДДЕРЖИВАЕМЫХ MIME-ТИПОВ
# ============================================
DEFAULT_MIMES = [
    # Изображения
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
    'image/svg+xml', 'image/bmp', 'image/tiff', 'image/x-icon',
    'image/heic', 'image/heif', 'image/avif',

    # Видео
    'video/mp4', 'video/webm', 'video/ogg', 'video/quicktime',
    'video/x-msvideo', 'video/x-matroska', 'video/mpeg', 'video/3gpp',
    'video/x-ms-wmv', 'video/x-flv',

    # Аудио
    'audio/mpeg', 'audio/ogg', 'audio/wav', 'audio/webm',
    'audio/aac', 'audio/flac', 'audio/mp4', 'audio/x-midi',
    'audio/x-wav', 'audio/x-m4a', 'audio/x-matroska',

    # Документы
    'application/pdf',
    'text/plain', 'text/html', 'text/css', 'text/javascript',
    'text/markdown', 'text/csv', 'text/rtf',
    'application/msword',  # .doc
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/vnd.ms-excel',  # .xls
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
    'application/vnd.ms-powerpoint',  # .ppt
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
    'application/rtf',  # .rtf
    'application/vnd.oasis.opendocument.text',  # .odt
    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
    'application/vnd.oasis.opendocument.presentation',  # .odp

    # Код и данные
    'application/json', 'application/xml', 'application/x-yaml',
    'text/x-python', 'text/x-sql', 'text/x-java-source',
    'text/x-c', 'text/x-c++', 'text/x-php', 'text/x-ruby',
    'text/x-go', 'text/x-rust', 'text/x-swift',
    'application/javascript', 'application/typescript',
    'application/x-sh', 'application/x-bash', 'application/x-perl',

    # Архивы
    'application/zip', 'application/x-zip-compressed',
    'application/x-rar-compressed', 'application/x-7z-compressed',
    'application/x-tar', 'application/gzip', 'application/x-bzip2',
    'application/x-brotli', 'application/x-xz', 'application/zstd',

    # Электронные книги
    'application/epub+zip', 'application/x-mobipocket-ebook',
    'application/vnd.amazon.ebook', 'application/x-fictionbook+xml',

    # Чертежи и 3D
    'application/x-dwg', 'application/x-dxf', 'model/stl',
    'application/x-step', 'model/obj', 'model/3mf',

    # Другое
    'application/octet-stream', 'application/x-www-form-urlencoded',
    'application/x-iso9660-image', 'application/x-cd-image',
    'application/x-msdownload', 'application/x-msi',
]

ALLOWED_MIMES_RAW = os.getenv('ALLOWED_MIMES', ','.join(DEFAULT_MIMES))
ALLOWED_MIMES = [mime.strip() for mime in ALLOWED_MIMES_RAW.split(',')]

RATE_LIMIT_UPLOAD = os.getenv('RATE_LIMIT_UPLOAD', '5/minute')
RATE_LIMIT_COMMENT = os.getenv('RATE_LIMIT_COMMENT', '3/minute')
RATE_LIMIT_DELETE = os.getenv('RATE_LIMIT_DELETE', '2/minute')


# ============================================
# ДИНАМИЧЕСКИЕ СООБЩЕНИЯ
# ============================================

def get_file_size_limit_text() -> str:
    """Возвращает текст с ограничением по размеру файла."""
    size_mb = MAX_FILE_SIZE // 1048576
    return f"До {size_mb} МБ"


def get_allowed_formats_text() -> str:
    """Возвращает текст с поддерживаемыми форматами."""
    format_map = {
        # Изображения
        'image/jpeg': 'JPG', 'image/jpg': 'JPG', 'image/png': 'PNG',
        'image/gif': 'GIF', 'image/webp': 'WEBP', 'image/svg+xml': 'SVG',
        'image/bmp': 'BMP', 'image/tiff': 'TIFF', 'image/x-icon': 'ICO',
        'image/heic': 'HEIC', 'image/heif': 'HEIF', 'image/avif': 'AVIF',

        # Видео
        'video/mp4': 'MP4', 'video/webm': 'WEBM', 'video/ogg': 'OGV',
        'video/quicktime': 'MOV', 'video/x-msvideo': 'AVI',
        'video/x-matroska': 'MKV', 'video/mpeg': 'MPEG',
        'video/3gpp': '3GP', 'video/x-ms-wmv': 'WMV', 'video/x-flv': 'FLV',

        # Аудио
        'audio/mpeg': 'MP3', 'audio/ogg': 'OGG', 'audio/wav': 'WAV',
        'audio/webm': 'WEBM', 'audio/aac': 'AAC', 'audio/flac': 'FLAC',
        'audio/mp4': 'M4A', 'audio/x-midi': 'MIDI',
        'audio/x-wav': 'WAV', 'audio/x-m4a': 'M4A', 'audio/x-matroska': 'MKA',

        # Документы
        'application/pdf': 'PDF', 'text/plain': 'TXT', 'text/html': 'HTML',
        'text/css': 'CSS', 'text/javascript': 'JS', 'text/markdown': 'MD',
        'text/csv': 'CSV', 'text/rtf': 'RTF',
        'application/msword': 'DOC',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
        'application/vnd.ms-excel': 'XLS',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
        'application/vnd.ms-powerpoint': 'PPT',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
        'application/rtf': 'RTF',
        'application/vnd.oasis.opendocument.text': 'ODT',
        'application/vnd.oasis.opendocument.spreadsheet': 'ODS',
        'application/vnd.oasis.opendocument.presentation': 'ODP',

        # Код и данные
        'application/json': 'JSON', 'application/xml': 'XML',
        'application/x-yaml': 'YAML', 'text/x-python': 'PY',
        'text/x-sql': 'SQL', 'text/x-java-source': 'JAVA',
        'text/x-c': 'C', 'text/x-c++': 'CPP', 'text/x-php': 'PHP',
        'text/x-ruby': 'RB', 'text/x-go': 'GO', 'text/x-rust': 'RS',
        'text/x-swift': 'SWIFT', 'application/javascript': 'JS',
        'application/typescript': 'TS', 'application/x-sh': 'SH',
        'application/x-bash': 'BASH', 'application/x-perl': 'PL',

        # Архивы
        'application/zip': 'ZIP', 'application/x-zip-compressed': 'ZIP',
        'application/x-rar-compressed': 'RAR', 'application/x-7z-compressed': '7Z',
        'application/x-tar': 'TAR', 'application/gzip': 'GZ',
        'application/x-bzip2': 'BZ2', 'application/x-brotli': 'BR',
        'application/x-xz': 'XZ', 'application/zstd': 'ZST',

        # Электронные книги
        'application/epub+zip': 'EPUB', 'application/x-mobipocket-ebook': 'MOBI',
        'application/vnd.amazon.ebook': 'AZW', 'application/x-fictionbook+xml': 'FB2',

        # Чертежи и 3D
        'application/x-dwg': 'DWG', 'application/x-dxf': 'DXF',
        'model/stl': 'STL', 'application/x-step': 'STEP',
        'model/obj': 'OBJ', 'model/3mf': '3MF',
    }

    formats = []
    for mime in ALLOWED_MIMES:
        if mime in format_map:
            formats.append(format_map[mime])

    # Убираем дубликаты и сортируем
    unique_formats = sorted(list(set(formats)))
    return ', '.join(unique_formats)


def get_upload_hint_text() -> str:
    """Возвращает полный текст подсказки для загрузки."""
    size_text = get_file_size_limit_text()
    formats_text = get_allowed_formats_text()
    return f"{size_text}, поддерживаются: {formats_text}"


def get_not_found_message() -> str:
    """Возвращает сообщение о ненайденном файле."""
    return "Файл не найден или был удален"