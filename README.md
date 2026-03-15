# 📦 ASPIC — A Simple Public Image/File Cloud

**ASPIC** — это минималистичный файловый хостинг с возможностью внешней авторизации через вебхуки, комментирования и безопасного удаления файлов.  
Никакой регистрации, никаких владельцев, никаких сроков хранения — только файлы и полный контроль над доступом к ним.

## ✨ Возможности

### 📤 Загрузка файлов
- ✅ **Три способа загрузки**: drag-and-drop, выбор файла или вставка из буфера (Ctrl+V)
- ✅ **Редактирование текста** перед созданием ссылки при вставке из буфера
- ✅ Поддержка **всех популярных форматов**: изображения, видео, аудио, документы, архивы, код
- ✅ **Предпросмотр** перед загрузкой с информацией о файле

### 🔗 Ссылки и доступ
- ✅ Получение **вечной ссылки** на файл (живёт, пока кто-то не удалит)
- ✅ **Две ссылки** на файл: страница просмотра и прямая ссылка для встраивания
- ✅ **Предпросмотр** изображений, PDF, видео, аудио и текста прямо в браузере
- ✅ **Статистика**: отдельные счетчики просмотров и скачиваний с датами последних действий
- ✅ **Защита от накрутки**: уникальные просмотры с одного IP раз в час

### 🔐 Внешняя авторизация через Webhook
- ✅ Возможность указать **URL внешнего API** для проверки доступа к файлу
- ✅ При открытии файла ASPIC передаёт **все параметры запроса** в вебхук
- ✅ Вебхук должен вернуть `{"allowed": "1"}` или `{"allowed": "0"}`
- ✅ **Кэширование ответов** (5 минут) для одинаковых параметров
- ✅ **Rate limiting**: защита от злоупотреблений на уровне IP и URL вебхука
- ✅ **Таймауты**: на подключение (3с), чтение (5с) и общий (5с)
- ✅ **SSRF защита**: блокировка внутренних IP и локальных адресов
- ✅ **Ограничение размера ответа**: максимум 1 МБ
- ✅ **Отключены редиректы** для предотвращения использования как прокси

### 💬 Комментарии и взаимодействие
- ✅ **Комментарии** к файлам с автоматическим сохранением имени автора
- ✅ **Удаление файлов** с подтверждением через капчу и указанием причины
- ✅ **Защита паролем** — возможность установить пароль для удаления файла при загрузке
- ✅ При удалении комментарий с причиной сохраняется в истории

### 🛡️ Безопасность
- ✅ **Rate limiting** для всех действий (загрузка, комментарии, удаление)
- ✅ **Капча**: обязательна для удаления файлов (защита от ботов)
- ✅ **Парольная защита**: опциональный пароль для удаления (от 4 до 16 символов)
- ✅ **Валидация MIME-типов**: проверка по содержимому, а не по расширению
- ✅ **Soft delete**: файлы помечаются удаленными, но физически удаляются отдельным скриптом
- ✅ **Изоляция файлов**: автоматическая структура папок по датам (YYYY/MM/DD)
- ✅ **Защита от Path Traversal**: проверка имен файлов при загрузке

### 🎨 Интерфейс
- ✅ **Адаптивный дизайн** для мобильных устройств
- ✅ **Темная тема** (автоматически подстраивается под систему)
- ✅ **Валидация форм** в реальном времени с подсветкой ошибок
- ✅ **Информационные попапы** с пояснениями для всех полей
- ✅ **Копирование ссылок** одним кликом с обратной связью

### 🛠 Технические особенности
- ✅ Полная изоляция: файлы хранятся на диске, метаданные в SQLite
- ✅ **WAL-режим** SQLite для лучшей производительности при конкурентном доступе
- ✅ **Фоновые задачи** для очистки временных файлов
- ✅ Гибкая настройка через `.env`
- ✅ Готов к запуску в **Docker**
- ✅ **Cleanup-скрипт** для физического удаления помеченных файлов

## 📋 Примеры использования

### Простой файл (без ограничений)
1. Перетащите файл в область загрузки
2. Нажмите «Создать ссылку»
3. Поделитесь ссылкой — файл доступен всем

### Файл с защитой через внешний API
1. Загрузите файл
2. В поле «Webhook URL» укажите URL вашего API: `https://api.example.com/check-access`
3. Создайте ссылку
4. Поделитесь ссылкой с параметрами: `https://aspic.example.com/view/abc123?order_id=INV-2025-042&user_id=789`
5. ASPIC вызовет ваш API с параметрами: `https://api.example.com/check-access?token=abc123&order_id=INV-2025-042&user_id=789&client_ip=1.2.3.4`
6. Ваш API возвращает `{"allowed": "1"}` или `{"allowed": "0"}`

### Файл с защитой паролем от удаления
1. Загрузите файл
2. В поле «Пароль для удаления» введите пароль (например, `MySecret123`)
3. Создайте ссылку
4. Теперь для удаления файла потребуется ввести этот пароль

## 🛡️ Безопасность вебхуков (для администраторов)

ASPIC включает многоуровневую защиту от злоупотреблений вебхуками:

| Защита | Описание | Настройка в `.env` |
|--------|----------|-------------------|
| **SSRF защита** | Блокировка внутренних IP (localhost, 10.0.0.0/8, 192.168.0.0/16 и др.) | Встроено, не настраивается |
| **Rate limiting по URL** | Не более X вызовов одного вебхука в минуту | `WEBHOOK_RATE_LIMIT_PER_URL=10` |
| **Rate limiting по IP** | Не более X вызовов вебхуков с одного IP в минуту | `WEBHOOK_RATE_LIMIT_PER_IP=30` |
| **Concurrent limit** | Не более X одновременных запросов с одного IP | `WEBHOOK_MAX_CONCURRENT_PER_IP=5` |
| **Таймауты** | Общий (5с), подключение (3с), чтение (5с) | `WEBHOOK_TIMEOUT=5`, `WEBHOOK_CONNECT_TIMEOUT=3`, `WEBHOOK_READ_TIMEOUT=5` |
| **Размер ответа** | Не более 1 МБ | `WEBHOOK_MAX_RESPONSE_SIZE=1048576` |
| **Кэширование** | Кэш ответов на 5 минут для одинаковых параметров | `WEBHOOK_CACHE_TTL=300` |
| **Протоколы** | Только HTTPS в production, HTTP разрешён в DEBUG | Автоматически |

## 🛠 Технологии

- **Python 3.12+**
- **FastAPI** — современный асинхронный фреймворк
- **SQLite** (с WAL-режимом) — легковесная база данных
- **aiosqlite** — асинхронная работа с SQLite
- **Jinja2** — шаблонизатор
- **SlowAPI** — rate limiting для защиты от злоупотреблений
- **python-magic** — проверка MIME-типов по содержимому
- **Pillow** — получение информации об изображениях
- **httpx** — асинхронные HTTP-запросы к вебхукам
- **Aiofiles** — асинхронная работа с файлами
- **Uvicorn** — ASGI-сервер

## 📁 Структура проекта

```
aspic/
├── app/
│   ├── main.py           # основной код приложения
│   ├── database.py       # работа с SQLite (aiosqlite)
│   ├── webhook.py        # логика вебхуков (безопасность, вызовы, кэширование)
│   ├── config.py         # конфигурация из .env
│   ├── captcha.py        # простая капча
│   ├── cleanup.py        # скрипт для физического удаления файлов
│   ├── static/           # CSS, JS, favicon
│   │   ├── style.css
│   │   └── app.js
│   └── templates/        # HTML-шаблоны
│       ├── index.html     # главная страница (загрузка)
│       └── view.html      # страница просмотра файла
├── data/                 # загруженные файлы и БД
│   ├── files/            # постоянное хранилище (разбито по YYYY/MM)
│   ├── preview/          # временные файлы для предпросмотра
│   └── aspic.db          # SQLite база данных
├── .env                  # конфигурация
├── requirements.txt
└── README.md
```

## ⚙️ Настройка

Пример `.env` с полной конфигурацией:

```env
# Режим отладки
DEBUG=False

# Хост и порт
HOST=0.0.0.0
PORT=15191

# Пути к данным
UPLOAD_DIR=/opt/dix/aspic/data/files
PREVIEW_DIR=/opt/dix/aspic/data/preview
DB_PATH=/opt/dix/aspic/data/aspic.db

# Время жизни временных файлов (1 час)
PREVIEW_TTL_SECONDS=3600

# Ограничения
MAX_FILE_SIZE=104857600  # 100 MB
TOKEN_LENGTH=8

# Поддерживаемые MIME-типы (изображения, видео, аудио, документы, архивы, код)
ALLOWED_MIMES=image/jpeg,image/jpg,image/png,image/gif,image/webp,image/svg+xml,image/bmp,image/tiff,image/x-icon,image/heic,image/avif,video/mp4,video/webm,video/ogg,video/quicktime,video/x-msvideo,video/x-matroska,video/mpeg,video/3gpp,audio/mpeg,audio/ogg,audio/wav,audio/aac,audio/flac,audio/mp4,audio/x-midi,application/pdf,text/plain,text/html,text/css,text/javascript,text/markdown,text/csv,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/rtf,application/json,application/xml,application/x-yaml,text/x-python,text/x-sql,application/zip,application/x-zip-compressed,application/x-rar-compressed,application/x-7z-compressed,application/x-tar,application/gzip

# Rate limiting для пользовательских действий
RATE_LIMIT_UPLOAD=5/minute
RATE_LIMIT_COMMENT=3/minute
RATE_LIMIT_DELETE=2/minute

# Капча
CAPTCHA_TTL_SECONDS=300

# ============================================
# НАСТРОЙКИ ВЕБХУКОВ (безопасность)
# ============================================
# Таймаут вызова вебхука в секундах
WEBHOOK_TIMEOUT=5

# Таймаут подключения к вебхуку
WEBHOOK_CONNECT_TIMEOUT=3

# Таймаут чтения ответа
WEBHOOK_READ_TIMEOUT=5

# Время кэширования ответов (5 минут)
WEBHOOK_CACHE_TTL=300

# Лимит вызовов одного вебхука в минуту
WEBHOOK_RATE_LIMIT_PER_URL=10

# Лимит вызовов вебхуков с одного IP в минуту
WEBHOOK_RATE_LIMIT_PER_IP=30

# Максимальное количество одновременных запросов с одного IP
WEBHOOK_MAX_CONCURRENT_PER_IP=5

# Максимальный размер ответа вебхука (1 MB)
WEBHOOK_MAX_RESPONSE_SIZE=1048576

# Максимальный размер заголовков ответа (8 KB)
WEBHOOK_MAX_HEADERS_SIZE=8192
```

## 🚀 Установка

### Через Docker

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

### Напрямую

```bash
# 1. Клонировать репозиторий
git clone <url>
cd aspic

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Создать папки для данных
mkdir -p data/files data/preview

# 5. Настроить .env (скопировать из примера)
cp .env.example .env
# Отредактировать .env под свои нужды

# 6. Запустить
python -m app.main
```

## 🔧 Nginx конфигурация

```nginx
server {
    listen 80;
    server_name aspic.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name aspic.example.com;
    
    ssl_certificate /etc/letsencrypt/live/aspic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aspic.example.com/privkey.pem;
    
    client_max_body_size 500M;
    
    # Заголовки безопасности
    add_header X-Content-Type-Options "nosniff";
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-XSS-Protection "1; mode=block";
    
    location / {
        proxy_pass http://127.0.0.1:15191;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # ВАЖНО: для открытия текстовых файлов в браузере
        proxy_hide_header Content-Disposition;
        
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;
    }
    
    location /static/ {
        alias /opt/dix/aspic/app/static/;
        expires 30d;
        access_log off;
    }
}
```

## 📡 API

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/api/preview` | Загрузить файл для предпросмотра |
| `POST` | `/api/confirm-upload` | Подтвердить загрузку (создать постоянную ссылку) |
| `GET` | `/view/{token}` | Страница просмотра файла с комментариями |
| `GET` | `/file/{token}` | Прямая ссылка на файл (для встраивания) |
| `GET` | `/download/{token}` | Скачать файл |
| `GET` | `/api/file/{token}` | Получить информацию о файле в JSON |
| `GET` | `/api/comments/{token}` | Получить комментарии к файлу |
| `GET` | `/api/captcha/{token}` | Получить капчу для удаления |
| `POST` | `/view/{token}/comment` | Добавить комментарий |
| `POST` | `/view/{token}/delete` | Удалить файл (с капчей и опциональным паролем) |

## 🧹 Очистка удаленных файлов

```bash
python app/cleanup.py
```

В cron:

```bash
0 3 * * * cd /opt/dix/aspic && /opt/dix/aspic/.venv/bin/python app/cleanup.py >> /var/log/aspic-cleanup.log 2>&1
```

## 📝 Лицензия

**ASPIC** — файлы живут «вечно», пока кто-то не нажмёт «Удалить» (или внешний API не запретит доступ).
