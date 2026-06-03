---
id: TASK-0073
title: Группы/теги доменов — схема + репозиторий + API/привязка (для WebApp)
status: open
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-09
---

# TASK-0073 — Группы/теги доменов (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 043; дизайн — `design/webapp/v1/` (группировка списка по
> клиентам, дашборд по группам, экран «Группы»). Перед миграцией — `MIGRATIONS.md`.

## Цель

Добавить модель «групп/тегов» доменов (клиенты/личное), которой **сейчас в БД
нет**, — основа для группировки в WebApp (список, дашборд, экран «Группы»).

## Контекст

В дизайне у домена есть `groups: [groupId...]`, список группируется «по
клиентам», дашборд даёт бюджет/риски по группам. В моделях (`src/db/models.py`)
группы отсутствуют — нужна новая таблица + связь many-to-many с `user_domains`
(домен может быть в нескольких группах), привязка к пользователю.

## Изменения по файлам

- `migrations/versions/<new>.py` — таблицы `domain_group` (id, user_id
  FK→users ON DELETE CASCADE, name, color/hue, created_at) и связь
  `user_domain_group` (user_domain_id FK, group_id FK; PK составной;
  ON DELETE CASCADE). Индексы по user_id. SQL-литералы в дефолтах; round-trip.
- `src/db/models.py` — модели `DomainGroup` + связь.
- `src/db/repositories/groups.py` — CRUD групп, привязка/отвязка домена,
  список с counts; регистрация в `__init__`.
- Подключить к WebApp API (TASK-0066/0070): `/groups` (list+counts),
  `/portfolio?group=`, добавление/удаление группы и членства; ownership-скоуп.

## Миграции БД

Да — `domain_group` + `user_domain_group`. Postgres, обратима, round-trip-smoke.

## Инварианты (защитить тестами)

- Домен в нескольких группах; снятие членства не удаляет домен/группу.
- Группы скоупятся по пользователю (нет чужих).
- Миграция round-trip.

## Definition of Done

- [ ] Схема + модели + репозиторий + API-хуки; миграция применяется/обратима
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/app/screen-more.jsx` (GroupsScreen),
  `screen-list.jsx` (группировка); `MIGRATIONS.md`.
- Связанные: 0066 (API), 0068/0069 (группировка в UI), 0070 (действия).
