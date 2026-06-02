---
id: TASK-0050
title: FSM MemoryStorage → RedisStorage (ADR 041)
status: open
milestone: v0.14.0
adr: 041
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-04
---

# TASK-0050 — FSM → RedisStorage (ADR 041)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 041 в `docs/decisions.md`.

## Цель

Перевести FSM-хранилище aiogram с `MemoryStorage` на `RedisStorage` (тот же
Redis, что ARQ) с `state_ttl`, чтобы state переживал рестарт бота и заброшенные
флоу истекали по TTL.

## Контекст / корень проблемы

`src/bot/app.py` собирает `Dispatcher(storage=MemoryStorage())`. State теряется
при каждом деплое; настоящего TTL нет (эмулируется `clear_state_on_command`).
См. ADR 041.

## Готовые факты (сверено архитектором — следовать)

- `from aiogram.fsm.storage.redis import RedisStorage` **доступен**; `redis>=5.0`
  уже в `pyproject.toml`. **Новых зависимостей не нужно.**
- Готовый конфиг: `settings.redis_url` (= `redis://{redis_host}:{redis_port}/{redis_db}`).
  Использовать `RedisStorage.from_url(settings.redis_url, state_ttl=…, data_ttl=…)`.
- Дефолтный `DefaultKeyBuilder` aiogram уже даёт префикс `fsm` — **не конфликтует**
  с ARQ-ключами (`arq:`). Достаточно дефолта; явный `key_builder` опционален.
- `state_ttl`/`data_ttl` принимают `int` секунд или `timedelta`.

## Изменения по файлам

- `src/bot/app.py` (`build_dispatcher`) — заменить `MemoryStorage()` на
  `RedisStorage.from_url(settings.redis_url, state_ttl=<ttl>, data_ttl=<ttl>)`.
  ⚠️ **Тесты тоже зовут `build_dispatcher`** (docstring «MemoryStorage в
  проде/тестах»). Чтобы не тянуть Redis в юнит-тестах сборки — сделать
  `storage` **инъектируемым параметром**: `build_dispatcher(..., storage:
  BaseStorage | None = None)`; если `None` → RedisStorage из конфига (прод),
  тесты/фикстуры передают `MemoryStorage()` явно. Обновить вызовы.
- `src/config/settings.py` — `redis_fsm_ttl: int = Field(300, ge=1)` (сек).
- `clear_state_on_command` middleware — **оставить** (решает другую задачу).
- (опц.) `docs/architecture.md` — обновить упоминание MemoryStorage.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- State, записанный в одном экземпляре storage, виден в новом (имитация
  рестарта) — интеграционно через `fakeredis`/реальный Redis.
- Заброшенный state истекает по `state_ttl`.
- FSM-ключи неймспейснуты (префикс), не конфликтуют с ARQ-ключами.
- Существующие FSM-флоу не регрессируют.

## Требования к тестам

- Интеграционный тест storage на `fakeredis` (persist/restart + TTL).
- Юнит-тесты затронутых хэндлеров остаются зелёными (моки со `spec`).

## Definition of Done

- [ ] Storage переведён на Redis; TTL + namespacing
- [ ] **Полный `pytest` зелёный** (вкл. storage-тест); `ruff`/`black`/`mypy`
- [ ] Реальная проверка флоу в Telegram + рестарт бота — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 041: `docs/decisions.md`; `src/bot/app.py`
