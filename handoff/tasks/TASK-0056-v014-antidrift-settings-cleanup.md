---
id: TASK-0056
title: v0.14 cleanup — подключить no_expiry_tlds + sweep getattr-на-ORM
status: open
milestone: v0.14.1
adr: ""
area: code
depends_on: [TASK-0051]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0056 — v0.14 cleanup (🟢, опционально)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🟢 follow-up из аудита `AUDIT-2026-06-08-v0-14-stabilization.md`. **Не блокер
> тега v0.14.0.**

## Цель

Закрыть два 🟢-нита аудита v0.14: инертный settings-список и `getattr`-на-ORM.

## Объём (каждый — отдельный коммит)

1. **`Settings.no_expiry_tlds` инертен.** Поле объявлено, но `format_whois_response`/
   `format_list_row` зовут `is_expiry_hidden_by_registry(domain)` без проброса
   settings → используется дефолт `KNOWN_NO_EXPIRY_SUFFIXES={"de"}`. **Решение
   (выбрать одно):** либо прокинуть `settings.no_expiry_tlds` в форматтеры
   (через параметр/контекст) и передавать в `is_expiry_hidden_by_registry(...,
   no_expiry_tlds=...)`; либо убрать поле из Settings и оставить
   `KNOWN_NO_EXPIRY_SUFFIXES` единственной точкой правды. Не держать две.
2. **Sweep `getattr`-на-ORM** (anti-drift, CLAUDE.md): заменить на прямой
   типизированный доступ там, где объект гарантированно не-None:
   - `src/services/formatters.py` `format_email_deep` →
     `cache.fetched_at` (cache не-None после верхнего гарда).
   - `src/services/csv_io.py` (`cache.expires_at`) и
     `src/services/whois_facade.py` (`cache.expires_at`) — типизировать и
     обращаться напрямую (или `cache.expires_at if cache else None`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Поведение DENIC-значка не меняется (если выбран settings-путь — тест, что
  список из настроек реально применяется).
- `grep "getattr(.*cache" src/` — пусто (или только обоснованные случаи).
- mypy чист.

## Definition of Done

- [ ] Пункты 1–2; тесты обновлены
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-06-08-v0-14-stabilization.md`
- TASK-0051 (DENIC), CLAUDE.md → anti-drift
