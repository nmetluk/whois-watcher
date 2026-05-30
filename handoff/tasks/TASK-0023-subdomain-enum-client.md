---
id: TASK-0023
title: crt.sh-клиент + парсер/нормализация + ARQ-задача (ADR 037)
status: done
milestone: v0.11.0
adr: 037
area: code
depends_on: [TASK-0022]
branch: task/0023-subdomain-enum-client
owner: ""
session: docs/sessions/2026-05-30_task_0023_subdomain_enum_client.md
pr: "16"
created: 2026-05-30
completed: 2026-05-30
---

# TASK-0023 — crt.sh-клиент и enumeration (ADR 037)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Async-клиент к crt.sh, чистый парсер/нормализация выдачи и ARQ-задача
enumeration с записью в `subdomain_enum_cache` и graceful degradation.

## Контекст

ADR 037. crt.sh бывает медленным/нестабильным → запрос изолирован в ARQ-задаче.
HTTP через `aiohttp` (уже в зависимостях).

## Изменения по файлам

- Новый пакет `src/subdomains/` (по образцу `src/email_intel/`):
  - `client.py` — async GET `https://crt.sh/?q=%25.<registrable>&output=json`
    с таймаутом; обработка недоступности/таймаута/rate-limit (без исключения
    наружу — возвращаем «недоступно»).
  - `parser.py` — чистая функция: из JSON crt.sh достать `name_value`,
    развернуть многострочные, lowercase, punycode (`idna`), dedup, **отбросить
    wildcard** (`*.`), отбросить сам registrable; оставить только поддомены
    запрошенного registrable (PSL, ADR 035).
  - `scheduler.py` — расчёт `next_check_at` (TTL; под v0.12, но TTL уже нужен
    для кэша).
- `src/tasks/check_subdomains.py` — ARQ-задача: запрос → парс → upsert в кэш →
  (для команды) вернуть результат. Redis-guard от задвоения (как у других задач).
- `src/tasks/arq_config.py` — регистрация задачи.

## Миграции БД

Не требуется (использует схему TASK-0022).

## Инварианты (защитить тестами)

- Парсер — чистый, юнит-тесты: dedup, wildcard-фильтр, IDN/punycode, мусорный
  JSON, пустой ответ, отбрасывание самого registrable.
- crt.sh-недоступность → «недоступно», не исключение; всё async.

## Требования к тестам

- `tests/unit/test_subdomains_parser.py` (+ при необходимости клиент с моком
  HTTP). Моки — со `spec` (anti-drift, CLAUDE.md).

## Definition of Done

- [x] `src/subdomains/` + ARQ-задача; кэш заполняется; degradation работает
- [x] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [x] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 037; образец структуры — `src/email_intel/`, `src/dns/`.
