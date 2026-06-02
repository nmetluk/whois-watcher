---
id: TASK-0050
title: FSM MemoryStorage → RedisStorage (ADR 041)
status: claimed
milestone: v0.14.0
adr: 041
area: code
depends_on: []
branch: task/0050-fsm-redisstorage
owner: grok-4.3
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

## Изменения по файлам

- `src/bot/app.py` — `Dispatcher(storage=RedisStorage.from_url(<redis_url>,
  state_ttl=…, data_ttl=…))` (или через готовый `Redis`-клиент). Namespacing
  ключей (`key_builder`/префикс `fsm:`), чтобы не пересекаться с ARQ/кэшем.
- `src/config/settings.py` — `REDIS_FSM_TTL` (дефолт 300 c), если нужен конфиг;
  переиспользовать существующий Redis URL из настроек.
- `pyproject.toml` — проверить, что redis-экстра aiogram доступна (redis уже в
  стеке через ARQ; добавить `aiogram[redis]`/зависимость только если её нет).
- `clear_state_on_command` middleware — **оставить** (другая задача).

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
