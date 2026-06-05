---
id: TASK-0089
title: 🔴 Email-слой — несуществующий TXT.to_unicode() ронял intel/deep для доменов с TXT
status: done
milestone: v0.16.1
adr: 040
area: code
depends_on: [TASK-0088]
branch: main (прямой hotfix архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-05_task-0089-fix-txt-rdata-to-unicode.md
pr: —
created: 2026-06-05
---

# TASK-0089 — Фикс TXT-извлечения в email-слое (корень из отчёта TASK-0088)

> Отчёт TASK-0088 дал точный `last_error`:
> `Unexpected error: 'TXT' object has no attribute 'to_unicode'`.
> В dnspython у TXT-rdata **нет** `to_unicode()` (есть только у
> `dns.name.Name`). 7 вызовов по email-слою: любой домен **с**
> TXT-записями ронял весь `fetch_email_intel` (→ нет MX/SPF/DMARC/DKIM)
> и `fetch_deep_email` (→ пустой deep-отчёт). Домены без TXT проходили —
> отсюда «то работает, то нет». Тесты были зелёными: мокали
> несуществующий метод. **Четвёртый anti-drift-инцидент**
> (TASK-0017, TASK-0020, _shape_domain).

## Сделано

- `src/email_intel/txt.py::txt_to_str` — официальный API `rdata.strings`
  (склейка 255-байтовых сегментов без разделителя, RFC 7208 §3.3),
  fallback `to_text()`.
- Заменены все 7 вызовов: `client.py` (TXT-список для SPF, DMARC, DKIM),
  `deep_client.py` (SPF-resolver, MTA-STS, TLS-RPT, BIMI).
  `parser.py` (`exchange.to_unicode()`) не тронут — это `Name`, валидно.
- Тесты: `test_email_txt.py` — 6 тестов на **реальных** rdata (включая
  «у настоящего TXT нет to_unicode» и многосегментный SPF);
  `test_deep_email.py` — to_unicode-моки заменены реальными rdata
  (`_txt_rdata()` helper).

## DoD

- [x] 171 email-тест зелёный; ruff/black чисто (mypy — CI)
- [x] Старые to_unicode-моки удалены из тестов deep
- [ ] Real-world после деплоя: `/whois` домена с почтой → MX виден;
      «Глубокий e-mail» → непустой отчёт (например, arbital.ru из отчёта 0088)
