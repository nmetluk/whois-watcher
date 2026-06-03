---
id: TASK-0067
title: WebApp frontend — foundation (Vite+React, токены PIN Voice, Telegram SDK, сборка+nginx)
status: in_review
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: task/0067-webapp-frontend-foundation
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0067 — WebApp frontend foundation (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 043; дизайн — `design/webapp/v1/`.

## Цель

Завести фронт-проект (React + Vite), перенести дизайн-систему PIN Voice и
Telegram-оболочку, интегрировать `Telegram.WebApp`, настроить роутинг и сборку.

## Изменения по файлам

- `webapp/` — новый Vite+React-проект (TS желательно). Отдельный
  `package.json`/lockfile; не смешивать с Python-стеком.
- Перенести **значения** токенов из `design/webapp/v1/app/ds/colors_and_type.css`
  (CSS-переменные) + нужные классы из `styles.css`/`tg.css` (chrome:
  `.tg-header`/`.tg-tabbar`/`.tg-mainbtn`/`.tg-fab`/`.tg-sheet`/`.tg-toast`).
  **Не** тащить `.tg-phone`/статус-бар (вьюпорт даёт Telegram), unpkg/Babel.
- `Telegram.WebApp` интеграция: `expand()`, `MainButton`, `BackButton`,
  `HapticFeedback`, `colorScheme`/`themeParams` → синк темы (`data-theme`),
  safe-area.
- Роутинг: 5 вкладок (Домены/Дашборд/Календарь/Алерты/Ещё) + стек экранов
  (push/back, скрытие таб-бара в стеке) — по `design/webapp/v1/app/app.jsx`.
- API-клиент: каждый запрос несёт `initData` (из `Telegram.WebApp.initData`).
- Сборка: `vite build` → статика; nginx — отдавать статику + `proxy_pass`
  `/api/webapp` на bot-сервис (конфиг-сниппет в `docs/deployment.md`).
- Иконки Material Symbols Rounded, шрифт PT Sans (Google Fonts или локально).

## Инварианты (защитить тестами)

- Сборка проходит (`vite build`) без unpkg/Babel-standalone.
- Токены = значения из `ds/` (smoke: ключевые переменные присутствуют).
- Тема синхронизируется с `Telegram.WebApp.colorScheme`.

## Definition of Done

- [ ] Vite-проект, токены/chrome, Telegram SDK, роутинг, API-клиент, build+nginx
- [ ] Линт/тайпчек фронта проходят; `vite build` ок
- [ ] Реальная проверка в Telegram (открывается mini-app) — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/app/{app.jsx,tg.css,ds/}`
- Связанные: TASK-0066 (API), 0068/0069 (экраны).
