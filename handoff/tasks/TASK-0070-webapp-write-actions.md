---
id: TASK-0070
title: WebApp — write-действия (тогглы/add/remove/массовые/настройки/импорт/wishlist)
status: blocked
blocked_reason: "снимки не складываются (параллельные ветки) → консолидация в TASK-0074"
milestone: v0.16.0
adr: 043
area: code
depends_on: [TASK-0068, TASK-0069]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0070 — WebApp write-действия (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 043.

## Цель

Добавить write-эндпойнты `/api/webapp/*` (через существующие сервисы) и
подключить действия во фронте (optimistic + toast, `MainButton`/sheets).

## Объём

- **Backend** (тонкие хэндлеры → `DomainService`/репозитории, лимиты, `audit()`
  на значимые):
  - тоггл уведомлений домена; добавить/снять домен; массовые действия
    (вкл/выкл уведомления, в группу, экспорт, снять); настройки (дни/время/TZ/
    лимит); пометить алерты прочитанными; wishlist add/remove; импорт CSV
    (превью+применение — переиспользовать `csv_io`).
- **Frontend**: подключить действия к UI из 0068/0069 — `MainButton`-состояния
  («Добавить»/«Импортировать N»/«Сохранить»/«Действия · N»), bottom-sheets
  массовых действий, optimistic-апдейт + toast, HapticFeedback.
- Валидация домена (regex) на фронте + сервере; лимит 50k.

## Инварианты (защитить тестами)

- Запись только через сервисы (не сырой SQL); лимиты соблюдены; `audit()` на
  add/remove/bulk.
- Add невалидного домена → 400/ошибка; превышение лимита → ошибка лимита.
- Пользователь не может менять чужие домены (PII/ownership-проверка).
- Optimistic-апдейт откатывается при ошибке API.

## Definition of Done

- [ ] Write-эндпойнты + фронт-действия; optimistic+toast
- [ ] **Полный `pytest` зелёный** (backend) + тесты фронта; линт/тайпчек/build
- [ ] Реальная проверка в Telegram (добавить/тоггл/массовые) — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `src/services/domains.py`, `src/services/csv_io.py`;
  `design/webapp/v1/README.md` (раздел Interactions & MainButton).
- Связанные: 0066–0069.
