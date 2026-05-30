---
id: TASK-0020
title: Срочный фикс — кнопка «Мои домены» в /start не работает
status: open
milestone: v0.10.1
adr: ""
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-30
---

# TASK-0020 — 🔴 СРОЧНО: кнопка «Мои домены» в /start не работает

> Найдено ручным тестом в Telegram. Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Кнопка «📋 Мои домены» в приветственном меню `/start` снова открывает список
доменов (как `/list`).

## Контекст / корень проблемы (диагностировано)

Дрейф сигнатуры — путь start-кнопка→`cmd_list` не обновили и не покрыли тестом.

- `src/bot/handlers/start.py`, `handle_start_button`, ветка `action == "list"`:
  ```python
  await cmd_list(query.message, user=user, lang=lang, arq_redis=arq_redis, limits=limits)
  ```
- `cmd_list` (`src/bot/handlers/list_domains.py:96`) требует **ещё два**
  обязательных параметра (добавлены под FSM/сброс поиска):
  ```python
  async def cmd_list(message, user, lang, arq_redis, limits,
                     redis: Redis[str], state: FSMContext) -> None
  ```
- Вызов не передаёт `redis` и `state` → **`TypeError` в рантайме** → callback
  падает → кнопка «Мои домены» ничего не делает.
- Вдобавок сам `handle_start_button` сейчас не получает `redis`/`state` через DI
  (его сигнатура: `query, callback_data, user, lang, arq_redis, limits`).

Ветки `check` и `settings` той же функции — **исправны** (`cmd_settings(message,
user, lang)` совпадает по сигнатуре; `check` просто шлёт подсказку). Трогать их
не нужно.

## Изменения по файлам

- `src/bot/handlers/start.py`, `handle_start_button`:
  - Добавить в сигнатуру инъекции `state: FSMContext` и `redis: Redis[str]`
    (aiogram прокинет через DI, как в других хэндлерах — см. `cmd_list`/
    `list_domains.py`).
  - В ветке `action == "list"` передать их:
    ```python
    await cmd_list(query.message, user=user, lang=lang, arq_redis=arq_redis,
                   limits=limits, redis=redis, state=state)
    ```
  - Импорты: `FSMContext` из `aiogram.fsm.context`, `Redis` из `redis.asyncio`
    (сверить, как импортируют другие хэндлеры).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Нажатие «Мои домены» (callback `StartAction(action="list")`) вызывает
  `cmd_list` с ПОЛНЫМ набором аргументов, без `TypeError`.
- Ветки `check` и `settings` продолжают работать.

## Требования к тестам

- Новый тест в `tests/` (integration или unit с aiogram-DI) на
  `handle_start_button`: для `action="list"` — `cmd_list` вызывается успешно
  (мокать `cmd_list`/зависимости со `spec`, чтобы рассинхрон аргументов падал).
  Покрыть также `settings`. Именно отсутствие этого теста скрыло баг.

## Definition of Done

- [ ] Кнопка «Мои домены» в `/start` открывает список (ручная проверка в Telegram)
- [ ] Тест на `handle_start_button` (list/settings) добавлен и зелёный
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR открыт, CI зелёный
- [ ] После merge — патч-релиз **v0.10.1**

## Ссылки

- `src/bot/handlers/start.py` (`handle_start_button`),
  `src/bot/handlers/list_domains.py` (`cmd_list`)
