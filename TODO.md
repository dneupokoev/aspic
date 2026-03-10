# TODO: Планы развития ASPIC

## 🔥 Высокий приоритет

### Внешняя авторизация через Webhook

**Идея:** При загрузке файла можно указать внешний API для проверки прав. Ссылка на файл содержит специальный ID, который ASPIC отправляет на этот API при открытии. API отвечает `true/false` — разрешать показ или нет.

---

### 🔧 Техническая реализация

#### 1. Формат защищенной ссылки
```
https://aspic.example.com/v/{token}?access_id={id}
```
где `{id}` — идентификатор для проверки (номер заказа, код клиента и т.п.).

#### 2. Изменения в БД
В таблицу `files` добавить поля:
- `webhook_url TEXT` — URL внешнего API
- `access_param_name TEXT DEFAULT 'access_id'` — имя параметра для отправки

#### 3. Изменения в загрузке (`/api/confirm-upload`)
Добавить опциональные поля в JSON:
```json
{
    "webhook_url": "https://api.example.com/check",
    "access_param_name": "order_id"
}
```

#### 4. Логика открытия файла (`GET /v/{token}`)

```python
if file.webhook_url:
    # Проверяем наличие access_id в query-параметрах
    if not access_id:
        return страница с запросом ID
    
    # Отправляем запрос на внешний API
    response = await client.post(
        file.webhook_url,
        json={file.access_param_name: access_id}
    )
    
    if not response.json().get("allowed"):
        return 403 Access Denied
```

#### 5. Защита
- Таймаут на запрос к API — 3 секунды
- Rate limiting на эндпоинт `/v/{token}`
- Если API недоступен — возвращать 503

---

### 📌 Пример использования

1. **Загрузка:** Владелец загружает файл с `webhook_url` и `access_param_name`
2. **Ссылка:** `https://aspic.example.com/v/XyZ789?order_id=INV-2025-042`
3. **Проверка:** ASPIC отправляет `{"order_id": "INV-2025-042"}` на внешний API
4. **Ответ:** `{"allowed": true}` → пользователь видит файл
5. **Отказ:** `{"allowed": false}` → 403 Forbidden

---

### 🚀 Потенциальные улучшения
- Кеширование положительных ответов (на 10-15 минут)
- Поддержка GET-запросов (параметры в query)
- Кастомные заголовки для авторизации на внешнем API
