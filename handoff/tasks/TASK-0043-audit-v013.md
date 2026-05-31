---
id: TASK-0043
title: Комплексный аудит v0.13 (deep email + on-demand views, ADR 040)
status: done
milestone: v0.13.0
adr: 040
area: audit
depends_on: [TASK-0041, TASK-0042]
branch: ""
owner: architect
session: handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md
pr: ""
created: 2026-05-31
completed: 2026-06-02
---

> **Итог (2026-06-02):** аудит проведён архитектором, отчёт —
> `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`. Вердикт —
> **fix-then-go**: перед тегом закрыть 🟠 **TASK-0047** (SSRF MTA-STS + узкий
> TXT-матч). 🟡/🟢 → **TASK-0048** (fast-follow, v0.13.1). Фич-код полный,
> краш KeyError уже закрыт (0046).

# TASK-0043 — Комплексный аудит v0.13 (ADR 040)

> Отдельная сессия после крупного раздела (конвенция CLAUDE.md). Отчёт —
> `handoff/audits/AUDIT-2026-..-v0-13-deep-email.md`. Образец формата —
> `AUDIT-2026-05-31-v0-12-subdomain-monitor.md`.

## Цель

Независимая проверка углублённого почтового слоя и on-demand deep-views
(ADR 040) перед тегом v0.13.0.

## Объём аудита

- **Безопасность:** MTA-STS HTTP-fetch — timeout, **no-redirect**, лимит
  размера тела, нет SSRF-вектора (URL строго `mta-sts.<domain>`); нет
  логирования чувствительного (ADR 019); `html.escape` во всех новых выводах.
- **Архитектура:** deep email — строго on-demand, без фонового трафика;
  поддомены-кнопка переиспользует поток ADR 037, не дублирует; кэш deep с TTL.
- **Перф:** SPF-резолвер не зацикливается (защита от рекурсии), лимит 10
  lookups соблюдён; redis-guard на on-demand задачах; нет N+1.
- **Тесты + anti-drift:** парсеры/резолвер — чистые с инъекцией DNS/HTTP;
  моки со `spec`/`autospec`; callback'и ≤64 байт; миграция `email_deep_cache`
  на Postgres (round-trip).
- **UX:** фикс свежести работает (пустой кэш → плейсхолдер, не пусто);
  локали ru/en паритетны.
- **Кроссплатформенность:** служебка через `scripts/handoff.py`.

## Definition of Done

- [ ] Отчёт в `handoff/audits/` с severity-классификацией
- [ ] 🔴/🟠 находки — отдельными таск-файлами (если есть)
- [ ] Вердикт: можно ли тегать v0.13.0
- [ ] `handoff.py validate` OK; PR (docs)

## Ссылки

- ADR 040; шаблон аудита; AUDIT v0.12 как образец.
- Связанные: TASK-0038…0042 (реализация), TASK-0044 (релиз)
