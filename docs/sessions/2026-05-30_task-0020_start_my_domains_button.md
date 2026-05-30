---
date: 2026-05-30
task: TASK-0020
title: Срочный фикс — кнопка «Мои домены» в /start
author: claude
---

# TASK-0020: Срочный фикс — кнопка «Мои домены» в /start

## Цель

Кнопка «📋 Мои домены» в приветственном меню `/start` снова открывает список
доменов (как `/list`). Была сломана из-за дрейфа сигнатуры `cmd_list`.

## Проблема

- `handle_start_button` вызывал `cmd_list` без новых обязательных параметров
  `redis` и `state`, добавленных в TASK-0018 (email-intel UX)
- Отсутствие теста позволило этому дрейфу остаться незамеченным
- Рантайм `TypeError` при нажатии кнопки → ничего не происходило

## Выполнено

### Исправление

- **`src/bot/handlers/start.py`**:
  - Добавлен импорт `Redis` из `redis.asyncio`
  - В сигнатуру `handle_start_button` добавлены DI-параметры:
    - `state: FSMContext`
    - `redis: Redis[str]`
  - Ветке `action == "list"` передаются `redis=redis, state=state` в `cmd_list`

### Тесты

- **`tests/unit/test_start_handler.py`** — новый файл с 3 тестами:
  - `test_list_action_calls_cmd_list_with_all_args` — проверяет полный набор
    аргументов (message + 7 kwargs)
  - `test_settings_action_calls_cmd_settings` — проверяет, что settings не
    требует redis/state
  - `test_check_action_sends_prompt` — проверяет кнопку «Проверить домен»

## Инварианты (защищены тестами)

- ✅ Кнопка «Мои домены» вызывает `cmd_list` с полным набором аргументов:
  - `message` (позиционный)
  - `user`, `lang`, `arq_redis`, `limits`, `redis`, `state` (kwargs)
- ✅ Кнопка «Настройки» вызывает `cmd_settings` (без redis/state)
- ✅ Кнопка «Проверить домен» отправляет подсказку

## Проверки

- ✅ `pytest tests/unit/test_start_handler.py` — 3 passed
- ✅ `ruff check` — все проверки пройдены (исправлен порядок импортов)
- ✅ `black --check` — форматирование корректно
- ✅ `mypy src/bot/handlers/start.py` — Success: no issues found

## Following steps

- Коммит и PR
- Ручное тестирование в Telegram
- После merge — патч-релиз **v0.10.1**

## Файлы изменены

- `src/bot/handlers/start.py` — добавлены redis/state в сигнатуру и вызов
- `tests/unit/test_start_handler.py` — новый тестовый файл
- `handoff/tasks/TASK-0020-fix-start-my-domains-button.md` — статус claimed
