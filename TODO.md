# TODO: Планы развития ASPIC

## 🔥 Высокий приоритет

### Внешняя авторизация через Webhook (УЛУЧШЕНИЕ)

**Идея:** Улучшить существующий механизм вебхуков, добавив недостающие возможности из плана и новые полезные функции.

**Статус:** ✅ Базовая реализация уже работает (передача всех параметров, таймауты, rate limiting, кэширование)

---

#### 1. Улучшенная обработка ошибок вебхука

Сейчас при любой ошибке (таймаут, 404, 500) доступ запрещается. Нужно сделать умнее:

```python
# Логирование ошибок для отладки
if response.status_code != 200:
    logger.error(f"Webhook {webhook_url} вернул {response.status_code}")
    # Можно вернуть специальную страницу с объяснением
    return custom_error_page("Сервис авторизации временно недоступен")
```

**Что добавить:**
- 📝 Детальное логирование ошибок вебхуков
- 🖥️ Специальную страницу для случаев, когда вебхук недоступен (503)
- ⏱️ Статистику по таймаутам и ошибкам

---

#### 2. Поддержка кастомных заголовков для вебхуков

Некоторые вебхуки требуют авторизации (например, `Authorization: Bearer <token>`). Добавим возможность указывать заголовки.

**В `config.py`:**
```python
# Разрешить отправку кастомных заголовков
WEBHOOK_ALLOW_CUSTOM_HEADERS = os.getenv('WEBHOOK_ALLOW_CUSTOM_HEADERS', 'False').lower() == 'true'

# Заголовки по умолчанию
WEBHOOK_DEFAULT_HEADERS = {
    'User-Agent': 'ASPIC-Webhook/1.0',
    'Accept': 'application/json',
}
```

**В таблицу `files` добавить:**
- `webhook_headers TEXT` — JSON с кастомными заголовками (опционально)

**Пример использования:**
```json
{
    "webhook_url": "https://api.example.com/check",
    "webhook_headers": {
        "Authorization": "Bearer eyJhbGci...",
        "X-API-Key": "secret-key-123"
    }
}
```

---

#### 3. Белый список доменов для вебхуков

Для дополнительной безопасности администратор сможет ограничить, на какие домены можно отправлять вебхуки.

**В `config.py`:**
```python
# Список разрешённых доменов (через запятую)
WEBHOOK_ALLOWED_DOMAINS = os.getenv('WEBHOOK_ALLOWED_DOMAINS', '').split(',')

# Режим: "allow" (разрешены только из списка) или "deny" (запрещены только из списка)
WEBHOOK_DOMAIN_MODE = os.getenv('WEBHOOK_DOMAIN_MODE', 'deny')
```

**Логика работы:**
- Если список пуст — разрешены все домены (кроме заблокированных IP)
- Если режим "allow" — разрешены только домены из списка
- Если режим "deny" — запрещены домены из списка (полезно для блокировки нежелательных)

---

#### 4. Документация и подсказки в интерфейсе

Улучшить UX для пользователей, которые настраивают вебхуки.

**В `index.html` (поле webhookUrl):**
```html
<div class="info-content">
    <strong>🔗 Webhook URL</strong>
    <p>Будет вызван при каждой попытке открыть файл. Ожидает ответ <code>{"allowed": "1"}</code> или <code>{"allowed": "0"}</code>.</p>
    <p><strong>Как это работает:</strong></p>
    <ol>
        <li>Пользователь открывает <code>/view/TOKEN?param1=value1&param2=value2</code></li>
        <li>ASPIC вызывает ваш URL со всеми параметрами: <code>https://your-api.com?token=TOKEN&param1=value1&param2=value2&client_ip=1.2.3.4</code></li>
        <li>Ваш API возвращает <code>{"allowed": "1"}</code> или <code>{"allowed": "0"}</code></li>
    </ol>
    <p><strong>Примеры:</strong></p>
    <ul>
        <li><code>https://api.example.com/check-access</code> — простой вариант</li>
        <li><code>https://api.example.com/v1/verify?system_id=123</code> — с фиксированными параметрами</li>
    </ul>
    <p><span class="label-icon">⏱️</span> Таймаут: 5 секунд</p>
    <p><span class="label-icon">🔄</span> Кэширование: 5 минут (для одинаковых параметров)</p>
    <span class="info-close" onclick="hideInfo('webhook')">✕</span>
</div>
```

**Добавить новую страницу `/docs/webhooks`:**
- Полная документация по формату запросов и ответов
- Примеры на разных языках (Python, PHP, Node.js, etc.)
- Информация о безопасности и rate limits

---

## 📊 Средний приоритет

### Мониторинг и метрики

Добавить эндпоинт для сбора метрик работы вебхуков (например, для Prometheus).

**Эндпоинт:** `GET /metrics`

**Метрики:**
```
# HELP webhook_calls_total Total number of webhook calls
# TYPE webhook_calls_total counter
webhook_calls_total{url="example.com", status="allowed"} 42
webhook_calls_total{url="example.com", status="denied"} 3
webhook_calls_total{url="example.com", status="error"} 5

# HELP webhook_duration_seconds Webhook request duration
# TYPE webhook_duration_seconds histogram
webhook_duration_seconds{url="example.com", quantile="0.5"} 0.23
webhook_duration_seconds{url="example.com", quantile="0.9"} 0.56
webhook_duration_seconds{url="example.com", quantile="0.99"} 1.23

# HELP webhook_cache_hits_total Webhook cache hits
# TYPE webhook_cache_hits_total counter
webhook_cache_hits_total{url="example.com"} 15

# HELP webhook_rate_limited_total Requests rate limited by IP or URL
# TYPE webhook_rate_limited_total counter
webhook_rate_limited_total{type="ip"} 7
webhook_rate_limited_total{type="url"} 3
```

**В `config.py`:**
```python
# Включить метрики
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'False').lower() == 'true'
# Защитить метрики паролем (опционально)
METRICS_TOKEN = os.getenv('METRICS_TOKEN', '')
```

---

### Улучшение кэширования

Сейчас кэш живёт 5 минут для всех ответов. Можно сделать умнее:

```python
# В config.py
# Кэшировать только положительные ответы (разрешающие доступ)
WEBHOOK_CACHE_ONLY_ALLOWED = os.getenv('WEBHOOK_CACHE_ONLY_ALLOWED', 'True').lower() == 'true'

# Разное время жизни для разных ответов
WEBHOOK_CACHE_TTL_ALLOWED = int(os.getenv('WEBHOOK_CACHE_TTL_ALLOWED', 300))  # 5 мин для allowed
WEBHOOK_CACHE_TTL_DENIED = int(os.getenv('WEBHOOK_CACHE_TTL_DENIED', 60))     # 1 мин для denied
```

---

## 🚀 Низкий приоритет

### Расширенная статистика для владельцев файлов

Показывать владельцам файлов статистику по вызовам вебхуков:

```sql
-- Новая таблица для статистики
CREATE TABLE webhook_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token TEXT NOT NULL,
    call_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    client_ip TEXT,
    query_params TEXT,
    response_time_ms INTEGER,
    allowed BOOLEAN,
    cached BOOLEAN DEFAULT 0,
    FOREIGN KEY (token) REFERENCES files (token) ON DELETE CASCADE
);
```

**В интерфейсе просмотра файла (`view.html`) добавить вкладку "Статистика":**
- График количества вызовов по дням
- Процент разрешённых/запрещённых доступов
- Среднее время ответа вебхука
- Последние 10 попыток доступа

---

### Поддержка нескольких вебхуков для одного файла

Возможность указать несколько вебхуков (основной и запасной) для отказоустойчивости.

**В таблицу `files` добавить:**
- `webhook_backup_url TEXT` — резервный URL
- `webhook_fallback_mode TEXT DEFAULT 'any'` — режим: 'any' (достаточно одного разрешения) или 'all' (нужны все)

**Логика:**
```python
results = []
for url in [webhook_url, webhook_backup_url]:
    if url:
        result = await call_webhook(url, ...)
        results.append(result)

if webhook_fallback_mode == 'any':
    return any(results)
else:  # 'all'
    return all(results)
```

---

### Webhook для уведомлений

Возможность указать отдельный вебхук для уведомлений о событиях (файл загружен, файл удален, комментарий добавлен).

**В таблицу `files` добавить:**
- `notification_url TEXT` — URL для уведомлений
- `notify_on TEXT` — события для уведомления (upload, delete, comment)

**Формат уведомления:**
```json
{
    "event": "file_uploaded",
    "token": "abc123",
    "filename": "document.pdf",
    "timestamp": "2026-03-15T12:00:00Z",
    "client_ip": "1.2.3.4"
}
```

---

## 📋 Сводный статус реализации

| Задача | Статус | Приоритет |
|--------|--------|-----------|
| **Базовая реализация вебхуков** | ✅ **ГОТОВО** | — |
| └ Передача всех параметров | ✅ | — |
| └ Таймауты | ✅ | — |
| └ Rate limiting | ✅ | — |
| └ Кэширование | ✅ | — |
| └ SSRF защита | ✅ | — |
| **Улучшения** | | |
| └ Умная обработка ошибок | ⏳ Нужно | 🔥 Высокий |
| └ Кастомные заголовки | ⏳ Нужно | 🔥 Высокий |
| └ Белый список доменов | ⏳ Нужно | 🔥 Высокий |
| └ Документация и подсказки | ⏳ Нужно | 🔥 Высокий |
| └ Метрики и мониторинг | ⏳ Нужно | 📊 Средний |
| └ Улучшенное кэширование | ⏳ Нужно | 📊 Средний |
| └ Статистика для владельцев | ⏳ Нужно | 🚀 Низкий |
| └ Несколько вебхуков | ⏳ Нужно | 🚀 Низкий |
| └ Webhook уведомлений | ⏳ Нужно | 🚀 Низкий |
```

## Что изменено:

1. **Добавлен статус** текущей реализации (базовый функционал уже готов)
2. **Переформулированы задачи** как улучшения существующего, а не новые разработки
3. **Добавлены конкретные примеры кода** для каждого улучшения
4. **Разбито по приоритетам** (Высокий, Средний, Низкий)
5. **Добавлена сводная таблица** статуса реализации
6. **Учтены все ваши текущие наработки** (передача всех параметров, rate limiting, кэширование и т.д.)