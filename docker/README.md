# 📦 ASPIC — A Simple Private Image/File Cloud

**ASPIC** — это минималистичный файловый хостинг с возможностью комментирования и удаления файлов через капчу.  
Никакой регистрации, никаких владельцев, никаких сроков хранения.

## 🚀 Возможности

- ✅ Загрузка файлов через **drag-and-drop** или по **API**
- ✅ Получение **вечной ссылки** на файл
- ✅ **Предпросмотр** изображений, PDF, видео, аудио и текста
- ✅ **Комментарии** к файлам (без регистрации)
- ✅ **Удаление файлов** с подтверждением через капчу
- ✅ Все действия логируются в единую таблицу `comments`
- ✅ Полная изоляция: файлы хранятся на диске, метаданные в SQLite
- ✅ Гибкая настройка через `.env`
- ✅ Готов к запуску в **Docker**

## 🧱 Технологии

- **Python 3.12** + **FastAPI**
- **SQLite** (с WAL-режимом)
- **Jinja2** — шаблонизатор
- **SlowAPI** — rate limiting
- **python-magic** — проверка MIME-типов по содержимому
- **Aiofiles** — асинхронная работа с файлами
- **Uvicorn** — ASGI-сервер

## 📁 Структура проекта

```
aspic/
├── app/
│   ├── main.py           # основной код приложения
│   ├── database.py       # работа с SQLite
│   ├── captcha.py        # простая капча
│   ├── static/           # CSS, JS
│   └── templates/        # HTML-шаблоны (base.html, view.html)
├── data/                 # загруженные файлы и БД
├── .env                  # конфигурация
├── requirements.txt
└── README.md
```

## ⚙️ Конфигурация (`.env`)

```env
# Режим отладки
DEBUG=False

# Хост и порт
HOST=0.0.0.0
PORT=15191

# Пути к данным
UPLOAD_DIR=/opt/dix/aspic/data/files
DB_PATH=/opt/dix/aspic/data/aspic.db

# Ограничения
MAX_FILE_SIZE=104857600         # 100 MB
TOKEN_LENGTH=8
ALLOWED_MIMES=image/jpeg,image/png,image/gif,image/webp,application/pdf,video/mp4,video/webm,text/plain

# Rate limiting
RATE_LIMIT_UPLOAD=5/minute
RATE_LIMIT_COMMENT=3/minute
RATE_LIMIT_DELETE=2/minute

# Капча
CAPTCHA_TTL_SECONDS=300
```

## 🐳 Запуск через Docker

```bash
# Сборка образа
docker build -t aspic .

# Запуск
docker run -d \
  --name aspic \
  -p 15191:15191 \
  -v $(pwd)/data:/opt/dix/aspic/data \
  aspic
```

Или через `docker-compose`:

```yaml
version: '3.8'

services:
  aspic:
    build: .
    ports:
      - "15191:15191"
    volumes:
      - ./data:/opt/dix/aspic/data
    env_file:
      - .env
    restart: unless-stopped
```

## 🧪 Локальный запуск

```bash
# 1. Клонировать репозиторий
git clone <url>
cd aspic

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать папку для данных
mkdir -p data/files

# 5. Запустить
python -m app.main
```

## 📡 API Endpoints

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/api/upload` | Загрузить файл |
| `GET` | `/v/{token}` | Страница просмотра файла |
| `GET` | `/d/{token}` | Скачать файл |
| `POST` | `/v/{token}/comment` | Добавить комментарий |
| `POST` | `/v/{token}/delete` | Удалить файл (с капчей) |
