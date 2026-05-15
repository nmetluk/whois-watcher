"""Заглушки задач уведомлений (Этап 5).

Эти функции уже регистрируем в ARQ, чтобы их можно было ``enqueue_job`` из
``check_domain``. Реальная отправка сообщений и шаблоны — на Этапе 5.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def send_change_notice(
    ctx: dict[str, Any],
    user_id: int,
    domain: str,
    change_type: str,
    old_value: object,
    new_value: object,
) -> None:
    """Заглушка уведомления о смене статуса (ADR 012).

    На Этапе 4 только логируем — реальная отправка через ``bot.send_message``
    с локализованным шаблоном появится на Этапе 5.
    """
    del ctx
    logger.info(
        "send_change_notice (stub): user=%s domain=%s type=%s %r -> %r",
        user_id,
        domain,
        change_type,
        old_value,
        new_value,
    )


async def send_problem_notice(ctx: dict[str, Any], user_id: int, domain: str) -> None:
    """Заглушка уведомления о длительных проблемах WHOIS (ADR 019).

    Триггерится воркером ``check_domain`` после ``FAIL_THRESHOLD_FOR_USER_NOTICE``
    неудач подряд и старого ``last_successful_fetch_at``.
    """
    del ctx
    logger.info("send_problem_notice (stub): user=%s domain=%s", user_id, domain)
