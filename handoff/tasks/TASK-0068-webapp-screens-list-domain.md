---
id: TASK-0068
title: WebApp экраны — список доменов + карточка домена
status: blocked
blocked_reason: "снимки не складываются (параллельные ветки) → консолидация в TASK-0074"
milestone: v0.16.0
adr: 043
area: code
depends_on: [TASK-0066, TASK-0067]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0068 — WebApp: список + карточка домена (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 043; дизайн — `design/webapp/v1/app/screen-list.jsx`,
> `screen-domain.jsx`, `core.jsx` (примитивы Icon/Ring/Check/statusOf…).

## Цель

Воссоздать два главных экрана из дизайна на API из TASK-0066.

## Объём

- **Список** (`screen-list.jsx`): липкий поиск + фильтр-чипы (со счётчиками),
  сортировки (sheet), группировка (нет/клиенты/статус), строки `DomainRow`
  (пак статуса/имя/подзаголовок/«через N дней»/мини-теги), алфавит-рельс,
  мультивыбор (UI + чек-кружки), пустое состояние. **Виртуализация** списка
  (50k) + серверная пагинация/поиск/фильтр из API.
- **Карточка** (`screen-domain.jsx`): вкладки Обзор/WHOIS/SSL/DNS/Email/
  Поддомены (как в README); health-ring, факторы health, лента изменений,
  блоки по вкладкам. Тогглы уведомлений — UI готов, запись — в TASK-0070
  (пока read/disabled или optimistic-заглушка с пометкой).
- Примитивы из `core.jsx` (Icon, Ring, Check, GroupTag, statusOf) — перенести.

## Инварианты (защитить тестами)

- Рендер списка/карточки на мок-API (компонентные тесты).
- `statusOf`-логика совпадает с дизайном (wishlist/nodata/<0/<7/<30/норма).
- Виртуализация: большой список не рендерит все строки разом.

## Definition of Done

- [ ] Список + карточка по дизайну, на API из 0066; виртуализация
- [ ] Тесты компонентов; линт/тайпчек/`vite build` ок
- [ ] Реальная проверка в Telegram — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/app/{screen-list,screen-domain,core}.jsx`
- Связанные: TASK-0066/0067; действия — 0070.
