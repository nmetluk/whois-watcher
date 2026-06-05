---
id: TASK-0092
title: 🔴 «Свободен» только после RDAP-верификации + «сбой ≠ свободен» (ADR 045)
status: done
milestone: v0.16.1
adr: 045
area: code
depends_on: [TASK-0091]
branch: main (прямой фикс архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-07_task-0092-free-verification.md
pr: —
created: 2026-06-07
---

# TASK-0092 — RDAP-верификация «свободен» (ADR 045)

> По уликам TASK-0091 (discozavr.ru): relay/TCI отдавал «No entries found»
> для зарегистрированного домена 2+ суток, бот уверенно показывал «свободен».

## Сделано

- `src/whois/client.py::_verify_unregistered` — в `lookup_domain` после
  обоих путей (proxy/direct): «свободен» из WHOIS-текста перепроверяется
  независимым RDAP (IANA bootstrap, мимо relay/proxy):
  RDAP registered → отдаём данные RDAP (ЗАНЯТ) + пометка противоречия;
  RDAP 404 → «свободен» подтверждён; RDAP недоступен → `free_unverified`.
- `src/whois/parser.py::looks_like_upstream_error` + `UPSTREAM_ERROR_PATTERNS`
  (рейтлимит/HTML/заглушки) — guard в `proxy_client` и в direct WHOIS:43:
  такой текст → `WhoisError(unavailable)`, а не «свободен».
- UX: `commands.whois.free_unverified` (ru/en) — осторожная формулировка
  с подсказкой `/check`; форматтер выбирает по `raw_data.free_unverified`.
- Без миграций: флаги в `raw_data` (JSONB).

## DoD

- [x] 16 тестов: верификация (противоречие/подтверждение/недоступность/
      скипы), free-детекция на реальном тексте TCI из отчёта 0091 +
      ошибки upstream, рендер через реальный t(); смежные whois/proxy/
      parser/wishlist — 267 passed; ruff/black чисто (mypy — CI)
- [ ] Real-world после деплоя: /check discozavr.ru → «занят» с данными
      RDAP (или честное «подтвердить не удалось», если RDAP TCI закрыт
      для IP бота — тогда эскалировать в TASK-0093)

## Связанное

- TASK-0093 (инфра, открыт): кэш/поведение RU-relay на VDS — почему
  отдаёт «No entries» для зарегистрированного домена.
