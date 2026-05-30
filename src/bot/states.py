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


class ListSearchStates(StatesGroup):
    """FSM для ввода подстроки поиска в ``/list`` (Этап 9).

    После нажатия кнопки «🔍 Поиск» пользователь вводит подстроку, мы
    сохраняем её в ``list_state:{user_id}`` (Redis) и возвращаем первую
    страницу отфильтрованных результатов.
    """

    waiting_for_query = State()


class NotifyDaysStates(StatesGroup):
    """FSM для редактирования ``UserDomain.notify_days`` (Этап 11, ADR 029).

    После нажатия «📅 Изменить дни» в конфигураторе уведомлений
    пользователь вводит список через запятую. ``/default`` — сбросить
    override в NULL (использовать user-level настройки). ``/cancel`` —
    вернуться к конфигуратору без изменений. ``state.data`` хранит
    ``domain`` для возврата.
    """

    waiting_for_days = State()


class NotifySslDaysStates(StatesGroup):
    """FSM для редактирования ``UserDomain.notify_ssl_days_override``
    (Этап 12, ADR 030).

    Аналог ``NotifyDaysStates`` для SSL-сертификатов: позволяет задать
    свой набор дней «за сколько до истечения SSL предупреждать», или
    сбросить override (``/default``) и использовать
    ``User.notify_ssl_days_before``.
    """

    waiting_for_days = State()


class AwaitingDomainArg(StatesGroup):
    """FSM-flow для команд с обязательным доменом-аргументом (ADR 033).

    Когда пользователь шлёт ``/add``, ``/rmv``, ``/check``, ``/notify``,
    ``/unnotify`` или ``/wishlist`` БЕЗ аргумента, бот переводит сессию
    в это состояние и просит ввести домен следующим сообщением.

    FSM-data: ``{"cmd": str, "token_map": dict[str, str]}``.

    - ``cmd`` — какую команду выполнить после подтверждения. Хранится в
      FSM-data, а не в имени state'а, чтобы один callback-handler
      обслуживал все 6 команд.
    - ``token_map`` — ``{uuid_short: domain}``, потому что Telegram
      режет callback_data до 64 байт и длинный домен туда не влезет.
      Карта (а не одно значение) разрешает пользователю несколько раз
      ввести разные домены до подтверждения — старые токены становятся
      stale, но не падают.
    """

    waiting = State()


class NotifySubdomainIntervalStates(StatesGroup):
    """FSM для редактирования ``UserDomain.subdomain_check_interval_override``
    (TASK-0029, ADR 038).

    Позволяет задать свой интервал проверки поддоменов (дни), или сбросить
    override (``/default``) и использовать ``User.subdomain_check_interval_days``.
    """

    waiting_for_interval = State()
