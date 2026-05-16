"""Sentry + structlog setup — общий код для бота и воркера (Этап 7a).

Раньше каждый entrypoint настраивал logging самостоятельно; теперь они зовут
``setup_logging`` и ``setup_sentry`` отсюда, чтобы поведение было идентичным.

Поведение:

- ``setup_logging`` ставит structlog с JSON-renderer в production и
  ConsoleRenderer в development. ``stdlib.logging`` подключается через
  ``ProcessorFormatter`` — так все логи (наши и сторонние) проходят
  через единый pipeline.
- ``setup_sentry`` инициализирует Sentry SDK, если задан ``SENTRY_DSN``.
  Иначе тихо ничего не делает (info-log). Интеграции: aiohttp, sqlalchemy,
  redis — это самое полезное в нашем стеке.
- ``before_send`` фильтрует event перед отправкой: маскирует значения
  чувствительных ключей (token/password/secret/...) и вырезает поля
  с сырыми WHOIS-ответами.
- ``bind_log_context`` / ``clear_log_context`` — тонкая обёртка над
  ``structlog.contextvars`` для middleware и тасок ARQ.

Использование::

    from src.observability import setup_logging, setup_sentry

    setup_logging(settings)
    setup_sentry(settings)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

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


def setup_logging(settings: Settings) -> None:
    """Конфигурирует structlog + stdlib logging.

    В ``production`` — JSON renderer (для Loki/ELK), в остальных режимах —
    ConsoleRenderer для удобства разработки. Все stdlib-логи (aiogram,
    aiohttp, SQLAlchemy) проходят через ``ProcessorFormatter`` — выход
    единого формата.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Процессоры, применяемые ко всем записям независимо от источника. Часть
    # из них применима только к structlog-loggerам, другая — общая.
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    renderer: structlog.types.Processor
    if settings.environment == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=[
            *shared_processors,
            # ProcessorFormatter expects this as the last step before render:
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # stdlib → structlog мост. Все ``logging.getLogger(...).info(...)`` пройдут
    # через ProcessorFormatter и тот же renderer.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Чуть приглушаем шумные логгеры, которые любят DEBUG-спам на INFO уровне.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)


def bind_log_context(**kwargs: Any) -> None:
    """Удобный alias для ``structlog.contextvars.bind_contextvars``.

    Используется в middleware/тасках: после вызова все последующие
    structlog-логи внутри того же контекста (asyncio task) будут содержать
    переданные поля.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_log_context() -> None:
    """Сбрасывает контекстные поля — вызывать после обработки запроса/таски."""
    structlog.contextvars.clear_contextvars()


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


__all__ = [
    "bind_log_context",
    "clear_log_context",
    "setup_logging",
    "setup_sentry",
]
