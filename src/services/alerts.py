"""Сервис алертов в админ-канал (ADR 019).

Бот шлёт в выделенный канал (``settings.admin_channel_id``):

- ``#critical`` — критические ошибки (БД, Redis, webhook, startup)
- ``#anomaly`` — массовые WHOIS-фейлы, аномалии трафика
- ``#info``    — важные события (старт/стоп процессов)
- ``#daily``   — ежедневная сводка

Дедупликация — Redis-ключ ``alert:<hash>`` с TTL
``Limits.alert_dedup_ttl_minutes``. Hash считается от
``(severity, title, details[:200])`` — этого достаточно, чтобы одно и то же
сообщение не зашло в канал десятки раз подряд.

Если ``admin_channel_id`` не задан или Telegram ответил ошибкой — фактический
no-op + warning в лог. Алерт не должен валить хост-процесс.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from aiogram import Bot
from redis.asyncio import Redis

from src.config.limits import Limits
from src.config.settings import Settings

logger = logging.getLogger(__name__)


# Префикс ключей дедупликации.
_DEDUP_PREFIX = "alert:"


class AlertService:
    """Отправка алертов в админ-канал с Redis-дедупликацией.

    Зависимости — ``Bot``, ``Redis``, ``Settings``, ``Limits`` — внедряются
    извне (точки сборки: ``main.py`` для бота, ``arq_config.py`` для воркера).
    """

    def __init__(
        self,
        *,
        bot: Bot,
        redis: Redis[str],
        settings: Settings,
        limits: Limits,
    ) -> None:
        self._bot = bot
        self._redis = redis
        self._settings = settings
        self._limits = limits

    # ------------------------------------------------------------------
    # Публичные методы по severity
    # ------------------------------------------------------------------

    async def send_critical(self, title: str, details: str) -> None:
        """🚨 #critical — критические ошибки: БД, Redis, webhook, миграции."""
        await self._send(severity="critical", icon="🚨", title=title, details=details)

    async def send_anomaly(self, title: str, details: str) -> None:
        """⚠️ #anomaly — массовые WHOIS-фейлы, всплески ошибок."""
        await self._send(severity="anomaly", icon="⚠️", title=title, details=details)

    async def send_info(self, title: str, details: str) -> None:
        """ℹ️ #info — важные системные события (старт/стоп процессов)."""
        await self._send(severity="info", icon="ℹ️", title=title, details=details)

    async def send_daily_summary(self, stats: dict[str, Any]) -> None:
        """📊 #daily — ежедневная сводка.

        ``stats`` — произвольный словарь со счётчиками. Форматирование —
        в ``_format_daily_summary``; дедупликация идёт по тексту сообщения,
        поэтому сводка за один и тот же день не задвоится в обычных условиях.
        """
        body = _format_daily_summary(stats)
        await self._send(severity="daily", icon="📊", title="Daily summary", details=body)

    # ------------------------------------------------------------------
    # Внутренняя реализация
    # ------------------------------------------------------------------

    async def _send(self, *, severity: str, icon: str, title: str, details: str) -> None:
        """Универсальный путь: тег #severity, дедуп через Redis, отправка."""
        channel_id = self._settings.admin_channel_id
        if channel_id is None:
            logger.warning(
                "AlertService: admin_channel_id is not configured; alert suppressed",
                extra={"severity": severity, "title": title},
            )
            return

        if not await self._reserve_dedup_slot(severity=severity, title=title, details=details):
            logger.debug(
                "AlertService: duplicate alert suppressed",
                extra={"severity": severity, "title": title},
            )
            return

        text = _format_alert(severity=severity, icon=icon, title=title, details=details)
        try:
            await self._bot.send_message(chat_id=channel_id, text=text)
        except Exception:  # — Telegram-API внешняя граница
            logger.exception(
                "AlertService: failed to send alert",
                extra={"severity": severity, "title": title},
            )

    async def _reserve_dedup_slot(self, *, severity: str, title: str, details: str) -> bool:
        """SET NX EX: возвращает True, если слот свободен и зарезервирован."""
        key = _dedup_key(severity=severity, title=title, details=details)
        ttl_seconds = self._limits.alert_dedup_ttl_minutes * 60
        # ``set(... nx=True)`` возвращает True/None в redis-py — приводим к bool.
        reserved = await self._redis.set(key, "1", ex=ttl_seconds, nx=True)
        return bool(reserved)


# ---------------------------------------------------------------------------
# Внутреннее форматирование
# ---------------------------------------------------------------------------


def _dedup_key(*, severity: str, title: str, details: str) -> str:
    """Хэш — детерминированный, не светит секреты."""
    digest = hashlib.sha256()
    digest.update(severity.encode("utf-8"))
    digest.update(b"|")
    digest.update(title.encode("utf-8"))
    digest.update(b"|")
    # Обрезаем details, чтобы пара «то же сообщение + новая длинная трасса»
    # не считалась новым алертом.
    digest.update(details[:200].encode("utf-8"))
    return f"{_DEDUP_PREFIX}{digest.hexdigest()[:32]}"


def _format_alert(*, severity: str, icon: str, title: str, details: str) -> str:
    """Простой plain-text формат с тегом #severity."""
    parts = [f"{icon} #{severity}", title.strip()]
    body = details.strip()
    if body:
        parts.append("")
        parts.append(body)
    return "\n".join(parts)


def _format_daily_summary(stats: dict[str, Any]) -> str:
    """Форматирует сводку. На неизвестных ключах — просто ``key: value``.

    Используется ``json.dumps`` для словарей-в-словарях; для плоской пары
    ``ключ: значение`` хватает str(...). Никаких HTML-тегов — у алерт-канала
    parse_mode не управляем, текст идёт сырым.
    """
    lines: list[str] = []
    for key, value in stats.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        elif isinstance(value, list | tuple):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  • {item}")
        else:
            lines.append(f"{key}: {value}")
    if not lines:
        return "(no data)"
    return "\n".join(lines)


def _stats_to_json(stats: dict[str, Any]) -> str:
    """Хелпер для тестов: стабильный JSON-вывод словаря."""
    return json.dumps(stats, ensure_ascii=False, sort_keys=True)


__all__ = ["AlertService"]
