---
id: TASK-0030
title: Комплексный аудит v0.12 (мониторинг поддоменов, ADR 037+038)
status: done
milestone: v0.12.0
adr: 038
area: audit
depends_on: [TASK-0029]
branch: ""
owner: architect
session: handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md
pr: ""
created: 2026-05-30
completed: 2026-05-31
---

> **Итог (2026-05-31):** аудит проведён, отчёт —
> `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`. Вердикт —
> **fix-then-go**: тег v0.12.0 после закрытия 🟠 TASK-0033/0034 (тест-гэпы
> fan-out и success→enqueue). 🟡 TASK-0035 (N+1 + дедуп toggle'ов) — follow-up.

# TASK-0030 — Комплексный аудит v0.12 (ADR 038)

> Отдельная сессия после крупного раздела (конвенция CLAUDE.md). Отчёт —
> `handoff/audits/AUDIT-2026-..-v0-12-subdomain-monitor.md`.

## Цель

Независимая проверка подсистемы мониторинга поддоменов (ADR 037 + 038) перед
тегом v0.12.0.

## Объём аудита

- **Безопасность**: нет логирования чувствительного (ADR 019); fan-out не течёт
  чужие домены другим пользователям; нагрузка на crt.sh ограничена (min-интервал
  floor 1д, кэш per-registrable, redis-guard).
- **Архитектура**: подсистема параллельна (как SSL/DNS); реконсиляция shared-cache
  vs per-user интервала корректна; baseline (`old=None`) не алертит.
- **Перф**: scheduler-выборка `get_due_for_check` использует индекс
  `next_check_at`; bootstrap идемпотентен; нет N+1 в fan-out.
- **Тесты**: diff (baseline/new/removed), scheduler (only track_subdomains+
  not muted), notify (toggles/mute/дедуп), FSM интервала, миграция round-trip.
- **Зависимости**: новых внешних нет.
- **Кроссплатформенность**: служебка через `scripts/handoff.py` (stdlib).
- **Anti-drift**: моки со `spec`/`autospec`; миграции на Postgres.

## Definition of Done

- [ ] Отчёт в `handoff/audits/` с severity-классификацией находок
- [ ] 🔴/🟠 находки заведены отдельными таск-файлами (если есть)
- [ ] Вердикт: можно ли тегать v0.12.0
- [ ] `handoff.py validate` OK; PR (docs)

## Ссылки

- ADR 037, ADR 038; шаблон аудита; AUDIT v0.9.0 как образец формата.
