import os
import uuid
import secrets
import time
import shutil
import hashlib
import random
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

# Импорты из ваших модулей
from app.database import (
    init_db, save_file_metadata, get_file_metadata,
    add_comment, get_comments, mark_file_as_deleted,
    get_deleted_files, permanently_delete_file,
    increment_view_count, increment_download_count
)
from app.captcha import captcha_store
from app.config import (
    DEBUG, HOST, PORT, UPLOAD_DIR, PREVIEW_DIR, DB_PATH,
    PREVIEW_TTL, MAX_FILE_SIZE, TOKEN_LENGTH, ALLOWED_MIMES,
    RATE_LIMIT_UPLOAD, RATE_LIMIT_COMMENT, RATE_LIMIT_DELETE,
    get_upload_hint_text, get_not_found_message, get_file_size_limit_text,
    get_allowed_formats_text, get_dated_upload_path
)

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
# LIFESPAN
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db(DB_PATH)
    print(f"✅ ASPIC запущен на порту {PORT}")
    print(f"📁 Постоянное хранилище: {UPLOAD_DIR}")
    print(f"📁 Временное хранилище: {PREVIEW_DIR}")
    print(f"💾 База данных: {DB_PATH}")
    print(f"📊 Поддерживаемые форматы: {len(ALLOWED_MIMES)} типов")

    yield

    # Shutdown
    print("👋 ASPIC остановлен")


# ============================================
# ИНИЦИАЛИЗАЦИЯ FASTAPI
# ============================================
app = FastAPI(
    debug=DEBUG,
    title="ASPIC",
    description="A Simple Public Image/File Cloud — минималистичный файловый хостинг с комментариями",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url="/openapi.json"
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


# ============================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================
@app.get("/", response_class=HTMLResponse)
async def index(request: Request, error: str = None):
    user_id = generate_user_id(request)

    error_message = None
    if error == "not_found":
        error_message = get_not_found_message()
    elif error == "deleted":
        error_message = "Файл успешно удален"

    response = templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "max_file_size": MAX_FILE_SIZE,
            "allowed_mimes": ALLOWED_MIMES,
            "upload_hint": get_upload_hint_text(),
            "user_id": user_id,
            "error_message": error_message,
            "format_file_size": format_file_size,
            "get_file_icon": get_file_icon
        }
    )

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
@app.get("/v/{token}", response_class=HTMLResponse)
async def view_file(request: Request, token: str):
    """Страница с предпросмотром и информацией о файле."""
    file_info = await get_file_metadata(token)
    if not file_info:
        return RedirectResponse(url=f"/?error=not_found", status_code=303)

    # Увеличиваем счетчик просмотров (с защитой от накрутки)
    client_ip = request.client.host
    if can_increment_view(token, client_ip):
        await increment_view_count(token)
        print(f"👁️ Просмотр для {token} от IP {client_ip}")

    # Получаем дополнительную информацию о файле
    file_path = Path(file_info['file_path'])
    extra_info = {}

    if file_info['mime_type'].startswith('image/'):
        extra_info['image'] = await get_image_info(file_path)

    comments = await get_comments(token)
    captcha = captcha_store.generate(token, client_ip)

    user_id = generate_user_id(request)

    # Ссылка на эту же страницу для копирования
    page_url = f"{request.url.scheme}://{request.url.netloc}/v/{token}"

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
            "get_file_type_name": get_file_type_name
        }
    )


# ============================================
# ПРЕДПРОСМОТР ФАЙЛА (ПРЯМОЙ ДОСТУП)
# ============================================
@app.get("/s/{token}")
async def preview_file(token: str):
    """Отдает файл для предпросмотра (НЕ увеличивает просмотры)."""
    file_info = await get_file_metadata(token)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    file_path = Path(file_info['file_path'])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=file_path,
        media_type=file_info['mime_type'],
        filename=file_info['filename'],
        headers={"Content-Disposition": "inline"}
    )


# ============================================
# СКАЧИВАНИЕ ФАЙЛА
# ============================================
@app.get("/d/{token}")
async def download_file(token: str):
    """Скачивание файла с увеличением счетчика скачиваний."""
    file_info = await get_file_metadata(token)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    # Увеличиваем счетчик скачиваний
    await increment_download_count(token)

    file_path = Path(file_info['file_path'])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден на диске")

    return FileResponse(
        path=file_path,
        filename=file_info['filename'],
        media_type='application/octet-stream'
    )


# ============================================
# API ДЛЯ ФАЙЛОВ
# ============================================
@app.get("/api/file/{token}")
async def get_file_info(token: str):
    file_info = await get_file_metadata(token)
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
        "page_url": f"/v/{token}",
        "preview_url": f"/s/{token}",
        "download_url": f"/d/{token}"
    }


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
    try:
        file_data = await file.read()
        print(f"📥 Загружен файл: {file.filename}, размер: {len(file_data)} байт")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения файла: {e}")

    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. {get_file_size_limit_text()}"
        )

    # ОПРЕДЕЛЕНИЕ MIME-ТИПА
    mime_type = "application/octet-stream"

    if file.filename:
        ext = Path(file.filename).suffix.lower()

        # Таблица соответствия расширений MIME-типам
        ext_to_mime = {
            # Документы
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pdf': 'application/pdf',
            '.txt': 'text/plain',

            # Изображения
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',

            # Видео
            '.mp4': 'video/mp4',
            '.webm': 'video/webm',

            # Аудио
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',

            # Архивы
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed',
        }

        if ext in ext_to_mime:
            mime_type = ext_to_mime[ext]
            print(f"🔍 MIME-тип по расширению: {mime_type}")

    # Проверка в ALLOWED_MIMES из .env
    if mime_type not in ALLOWED_MIMES:
        print(f"❌ MIME-тип {mime_type} не разрешен")
        raise HTTPException(
            status_code=400,
            detail=f"Тип файла не разрешен. Разрешены: {get_allowed_formats_text()}"
        )

    preview_id = str(uuid.uuid4())
    filename = file.filename or "file"
    ext = Path(filename).suffix
    temp_filename = f"{preview_id}{ext}"
    temp_path = Path(PREVIEW_DIR) / temp_filename

    try:
        async with aiofiles.open(temp_path, "wb") as f:
            await f.write(file_data)
        print(f"💾 Временный файл сохранен: {temp_path}")
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
    mime_map = {
        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
        '.gif': 'image/gif', '.webp': 'image/webp', '.svg': 'image/svg+xml',
        '.mp4': 'video/mp4', '.webm': 'video/webm',
        '.mp3': 'audio/mpeg', '.wav': 'audio/wav',
        '.pdf': 'application/pdf',
        '.txt': 'text/plain',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.zip': 'application/zip',
    }

    media_type = mime_map.get(ext, 'application/octet-stream')
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": "inline"}
    )


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
    text_content = data.get("text_content")  # редактируемый текст

    if not preview_id:
        raise HTTPException(status_code=400, detail="preview_id обязателен")

    preview_files = list(Path(PREVIEW_DIR).glob(f"{preview_id}.*"))
    if not preview_files:
        raise HTTPException(status_code=404, detail="Временный файл не найден")

    temp_path = preview_files[0]
    token = generate_token()
    ext = temp_path.suffix
    permanent_filename = f"{token}{ext}"

    # ИСПРАВЛЕНО: используем путь с датой
    permanent_path = get_dated_upload_path(permanent_filename)

    try:
        # ✅ Если передан редактируемый текст - записываем его вместо файла
        if text_content is not None and mime_type.startswith('text/'):
            file_content = text_content.encode('utf-8')
            async with aiofiles.open(str(permanent_path), 'wb') as f:
                await f.write(file_content)
            # Обновляем размер файла
            size = len(file_content)
            print(f"✅ Файл создан из редактированного текста: {permanent_path}")
        else:
            # ✅ Обычное перемещение файла
            shutil.move(str(temp_path), str(permanent_path))
            print(f"✅ Файл перемещен: {temp_path} -> {permanent_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении файла: {e}")

    try:
        await save_file_metadata(
            token=token,
            filename=filename,
            mime_type=mime_type,
            size=size,  # ✅ Размер обновлён если текст редактировался
            file_path=str(permanent_path)
        )
        print(f"💾 Метаданные сохранены для токена: {token}")
    except Exception as e:
        if permanent_path.exists():
            permanent_path.unlink()
        raise HTTPException(status_code=500, detail=f"Ошибка при сохранении метаданных: {e}")

    background_tasks.add_task(cleanup_old_previews)

    return {
        "status": "success",
        "token": token,
        "file_url": f"/v/{token}",
        "preview_url": f"/s/{token}",
        "download_url": f"/d/{token}"
    }


# ============================================
# СТАРЫЙ API (ДЛЯ СОВМЕСТИМОСТИ)
# ============================================
@app.post("/api/upload")
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_file_api(
        request: Request,
        file: UploadFile = File(...)
):
    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой")

    try:
        mime_type = magic.from_buffer(file_data, mime=True)

        if file.filename:
            if file.filename.endswith('.docx') and mime_type == 'application/zip':
                mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif file.filename.endswith('.doc') and mime_type == 'application/zip':
                mime_type = 'application/msword'
    except:
        mime_type = "application/octet-stream"

    if mime_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail="Тип файла не разрешен")

    token = generate_token()
    filename = file.filename or "file"
    ext = Path(filename).suffix
    permanent_filename = f"{token}{ext}"

    # ИСПРАВЛЕНО: используем путь с датой
    file_path = get_dated_upload_path(permanent_filename)

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_data)

    await save_file_metadata(
        token=token,
        filename=filename,
        mime_type=mime_type,
        size=len(file_data),
        file_path=str(file_path)
    )

    return {
        "status": "success",
        "token": token,
        "file_url": f"/v/{token}",
        "preview_url": f"/s/{token}",
        "download_url": f"/d/{token}"
    }


# ============================================
# КОММЕНТАРИИ
# ============================================
@app.post("/v/{token}/comment")
@limiter.limit(RATE_LIMIT_COMMENT)
async def add_comment_to_file(
        request: Request,
        token: str,
        author: str = Form(...),
        comment: str = Form(...)
):
    file_info = await get_file_metadata(token)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    if not author or not author.strip():
        author = "ЗЛОБНЫЙ_АНОНИМ"

    await add_comment(token, author.strip(), comment, 'comment')
    return RedirectResponse(url=f"/v/{token}", status_code=303)


# ============================================
# УДАЛЕНИЕ
# ============================================
@app.post("/v/{token}/delete")
@limiter.limit(RATE_LIMIT_DELETE)
async def delete_file(
        request: Request,
        token: str,
        captcha_key: str = Form(...),
        captcha_answer: str = Form(...),
        delete_reason: str = Form(...),
        author: str = Form(...)
):
    client_ip = request.client.host

    if not captcha_store.verify(token, client_ip, captcha_answer):
        raise HTTPException(status_code=400, detail="Неверный ответ капчи")

    file_info = await get_file_metadata(token, include_deleted=True)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")

    if file_info.get('deleted', False):
        raise HTTPException(status_code=400, detail="Файл уже удален")

    if not author or not author.strip():
        author = "ЗЛОБНЫЙ_АНОНИМ"

    if delete_reason and delete_reason.strip():
        await add_comment(token, author.strip(), f"🗑️ Файл помечен как удаленный. Причина: {delete_reason}", 'deletion_reason')

    await mark_file_as_deleted(token, delete_reason)
    return RedirectResponse(url="/?error=deleted", status_code=303)


# ============================================
# API ДЛЯ КОММЕНТАРИЕВ
# ============================================
@app.get("/api/comments/{token}")
async def get_file_comments(token: str):
    file_info = await get_file_metadata(token, include_deleted=True)
    if not file_info:
        raise HTTPException(status_code=404, detail="Файл не найден")
    comments = await get_comments(token)
    return {"comments": comments}


@app.get("/api/captcha/{token}")
async def get_captcha(request: Request, token: str):
    client_ip = request.client.host
    captcha = captcha_store.generate(token, client_ip)
    return captcha


# ============================================
# FAVICON
# ============================================
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
        <rect width="100" height="100" fill="white"/>
        <text x="50" y="80" font-size="80" text-anchor="middle" font-family="Apple Color Emoji, Segoe UI Emoji, Noto Color Emoji, sans-serif">📦</text>
    </svg>'''
    from fastapi.responses import Response
    return Response(content=svg, media_type="image/svg+xml")


# ============================================
# ЗАПУСК
# ============================================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)