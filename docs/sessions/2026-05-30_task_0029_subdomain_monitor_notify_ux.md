# Сессия 2026-05-30: TASK-0029 — Уведомления + UX мониторинга поддоменов (ADR 038)

## Задача

TASK-0029 — fan-out уведомлений о diff + конфигурирование мониторинга в карточке `/whois`.

## Выполнено

### 1. `src/tasks/notify_subdomain_changes.py` (новый)

ARQ-задача для уведомлений о новых/исчезнувших поддоменах:
- Fan-out: рассылает **всем** подписчикам registrable с `track_subdomains=true`
- Honoring: `notify_subdomain_new`, `notify_subdomain_removed`, `is_muted`
- Дедуп одному пользователю
- Текст security-стиль: «🆕 новый поддомен» / «➖ исчез поддомен»

### 2. `src/db/repositories/domains.py`

Добавлен метод `get_subscribers_by_registrable`:
- Фильтрация по `registrable_domain` и опционально `track_subdomains`

### 3. `src/tasks/arq_config.py`

- Импорт `notify_subdomain_changes`
- Добавлен в `_build_functions`

### 4. `src/bot/keyboards.py`

- `_TOGGLE_FIELDS`: добавлены 3 поля для поддоменов
- `notify_config_keyboard`: кнопка «🌐 Изменить интервал проверки поддоменов»

### 5. `src/bot/states.py`

Добавлен `NotifySubdomainIntervalStates` FSM-класс для редактирования интервала

### 6. `src/bot/handlers/notify_config.py`

- Импорт `NotifySubdomainIntervalStates`
- Callback `edit_subdomain_interval` → установка FSM-состояния
- FSM-обработчики: `/default` (сброс), ввод числа (валидация ≥1)

### 7. `src/locales/ru.py`

**Toggle-подписи:**
- `notify_config.type.track_subdomains`
- `notify_config.type.subdomain_new`
- `notify_config.type.subdomain_removed`

**FSM интервала:**
- `notify_config.edit_subdomain_interval`
- `notify_config.subdomain_interval_prompt`
- `notify_config.subdomain_interval_saved_override/default`
- `notify_config.subdomain_interval_invalid`

**Уведомления:**
- `notifications.subdomain.new_header`
- `notifications.subdomain.removed_header`
- `notifications.subdomain.and_more`

### 8. `src/locales/en.py`

Аналогичные ключи на английском

### 9. Тесты

**`tests/unit/test_notify_subdomain_changes.py`** (новый):
- `test_empty_diff_does_nothing` — ранний return
- `test_function_exists_and_callable` — базовая проверка

**`tests/unit/test_locales.py`:**
- `test_all_ru_keys_present_in_en` — PASSED (все ru ключи есть в en)

### 10. Проверки

- `ruff check --fix` — OK
- `black` — OK
- `mypy src` — OK
- `pytest` — 2 passed (notify_subdomain_changes), 8 passed (locales)
- `handoff.py validate` — OK

## Следующие шаги

TASK-0029 → TASK-0030 (комплексный аудит v0.12).

## Артефакты

- Ветка: `task/0029-subdomain-monitor-notify-ux`
- PR: (будет открыт после коммита)
