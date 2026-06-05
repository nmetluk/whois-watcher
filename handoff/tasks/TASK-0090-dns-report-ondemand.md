---
id: TASK-0090
title: 🟢 DNS-отчёт — on-demand расширенный анализ всех DNS-записей файлом
status: done
milestone: v0.17.0
adr: 044
area: code
depends_on: []
branch: main (прямой фикс архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-05_task-0090-dns-report.md
pr: —
created: 2026-06-05
---

# TASK-0090 — DNS-отчёт (ADR 044)

> Запрос владельца: профессиональный инструмент — кнопка в /whois,
> выгружает все DNS-записи домена сгруппированными по типам, текстовым файлом.

## Сделано

- `src/dns_report/` — новая подсистема (types/client/formatter):
  - `fetch_dns_report` — SOA/NS/A/AAAA/CNAME/MX/TXT/SRV/CAA + DNSKEY/DS
    (DNSSEC), обратные PTR (лимит 16), AXFR-проба (открытый трансфер зоны
    = security-finding). TXT через `txt_to_str` (урок 0089).
  - `format_dns_report` — текстовый файл: шапка (домен/резолвер/DNSSEC/AXFR),
    секции по типам в аналитическом порядке, TTL, отсутствующие типы, сводка.
- `src/tasks/check_dns_report.py` — ARQ-задача (redis-guard, доставка
  `.txt` через `send_document`, фейл → `deliver_ondemand_failure`).
  Зарегистрирована в `arq_config`.
- Кнопка «🧾 DNS-отчёт» в `whois_actions` (`action="dnsrep"`, исходное имя),
  callback в `on_whois_action` → `_show_dns_report_from_whois_card`.
- Локали ru/en: `button.dns_report`, `dns_report.searching`.

## DoD

- [x] 11 тестов (форматтер на синтетике, TXT через реальный rdata, wiring
      задачи: success шлёт документ / error шлёт notice / guard)
      + 2 теста клавиатуры; ruff/black чисто (mypy — CI)
- [x] Без БД-кэша/миграций (отчёт одноразовый, redis-guard)
- [ ] Real-world в Telegram после деплоя: кнопка → приходит .txt с записями;
      проверить домен с DNSSEC и домен с открытым AXFR (если найдётся)

## Заметки

- DNS-запрос на ИСХОДНОЕ имя (ADR 035), не registrable.
- `dnsrep` (6) короче `refresh` (7) — границу callback 64б не двигает.
- AXFR best-effort; на проде проверить, что egress на 53/tcp к чужим NS
  не режется фаерволом (иначе axfr_open всегда False — это ок, не ошибка).
EOF
echo ok