---
id: TASK-0038
title: Deep email — парсеры и коллекторы (SPF include / MTA-STS / TLS-RPT / DANE / BIMI)
status: open
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0018]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0038 — Deep email: парсеры и коллекторы (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 040 в `docs/decisions.md`.

## Цель

Реализовать **чистые парсеры** и **async-коллекторы** для углублённого
почтового разбора. UI/ARQ — в следующих тасках; здесь только логика + типы +
юнит-тесты. Никакого фонового трафика — функции вызываются по запросу.

## Контекст / корень проблемы

ADR 036 даёт базовый MX/SPF(режим)/DMARC/DKIM. ADR 040 углубляет: рекурсивный
SPF, MTA-STS, TLS-RPT, DANE/TLSA, BIMI. Источник DNS — `dnspython` (уже есть,
см. `src/dns_monitor/`), HTTP для MTA-STS policy — `aiohttp` (как
`src/subdomains/client.py`).

## Изменения по файлам

- `src/email_intel/deep_types.py` — dataclasses результатов:
  `SpfResolution(sources: list[str], lookup_count: int, exceeds_limit: bool)`,
  `MtaStsResult(txt_present, policy_mode, mx: list[str], max_age, reachable)`,
  `TlsRptResult(present, rua)`, `DaneResult(host_tlsa: dict[str,bool])`,
  `BimiResult(present, logo_url, vmc_url)`; общий `DeepEmailResult` + error-тип.
- `src/email_intel/spf_resolver.py` — `resolve_spf(domain, *, resolve_txt)` —
  рекурсивный разбор `include:`/`redirect=` со счётчиком lookups (лимит 10,
  RFC 7208 §4.6.4), защита от циклов (set посещённых), флаг превышения.
  Резолвер TXT инъектируется (callable) для тестов.
- `src/email_intel/deep_client.py` — async-коллекторы:
  `fetch_mta_sts(domain)` (TXT `_mta-sts.<d>` + GET
  `https://mta-sts.<d>/.well-known/mta-sts.txt`, timeout, **allow_redirects=False**,
  лимит размера тела, graceful degradation), `fetch_tls_rpt(domain)`,
  `fetch_dane(mx_hosts)` (TLSA `_25._tcp.<host>`), `fetch_bimi(domain)`.
- `src/email_intel/deep_parser.py` — чистые парсеры policy MTA-STS
  (mode enforce/testing/none, mx[], max_age), TLS-RPT (`rua`), BIMI (`l=`,`a=`).

## Миграции БД

Не требуется (хранение результатов — в TASK-0039).

## Инварианты (защитить тестами)

- SPF: вложенные include, redirect, **цикл** (не зависает), превышение 10
  lookups → `exceeds_limit=True`, нет записи → пустой результат.
- MTA-STS: parse enforce/testing/none + mx[] + max_age; HTTP timeout/недоступность
  → `reachable=False`, без исключения; **редиректы не следуются**; лимит размера.
- TLS-RPT/BIMI/DANE: отсутствие записи — валидное состояние (не ошибка).
- Все парсеры — чистые функции; коллекторы — async, без блокировок loop.

## Требования к тестам

- Unit на каждый парсер/резолвер с инъекцией DNS/HTTP-моков (моки со
  `spec`/`autospec`). Edge-кейсы из инвариантов.

## Definition of Done

- [ ] Код реализован по спецификации
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` и вписан в `session:`
- [ ] `handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 040; база — ADR 036)
- Образцы: `src/email_intel/parser.py`, `src/subdomains/client.py`,
  `src/dns_monitor/`
- Связанные: TASK-0039 (ARQ + кэш), TASK-0041 (UX deep-email)
