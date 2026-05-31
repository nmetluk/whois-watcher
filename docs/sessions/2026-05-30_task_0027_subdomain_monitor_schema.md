# Сессия 2026-05-30: TASK-0027 — Схема мониторинга поддоменов (ADR 038)

## Задача

TASK-0027 — добавление 5 полей в БД для per-domain opt-in мониторинга поддоменов
и per-user интервала проверки (ADR 038).

## Выполнено

### 1. Модель `src/db/models.py`

Добавлены 5 полей:

**User:**
- `subdomain_check_interval_days: Mapped[int]` — default 7 (пер-user интервал)

**UserDomain:**
- `track_subdomains: Mapped[bool]` — default false (opt-in, т.к. enumeration бьёт crt.sh)
- `notify_subdomain_new: Mapped[bool]` — default true (алерт на новые поддомены)
- `notify_subdomain_removed: Mapped[bool]` — default true (алерт на исчезнувшие)
- `subdomain_check_interval_override: Mapped[int | None]` — nullable (per-domain override)

### 2. Миграция Alembic

Создан файл `migrations/versions/20260530_0001_add_subdomain_monitor_toggles_and_user_interval.py`:

- `down_revision: 20260530_subdomain_enum`
- 5 `add_column` операций с валидными SQL-дефолтами (`false`/`true`/`7`)
- Reversible: downgrade удаляет в обратном порядке

### 3. Тесты `tests/unit/test_user_domain_model.py`

Добавлен класс `TestSubdomainMonitorFields` с 7 тестами:
- `test_user_subdomain_check_interval_days_exists`
- `test_user_domain_track_subdomains_exists`
- `test_user_domain_notify_subdomain_new_exists`
- `test_user_domain_notify_subdomain_removed_exists`
- `test_user_domain_subdomain_check_interval_override_exists`
- `test_model_instantiation_with_subdomain_fields`
- `test_model_instantiation_with_custom_interval`

Все тесты проверяют только наличие полей и базовую инстанциацию — без `autospec`,
т.к. это простые поля ORM без бизнес-логики.

### 4. Проверки

- `ruff check src tests` — OK
- `black --check` → `black` (переформатирован 1 файл) — OK
- `mypy src` — OK
- `pytest tests/unit/test_user_domain_model.py` — 11 passed

## Следующие шаги

TASK-0027 → TASK-0028 (diff + scheduler), TASK-0029 (notify UX), TASK-0030 (audit v0.12).

## Артефакты

- Ветка: `task/0027-subdomain-monitor-schema`
- Миграция: `20260530_0001_add_subdomain_monitor_toggles_and_user_interval.py`
- PR: (будет открыт после коммита)
