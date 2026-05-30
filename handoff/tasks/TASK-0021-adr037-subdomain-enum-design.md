---
id: TASK-0021
title: Дизайн ADR 037 — subdomain enumeration через CT-логи (v0.11)
status: done
milestone: v0.11.0
adr: 037
area: docs
depends_on: []
branch: ""
owner: architect
session: docs/decisions.md
pr: ""
created: 2026-05-30
---

# TASK-0021 — Дизайн ADR 037 (subdomain enumeration, v0.11)

Архитекторская design-задача. ADR 037 написан в `docs/decisions.md`.

## Итог (решения)

- Источник — **CT-логи через crt.sh** (бесплатно, пассивно).
- v0.11 = **on-demand** команда `/subdomains <domain>`: read-only список +
  **opt-in** на отслеживание (через существующий `/add`-путь). Авто-добавления
  нет (лимит 50k).
- Запрос через **ARQ-задачу** (crt.sh медленный) + кэш `subdomain_enum_cache`
  (per-registrable, TTL) + graceful degradation при недоступности crt.sh.
- Периодический мониторинг новых поддоменов + алерты → **v0.12 (ADR 038)**.

## Разбивка на исполнительские таски

- **TASK-0022** — схема `subdomain_enum_cache` + миграция.
- **TASK-0023** — crt.sh-клиент + парсер/нормализация + ARQ-задача.
- **TASK-0024** — UX: команда `/subdomains` + opt-in + локали.

## Ссылки

- ADR 037 в `docs/decisions.md`; ADR 035 (PSL/поддомены), ADR 011 (лимит 50k).
