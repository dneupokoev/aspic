# 📦 ASPIC — A Simple Public Image/File Cloud

**ASPIC** — это минималистичный файловый хостинг с возможностью комментирования и удаления файлов через капчу.  
Никакой регистрации, никаких владельцев, никаких сроков хранения.

## ✨ Возможности

- ✅ Загрузка файлов через **drag-and-drop**, **выбор файла** или **вставку из буфера** (Ctrl+V)
- ✅ **Редактирование текста** перед загрузкой при вставке из буфера обмена
- ✅ Поддержка **всех популярных форматов**: изображения, видео, аудио, документы, архивы, код
- ✅ Получение **вечной ссылки** на файл
- ✅ **Предпросмотр** изображений, PDF, видео, аудио и текста прямо в браузере
- ✅ **Комментарии** к файлам с автоматическим сохранением имени автора
- ✅ **Удаление файлов** с подтверждением через капчу и сохранением причины
- ✅ **Защита паролем** — возможность установить пароль для удаления файла при загрузке
- ✅ **Webhook URL** — возможность указать URL для вызова при доступе к файлу
- ✅ **Две ссылки** на файл: на страницу просмотра и прямую ссылку для встраивания
- ✅ **Статистика**: отдельные счетчики просмотров и скачиваний с датами последних действий
- ✅ **Защита от накрутки**: уникальные просмотры с одного IP раз в час
- ✅ **Rate limiting** для всех действий (загрузка, комментарии, удаление)
- ✅ **Soft delete**: файлы помечаются удаленными, но физически удаляются отдельным скриптом
- ✅ **Адаптивный дизайн** для мобильных устройств
- ✅ **Темная тема** (автоматически подстраивается под систему)
- ✅ Полная изоляция: файлы хранятся на диске, метаданные в SQLite
- ✅ Гибкая настройка через `.env`
- ✅ Готов к запуску в **Docker**

## 📋 Примеры использования

### Загрузка файла
1. Перетащите файл в область загрузки
2. Или нажмите «Выбрать файл»
3. Или скопируйте изображение/текст и нажмите «Вставить из буфера» (Ctrl+V)
4. При вставке текста вы можете отредактировать его перед созданием ссылки
5. **Опционально**: укажите Webhook URL для вызова при доступе к файлу
6. **Опционально**: установите пароль для защиты удаления файла
7. Нажмите «Создать ссылку»

### Просмотр файла
- Откройте ссылку на файл
- Просматривайте содержимое прямо в браузере
- Оставляйте комментарии
- Скачивайте файл при необходимости
- Копируйте ссылку на файл или прямую ссылку для встраивания

### Удаление файла
- Откройте страницу файла
- Нажмите «Удалить»
- Введите капчу (если файл защищен паролем, потребуется и его ввод)
- Укажите причину удаления
- Подтвердите удаление

## 🛡️ Безопасность и ограничения

- **Rate limiting**: не более X загрузок, X комментариев и X удалений в минуту с одного IP
- **Капча**: обязательна для удаления файлов
- **Парольная защита**: опциональный пароль для удаления (от 4 до 16 символов)
- **Защита от накрутки**: просмотры с одного IP учитываются не чаще раза в час
- **Валидация MIME-типов**: проверка по содержимому, а не по расширению
- **Изоляция файлов**: пути с датами (YYYY/MM) для предотвращения переполнения директории

## 🛠 Технологии

- **Python 3.12**+
- **FastAPI** — современный асинхронный фреймворк
- **SQLite** (с WAL-режимом) — легковесная база данных
- **aiosqlite** — асинхронная работа с SQLite
- **Jinja2** — шаблонизатор
- **SlowAPI** — rate limiting для защиты от злоупотреблений
- **python-magic** — проверка MIME-типов по содержимому
- **Pillow** — получение информации об изображениях
- **Aiofiles** — асинхронная работа с файлами
- **Uvicorn** — ASGI-сервер

## 📁 Структура проекта

```
aspic/
├── app/
│   ├── main.py           # основной код приложения
│   ├── database.py       # работа с SQLite (aiosqlite)
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

Пример `.env`:

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

# Ограничения (104857600 = 100 MB)
MAX_FILE_SIZE=104857600
TOKEN_LENGTH=8

# ВСЕ поддерживаемые MIME-типы (изображения, видео, аудио, документы, архивы, код)
ALLOWED_MIMES=image/jpeg,image/jpg,image/png,image/gif,image/webp,image/svg+xml,image/bmp,image/tiff,image/x-icon,image/heic,image/avif,video/mp4,video/webm,video/ogg,video/quicktime,video/x-msvideo,video/x-matroska,video/mpeg,video/3gpp,audio/mpeg,audio/ogg,audio/wav,audio/aac,audio/flac,audio/mp4,audio/x-midi,application/pdf,text/plain,text/html,text/css,text/javascript,text/markdown,text/csv,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/rtf,application/json,application/xml,application/x-yaml,text/x-python,text/x-sql,application/zip,application/x-zip-compressed,application/x-rar-compressed,application/x-7z-compressed,application/x-tar,application/gzip

# Rate limiting
RATE_LIMIT_UPLOAD=5/minute
RATE_LIMIT_COMMENT=3/minute
RATE_LIMIT_DELETE=2/minute

# Капча
CAPTCHA_TTL_SECONDS=300
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

Пример конфигурации для Nginx с HTTPS:

```nginx
# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name aspic.example.com;
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name aspic.example.com;
    
    # SSL-сертификаты (пример для Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/aspic.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/aspic.example.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Максимальный размер загружаемого файла
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
        
        # ВАЖНО: убираем заголовок Content-Disposition,
        # чтобы текстовые файлы открывались в браузере, а не скачивались
        proxy_hide_header Content-Disposition;
        
        # Увеличиваем таймауты для больших файлов
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_read_timeout 3600s;
    }
    
    # Если хотите, чтобы статику раздавал Nginx (быстрее)
    location /static/ {
        alias /opt/dix/aspic/app/static/;
        expires 30d;
        access_log off;
    }
}
```

**Важные моменты:**
- `proxy_hide_header Content-Disposition;` — позволяет текстовым файлам открываться в браузере
- `client_max_body_size 500M;` — максимальный размер загружаемого файла (должен соответствовать `MAX_FILE_SIZE` в `.env`)
- Таймауты увеличены для поддержки больших файлов

## 📡 API

| Метод | Эндпоинт | Описание |
|-------|----------|----------|
| `POST` | `/api/upload` | Загрузить файл (без предпросмотра) |
| `POST` | `/api/preview` | Загрузить файл для предпросмотра |
| `POST` | `/api/confirm-upload` | Подтвердить загрузку (создать постоянную ссылку) |
| `GET` | `/v/{token}` | Страница просмотра файла с комментариями |
| `GET` | `/s/{token}` | Прямая ссылка на файл (для встраивания) |
| `GET` | `/d/{token}` | Скачать файл |
| `GET` | `/api/file/{token}` | Получить информацию о файле в JSON |
| `GET` | `/api/comments/{token}` | Получить комментарии к файлу |
| `GET` | `/api/captcha/{token}` | Получить капчу для удаления |
| `POST` | `/v/{token}/comment` | Добавить комментарий |
| `POST` | `/v/{token}/delete` | Удалить файл (с капчей и опциональным паролем) |

## 🧹 Очистка удаленных файлов

Файлы помечаются как удаленные, но физически не удаляются с диска. Для физического удаления запустите:

```bash
python app/cleanup.py
```

Можно добавить в cron для автоматической очистки:

```bash
# Очистка каждый день в 3 часа ночи
0 3 * * * cd /opt/dix/aspic && /opt/dix/aspic/.venv/bin/python app/cleanup.py >> /var/log/aspic-cleanup.log 2>&1
```

## 📝 Лицензия

**ASPIC** — файлы живут «вечно», пока кто-то не нажмёт «Удалить»