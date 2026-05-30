---
id: TASK-0027
title: Схема — toggles track_subdomains/notify_subdomain_* + per-user интервал + миграция (ADR 038)
status: open
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0026]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-30
---

# TASK-0027 — Схема мониторинга поддоменов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> `down_revision` сверить с актуальным alembic-head на свежем main.

## Цель

Добавить поля под per-domain opt-in мониторинг поддоменов и per-user интервал.
Параллель toggle'ам SSL/DNS/email (ADR 029/030/032/036).

## Изменения по файлам

- `src/db/models.py`:
  - `UserDomain.track_subdomains: Mapped[bool]` — `server_default=text("false")`
    (**важно: false**, не true; enumeration бьёт crt.sh — только явный opt-in).
  - `UserDomain.notify_subdomain_new: Mapped[bool]` — `server_default=text("true")`.
  - `UserDomain.notify_subdomain_removed: Mapped[bool]` — `server_default=text("true")`.
  - `UserDomain.subdomain_check_interval_override: Mapped[int | None]` — nullable
    (NULL → берём `User.subdomain_check_interval_days`; паттерн
    `notify_ssl_days_override`).
  - `User.subdomain_check_interval_days: Mapped[int]` — `server_default="7"`.
- Новая Alembic-миграция: `add_column` для пяти полей; дефолты — валидным SQL
  (`false`/`true`/`7`; урок TASK-0008). Синхрон модель↔миграция (без лишних
  server_default, anti-drift CLAUDE.md).

## Миграции БД

Требуется. Проверить применение и обратимость на **Postgres** (TASK-0009 smoke).

## Инварианты (защитить тестами)

- Миграция применяется на чистой БД и обратима (round-trip — CI TASK-0009).
- Модель ↔ БД синхронны; дефолты: `track_subdomains=false`,
  `notify_subdomain_new/removed=true`, `subdomain_check_interval_days=7`.

## Требования к тестам

- Модель-тест (наличие полей + дефолты). Моки со `spec`/`autospec`.

## Definition of Done

- [ ] 5 полей + миграция; синхрон модель↔миграция; дефолты корректны
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 038; образец — `track_ssl`/`notify_ssl_*`/`notify_ssl_days_override`
  (ADR 030), `User.notify_ssl_days_before`.
