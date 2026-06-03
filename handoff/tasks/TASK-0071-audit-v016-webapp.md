---
id: TASK-0071
title: Аудит v0.16 (WebApp — security-heavy: initData/CORS/CSP/PII)
status: open
milestone: v0.16.0
adr: 043
area: audit
depends_on: [TASK-0074, TASK-0073]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0071 — Аудит v0.16 (WebApp)

> Отдельная сессия после раздела (конвенция CLAUDE.md). Отчёт —
> `handoff/audits/AUDIT-..-v0-16-webapp.md`. Образец — AUDIT v0.15.

## Цель

Независимая проверка WebApp-слоя (ADR 043) перед тегом v0.16.0. **Упор на
безопасность** — это первая внешняя HTTP-поверхность проекта.

## Объём

- **Auth/initData:** валидация HMAC корректна (тест-вектор Telegram); `auth_date`
  TTL; подделка/replay отбиваются; bot-token не на фронте/в логах.
- **Ownership/PII:** пользователь видит/меняет только свои домены; нет IDOR
  (`/domain/{id}` чужого → 403/404); в ответах нет лишних PII.
- **HTTP-периметр:** CORS только на webapp-origin; CSP; rate-limit; нет
  SSRF/инъекций; ошибки не текут стектрейсами наружу.
- **Запись:** через сервисы (не сырой SQL); лимиты; `audit()` на действия;
  optimistic-откат.
- **Тесты/anti-drift:** моки со `spec`; **полный backend `pytest` зелёный**;
  фронт — линт/тайпчек/build/тесты; health-score = дизайн-формула.
- **Перф:** серверная пагинация/поиск на 50k; виртуализация списка; API не
  блокирует event loop.

## Definition of Done

- [ ] Отчёт в `handoff/audits/` с severity-классификацией
- [ ] 🔴/🟠 находки — отдельными тасками
- [ ] Вердикт: можно ли тегать v0.16.0
- [ ] `handoff.py validate`; PR (docs)

## Ссылки

- ADR 043; AUDIT v0.15 как образец; TASK-0066…0070.
