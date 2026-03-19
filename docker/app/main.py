import os
import uuid
import secrets
import time
import shutil
import hashlib
import random
import html
from pathlib import Path
from typing import Optional, List, Dict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import magic
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiofiles

# Импортируем хранилище
from app.storage.factory import get_storage_backend

from app.database import (
    init_db, save_file_metadata, get_file_metadata,
    add_comment, get_comments, mark_file_as_deleted,
    get_deleted_files, permanently_delete_file,
    increment_view_count, increment_download_count,
    update_webhook_url, set_delete_password, verify_delete_password
)
from app.webhook import check_webhook_access
from app.captcha import captcha_store
from app.config import (
    DEBUG, HOST, PORT, UPLOAD_DIR, PREVIEW_DIR, DB_PATH,
    PREVIEW_TTL, MAX_FILE_SIZE, TOKEN_LENGTH,
    RATE_LIMIT_UPLOAD, RATE_LIMIT_COMMENT, RATE_LIMIT_DELETE,
    WEBHOOK_TIMEOUT, WEBHOOK_CACHE_TTL,
    get_upload_hint_text, get_not_found_message, get_file_size_limit_text,
    get_dated_upload_path, get_api_only_message,
    STORAGE_BACKEND, ENABLE_WEB_UI,
    # для обхода лимита размера
    UNLIMITED_UPLOAD_SECRET, MAX_UNLIMITED_FILE_SIZE,
    EXT_TO_MIME, PREVIEW_MIME_MAP
)

# Константы для ограничений длины текста
MAX_COMMENT_LENGTH = 1000
MAX_DELETE_REASON_LENGTH = 200

# Для работы с изображениями
try:
    from PIL import Image

    HAS_PIL = True
    print("✅ PIL (Pillow) установлен - доступна информация об изображениях")
except ImportError:
    HAS_PIL = False
    print("⚠️ PIL (Pillow) не установлен - информация об изображениях будет ограничена")
    Image = None

# Хранилище для отслеживания уникальных просмотров по IP
view_tracker = {}  # {f"{token}:{ip}": timestamp}


def can_increment_view(token: str, ip: str) -> bool:
    """
    Проверяет, можно ли увеличить счетчик просмотров для данного IP.
    Возвращает True, если прошло больше 1 часа с последнего просмотра.
    """
    key = f"{token}:{ip}"
    now = datetime.now()
    if key in view_tracker:
        last_view = view_tracker[key]
        if now - last_view < timedelta(hours=1):
            return False

    view_tracker[key] = now

    # Очистка старых записей
    if random.randint(1, 100) == 1:
        cleanup_old_views()

    return True


def cleanup_old_views():
    """Удаляет записи старше 24 часов."""
    now = datetime.now()
    expired = []
    for key, timestamp in view_tracker.items():
        if now - timestamp > timedelta(hours=24):
            expired.append(key)
    for key in expired:
        del view_tracker[key]


# ============================================
# ПРОВЕРКА ДОСТУПА К БОЛЬШИМ ФАЙЛАМ
# ============================================
def _generate_upload_token(secret: str, timestamp: float, salt: str) -> str:
    """Генерирует хэш-токен для доступа к большим файлам."""
    data = f"{secret}:{timestamp}:{salt}"
    return hashlib.sha256(data.encode()).hexdigest()


def _parse_upload_token(cookie_value: str) -> Optional[tuple]:
    """Парсит куку и возвращает (хэш, таймстамп, соль) или None если формат неверный."""
    try:
        parts = cookie_value.split(':')
        if len(parts) != 3:
            return None
        token_hash, timestamp_str, salt = parts
        timestamp = float(timestamp_str)
        return token_hash, timestamp, salt
    except (ValueError, IndexError):
        return None


def check_unlimited_upload_access(request: Request) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к загрузке больших файлов.

    Проверяет:
    1. Параметр ?upload_secret=XXX в запросе
    2. Куку upload_token с валидным хэшем

    Возвращает True если доступ разрешён, False иначе.
    """
    # Если секрет не настроен - доступ к большим файлам отключён
    if not UNLIMITED_UPLOAD_SECRET:
        return False

    # Проверяем параметр в запросе (первый вход)
    upload_secret = request.query_params.get('upload_secret', '')
    if upload_secret and upload_secret == UNLIMITED_UPLOAD_SECRET:
        return True

    # Проверяем куку (последующие запросы)
    upload_token = request.cookies.get('upload_token', '')
    if not upload_token:
        return False

    parsed = _parse_upload_token(upload_token)
    if not parsed:
        return False

    token_hash, timestamp, salt = parsed

    # Проверяем, что токен не истёк (1 час = 3600 секунд)
    now = time.time()
    if now - timestamp > 3600:
        return False

    # Проверяем хэш
    expected_hash = _generate_upload_token(UNLIMITED_UPLOAD_SECRET, timestamp, salt)
    return secrets.compare_digest(token_hash, expected_hash)


def set_unlimited_upload_cookie(response, timestamp: float, salt: str) -> None:
    """Устанавливает куку с токеном доступа к большим файлам на 1 час."""
    token_hash = _generate_upload_token(UNLIMITED_UPLOAD_SECRET, timestamp, salt)
    cookie_value = f"{token_hash}:{timestamp}:{salt}"
    response.set_cookie(
        key="upload_token",
        value=cookie_value,
        max_age=3600,  # 1 час
        httponly=False,  # Нужно для JS, если потребуется
        samesite="lax",
        secure=not DEBUG  # Только HTTPS в продакшене
    )


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЗАГЛУШКИ 404
# ============================================
async def api_only_404_page(request: Request) -> HTMLResponse:
    """Возвращает стилизованную страницу 404 для режима API-only."""
    return templates.TemplateResponse(
        "404.html",
        {
            "request": request,
            "message": get_api_only_message(),
            "enable_web_ui": ENABLE_WEB_UI
        },
        status_code=404
    )


# ============================================
# ФУНКЦИИ ДЛЯ ЭСКАПИРОВАНИЯ HTML
# ============================================
def escape_html(text: str) -> str:
    """Экранирует HTML-спецсимволы для защиты от XSS."""
    if text is None:
        return ""
    return html.escape(str(text))


# ============================================
# LIFESPAN
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db(DB_PATH)

    # Инициализация хранилища файлов
    global file_storage
    storage_config = {
        'STORAGE_BACKEND': STORAGE_BACKEND,
        'UPLOAD_DIR': UPLOAD_DIR,
    }
    file_storage = get_storage_backend(storage_config)

    web_ui_status = "включен (загрузка и просмотр)" if ENABLE_WEB_UI else "ОТКЛЮЧЕН (доступен только просмотр существующих файлов)"
    print(f"✅ ASPIC запущен на порту {PORT}")
    print(f"📁 Постоянное хранилище: {UPLOAD_DIR}")
    print(f"📁 Временное хранилище: {PREVIEW_DIR}")
    print(f"💾 База данных: {DB_PATH}")
    print(f"📊 Режим: принимаем любые файлы, отображаем поддерживаемые")
    print(f"🔧 Режим DEBUG: {DEBUG}")
    print(f"🌐 Веб-интерфейс: {web_ui_status}")
    print(f"🔗 Webhook timeout: {WEBHOOK_TIMEOUT}s, cache TTL: {WEBHOOK_CACHE_TTL}s")

    yield

    # Shutdown
    print("👋 ASPIC остановлен")


# ============================================
# ИНИЦИАЛИЗАЦИЯ FASTAPI
# ============================================
# Настраиваем документацию в зависимости от режима DEBUG
docs_url = "/docs" if DEBUG else None
redoc_url = "/redoc" if DEBUG else None

app = FastAPI(
    debug=DEBUG,
    title="ASPIC",
    description="A Simple Public Image/File Cloud - минималистичный файловый хостинг с комментариями",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json" if DEBUG else None,
    docs_url=docs_url,
    redoc_url=redoc_url
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Шаблоны и статика
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Создаем необходимые директории
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(PREVIEW_DIR).mkdir(parents=True, exist_ok=True)


# ============================================
# ОБРАБОТЧИКИ ОШИБОК 404
# ============================================
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Обработчик для несуществующих страниц."""
    # Проверяем, является ли запрос API-запросом
    if request.url.path.startswith('/api/'):
        return JSONResponse(
            status_code=404,
            content={"detail": "Ресурс не найден"}
        )

    # Для всех остальных страниц - перенаправляем на главную с сообщением об ошибке
    # Но только если веб-интерфейс включен
    if ENABLE_WEB_UI:
        return RedirectResponse(url="/?error=not_found", status_code=303)
    else:
        # В режиме API-only возвращаем стилизованную 404
        return await api_only_404_page(request)


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================
def generate_token() -> str:
    return secrets.token_urlsafe(TOKEN_LENGTH)[:TOKEN_LENGTH]


async def cleanup_old_previews():
    try:
        now = time.time()
        for item in Path(PREVIEW_DIR).iterdir():
            if item.is_file():
                file_age = now - item.stat().st_mtime
                if file_age > PREVIEW_TTL:
                    try:
                        item.unlink()
                    except Exception as e:
                        print(f"[Cleanup] Ошибка: {e}")
    except Exception as e:
        print(f"[Cleanup] Ошибка очистки: {e}")


def generate_user_id(request: Request) -> str:
    """Генерирует или получает ID пользователя из куки."""
    user_id = request.cookies.get("user_id")
    if not user_id:
        timestamp = str(int(time.time()))
        random_part = ''.join([str(random.randint(0, 9)) for _ in range(8)])
        user_id = f"{timestamp}{random_part}"[:18]
    return user_id


def format_file_size(size: int) -> str:
    """Форматирует размер файла в человекочитаемый вид."""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} ТБ"


def get_file_icon(mime_type: str) -> str:
    """Возвращает иконку для типа файла."""
    if mime_type.startswith('image/'):
        return '🖼️'
    elif mime_type.startswith('video/'):
        return '🎬'
    elif mime_type.startswith('audio/'):
        return '🎵'
    elif mime_type == 'application/pdf':
        return '📑'
    elif mime_type.startswith('text/'):
        return '📝'
    elif 'document' in mime_type or 'word' in mime_type:
        return '📄'
    elif 'spreadsheet' in mime_type or 'excel' in mime_type:
        return '📊'
    elif 'presentation' in mime_type or 'powerpoint' in mime_type:
        return '📽️'
    elif 'zip' in mime_type or 'rar' in mime_type:
        return '🗜️'
    else:
        return '📦'


def get_file_type_name(mime_type: str) -> str:
    """Возвращает человекочитаемое название типа файла."""
    type_map = {
        'image/jpeg': 'JPEG', 'image/jpg': 'JPEG', 'image/png': 'PNG',
        'image/gif': 'GIF', 'image/webp': 'WEBP', 'image/svg+xml': 'SVG',
        'application/pdf': 'PDF', 'text/plain': 'TXT',
        'video/mp4': 'MP4', 'video/webm': 'WEBM',
        'application/msword': 'DOC',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
        'application/vnd.ms-excel': 'XLS',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
        'application/vnd.ms-powerpoint': 'PPT',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
        'application/zip': 'ZIP',
    }
    return type_map.get(mime_type, 'Файл')


async def get_image_info(file_path: Path) -> Optional[Dict]:
    """Получает информацию об изображении."""
    if not HAS_PIL:
        return None
    try:
        with Image.open(file_path) as img:
            width, height = img.size
            format_name = img.format
            return {
                'dimensions': f"{width}×{height}",
                'format': format_name,
                'megapixels': f"{(width * height) / 1_000_000:.1f} Мп"
            }
    except:
        return None


async def verify_file_access(
        token: str,
        request: Request,
        check_view: bool = False
) -> Optional[Dict]:
    """
    Проверяет доступ к файлу с учетом вебхука.
    Передаёт ВСЕ параметры запроса в вебхук.
    Возвращает file_info если доступ разрешен, None если нет.
    Если check_view=True, увеличивает счетчик просмотров при успешном доступе.
    """
    file_info = await get_file_metadata(token)
    if not file_info:
        return None

    # Проверяем доступ через вебхук (передаём весь request)
    webhook_url = file_info.get('webhook_url', '')

    if not await check_webhook_access(webhook_url, request, token):
        if DEBUG:
            print(f"🔒 Webhook access denied for {token} with params {request.query_params}")
        return None

    # Если check_view=True, увеличиваем счетчик просмотров
    client_ip = request.client.host
    if check_view and can_increment_view(token, client_ip):
        await increment_view_count(token)
        print(f"👁️ Просмотр для {token} от IP {client_ip}")

    return file_info


# ============================================
# ГЛАВНАЯ СТРАНИЦА (ЗАГРУЗКА)
# ============================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, error: str = None):
    # Если веб-интерфейс отключен, загрузка недоступна - возвращаем 404
    if not ENABLE_WEB_UI:
        return await api_only_404_page(request)

    user_id = generate_user_id(request)
    error_message = None

    if error == "not_found":
        error_message = get_not_found_message()
    elif error == "deleted":
        error_message = "Файл успешно удален"

    # Проверяем доступ к большим файлам
    has_unlimited = check_unlimited_upload_access(request)
    effective_max_size = MAX_UNLIMITED_FILE_SIZE if has_unlimited else MAX_FILE_SIZE

    response = templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "max_file_size": effective_max_size,
            "upload_hint": get_upload_hint_text(effective_max_size),
            "user_id": user_id,
            "error_message": error_message,
            "format_file_size": format_file_size,
            "get_file_icon": get_file_icon
        }
    )

    # Если пользователь ввёл правильный секрет - устанавливаем куку на 1 час
    upload_secret = request.query_params.get('upload_secret', '')
    if UNLIMITED_UPLOAD_SECRET and upload_secret == UNLIMITED_UPLOAD_SECRET:
        timestamp = time.time()
        salt = secrets.token_urlsafe(16)
        set_unlimited_upload_cookie(response, timestamp, salt)
        print(f"🔓 Unlimited upload cookie set for 1 hour")

    if not request.cookies.get("user_id"):
        response.set_cookie(
            key="user_id",
            value=user_id,
            max_age=31536000,
            httponly=True,
            samesite="lax"
        )

    return response


# ============================================
# СТРАНИЦА ПРОСМОТРА ФАЙЛА
# ============================================
@app.get("/view/{token}", response_class=HTMLResponse)
async def view_file(request: Request, token: str):
    """Страница с предпросмотром и информацией о файле."""
    # Просмотр доступен ВСЕГДА, даже если веб-интерфейс отключен!
    # Не проверяем ENABLE_WEB_UI здесь

    # Проверяем доступ к файлу (и увеличиваем счетчик просмотров)
    file_info = await verify_file_access(token, request, check_view=True)
    if not file_info:
        return RedirectResponse(url="/?error=not_found", status_code=303)

    # Получаем дополнительную информацию о файле
    file_path = Path(file_info['file_path'])
    extra_info = {}

    if file_info['mime_type'].startswith('image/'):
        extra_info['image'] = await get_image_info(file_path)

    comments = await get_comments(token)

    # Экранируем комментарии для защиты от XSS
    for comment in comments:
        comment['author'] = escape_html(comment['author'])
        comment['text'] = escape_html(comment['text'])

    client_ip = request.client.host
    captcha = captcha_store.generate(token, client_ip)

    user_id = generate_user_id(request)

    # Ссылка на эту же страницу для копирования
    page_url = f"{request.url.scheme}://{request.url.netloc}/view/{token}"

    # Получаем строку параметров запроса для передачи в предпросмотр
    query_string = ""
    if request.query_params:
        query_string = f"?{request.query_params}"

    return templates.TemplateResponse(
        "view.html",
        {
            "request": request,
            "file": file_info,
            "extra_info": extra_info,
            "comments": comments,
            "captcha": captcha,
            "page_url": page_url,
            "user_id": user_id,
            "default_author": "ЗЛОБНЫЙ_АНОНИМ",
            "format_file_size": format_file_size,
            "get_file_icon": get_file_icon,
            "get_file_type_name": get_file_type_name,
            "query_string": query_string,
            "max_comment_length": MAX_COMMENT_LENGTH,
            "max_delete_reason_length": MAX_DELETE_REASON_LENGTH
        }
    )


# ============================================
# ПРЕДПРОСМОТР ФАЙЛА (ПРЯМОЙ ДОСТУП)
# ============================================
@app.get("/file/{token}")
async def preview_file(request: Request, token: str):
    """Отдает файл для предпросмотра (НЕ увеличивает просмотры)."""
    # Проверяем доступ к файлу (без увеличения счетчика)
    file_info = await verify_file_access(token, request, check_view=False)
    if not file_info:
        # Если файл не найден или доступ запрещен, отдаем заглушку
        oops_path = Path("app/static/oops_img.jpg")
        if oops_path.exists():
            return FileResponse(
                path=oops_path,
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )
        else:
            raise HTTPException(status_code=404, detail="Файл не найден")

    # Используем абстракцию хранилища - теперь get() возвращает путь как строку
    file_path = await file_storage.get(token, file_info['filename'])
    if not file_path:
        # Если файл не найден в хранилище, отдаем заглушку
        oops_path = Path("app/static/oops_img.jpg")
        if oops_path.exists():
            return FileResponse(
                path=oops_path,
                media_type="image/jpeg",
                headers={"Content-Disposition": "inline"}
            )
        else:
            raise HTTPException(status_code=404, detail="Файл не найден в хранилище")

    return FileResponse(
        path=file_path,  # Теперь это строка-путь
        media_type=file_info['mime_type'],
        filename=file_info['filename'],
        headers={"Content-Disposition": "inline"}
    )


# ============================================
# СКАЧИВАНИЕ ФАЙЛА
# ============================================
@app.get("/download/{token}")
async def download_file(request: Request, token: str):
    """Скачивание файла с увеличением счетчика скачиваний."""
    # Проверяем доступ к файлу (без увеличения просмотров)
    file_info = await verify_file_access(token, request, check_view=False)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Увеличиваем счетчик скачиваний
    await increment_download_count(token)

    # Используем абстракцию хранилища - теперь get() возвращает путь как строку
    file_path = await file_storage.get(token, file_info['filename'])
    if not file_path:
        raise HTTPException(status_code=404, detail="Файл не найден в хранилище")

    return FileResponse(
        path=file_path,  # Теперь это строка-путь
        filename=file_info['filename'],
        media_type='application/octet-stream'
    )


# ============================================
# API ДЛЯ ФАЙЛОВ
# ============================================
@app.get("/api/file/{token}")
async def get_file_info(request: Request, token: str):
    """API для получения информации о файле (с проверкой доступа)."""
    file_info = await verify_file_access(token, request, check_view=False)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    return {
        "token": file_info['token'],
        "filename": file_info['filename'],
        "mime_type": file_info['mime_type'],
        "type_name": get_file_type_name(file_info['mime_type']),
        "size": file_info['size'],
        "size_formatted": format_file_size(file_info['size']),
        "icon": get_file_icon(file_info['mime_type']),
        "upload_date": file_info['upload_date'],
        "views": file_info['views'],
        "downloads": file_info['downloads'],
        "has_webhook": bool(file_info.get('webhook_url')),
        "page_url": f"/view/{token}",
        "preview_url": file_storage.get_public_path(token, file_info['filename']),
        "download_url": f"/download/{token}"
    }


# ============================================
# API ДЛЯ MIME-МАППИНГА (для frontend)
# ============================================
@app.get("/api/mime-map")
async def get_mime_map_api():
    """Возвращает маппинг расширений для предпросмотра (для frontend)."""
    return PREVIEW_MIME_MAP


# ============================================
# ЗАГРУЗКА С ПРЕДПРОСМОТРОМ
# ============================================
@app.post("/api/preview")
@limiter.limit(RATE_LIMIT_UPLOAD)
async def create_preview(
        request: Request,
        file: UploadFile = File(...),
        background_tasks: BackgroundTasks = None
):
    # Проверяем доступ к большим файлам через отдельную функцию
    effective_max_size = MAX_UNLIMITED_FILE_SIZE if check_unlimited_upload_access(request) else MAX_FILE_SIZE

    # Проверяем размер файла ДО чтения в память (если файл сообщает свой размер)
    if file.size is not None and file.size > effective_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. {get_file_size_limit_text(effective_max_size)}"
        )

    try:
        file_data = await file.read()
        print(f"📥 Загружен файл: {file.filename}, размер: {len(file_data)} байт")
    except MemoryError:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно памяти для обработки файла. {get_file_size_limit_text(effective_max_size)}"
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {e}")

    # Дополнительная проверка после чтения (на случай если file.size был None)
    if len(file_data) > effective_max_size:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. {get_file_size_limit_text(effective_max_size)}"
        )

    # Проверка свободного места на диске
    from app.config import check_disk_space, get_disk_space_warning, MIN_DISK_SPACE, format_bytes

    enough_space, free_bytes, free_formatted = check_disk_space(len(file_data))
    if not enough_space:
        error_msg = (f"На сервере недостаточно свободного места. "
                     f"Свободно {free_formatted}, требуется ещё минимум {format_bytes(MIN_DISK_SPACE)} "
                     f"после загрузки. Попробуйте позже или обратитесь к администратору.")
        print(f"❌ {error_msg}")
        raise HTTPException(status_code=507, detail=error_msg)

    print(f"💾 Проверка места: свободно {free_formatted}, требуется {format_bytes(len(file_data))}, порог {format_bytes(MIN_DISK_SPACE)}")

    # ОПРЕДЕЛЕНИЕ MIME-ТИПА с помощью python-magic (по содержимому, а не по расширению)
    mime_type = "application/octet-stream"

    try:
        # Используем python-magic для определения MIME-типа по содержимому
        mime_detected = magic.from_buffer(file_data, mime=True)
        if mime_detected:
            mime_type = mime_detected
            print(f"🔍 MIME-тип по содержимому: {mime_type}")
    except Exception as e:
        print(f"⚠️ Ошибка определения MIME-типа через magic: {e}")
        # Если не удалось определить через magic, пробуем по расширению
        if file.filename:
            ext = Path(file.filename).suffix.lower()
            if ext in EXT_TO_MIME:
                mime_type = EXT_TO_MIME[ext]
                print(f"🔍 MIME-тип по расширению (fallback): {mime_type}")

    # Файлы любых типов будут сохранены, но отображаться будут только поддерживаемые браузером

    preview_id = str(uuid.uuid4())
    filename = file.filename or "file"
    ext = Path(filename).suffix
    temp_filename = f"{preview_id}{ext}"
    temp_path = Path(PREVIEW_DIR) / temp_filename

    try:
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(file_data)
        print(f"💾 Временный файл сохранен: {temp_path}")
    except OSError as e:
        # Ошибка диска (например, нет места)
        if "No space left on device" in str(e):
            raise HTTPException(
                status_code=507,
                detail="На сервере закончилось свободное место. Попробуйте позже."
            )
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения временного файла: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения временного файла: {e}")

    if background_tasks:
        background_tasks.add_task(cleanup_old_previews)

    return {
        "preview_id": preview_id,
        "preview_url": f"/preview/{temp_filename}",
        "filename": filename,
        "mime_type": mime_type,
        "size": len(file_data),
        "size_formatted": format_file_size(len(file_data)),
        "icon": get_file_icon(mime_type),
        "type_name": get_file_type_name(mime_type)
    }


@app.get("/preview/{filename}")
async def get_preview_file(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Некорректное имя файла")

    file_path = Path(PREVIEW_DIR) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл предпросмотра не найден")

    ext = file_path.suffix.lower()
    # Используем PREVIEW_MIME_MAP из config.py (единый источник истины)
    media_type = PREVIEW_MIME_MAP.get(ext, 'application/octet-stream')
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": "inline"}
    )


# ============================================
# ПОДТВЕРЖДЕНИЕ ЗАГРУЗКИ
# ============================================
@app.post("/api/confirm-upload")
@limiter.limit(RATE_LIMIT_UPLOAD)
async def confirm_upload(
        request: Request,
        data: dict,
        background_tasks: BackgroundTasks
):
    preview_id = data.get("preview_id")
    filename = data.get("filename", "file")
    mime_type = data.get("mime_type", "application/octet-stream")
    size = data.get("size", 0)
    text_content = data.get("text_content")
    webhook_url = data.get("webhook_url", "")
    delete_password = data.get("delete_password", "")

    # Валидация полей
    if webhook_url and (len(webhook_url) < 4 or len(webhook_url) > 1024):
        raise HTTPException(status_code=400, detail="webhook_url должен быть от 4 до 1024 символов")

    if delete_password and (len(delete_password) < 4 or len(delete_password) > 16):
        raise HTTPException(status_code=400, detail="delete_password должен быть от 4 до 16 символов")

    if not preview_id:
        raise HTTPException(status_code=400, detail="preview_id обязателен")

    preview_files = list(Path(PREVIEW_DIR).glob(f"{preview_id}.*"))
    if not preview_files:
        raise HTTPException(status_code=404, detail="Временный файл не найден")

    temp_path = preview_files[0]

    # Проверка свободного места на диске перед финальным сохранением
    from app.config import check_disk_space, get_disk_space_warning, MIN_DISK_SPACE, format_bytes

    enough_space, free_bytes, free_formatted = check_disk_space(size)
    if not enough_space:
        error_msg = (f"На сервере недостаточно свободного места. "
                     f"Свободно {free_formatted}, требуется ещё минимум {format_bytes(MIN_DISK_SPACE)} "
                     f"после загрузки. Попробуйте позже или обратитесь к администратору.")
        print(f"❌ {error_msg}")
        # Удаляем временный файл
        try:
            temp_path.unlink()
        except:
            pass
        raise HTTPException(status_code=507, detail=error_msg)

    token = generate_token()
    ext = temp_path.suffix

    # Если MIME-тип не передан или это octet-stream, пробуем определить его заново
    if mime_type == "application/octet-stream" or not mime_type:
        try:
            # Читаем начало файла для определения MIME
            async with aiofiles.open(temp_path, 'rb') as f:
                file_head = await f.read(2048)  # Читаем первые 2KB для определения типа
                mime_detected = magic.from_buffer(file_head, mime=True)
                if mime_detected:
                    mime_type = mime_detected
                    print(f"🔍 MIME-тип при подтверждении: {mime_type}")
        except Exception as e:
            print(f"⚠️ Не удалось определить MIME-тип при подтверждении: {e}")

    # Используем абстракцию хранилища для сохранения
    try:
        if text_content is not None and mime_type.startswith('text/'):
            # Если текст редактировался - сохраняем новое содержимое
            file_content = text_content.encode('utf-8')
            size = len(file_content)
            public_path = await file_storage.save(token, file_content, filename, mime_type)
            print(f"✅ Файл создан из редактированного текста: {public_path}")
        else:
            # Читаем временный файл и сохраняем через абстракцию
            async with aiofiles.open(temp_path, 'rb') as f:
                file_content = await f.read()
            public_path = await file_storage.save(token, file_content, filename, mime_type)
            print(f"✅ Файл сохранен через storage: {public_path}")
    except OSError as e:
        # Ошибка диска (например, нет места)
        if "No space left on device" in str(e):
            raise HTTPException(
                status_code=507,
                detail="На сервере закончилось свободное место. Попробуйте позже."
            )
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {e}")

    try:
        await save_file_metadata(
            token=token,
            filename=filename,
            mime_type=mime_type,
            size=size,
            file_path=public_path,
            webhook_url=webhook_url,
            delete_password=delete_password
        )
        print(f"💾 Метаданные сохранены для токена: {token}")
    except Exception as e:
        # Попытка удалить файл из хранилища при ошибке сохранения метаданных
        try:
            await file_storage.delete(token, filename)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении метаданных: {e}")

    background_tasks.add_task(cleanup_old_previews)

    view_path = f"/view/{token}"
    file_path = file_storage.get_public_path(token, filename)
    download_path = f"/download/{token}"

    print(f"✅ Созданы пути: view={view_path}, file={file_path}, download={download_path}")

    return {
        "status": "success",
        "token": token,
        "file_url": view_path,
        "preview_url": file_path,
        "download_url": download_path,
        "has_webhook": bool(webhook_url)
    }


# ============================================
# КОММЕНТАРИИ
# ============================================
@app.post("/view/{token}/comment")
@limiter.limit(RATE_LIMIT_COMMENT)
async def add_comment_to_file(
        request: Request,
        token: str,
        author: str = Form(...),
        comment: str = Form(...)
):
    file_info = await get_file_metadata(token)
    if not file_info:
        return JSONResponse(
            status_code=404,
            content={"detail": "Файл не найден"}
        )

    if file_info.get('deleted', False):
        return JSONResponse(
            status_code=400,
            content={"detail": "Нельзя комментировать удаленный файл"}
        )

    if not author or not author.strip():
        author = "ЗЛОБНЫЙ_АНОНИМ"

    if not comment or not comment.strip():
        return JSONResponse(
            status_code=400,
            content={"detail": "Комментарий не может быть пустым"}
        )

    # Ограничение длины комментария
    if len(comment) > MAX_COMMENT_LENGTH:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Комментарий не может быть длиннее {MAX_COMMENT_LENGTH} символов"}
        )

    # Экранируем HTML-спецсимволы для защиты от XSS
    safe_author = escape_html(author.strip())
    safe_comment = escape_html(comment.strip())

    await add_comment(token, safe_author, safe_comment, 'comment')

    return JSONResponse(
        status_code=200,
        content={"status": "success"}
    )


# ============================================
# УДАЛЕНИЕ
# ============================================
@app.post("/view/{token}/delete")
@limiter.limit(RATE_LIMIT_DELETE)
async def delete_file(
        request: Request,
        token: str,
        captcha_key: str = Form(...),
        captcha_answer: str = Form(...),
        delete_reason: str = Form(...),
        author: str = Form(...),
        delete_password_input: str = Form(None),
        password_required: str = Form(None)
):
    client_ip = request.client.host
    if not captcha_store.verify(token, client_ip, captcha_answer):
        return JSONResponse(
            status_code=400,
            content={"detail": "Неверный ответ капчи"}
        )

    file_info = await get_file_metadata(token, include_deleted=True)
    if not file_info:
        return JSONResponse(
            status_code=404,
            content={"detail": "Файл не найден"}
        )

    if file_info.get('deleted', False):
        return JSONResponse(
            status_code=400,
            content={"detail": "Файл уже удален"}
        )

    has_password = bool(file_info.get('delete_password'))

    if has_password and not password_required:
        return JSONResponse(
            status_code=400,
            content={"detail": "Требуется ввести пароль для удаления"}
        )

    if has_password:
        if not delete_password_input:
            return JSONResponse(
                status_code=400,
                content={"detail": "Требуется ввести пароль для удаления"}
            )

        if not await verify_delete_password(token, delete_password_input):
            return JSONResponse(
                status_code=400,
                content={"detail": "Неверный пароль для удаления"}
            )

    if not author or not author.strip():
        author = "ЗЛОБНЫЙ_АНОНИМ"

    # Ограничение длины причины удаления
    if delete_reason and len(delete_reason) > MAX_DELETE_REASON_LENGTH:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Причина удаления не может быть длиннее {MAX_DELETE_REASON_LENGTH} символов"}
        )

    if delete_reason and delete_reason.strip():
        # Экранируем HTML-спецсимволы для защиты от XSS
        safe_author = escape_html(author.strip())
        safe_reason = escape_html(delete_reason.strip())
        await add_comment(token, safe_author, f"Файл удален. Причина: {safe_reason}", 'deletion_reason')

    # Soft delete в БД
    await mark_file_as_deleted(token, delete_reason)

    # Используем абстракцию хранилища для удаления файла
    try:
        await file_storage.delete(token, file_info['filename'])
        print(f"🗑️ Файл удален из хранилища: {token}")
    except Exception as e:
        print(f"⚠️ Не удалось удалить файл из хранилища: {e}")
        # Не прерываем процесс, т.к. soft delete в БД уже выполнен

    return JSONResponse(
        status_code=200,
        content={"redirect": "/?error=deleted"}
    )


# ============================================
# API ДЛЯ КОММЕНТАРИЕВ
# ============================================
@app.get("/api/comments/{token}")
async def get_file_comments(token: str):
    file_info = await get_file_metadata(token, include_deleted=True)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    comments = await get_comments(token)

    # Экранируем комментарии для API
    for comment in comments:
        comment['author'] = escape_html(comment['author'])
        comment['text'] = escape_html(comment['text'])

    return {"comments": comments}


@app.get("/api/captcha/{token}")
async def get_captcha(request: Request, token: str):
    client_ip = request.client.host
    captcha = captcha_store.generate(token, client_ip)
    return captcha


# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)