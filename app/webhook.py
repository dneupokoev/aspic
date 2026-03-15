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
    WEBHOOK_MAX_HEADERS_SIZE,
    WEBHOOK_RATE_LIMIT_PER_URL,
    WEBHOOK_RATE_LIMIT_PER_IP
)

# Хранилище для кэширования ответов вебхуков
webhook_cache = {}

# Хранилище для rate limiting вызовов вебхуков
webhook_rate_limit_tracker = {}

# Хранилище для ограничения одновременных вызовов с одного IP
webhook_concurrent_tracker = {}

# Хранилище для rate limiting по IP
webhook_ip_rate_limit_tracker = {}


def get_cache_key(webhook_url: str, query_params: Dict[str, str]) -> str:
    """Генерирует ключ для кэширования на основе URL вебхука и ВСЕХ параметров запроса."""
    sorted_params = sorted(query_params.items())
    params_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    data = f"{webhook_url}:{params_str}"
    return hashlib.md5(data.encode()).hexdigest()


def extract_query_params(request) -> Dict[str, str]:
    """Извлекает ВСЕ параметры из query string запроса."""
    params = {}
    for key, values in request.query_params.items():
        params[key] = values[0] if isinstance(values, list) else values
    return params


def cleanup_old_entries(tracker, ttl_seconds: int = 60):
    """Очищает старые записи из трекера."""
    now = datetime.now()
    cutoff = now - timedelta(seconds=ttl_seconds)
    expired = []

    for key, entries in tracker.items():
        if isinstance(entries, list):
            fresh = [ts for ts in entries if ts > cutoff]
            if fresh:
                tracker[key] = fresh
            else:
                expired.append(key)
        elif isinstance(entries, dict):
            if isinstance(entries.get('expires'), datetime) and entries['expires'] <= now:
                expired.append(key)

    for key in expired:
        del tracker[key]

    if DEBUG and expired:
        print(f"🧹 Cleaned {len(expired)} expired entries")


async def validate_webhook_url(webhook_url: str) -> bool:
    """Проверяет, безопасен ли URL вебхука."""
    try:
        parsed = urlparse(webhook_url)

        if parsed.scheme not in ALLOWED_WEBHOOK_SCHEMES:
            if DEBUG:
                print(f"⚠️ Webhook rejected: invalid scheme {parsed.scheme}")
            return False

        hostname = parsed.hostname
        if not hostname:
            return False

        if hostname in ['localhost', 'localhost.localdomain', '[::1]', '127.0.0.1']:
            if DEBUG:
                print(f"⚠️ Webhook rejected: localhost hostname {hostname}")
            return False

        if hostname == '::1' or hostname.startswith('0:0:0:0:0:0:0:1'):
            return False

        try:
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

        for ip in ips:
            try:
                ip_obj = ipaddress.ip_address(ip)
                for blocked_range in BLOCKED_IP_RANGES:
                    try:
                        if ip_obj in ipaddress.ip_network(blocked_range):
                            if DEBUG:
                                print(f"⚠️ Webhook rejected: IP {ip} in blocked range {blocked_range}")
                            return False
                    except ValueError:
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
    """Проверяет, не превышен ли лимит одновременных запросов с одного IP."""
    if client_ip not in webhook_concurrent_tracker:
        webhook_concurrent_tracker[client_ip] = set()

    current_count = len(webhook_concurrent_tracker[client_ip])

    if current_count >= WEBHOOK_MAX_CONCURRENT_PER_IP:
        if DEBUG:
            print(f"⚠️ Concurrent webhook limit exceeded for IP {client_ip}: {current_count} active")
        return False

    task_id = id(asyncio.current_task())
    webhook_concurrent_tracker[client_ip].add(task_id)
    return True


def cleanup_concurrent(client_ip: str):
    """Очищает запись о завершённом запросе."""
    if client_ip in webhook_concurrent_tracker:
        task_id = id(asyncio.current_task())
        webhook_concurrent_tracker[client_ip].discard(task_id)

        if not webhook_concurrent_tracker[client_ip]:
            del webhook_concurrent_tracker[client_ip]


async def check_ip_rate_limit(client_ip: str) -> bool:
    """Проверяет, не превышен ли лимит вызовов вебхуков с одного IP."""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)

    calls = webhook_ip_rate_limit_tracker.get(client_ip, [])
    calls = [ts for ts in calls if ts > minute_ago]

    if len(calls) >= WEBHOOK_RATE_LIMIT_PER_IP:
        if DEBUG:
            print(f"⚠️ IP rate limit exceeded for {client_ip}: {len(calls)} calls in last minute")
        return False

    calls.append(now)
    webhook_ip_rate_limit_tracker[client_ip] = calls

    if len(webhook_ip_rate_limit_tracker) > 1000:
        cleanup_old_entries(webhook_ip_rate_limit_tracker, 60)

    return True


async def check_webhook_rate_limit(webhook_url: str) -> bool:
    """Проверяет, не превышен ли лимит вызовов конкретного вебхука."""
    now = datetime.now()
    minute_ago = now - timedelta(minutes=1)

    calls = webhook_rate_limit_tracker.get(webhook_url, [])
    calls = [ts for ts in calls if ts > minute_ago]

    if len(calls) >= WEBHOOK_RATE_LIMIT_PER_URL:
        return False

    calls.append(now)
    webhook_rate_limit_tracker[webhook_url] = calls

    if len(webhook_rate_limit_tracker) > 1000:
        cleanup_old_entries(webhook_rate_limit_tracker, 60)

    return True


async def call_webhook(
        webhook_url: str,
        query_params: Dict[str, str],
        client_ip: Optional[str] = None
) -> bool:
    """Вызывает вебхук для проверки доступа к файлу."""
    if not await validate_webhook_url(webhook_url):
        if DEBUG:
            print(f"⚠️ Webhook URL rejected (security): {webhook_url}")
        return False

    if client_ip and not await check_ip_rate_limit(client_ip):
        return False

    if client_ip:
        if not await check_concurrent_limit(client_ip):
            return False
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
    """Внутренняя реализация вызова вебхука."""
    cache_key = get_cache_key(webhook_url, query_params)
    if cache_key in webhook_cache:
        cached = webhook_cache[cache_key]
        if cached["expires"] > datetime.now():
            if DEBUG:
                print(f"🔵 Webhook cache HIT for {webhook_url} with params {query_params}: {cached['allowed']}")
            return cached["allowed"]
        else:
            del webhook_cache[cache_key]

    if not await check_webhook_rate_limit(webhook_url):
        if DEBUG:
            print(f"⚠️ Webhook rate limit exceeded for {webhook_url}")
        return False

    all_params = query_params.copy()
    if client_ip:
        all_params['client_ip'] = client_ip

    full_url = f"{webhook_url}?{urlencode(all_params)}"

    if DEBUG:
        print(f"🔄 Calling webhook: {full_url}")

    try:
        limits = httpx.Limits(
            max_keepalive_connections=5,
            max_connections=10,
            keepalive_expiry=30.0
        )

        timeout = httpx.Timeout(
            WEBHOOK_TIMEOUT,
            connect=WEBHOOK_CONNECT_TIMEOUT,
            read=WEBHOOK_READ_TIMEOUT
        )

        transport = httpx.AsyncHTTPTransport(
            limits=limits,
            retries=0
        )

        async with httpx.AsyncClient(
                timeout=timeout,
                transport=transport,
                follow_redirects=False,
                max_redirects=0,
                headers={
                    'User-Agent': 'ASPIC-Webhook/1.0',
                    'Accept': 'application/json',
                    'X-Forwarded-For': client_ip if client_ip else '',
                    'X-Real-IP': client_ip if client_ip else ''
                }
        ) as client:

            response = await client.get(full_url)

            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > WEBHOOK_MAX_RESPONSE_SIZE:
                if DEBUG:
                    print(f"⚠️ Webhook response too large: {content_length} bytes")
                cache_result(webhook_url, query_params, False)
                return False

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

            try:
                data = json.loads(content)
                allowed = data.get("allowed") == "1" or data.get("allowed") == 1

                if DEBUG:
                    print(f"✅ Webhook response: {data}, allowed: {allowed}")

                cache_result(webhook_url, query_params, allowed)
                return allowed

            except json.JSONDecodeError as e:
                if DEBUG:
                    print(f"❌ Webhook returned invalid JSON: {content[:200]}... Error: {e}")
                cache_result(webhook_url, query_params, False)
                return False

    except Exception as e:
        if DEBUG:
            print(f"❌ Webhook error: {e}")
        cache_result(webhook_url, query_params, False)
        return False


def cache_result(webhook_url: str, query_params: Dict[str, str], allowed: bool):
    """Кэширует результат вызова вебхука."""
    cache_key = get_cache_key(webhook_url, query_params)
    webhook_cache[cache_key] = {
        "allowed": allowed,
        "expires": datetime.now() + timedelta(seconds=WEBHOOK_CACHE_TTL)
    }

    if DEBUG:
        print(f"💾 Cached result for {webhook_url} with params {query_params}: {allowed} (expires in {WEBHOOK_CACHE_TTL}s)")

    if len(webhook_cache) > 1000:
        cleanup_old_entries(webhook_cache, WEBHOOK_CACHE_TTL)


async def check_webhook_access(
        webhook_url: str,
        request,
        token: str
) -> bool:
    """Проверяет доступ к файлу через вебхук."""
    if not webhook_url or webhook_url.strip() == "":
        return True

    if not (webhook_url.startswith('http://') or webhook_url.startswith('https://')):
        if DEBUG:
            print(f"⚠️ Invalid webhook URL: {webhook_url}")
        return False

    query_params = extract_query_params(request)

    if 'token' not in query_params:
        query_params['token'] = token

    client_ip = request.client.host

    return await call_webhook(webhook_url, query_params, client_ip)