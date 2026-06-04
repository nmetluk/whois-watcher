"""Доставка ошибки on-demand проверки пользователю (TASK-0086).

Контекст: on-demand задачи (`check_subdomains`, `check_email_deep`,
`check_email_intel`, `check_dns`, `check_ssl`) при вызове с
``deliver_chat_id`` (кнопки whois-карточки, TASK-0075/0076) досылали
результат **только при успехе**. При фейле (crt.sh недоступен, DNS-сбой)
пользователь не получал ничего — «⏳ ищу…» и тишина, что неотличимо от
сломанной доставки (см. инцидент
``docs/sessions/2026-06-05_diagnosis-ondemand-email-prod.md``).

Этот помощник шлёт локализованное сообщение об ошибке. Никогда не бросает —
доставка ошибки не должна ронять задачу.
"""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

from src.locales import t
from src.utils.idn import from_punycode

logger = logging.getLogger(__name__)

#: kind → ключ локали. Отдельные тексты: пользователю важно, ЧТО именно
#: не удалось (поддомены / deep email / email / DNS / SSL).
_KIND_KEYS = {
    "subdomains": "tasks.deliver.failed.subdomains",
    "email_deep": "tasks.deliver.failed.email_deep",
    "email": "tasks.deliver.failed.email",
    "dns": "tasks.deliver.failed.dns",
    "ssl": "tasks.deliver.failed.ssl",
}


async def deliver_ondemand_failure(
    ctx: dict[str, Any],
    deliver_chat_id: int | None,
    deliver_lang: str | None,
    *,
    kind: str,
    domain: str,
) -> bool:
    """Дослать пользователю сообщение о фейле on-demand проверки.

    :param ctx: ARQ context (берём ``ctx["bot"]``)
    :param deliver_chat_id: чат для доставки; ``None`` → no-op (периодический
        запуск без кнопки — поведение не меняется)
    :param deliver_lang: язык локализации (``None`` → ru)
    :param kind: тип проверки (ключ из ``_KIND_KEYS``)
    :param domain: домен (punycode — конвертируется для отображения)
    :returns: True, если сообщение отправлено
    """
    if not deliver_chat_id:
        return False
    bot: Bot | None = ctx.get("bot")
    if bot is None:
        return False
    key = _KIND_KEYS.get(kind)
    if key is None:  # защита от опечатки в kind — лог, не падение
        logger.warning("Unknown on-demand failure kind %r for %s", kind, domain)
        return False
    try:
        await bot.send_message(
            deliver_chat_id,
            t(key, deliver_lang or "ru", domain=from_punycode(domain)),
        )
    except Exception as exc:
        logger.warning(
            "Failed to deliver on-demand failure (%s, %s) to %s: %s",
            kind,
            domain,
            deliver_chat_id,
            exc,
        )
        return False
    logger.info(
        "Delivered on-demand failure notice (%s) to chat %s for %s",
        kind,
        deliver_chat_id,
        domain,
    )
    return True
