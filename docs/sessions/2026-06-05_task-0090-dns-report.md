# 2026-06-05 — TASK-0090: DNS-отчёт (on-demand расширенный анализ, ADR 044)

**Контекст.** Запрос владельца: профессиональный инструмент анализа домена —
кнопка в /whois, выгружает все DNS-записи сгруппированными по типам в
текстовый файл. Выбран расширенный набор (PTR + AXFR + DNSKEY). Выполнено
архитектором напрямую в main.

## Реализация

Новая подсистема `src/dns_report/` по образцу email_intel/dns_monitor
(async, общий `build_resolver`, никогда не бросает наружу):

- `types.py` — `DnsRecord`, `DnsReportResult` (records/dnssec/axfr_open/
  errors), `DnsReportError`.
- `client.py::fetch_dns_report` — параллельный обход прямых типов
  (SOA/NS/A/AAAA/CNAME/MX/TXT/SRV/CAA), затем DNSKEY/DS (DNSSEC), обратные
  PTR для A/AAAA (лимит 16), AXFR-проба у каждого NS (открытый трансфер =
  finding). TXT — через `txt_to_str` (rdata.strings; урок 0089).
- `formatter.py::format_dns_report` — текстовый файл: шапка, секции по
  типам в аналитическом порядке, TTL у записей, перечень отсутствующих
  типов, секция ошибок, сводка. Чистая функция.
- `tasks/check_dns_report.py` — ARQ-задача: redis-guard
  `dns_report_in_progress:<domain>` (TTL 90с), доставка `.txt` через
  `send_document`; при `DnsReportError` или исключении — `deliver_ondemand_failure`
  (kind="dns", TASK-0086). Без БД-кэша.

Интеграция: кнопка «🧾 DNS-отчёт» в `whois_actions` (`action="dnsrep"`,
исходное имя — ADR 035), ветка в `on_whois_action` →
`_show_dns_report_from_whois_card` (всегда enqueue, без freshness-gate).
Локали ru/en. Задача в `arq_config`.

## Решения по краям

- **Callback 64б**: `dnsrep` (6 симв.) короче `refresh` (7) → не двигает
  границу. Если клавиатура вообще собирается (refresh влез), dnsrep влезает —
  guard не нужен (проверено тестом сравнения длин).
- **Исходное имя vs registrable**: на исходное (DNS-записи у точного имени).
- **AXFR best-effort**: все исключения проглатываются; `axfr_open` —
  True/False/None. Закрытый трансфер (норма) → False, не ошибка.

## Верификация

- `tests/unit/test_dns_report.py` — 11: форматтер (группировка/порядок/
  DNSSEC/AXFR-flag/PTR/missing/errors/IDN), `_rdata_to_str` на **реальном**
  TXT-rdata (+ регресс «нет to_unicode»), wiring задачи (success→document,
  error→notice не document, in_progress guard).
- `test_keyboards.py` — кнопка присутствует, callback `dnsrep`, длина ≤ refresh.
- `arq_config._build_functions()` содержит `check_dns_report`; импорты
  хэндлера/задачи не падают.
- ruff/black чисто; smoke форматтера дал валидный отчёт.

## Хвосты

- Real-world в Telegram после деплоя (DoD).
- Прод: убедиться, что egress 53/tcp к произвольным NS не режется (иначе
  AXFR всегда «закрыт» — это ок, но и легитимный finding не словим).
- Milestone v0.17.0 — это фича, не hotfix; релиз отдельным шагом после
  накопления (вместе с webapp-достройкой 0087 этап 2).
