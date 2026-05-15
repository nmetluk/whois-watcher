"""FSM-состояния бота (aiogram 3.x).

Состояния — для команд, требующих многошагового ввода: ``/download``
(ожидание файла, подтверждение импорта) и ``/settings`` (ручной ввод
часового пояса или списка дней).

``/delete_me`` НЕ использует FSM (см. ADR 017): подтверждение через
Redis-флаг ``delete_pending:{user_id}`` с TTL.
"""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DownloadStates(StatesGroup):
    """FSM для команды ``/download`` (массовый импорт)."""

    waiting_for_file = State()
    confirming_import = State()


class SettingsStates(StatesGroup):
    """FSM для ручного ввода значений настроек.

    Используется, когда пользователь нажал кнопку «Ввести вручную» в
    submenu таймзоны или дней напоминаний.
    """

    waiting_for_timezone = State()
    waiting_for_notify_days = State()
