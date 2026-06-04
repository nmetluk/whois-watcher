---
id: TASK-0082
title: 🔴 WebApp — убрать фейковые demo-данные на фронте (error/empty-state)
status: in_review
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: "task/0082-webapp-remove-demo-fallback"
owner: "grok"
session: "docs/sessions/2026-06-11_task-0082-webapp-remove-demo-fallback.md"
pr: "https://github.com/nmetluk/whois-watcher/pull/56"
created: 2026-06-10
---

# TASK-0082 — Убрать demo-fallback во фронте (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🔴 Блокер релиза v0.16 (аудит 0071, F2).

## Проблема (подтверждена по коду)

При сбое API экраны показывают **выдуманные** данные:
- `webapp/src/screens/DashboardScreen.tsx` —
  `.catch(()=>setData({totalDomains:42, expiring30:5, ... renewalBudget:125000 ...}))`;
- `webapp/src/screens/AlertsScreen.tsx` — `demo.ru истекает через 5 дн.`;
- `webapp/src/screens/CalendarScreen.tsx` — пустой каркас `{heat:{}, agenda:[]}`
  тоже маскирует ошибку под «пусто».

Пользователь видит фейковый портфель вместо ошибки.

## Цель

- Убрать demo-fallback во всех экранах.
- На ошибку API → явное **error-состояние** с кнопкой «Повторить» (retry).
- На реально пустые данные → **empty-state** («Пока нет доменов/алертов»).
- Различать «ошибка» и «пусто» (не показывать empty при сетевой ошибке).

## Инварианты (тестами фронта, если есть харнесс; иначе — ручная проверка)

- Мок API-ошибки → рендерится error-state (не цифры).
- Мок пустого ответа → empty-state.
- Мок валидного ответа → данные.

## Definition of Done

- [ ] Ни один экран не показывает выдуманные данные; error/empty-state на месте
- [ ] `vite build` + lint/typecheck зелёные; (тесты фронта если есть)
- [ ] Реальная проверка в Telegram (отключить бэк → видно ошибку, не «42 домена»)
- [ ] Per-session отчёт; `handoff.py validate`; PR

## Ссылки

- ADR 043; `webapp/src/screens/{Dashboard,Alerts,Calendar}Screen.tsx`,
  `webapp/src/lib/api.ts`; аудит F2.
