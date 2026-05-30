---
id: TASK-0016
title: Сбор и парсеры MX/SPF/DKIM/DMARC + базовая диагностика (ADR 036)
status: done
milestone: v0.10.0
adr: 036
area: code
depends_on: [TASK-0015]
branch: task/0016-email-intel-parsers
owner: claude
session: docs/sessions/2026-05-30_task-0016_email_intel_parsers.md
pr: ""
created: 2026-05-29
---

# TASK-0016 — Сбор и парсеры email-records (ADR 036)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Чистый модуль сбора и разбора MX/SPF/DKIM/DMARC с **базовой диагностикой**
(не полный аудит-движок) + diff для уведомлений.

## Контекст

ADR 036, раздел «Решение». Резолв через `dnspython` (уже в зависимостях),
async, без блокировок loop. Записи берутся у самого домена/поддомена (ADR 035).

## ⚠️ Замечание из ревью TASK-0015

Колонка `email_intel_cache.spf_mode` (уже создана в TASK-0015) в комментарии
ошибочно описывает SPF-*результаты* (`pass/fail/softfail…`). По ADR 036 туда
кладём **квалификатор `all`**: `-all` / `~all` / `?all` / `+all` (или `none`,
если SPF нет). Парсер SPF должен заполнять именно это; заодно поправить
комментарий к колонке в `src/db/models.py` (миграцию не трогать — тип `Text`).

## Изменения по файлам

- Новый пакет `src/email_intel/` (по образцу `src/ssl/`, `src/dns/`):
  - `client.py` — async-резолв `MX`, `TXT` (apex SPF), `_dmarc.<domain>` TXT,
    `<selector>._domainkey.<domain>` для набора селекторов
    (`default`, `google`, `selector1`, `selector2`, `k1`, `mail`).
  - `parser.py` — чистые функции: разбор MX (host+priority), SPF (режим
    `-all`/`~all`/`?all`/`+all`, флаг >1 SPF = RFC-нарушение, **без**
    рекурсии `include`), DMARC (`p`/`sp`/`pct`), DKIM (наличие по селекторам).
  - `types.py` — dataclass'ы результата.
  - `diff.py` — `compute_email_diff(old, new)`; `old=None` → пустой diff.
  - `scheduler.py` — расчёт `next_check_at` (TTL как у DNS-подсистемы).

## Миграции БД

Не требуется (использует схему TASK-0015).

## Инварианты (защитить тестами)

- Парсеры — чистые, юнит-тесты на edge: нет записи; несколько SPF;
  `include` без рекурсии; IDN/punycode; DMARC без `p`; DKIM-селектор найден/нет.
- `compute_email_diff(old=None, ...)` → пустой diff.
- Отсутствие SPF/DMARC — валидное состояние, не ошибка.
- DNS-фейл (NXDOMAIN/timeout) ≠ «политики удалены»; только переход
  reachable→unreachable значим (не повтор).
- Никаких блокирующих вызовов в горячем пути (async).

## Требования к тестам

- `tests/unit/test_email_parser.py`, `test_email_diff.py`,
  `test_email_scheduler.py` — по образцу ssl/dns-тестов.

## Definition of Done

- [ ] Модуль `src/email_intel/` с парсерами/diff/scheduler; покрыт тестами
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 036; `src/ssl/`, `src/dns/` как образец структуры
