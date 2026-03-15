import httpx
import asyncio
import ipaddress
import socket
from typing import Optional, Dict, Any, List, Tuple, Set
from datetime import datetime, timedelta
from urllib.parse import urlparse
import hashlib
import json
from urllib.parse import urlencode, parse_qs

from app.config import (
    WEBHOOK_TIMEOUT, WEBHOOK_CACHE_TTL, DEBUG,
    BLOCKED_IP_RANGES, ALLOWED_WEBHOOK_SCHEMES,
    WEBHOOK_MAX_RESPONSE_SIZE, WEBHOOK_MAX_CONCURRENT_PER_IP,
    WEBHOOK_CONNECT_TIMEOUT, WEBHOOK_READ_TIMEOUT,
    WEBHOOK_MAX_HEADERS_SIZE
)

# Хранилище для кэширования ответов вебхуков
# Структура: {cache_key: {"allowed": bool, "expires": datetime}}
webhook_cache = {}

# Хранилище для rate limiting вызовов вебхуков
# Структура: {webhook_url: [timestamp1, timestamp2, ...]}
webhook_rate_limit_tracker = {}

# Хранилище для ограничения одновременных вызовов с одного IP
# Структура: {client_ip: set([task_id1, task_id2, ...])}
webhook_concurrent_tracker = {}

# Хранилище для rate limiting по IP (сколько разных вебхуков вызывает один IP)
# Структура: {client_ip: [timestamp1, timestamp2, ...]}
webhook_ip_rate_limit_tracker = {}


def get_cache_key(webhook_url: str, query_params: Dict[str, str]) -> str:
    """
    Генерирует ключ для кэширования на основе URL вебхука и ВСЕХ параметров запроса.
    Параметры сортируются для консистентности.
    """
    # Сортируем параметры для стабильного ключа
    sorted_params = sorted(query_params.items())
    # Создаём строку вида: key1=value1&key2=value2
    params_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    data = f"{webhook_url}:{params_str}"
    return hashlib.md5(data.encode()).hexdigest()


def extract_query_params(request) -> Dict[str, str]:
    """
    Извлекает ВСЕ параметры из query string запроса.
    Возвращает словарь с параметрами (берётся первое значение для каждого ключа).
    """
    params = {}
    for key, values in request.query_params.items():
        # Берём первое значение (обычно оно одно)
        params[key] = values[0] if isinstance(values, list) else values
    return params


async def validate_webhook_url(webhook_url: str) -> bool:
    """
    Проверяет, безопасен ли URL вебхука.
    Защита от SSRF: блокировка внутренних IP, проверка протокола.
    """
    try:
        parsed = urlparse(webhook_url)

        # Проверка протокола
        if parsed.scheme not in ALLOWED_WEBHOOK_SCHEMES:
            if DEBUG:
                print(f"⚠️ Webhook rejected: invalid scheme {parsed.scheme}")
            return False

        # Проверка на наличие хостнейма
        hostname = parsed.hostname
        if not hostname:
            return False

        # Проверка на localhost в имени (дополнительная защита)
        if hostname in ['localhost', 'localhost.localdomain', '[::1]', '127.0.0.1']:
            if DEBUG:
                print(f"⚠️ Webhook rejected: localhost hostname {hostname}")
            return False

        # Проверка на loopback в IPv6
        if hostname == '::1' or hostname.startswith('0:0:0:0:0:0:0:1'):
            return False

        # Резолвим домен в IP (блокирующая операция, но необходима для безопасности)
        try:
            # Используем asyncio.to_thread для неблокирующего выполнения
            addrinfo = await asyncio.to_thread(
                socket.getaddrinfo, hostname, None,
                socket.AF_UNSPEC, socket.SOCK_STREAM
            )
            ips = set()
            for addr in addrinfo:
                ip = addr[4][0]
                ips.add(ip)
        except socket.gaierror:
            if DEBUG:
                print(f"⚠️ Webhook rejected: cannot resolve {hostname}")
            return False
        except Exception as e:
            if DEBUG:
                print(f"⚠️ Webhook resolution error: {e}")
            return False

        # Проверяем каждый IP
        for ip in ips:
            try:
                # Пытаемся определить версию IP
                ip_obj = ipaddress.ip_address(ip)

                # Проверяем по всем заблокированным диапазонам
                for blocked_range in BLOCKED_IP_RANGES:
                    try:
                        if ip_obj in ipaddress.ip_network(blocked_range):
                            if DEBUG:
                                print(f"⚠️ Webhook rejected: IP {ip} in blocked range {blocked_range}")
                            return False
                    except ValueError:
                        # Игнорируем некорректные диапазоны
                        continue

            except ValueError:
                if DEBUG:
                    print(f"⚠️ Webhook rejected: invalid IP {ip}")
                return False

        return True

    except Exception as e:
        if DEBUG:
            print(f"⚠️ Webhook validation error: {e}")
        return False


async def check_concurrent_limit(client_ip: str) -> bool:
    """
    Проверяет, не превышен ли лимит одновременных запросов с одного IP.
    """
    if client_ip not in webhook_concurrent_tracker:
        webhook_concurrent_tracker[client_ip] = set()

    current_count = len(webhook_concurrent_tracker[client_ip])

    if current_count >= WEBHOOK_MAX_CONCURRENT_PER_IP:
        if DEBUG:
            print(f"⚠️ Concurrent webhook limit exceeded for IP {client_ip}: {current_count} active")
        return False

    # Генерируем уникальный ID для этого запроса
    task_id = id(asyncio.current_task())
    webhook_concurrent_tracker[client_ip].add(task_id)

    # Возвращаем True и функцию для очистки
    return True


def cleanup_concurrent(client_ip: str):
    """Очищает запись о завершённом запросе."""
    if client_ip in webhook_concurrent_tracker:
        task_id = id(asyncio.current_task())
        webhook_concurrent_tracker[client_ip].discard(task_id)

        # Если множество пустое, удаляем запись
        if not webhook_concurrent_tracker[client_ip]:
            del webhook_concurrent_tracker[client_ip]


async def check_ip_rate_limit(client_ip: str, limit_per_minute: int = 30) -> bool:
    """
    Проверяет, не превышен ли лимит вызовов вебхуков с одного IP.
    Ограничивает, сколько разных вебхуков может вызвать один IP.
    """
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)

    # Получаем историю вызовов для этого IP
    calls = webhook_ip_rate_limit_tracker.get(client_ip, [])

    # Оставляем только вызовы за последнюю минуту
    calls = [ts for ts in calls if ts > minute_ago]

    if len(calls) >= limit_per_minute:
        if DEBUG:
            print(f"⚠️ IP rate limit exceeded for {client_ip}: {len(calls)} calls in last minute")
        return False

    # Добавляем текущий вызов
    calls.append(now)
    webhook_ip_rate_limit_tracker[client_ip] = calls

    # Очистка старых записей
    if len(webhook_ip_rate_limit_tracker) > 1000:
        cleanup_ip_rate_limit_tracker()

    return True


def cleanup_ip_rate_limit_tracker():
    """Очищает старые записи из трекера rate limiting по IP."""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    expired = []

    for ip, calls in webhook_ip_rate_limit_tracker.items():
        fresh_calls = [ts for ts in calls if ts > minute_ago]
        if fresh_calls:
            webhook_ip_rate_limit_tracker[ip] = fresh_calls
        else:
            expired.append(ip)

    for ip in expired:
        del webhook_ip_rate_limit_tracker[ip]

    if DEBUG:
        print(f"🧹 Cleaned {len(expired)} expired IP rate limit entries")


async def check_webhook_rate_limit(webhook_url: str, limit_per_minute: int = 10) -> bool:
    """
    Проверяет, не превышен ли лимит вызовов конкретного вебхука.
    Возвращает True, если вызов разрешен, False если превышен лимит.
    """
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)

    # Получаем историю вызовов для этого вебхука
    calls = webhook_rate_limit_tracker.get(webhook_url, [])

    # Оставляем только вызовы за последнюю минуту
    calls = [ts for ts in calls if ts > minute_ago]

    if len(calls) >= limit_per_minute:
        return False

    # Добавляем текущий вызов
    calls.append(now)
    webhook_rate_limit_tracker[webhook_url] = calls

    # Очистка старых записей (опционально)
    if len(webhook_rate_limit_tracker) > 1000:
        cleanup_rate_limit_tracker()

    return True


def cleanup_rate_limit_tracker():
    """Очищает старые записи из трекера rate limiting."""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)
    expired = []

    for url, calls in webhook_rate_limit_tracker.items():
        # Оставляем только свежие вызовы
        fresh_calls = [ts for ts in calls if ts > minute_ago]
        if fresh_calls:
            webhook_rate_limit_tracker[url] = fresh_calls
        else:
            expired.append(url)

    for url in expired:
        del webhook_rate_limit_tracker[url]


async def call_webhook(
        webhook_url: str,
        query_params: Dict[str, str],
        client_ip: Optional[str] = None
) -> bool:
    """
    Вызывает вебхук для проверки доступа к файлу, передавая ВСЕ параметры запроса.
    Возвращает True если доступ разрешен, False если запрещен или ошибка.
    """
    # Проверяем URL на безопасность (SSRF защита)
    if not await validate_webhook_url(webhook_url):
        if DEBUG:
            print(f"⚠️ Webhook URL rejected (security): {webhook_url}")
        return False

    # Проверяем rate limit по IP (сколько всего запросов с этого IP)
    if client_ip and not await check_ip_rate_limit(client_ip, 30):
        return False

    # Проверяем лимит одновременных запросов с этого IP
    if client_ip:
        if not await check_concurrent_limit(client_ip):
            return False
        # Добавляем очистку при завершении
        try:
            return await _call_webhook_impl(webhook_url, query_params, client_ip)
        finally:
            cleanup_concurrent(client_ip)
    else:
        return await _call_webhook_impl(webhook_url, query_params, client_ip)


async def _call_webhook_impl(
        webhook_url: str,
        query_params: Dict[str, str],
        client_ip: Optional[str] = None
) -> bool:
    """
    Внутренняя реализация вызова вебхука.
    """
    # Проверяем кэш для этой связки параметров
    cache_key = get_cache_key(webhook_url, query_params)
    if cache_key in webhook_cache:
        cached = webhook_cache[cache_key]
        if cached["expires"] > datetime.now():
            if DEBUG:
                print(f"🔵 Webhook cache HIT for {webhook_url} with params {query_params}: {cached['allowed']}")
            return cached["allowed"]
        else:
            # Удаляем просроченный кэш
            del webhook_cache[cache_key]

    # Проверяем rate limit (10 вызовов в минуту по умолчанию)
    if not await check_webhook_rate_limit(webhook_url, 10):
        if DEBUG:
            print(f"⚠️ Webhook rate limit exceeded for {webhook_url}")
        # При превышении лимита считаем, что доступ запрещен
        return False

    # Копируем параметры и добавляем client_ip если передан
    all_params = query_params.copy()
    if client_ip:
        all_params['client_ip'] = client_ip

    # Формируем URL со ВСЕМИ параметрами
    full_url = f"{webhook_url}?{urlencode(all_params)}"

    if DEBUG:
        print(f"🔄 Calling webhook: {full_url}")

    try:
        # Настраиваем клиент с безопасными параметрами
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )

        # Таймауты для разных этапов
        timeout = httpx.Timeout(
            WEBHOOK_TIMEOUT,
            connect=WEBHOOK_CONNECT_TIMEOUT,
            read=WEBHOOK_READ_TIMEOUT
        )

        # Настраиваем транспорт с ограничениями
        transport = httpx.AsyncHTTPTransport(
            limits=limits,
            retries=0  # Не повторяем при ошибках
        )

        async with httpx.AsyncClient(
                timeout=timeout,
                transport=transport,
                follow_redirects=False,  # Не следуем редиректам
                max_redirects=0,
                headers={
                    'User-Agent': 'ASPIC-Webhook/1.0',
                    'Accept': 'application/json',
                    'X-Forwarded-For': client_ip if client_ip else '',
                    'X-Real-IP': client_ip if client_ip else ''
                }
        ) as client:

            response = await client.get(full_url)

            # Проверяем размер ответа по заголовку Content-Length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > WEBHOOK_MAX_RESPONSE_SIZE:
                if DEBUG:
                    print(f"⚠️ Webhook response too large: {content_length} bytes")
                cache_result(webhook_url, query_params, False)
                return False

            # Читаем ответ с ограничением
            try:
                content = await response.aread()
            except httpx.ResponseNotRead:
                content = b''

            if len(content) > WEBHOOK_MAX_RESPONSE_SIZE:
                if DEBUG:
                    print(f"⚠️ Webhook response too large: {len(content)} bytes")
                cache_result(webhook_url, query_params, False)
                return False

            if response.status_code != 200:
                if DEBUG:
                    print(f"❌ Webhook returned non-200 status: {response.status_code}")
                cache_result(webhook_url, query_params, False)
                return False

            # Парсим JSON с ограничением
            try:
                data = json.loads(content)
                allowed = data.get("allowed") == "1" or data.get("allowed") == 1

                if DEBUG:
                    print(f"✅ Webhook response: {data}, allowed: {allowed}")

                # Кэшируем результат для этой связки параметров
                cache_result(webhook_url, query_params, allowed)

                return allowed

            except json.JSONDecodeError as e:
                if DEBUG:
                    print(f"❌ Webhook returned invalid JSON: {content[:200]}... Error: {e}")
                cache_result(webhook_url, query_params, False)
                return False

    except httpx.TimeoutException as e:
        if DEBUG:
            print(f"⏱️ Webhook timeout: {e}")
        cache_result(webhook_url, query_params, False)
        return False

    except httpx.ConnectError as e:
        if DEBUG:
            print(f"🔌 Webhook connection error: {e}")
        cache_result(webhook_url, query_params, False)
        return False

    except httpx.HTTPError as e:
        if DEBUG:
            print(f"🌐 Webhook HTTP error: {e}")
        cache_result(webhook_url, query_params, False)
        return False

    except Exception as e:
        if DEBUG:
            print(f"❌ Webhook unexpected error: {e}")
        cache_result(webhook_url, query_params, False)
        return False


def cache_result(webhook_url: str, query_params: Dict[str, str], allowed: bool):
    """Кэширует результат вызова вебхука для конкретной связки параметров."""
    cache_key = get_cache_key(webhook_url, query_params)
    webhook_cache[cache_key] = {
        "allowed": allowed,
        "expires": datetime.now() + timedelta(seconds=WEBHOOK_CACHE_TTL)
    }

    if DEBUG:
        print(f"💾 Cached result for {webhook_url} with params {query_params}: {allowed} (expires in {WEBHOOK_CACHE_TTL}s)")

    # Очистка старых записей кэша (если их слишком много)
    if len(webhook_cache) > 1000:
        cleanup_cache()


def cleanup_cache():
    """Очищает просроченные записи кэша."""
    now = datetime.now()
    expired = []

    for key, value in webhook_cache.items():
        if value["expires"] <= now:
            expired.append(key)

    for key in expired:
        del webhook_cache[key]

    if DEBUG:
        print(f"🧹 Cleaned {len(expired)} expired cache entries")


async def check_webhook_access(
        webhook_url: str,
        request,
        token: str
) -> bool:
    """
    Проверяет доступ к файлу через вебхук.
    Передаёт ВСЕ параметры запроса в вебхук.
    Возвращает True если доступ разрешен, False если нет вебхука или доступ запрещен.
    """
    # Если вебхук не указан, доступ разрешен
    if not webhook_url or webhook_url.strip() == "":
        return True

    # Проверяем, является ли URL валидным (начинается с http)
    if not (webhook_url.startswith('http://') or webhook_url.startswith('https://')):
        if DEBUG:
            print(f"⚠️ Invalid webhook URL: {webhook_url}")
        return False

    # Извлекаем ВСЕ параметры из запроса
    query_params = extract_query_params(request)

    # Добавляем token в параметры (если его нет)
    if 'token' not in query_params:
        query_params['token'] = token

    # Получаем IP клиента
    client_ip = request.client.host

    # Вызываем вебхук со всеми параметрами
    return await call_webhook(webhook_url, query_params, client_ip)