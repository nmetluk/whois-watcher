---
id: TASK-0084
title: 🟢 WebApp — ниты (длины полей группы, CORS Allow-Headers, доки replay-риска)
status: done
milestone: v0.16.1
adr: 043
area: code
depends_on: []
branch: task/0084-webapp-security-nits
owner: grok
session: docs/sessions/2026-06-11_task-0084-webapp-security-nits.md
pr: https://github.com/nmetluk/whois-watcher/pull/58
created: 2026-06-10
---

# TASK-0084 — WebApp fast-follow ниты (ADR 043)

> Тело самодостаточно. 🟢 Не блокеры релиза (аудит 0071: F8–F10). Fast-follow.

## Объём

- **F8.** `create_group`/`update`: добавить лимиты длины `name` (≤100),
  `color`/`icon` (≤32); опц. allowlist hue-токенов (`a0..a7`) и набора
  Material-Symbol-имён. Невалидно → 400.
- **F9.** CORS `Access-Control-Allow-Headers`: убрать `*` (игнорируется
  браузером при `Allow-Credentials: true`), оставить явный список
  (`X-Telegram-Init-Data, Authorization, Content-Type`).
- **F10.** Задокументировать принятый риск: replay-nonce-стора нет, защита —
  короткий initData TTL (см. F3). Запись в `docs/decisions.md` (ADR 043) или
  `docs/deployment.md`.

## Definition of Done

- [ ] F8–F10 закрыты; тесты на валидацию длины группы; `pytest`/`ruff`/`mypy`;
      `vite build`
- [ ] Per-session отчёт; `handoff.py validate`; PR

## Ссылки

- ADR 043; `src/bot/webapp/api.py`, `docs/decisions.md`; аудит F8–F10.
