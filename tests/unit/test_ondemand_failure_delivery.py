"""Тесты ``deliver_ondemand_failure`` (TASK-0086).

Контекст: on-demand задачи при фейле молчали — пользователь не отличал
«crt.sh упал» от «доставка сломалась» (инцидент 2026-06-05). Помощник шлёт
локализованное сообщение об ошибке.

Правила CLAUDE.md: ``t()`` — настоящий (рендер-тест шаблонов с {domain});
бот — ``AsyncMock(spec=Bot)``, а не голый mock.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot

from src.tasks._ondemand import _KIND_KEYS, deliver_ondemand_failure

pytestmark = pytest.mark.asyncio


def _ctx(bot: Any) -> dict[str, Any]:
    return {"bot": bot}


async def test_sends_localized_message_with_domain() -> None:
    bot = AsyncMock(spec=Bot)
    sent = await deliver_ondemand_failure(
        _ctx(bot), 12345, "ru", kind="subdomains", domain="example.com"
    )
    assert sent is True
    bot.send_message.assert_awaited_once()
    chat_id, text = bot.send_message.await_args.args
    assert chat_id == 12345
    assert "example.com" in text
    assert "crt.sh" in text  # реальный t(), не мок


@pytest.mark.parametrize("kind", sorted(_KIND_KEYS))
@pytest.mark.parametrize("lang", ["ru", "en"])
async def test_all_kinds_render_via_real_t(kind: str, lang: str) -> None:
    """Каждый kind рендерится настоящим t() в обеих локалях (урок TASK-0046)."""
    bot = AsyncMock(spec=Bot)
    sent = await deliver_ondemand_failure(
        _ctx(bot), 1, lang, kind=kind, domain="xn--d1acufc.xn--p1ai"
    )
    assert sent is True
    text = bot.send_message.await_args.args[1]
    assert "домен.рф" in text  # from_punycode применён
    assert "{domain}" not in text  # placeholder подставлен


async def test_no_chat_id_is_noop() -> None:
    """Периодический запуск (без кнопки) — поведение не меняется."""
    bot = AsyncMock(spec=Bot)
    sent = await deliver_ondemand_failure(_ctx(bot), None, "ru", kind="dns", domain="example.com")
    assert sent is False
    bot.send_message.assert_not_awaited()


async def test_no_bot_in_ctx_is_noop() -> None:
    sent = await deliver_ondemand_failure({}, 1, "ru", kind="ssl", domain="example.com")
    assert sent is False


async def test_unknown_kind_logs_not_raises() -> None:
    bot = AsyncMock(spec=Bot)
    sent = await deliver_ondemand_failure(_ctx(bot), 1, "ru", kind="nope", domain="example.com")
    assert sent is False
    bot.send_message.assert_not_awaited()


async def test_send_failure_does_not_raise() -> None:
    """Доставка ошибки не должна ронять задачу (например, бот заблокирован)."""
    bot = AsyncMock(spec=Bot)
    bot.send_message.side_effect = RuntimeError("blocked by user")
    sent = await deliver_ondemand_failure(
        _ctx(bot), 1, "en", kind="email_deep", domain="example.com"
    )
    assert sent is False
