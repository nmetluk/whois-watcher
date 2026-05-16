"""Sentry SDK setup — общий код для бота и воркера (Этап 7a).

Раньше каждый entrypoint инициализировал Sentry самостоятельно; теперь
``main.py`` и ``worker.py`` зовут ``setup_sentry`` отсюда, чтобы поведение
было идентичным.

Поведение:

- если ``SENTRY_DSN`` пуст — info-лог «Sentry not configured» и выход
- иначе ``sentry_sdk.init`` с интеграциями aiohttp/sqlalchemy/redis,
  ``traces_sample_rate=0.1`` и ``send_default_pii=False``
- ``before_send`` фильтрует event перед отправкой: маскирует значения
  чувствительных ключей (token/password/secret/...) и вырезает поля
  с сырыми WHOIS-ответами — Sentry не должен видеть наши секреты и
  персональные данные владельцев доменов, даже если кто-то случайно
  залогирует их.

Использование::

    from src.observability import setup_sentry

    setup_sentry(settings)
"""

from __future__ import annotations

import logging
from typing import Any

from src.config.settings import Settings

logger = logging.getLogger(__name__)


# Поля, которые мы НИКОГДА не хотим видеть в Sentry-эвентах. Регистронезависимое
# вхождение в ключ — этого достаточно, чтобы покрыть и snake_case, и kebab-case,
# и заголовки HTTP.
_SENSITIVE_KEY_SUBSTRINGS: tuple[str, ...] = (
    "token",
    "password",
    "secret",
    "authorization",
    "api_key",
    "apikey",
    "x-telegram-bot-api-secret",
)

# Ключи, которые мы целиком вырезаем из ``extra``/``contexts`` Sentry-эвента:
# содержимое полных WHOIS-ответов может включать персональные данные (vCard,
# контакты администратора домена) — нам этого не нужно ни в логе, ни в Sentry.
_BULK_DATA_KEYS: tuple[str, ...] = (
    "raw_data",
    "raw_response",
    "raw_text",
    "raw_whois",
)


def setup_sentry(settings: Settings) -> None:
    """Инициализирует Sentry SDK, если ``SENTRY_DSN`` задан.

    Без DSN — info-сообщение в лог и выход (Sentry опционален). При DSN
    включаем aiohttp/sqlalchemy/redis-интеграции — этого достаточно для
    автоматического перехвата HTTP-запросов, SQL-запросов и Redis-команд.

    ``before_send`` фильтрует event перед отправкой:

    - заменяет значения чувствительных ключей на ``"[Filtered]"``
    - вырезает поля с массивами WHOIS-данных (могут содержать персональные)

    ``send_default_pii=False`` — Sentry не светит Telegram username и аналоги.
    """
    if not settings.sentry_dsn:
        logger.info("Sentry not configured (SENTRY_DSN is empty)")
        return

    import sentry_sdk
    from sentry_sdk.integrations.aiohttp import AioHttpIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        # Trace 10% запросов — достаточно для performance-инсайтов, не
        # выжигает квоту бесплатного тарифа.
        traces_sample_rate=0.1,
        integrations=[
            AioHttpIntegration(),
            SqlalchemyIntegration(),
            RedisIntegration(),
        ],
        # Не светим Telegram-username / email / IP в трейсбеках.
        send_default_pii=False,
        # ``Event`` из sentry-stub — это TypedDict, наш фильтр работает с dict
        # как с обычным mutable mapping. Сигнатура совместима, но stub требует
        # точный тип — отключаем проверку по месту.
        before_send=_before_send,  # type: ignore[arg-type]
    )
    logger.info(
        "Sentry initialized",
        extra={"environment": settings.environment},
    )


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Фильтрация Sentry-эвентов перед отправкой.

    Действует в две стадии:

    1. По всем словарям в event'е заменяет значения у чувствительных ключей
       на ``"[Filtered]"``.
    2. Вырезает поля с массивами WHOIS-данных (``raw_data``, ``raw_response``)
       — они могут содержать персональные данные владельца домена.

    Возвращает event или ``None`` чтобы отбросить вовсе (мы не отбрасываем).
    """
    del hint  # пока не используется, оставляем для будущих расширений
    _scrub_in_place(event)
    return event


def _scrub_in_place(node: Any) -> None:
    """Рекурсивно вычищает sensitive-значения из вложенных dict/list."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            lower = key.lower() if isinstance(key, str) else ""
            if any(needle in lower for needle in _BULK_DATA_KEYS):
                node[key] = "[Filtered: bulk]"
                continue
            if any(needle in lower for needle in _SENSITIVE_KEY_SUBSTRINGS):
                node[key] = "[Filtered]"
                continue
            _scrub_in_place(node[key])
    elif isinstance(node, list):
        for item in node:
            _scrub_in_place(item)


__all__ = ["setup_sentry"]
