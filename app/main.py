import os
import secrets
import shutil
import magic
from pathlib import Path
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .database import init_db, get_db
from .captcha import captcha_store

# ==================== ЗАГРУЗКА .ENV ====================
load_dotenv()

# ==================== КОНФИГ ИЗ .ENV ====================
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 15191))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "/opt/dix/aspic/data/files"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 100 * 1024 * 1024))
TOKEN_LENGTH = int(os.getenv("TOKEN_LENGTH", 8))

ALLOWED_MIMES = os.getenv("ALLOWED_MIMES",
    "image/jpeg,image/png,image/gif,image/webp,application/pdf,video/mp4,video/webm,text/plain,text/markdown"
).split(",")

RATE_LIMIT_UPLOAD = os.getenv("RATE_LIMIT_UPLOAD", "5/minute")
RATE_LIMIT_COMMENT = os.getenv("RATE_LIMIT_COMMENT", "3/minute")
RATE_LIMIT_DELETE = os.getenv("RATE_LIMIT_DELETE", "2/minute")

CAPTCHA_TTL_SECONDS = int(os.getenv("CAPTCHA_TTL_SECONDS", 300))

# ==================== ПРИЛОЖЕНИЕ ====================
app = FastAPI(title="aspic")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ==================== УТИЛИТЫ ====================
def generate_token(length: int = TOKEN_LENGTH) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def validate_mime_type(file_path: Path) -> Optional[str]:
    try:
        mime = magic.from_file(str(file_path), mime=True)
        return mime if mime in ALLOWED_MIMES else None
    except Exception:
        return None

def get_file_preview_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    elif mime_type == "application/pdf":
        return "pdf"
    elif mime_type.startswith("video/"):
        return "video"
    elif mime_type.startswith("audio/"):
        return "audio"
    elif mime_type.startswith("text/"):
        return "text"
    else:
        return "download"

# ==================== ЭНДПОИНТЫ ====================

@app.on_event("startup")
async def startup_event():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

@app.get("/", response_class=HTMLResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def index(request: Request):
    return templates.TemplateResponse("base.html", {
        "request": request,
        "title": "aspic - Загрузка файла"
    })

@app.post("/api/upload")
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_file(request: Request, file: UploadFile = File(...)):
    # ... (код загрузки без изменений, он рабочий) ...
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"Файл слишком большой (макс. {MAX_FILE_SIZE // 1024 // 1024} MB)")
    if size == 0:
        raise HTTPException(status_code=400, detail="Пустой файл")

    token = generate_token()
    now = datetime.now()
    year_month = f"{now.year}/{now.month:02d}"
    storage_dir = UPLOAD_DIR / year_month
    storage_dir.mkdir(parents=True, exist_ok=True)
    filepath = storage_dir / f"{token}_{file.filename}"

    try:
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения: {str(e)}")

    mime_type = validate_mime_type(filepath)
    if not mime_type:
        filepath.unlink()
        raise HTTPException(status_code=400, detail="Недопустимый тип файла")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO files (token, filename, filepath, size, mime_type)
            VALUES (?, ?, ?, ?, ?)
        """, (token, file.filename, str(filepath), size, mime_type))
        conn.commit()

    return JSONResponse({
        "token": token,
        "url": f"/v/{token}",
        "size": size,
        "mime_type": mime_type
    })

@app.get("/v/{token}", response_class=HTMLResponse)
async def view_file(request: Request, token: str):
    # ... (код просмотра без изменений, он рабочий) ...
    client_ip = get_client_ip(request)
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE token = ?", (token,))
        file_row = cursor.fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        if file_row["deleted_comment_id"] is not None:
            return templates.TemplateResponse("view.html", {
                "request": request, "title": "Файл удалён",
                "file": None, "deleted": True, "captcha": None
            })

        cursor.execute("""
            SELECT * FROM comments WHERE file_token = ? AND action_type = 'comment'
            ORDER BY created_at DESC LIMIT 50
        """, (token,))
        comments_rows = cursor.fetchall()
        captcha = captcha_store.generate(token, client_ip)

        created_at = file_row["created_at"]
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            except:
                created_at = datetime.now()

        file_data = {
            "token": file_row["token"], "filename": file_row["filename"],
            "size": file_row["size"], "mime_type": file_row["mime_type"],
            "preview_type": get_file_preview_type(file_row["mime_type"]),
            "created_at": created_at
        }

        comments = []
        for comment in comments_rows:
            comment_dict = dict(comment)
            comment_created = comment_dict["created_at"]
            if isinstance(comment_created, str):
                try:
                    comment_dict["created_at"] = datetime.fromisoformat(comment_created.replace('Z', '+00:00'))
                except:
                    comment_dict["created_at"] = datetime.now()
            comments.append(comment_dict)

    return templates.TemplateResponse("view.html", {
        "request": request, "title": file_row["filename"],
        "file": file_data, "comments": comments,
        "deleted": False, "captcha": captcha
    })


@app.get("/d/{token}")
async def download_file(token: str):
    """Скачивание или просмотр файла."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE token = ?", (token,))
        file_row = cursor.fetchone()

        if not file_row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        if file_row["deleted_comment_id"] is not None:
            raise HTTPException(status_code=410, detail="Файл удалён")

        filepath = Path(file_row["filepath"])
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Файл не найден на диске")

    mime_type = file_row["mime_type"]
    filename = file_row["filename"]

    # Список MIME-типов, которые браузер должен показывать (inline), а не скачивать
    inline_mime_types = [
        "text/plain", "text/markdown", "text/csv",
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "video/mp4", "video/webm",
        "audio/mpeg", "audio/wav", "audio/ogg"
    ]

    # Базовые заголовки безопасности
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'"
    }

    # --- ЭТО КЛЮЧЕВОЕ ИЗМЕНЕНИЕ ---
    # Проверяем, должен ли файл показываться в браузере
    if mime_type in inline_mimes or mime_type.startswith("text/"):
        # Отдаём для просмотра (inline)
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type=mime_type,
            headers=headers
        )
    else:
        # Отдаём для скачивания (attachment)
        headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type=mime_type,
            headers=headers
        )


@app.post("/v/{token}/comment")
@limiter.limit(RATE_LIMIT_COMMENT)
async def add_comment(request: Request, token: str, author_name: str = Form(""), content: str = Form(...)):
    # ... (код без изменений) ...
    client_ip = get_client_ip(request)
    if not content or len(content.strip()) == 0:
        raise HTTPException(status_code=400, detail="Пустой комментарий")
    if len(content) > 2000:
        raise HTTPException(status_code=400, detail="Комментарий слишком длинный")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE token = ?", (token,))
        file_row = cursor.fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        if file_row["deleted_comment_id"] is not None:
            raise HTTPException(status_code=410, detail="Файл удалён")

        cursor.execute("""
            INSERT INTO comments (file_token, action_type, author_name, author_ip, content)
            VALUES (?, 'comment', ?, ?, ?)
        """, (token, author_name.strip() or "Аноним", client_ip, content.strip()))
        conn.commit()
    return JSONResponse({"status": "ok"})


@app.post("/v/{token}/delete")
@limiter.limit(RATE_LIMIT_DELETE)
async def delete_file(request: Request, token: str, reason: str = Form(""), captcha: str = Form(...)):
    # ... (код без изменений) ...
    client_ip = get_client_ip(request)
    if not captcha_store.verify(token, client_ip, captcha):
        raise HTTPException(status_code=400, detail="Неверная капча")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM files WHERE token = ?", (token,))
        file_row = cursor.fetchone()
        if not file_row:
            raise HTTPException(status_code=404, detail="Файл не найден")
        if file_row["deleted_comment_id"] is not None:
            raise HTTPException(status_code=410, detail="Файл уже удалён")

        cursor.execute("""
            INSERT INTO comments (file_token, action_type, author_name, author_ip, content)
            VALUES (?, 'deletion', 'Аноним', ?, ?)
        """, (token, client_ip, reason.strip() or "Без причины"))
        deletion_id = cursor.lastrowid
        cursor.execute("UPDATE files SET deleted_comment_id = ? WHERE token = ?", (deletion_id, token))
        conn.commit()
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)