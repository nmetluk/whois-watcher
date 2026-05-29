---
id: TASK-0015
title: Схема email_intel_cache + toggle'ы уведомлений (ADR 036)
status: done
milestone: v0.10.0
adr: 036
area: code
depends_on: [TASK-0012]
branch: task/0015-email-intel-schema
owner: claude
session: docs/sessions/2026-05-30_task-0015_email_intel_schema.md
pr: ""
created: 2026-05-29
---

# TASK-0015 — Схема email-intel (ADR 036)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> `down_revision` сверить с актуальным alembic-head на свежем main.

## Цель

Завести хранилище для email/policy-записей (MX/SPF/DKIM/DMARC) и per-domain
toggle'ы уведомлений — фундамент подсистемы ADR 036.

## Контекст

ADR 036: email-intel — **параллельная подсистема** (как SSL ADR 030 / DNS
ADR 032). Своя таблица `email_intel_cache`, keyed по `domain` (самому
домену/поддомену, ADR 035). Уведомления per-domain в стиле ADR 029.

## Изменения по файлам

- Новая Alembic-миграция: таблица `email_intel_cache` (PK/FK по `domain`/кэш-
  модели как у `dns_cache`/`ssl_cache`), поля под разобранные данные:
  MX (список host+priority, JSON/текст), SPF (raw + режим all), DMARC
  (policy/sp/pct), DKIM (найденные селекторы), `fetched_at`, `next_check_at`,
  `is_reachable`/флаг неответа, TTL-поля. Сверить набор полей с тем, как
  устроены `dns_cache`/`ssl_cache`.
- `src/db/models.py` — модель `EmailIntelCache` (зеркалит миграцию; FK,
  индексы обязательны).
- `src/db/models.py` (`UserDomain`) + миграция — toggle'ы `track_email`
  (default true) и `notify_email_change` (default true), по образцу
  `track_ssl`/`notify_ssl_*` (ADR 029).
- Репозиторий `src/db/repositories/` для `email_intel_cache` (get/upsert),
  по образцу dns/ssl-репозиториев. **Доступ к БД только через репозиторий.**

## Миграции БД

Требуется. Новая таблица + 2 boolean-колонки на `user_domains` с
`server_default`. **Внимание (урок TASK-0008):** строковые/булевы дефолты —
валидным SQL-литералом; проверить применение на **Postgres** (smoke-test
TASK-0009 уже в CI).

## Инварианты (защитить тестами)

- Миграция применяется на чистой БД и обратима (round-trip, ловит TASK-0009).
- Модель ↔ БД синхронны (нет лишних server_default vs модель).

## Требования к тестам

- `test_user_domain_model`/новый — наличие новых полей и дефолтов.
- Миграционный round-trip покрыт общим smoke-тестом (TASK-0009).

## Definition of Done

- [ ] Таблица + toggle'ы + репозиторий; модель синхронна с миграцией
- [ ] Миграция применяется на чистой БД (Postgres), обратима
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 036, ADR 030 (SSL как образец), ADR 029 (toggle'ы), ADR 032 (DNS)
