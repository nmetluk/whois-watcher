---
id: TASK-0026
title: Дизайн ADR 038 — мониторинг новых поддоменов + алерты (v0.12)
status: done
milestone: v0.12.0
adr: 038
area: docs
depends_on: [TASK-0025]
branch: ""
owner: architect
session: docs/decisions.md
pr: ""
created: 2026-05-30
completed: 2026-05-30
---

# TASK-0026 — Дизайн ADR 038 (v0.12)

## Цель

Спроектировать периодический мониторинг новых/исчезнувших поддоменов поверх
`subdomain_enum_cache` (ADR 037), по образцу SSL/DNS-подсистем.

## Результат

ADR 038 записан в `docs/decisions.md`. Ключевые решения:

- Opt-in per-domain `track_subdomains` (**default false**, в отличие от
  track_ssl/dns/email).
- Сигнал: новые + исчезнувшие (`notify_subdomain_new` / `notify_subdomain_removed`,
  оба default true).
- Частота — per-user `User.subdomain_check_interval_days` (default 7) +
  per-domain override (`NULL` → user).
- Shared-cache vs per-user: scheduler `next_check_at` per registrable =
  `now + min(интервалов подписчиков)` (floor 1д) + adaptive backoff.
- Scheduler по образцу `ssl_scheduler_tick`; diff `compute_subdomain_diff`
  (baseline `old=None` → пусто); fan-out `notify_subdomain_changes`.

## Исполнительская цепочка

TASK-0027 (схема) → 0028 (diff + scheduler) → 0029 (уведомления + UX) →
0030 (комплексный аудит v0.12). После 0030 — релиз v0.12.0.

## Ссылки

- ADR 038, ADR 037 (enumeration), ADR 030 (SSL — образец подсистемы/scheduler/diff).
