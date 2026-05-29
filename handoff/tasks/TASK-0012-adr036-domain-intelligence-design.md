---
id: TASK-0012
title: Дизайн ADR 036 — domain intelligence v0.10 (MX/SPF/DKIM/DMARC, subdomain enum)
status: open
milestone: v0.10.0
adr: 036
area: docs
depends_on: [TASK-0008]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0012 — Дизайн ADR 036 (domain intelligence v0.10)

> Forward-задача (планирование). Выполняет **архитектор** в отдельной
> сессии **после** того как миграция v0.9.0 починена (TASK-0008 смержен) и
> тег v0.9.0 выпущен. Перед стартом: `git pull --rebase origin main`.

## Цель

Сформулировать ADR 036 для следующего раздела — domain intelligence:
почтовые/политики-записи (MX, SPF, DKIM, DMARC) и enumeration поддоменов.
Зафиксировать решения и разбить на исполняемые таски v0.10.

## Контекст

ADR 035 (поддомены/PSL) открыл дорогу к domain intelligence (см. «Следствия»
в `docs/decisions.md` и roadmap в `handoff/STATE.md`). DNS-подсистема
(A/AAAA/NS, ADR 032) уже есть — MX/TXT логично пристроить к ней.
PSL/registrable уже доступны для enumeration.

## Вопросы к проработке (вынести в ADR как решения)

- **Источник данных:** расширять DNS-подсистему (`src/dns/`, `dns_cache`) на
  MX/TXT или отдельная таблица? Кэш-TTL.
- **SPF/DKIM/DMARC:** только сбор/показ или валидация/диагностика (синтаксис,
  `-all` vs `~all`, наличие DMARC-политики)? Toggle'ы уведомлений (ADR 029).
- **Subdomain enumeration:** источник (CT-логи / пассивный DNS / brute по
  словарю) с оглядкой на «бесплатно, без платных API» (CLAUDE.md). Лимиты,
  rate-limit, объём для портфелей в десятки тысяч доменов.
- **Производительность/async:** всё через ARQ, без блокировок loop.
- **UX:** где показывать (карточка `/whois`, отдельная команда), локали.

## Изменения по файлам

- `docs/decisions.md` — новый раздел «036. Domain intelligence...».
- `PLAN_*.md` / `handoff/STATE.md` — обновить roadmap, зафиксировать этапы.
- `handoff/tasks/` — завести исполнительские таски v0.10 по разбивке ADR 036.

## Миграции БД

Зависит от решения по источнику данных — определить в ADR.

## Инварианты (защитить тестами)

- На этапе дизайна тестов нет; зафиксировать инварианты для будущих тасков.

## Требования к тестам

- Не требуется (дизайн).

## Definition of Done

- [ ] ADR 036 написан (контекст, решение, инварианты, альтернативы, следствия)
- [ ] Открытые вопросы закрыты дефолтами или явно помечены
- [ ] Исполнительские таски v0.10 заведены и связаны зависимостями
- [ ] STATE.md/roadmap обновлены
- [ ] `handoff.py validate` проходит

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- ADR 032 (DNS), ADR 035 (PSL/поддомены), ADR 029 (per-domain notifications)
