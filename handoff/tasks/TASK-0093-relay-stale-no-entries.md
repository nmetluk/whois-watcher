---
id: TASK-0093
title: 🟡 RU-relay/VDS — выяснить, почему «No entries» для зарегистрированного домена (и кэш relay)
status: open
milestone: v0.16.1
adr: 028
area: infra
depends_on: [TASK-0091]
branch: — (диагностика на VDS; в git идёт только отчёт)
owner: —
session: docs/sessions/<дата>_task-0093-relay-stale-no-entries.md
pr: —
created: 2026-06-07
---

# TASK-0093 — RU-relay: stale «No entries» (ADR 028)

> Из отчёта TASK-0091: proxy отдавал кэшированный «No entries found» от
> `whois_ru_upstream` для зарегистрированного discozavr.ru. Бот теперь
> защищён RDAP-верификацией (TASK-0092, ADR 045), но первоисточник надо
> понять и вылечить.

## Шаги (на VDS relay + прод-хосте)

1. С VDS напрямую: `whois -h whois.tcinet.ru discozavr.ru` — что отвечает
   TCI сейчас? (ожидаем REGISTERED). Если «No entries» — лаг/блок TCI
   для IP VDS → зафиксировать, попробовать с другого IP.
2. Есть ли у relay собственный кэш? Конфиг/код relay на VDS: TTL,
   условия инвалидации. Если кэширует негативные ответы — сократить
   TTL негативных (рекомендация: ≤1ч против 24ч позитивных).
3. Проверить логи relay за период инцидента: что он отдавал proxy.
4. На прод-хосте: TTL негативных ответов в proxy gateway — отдельный
   короткий TTL для «no_data»/«No entries» (рекомендация: ≤1ч).

## DoD

- [ ] Отчёт в docs/sessions/: ответы TCI с VDS, устройство кэшей relay и
      proxy, применённые изменения TTL (если были)
- [ ] Негативные ответы кэшируются заметно короче позитивных (или
      обоснование, почему нет)
- [ ] `handoff.py done TASK-0093` + push
