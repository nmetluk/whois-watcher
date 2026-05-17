"""Тест: inline-кнопка «📥 CSV» в /list реально шлёт файл (Этап 9 fix).

Это была заглушка — кнопка отвечала «используйте /csv» вместо экспорта.
Тест проверяет, что callback ``ListPage(action='csv')`` вызывает
``send_user_csv_file`` и в итоге доходит до ``answer_document`` с
правильным именем файла.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.handlers.list_domains import on_list_page
from src.bot.keyboards import ListPage as ListPageCb


def _async_cm(session: object) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


@pytest.mark.asyncio
async def test_csv_button_sends_document(monkeypatch: pytest.MonkeyPatch) -> None:
    """ListPage(action='csv') → answer_document с CSV-файлом."""
    user = MagicMock()
    user.id = 42

    message = MagicMock()
    message.answer = AsyncMock()
    message.answer_document = AsyncMock()

    query = MagicMock()
    query.answer = AsyncMock()
    query.message = message
    # Чтобы isinstance(query.message, Message) прошёл, патчим isinstance в модуле.
    # Проще — добавим маркер класса.
    from aiogram.types import Message

    query.message = MagicMock(spec=Message)
    query.message.answer = AsyncMock()
    query.message.answer_document = AsyncMock()

    # Мокаем БД-репозиторий и генератор CSV.
    domain_repo_mock = AsyncMock()
    domain_repo_mock.count_by_user = AsyncMock(return_value=3)

    @asynccontextmanager
    async def fake_session():
        yield AsyncMock()

    monkeypatch.setattr("src.bot.handlers.csv_export.get_session", fake_session)
    monkeypatch.setattr("src.bot.handlers.list_domains.get_session", fake_session)
    monkeypatch.setattr(
        "src.bot.handlers.csv_export.DomainRepository",
        lambda _s: domain_repo_mock,
    )

    csv_payload = (b"domain,note\nexample.com,\n", 3)
    with patch(
        "src.bot.handlers.csv_export.generate_user_csv",
        new=AsyncMock(return_value=csv_payload),
    ):
        await on_list_page(
            query=query,
            callback_data=ListPageCb(action="csv", page=0),
            user=user,
            lang="ru",
            arq_redis=MagicMock(),
            limits=MagicMock(),
            redis=MagicMock(),
        )

    # answer был, чтобы убрать loading-state у кнопки.
    query.answer.assert_awaited()
    # answer_document вызвался — файл реально отправлен.
    query.message.answer_document.assert_awaited_once()
    call_kwargs = query.message.answer_document.await_args
    document_arg = call_kwargs.args[0]
    # filename следует шаблону domains_YYYY-MM-DD.csv
    assert document_arg.filename.startswith("domains_")
    assert document_arg.filename.endswith(".csv")


@pytest.mark.asyncio
async def test_csv_button_empty_portfolio_sends_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Если у пользователя 0 доменов — answer_document НЕ вызывается,
    идёт ``csv.empty``-сообщение."""
    from aiogram.types import Message

    query = MagicMock()
    query.answer = AsyncMock()
    query.message = MagicMock(spec=Message)
    query.message.answer = AsyncMock()
    query.message.answer_document = AsyncMock()

    user = MagicMock()
    user.id = 7

    domain_repo_mock = AsyncMock()
    domain_repo_mock.count_by_user = AsyncMock(return_value=0)

    @asynccontextmanager
    async def fake_session():
        yield AsyncMock()

    monkeypatch.setattr("src.bot.handlers.list_domains.get_session", fake_session)
    monkeypatch.setattr(
        "src.bot.handlers.csv_export.DomainRepository",
        lambda _s: domain_repo_mock,
    )

    await on_list_page(
        query=query,
        callback_data=ListPageCb(action="csv", page=0),
        user=user,
        lang="ru",
        arq_redis=MagicMock(),
        limits=MagicMock(),
        redis=MagicMock(),
    )

    query.message.answer.assert_awaited_once()  # «У вас нет доменов для экспорта»
    query.message.answer_document.assert_not_called()
