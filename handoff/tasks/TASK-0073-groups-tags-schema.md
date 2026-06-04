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

В дизайне (`screen-more.jsx` → `GroupsScreen`) у домена есть
`groups: [groupId...]`, список группируется «по клиентам», дашборд даёт
бюджет/риски по группам. Объект группы в дизайне:
`{ id, kind: 'client'|'personal', name, color: <hue-токен 'a0'..'a7'>,
icon: <Material-Symbol-имя, напр. 'folder_special'> }`; экран делит группы на
`client` и `personal` (`g.kind`). В моделях (`src/db/models.py`) групп нет —
нужна новая таблица + связь many-to-many с `user_domains` (домен в нескольких
группах), привязка к пользователю.

## Изменения по файлам

- `migrations/versions/<new>.py` — **down_revision = `20260609_audit_log`**
  (текущий single-head; сверь перед autogenerate). Таблицы:
  - `domain_group`: `id` BigInteger PK autoincrement; `user_id` BigInteger
    FK→`users.id` ON DELETE CASCADE NOT NULL; `name` Text NOT NULL;
    `kind` Text NOT NULL (значения `client`/`personal`); `color` Text
    (hue-токен, напр. `a1`); `icon` Text (Material-Symbol-имя); `created_at`
    timestamptz NOT NULL server_default `now()`. Индекс `ix_domain_group_user_id`.
  - `user_domain_group` (membership): `user_domain_id` BigInteger
    FK→`user_domains.id` ON DELETE CASCADE; `group_id` BigInteger
    FK→`domain_group.id` ON DELETE CASCADE; **составной PK
    (user_domain_id, group_id)**. Индекс по `group_id`.
  - SQL-литералы в server_default (урок TASK-0008/0009); round-trip-smoke на
    Postgres.
- `src/db/models.py` — модели `DomainGroup` + membership (relationship'ы как у
  существующих, см. `UserDomain`).
- `src/db/repositories/groups.py` — `GroupRepository`: CRUD групп (scoped по
  `user_id`), attach/detach домена (idempotent), `list_with_counts(user_id)`
  (group + число доменов одним запросом, без N+1). Регистрация в
  `src/db/repositories/__init__.py` (импорт + `__all__`).
- Подключить к WebApp API (расширить `src/bot/webapp/api.py` из 0074):
  `GET /groups` (list+counts), `GET /portfolio?group=<id>` (фильтр членства),
  add/remove группы и membership; **ownership-скоуп по `request['user'].id`**
  на всех роутах; `audit()` на мутациях (как в 0074).

## Миграции БД

Да — `domain_group` + `user_domain_group`, down_revision `20260609_audit_log`.
Postgres, обратима, round-trip-smoke. Перед стартом — `MIGRATIONS.md`.

## Инварианты (защитить тестами)

- Домен в нескольких группах; снятие членства не удаляет домен/группу.
- Повторный attach того же домена в группу — idempotent (нет дубля/краша на
  составном PK).
- Удаление домена (`user_domains`) или группы каскадит membership (ON DELETE
  CASCADE), но не трогает другую сторону.
- Группы и membership скоупятся по `user_id` (нельзя положить чужой домен в свою
  группу и наоборот — проверка владения `user_domain` перед attach).
- `list_with_counts` — один запрос (без N+1).
- Миграция round-trip на Postgres (upgrade→downgrade→upgrade).

## Definition of Done

- [ ] Схема + модели + репозиторий + API-хуки; миграция применяется/обратима
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 043; `design/webapp/v1/app/screen-more.jsx` (GroupsScreen),
  `screen-list.jsx` (группировка); `MIGRATIONS.md`.
- Связанные: 0066 (API), 0068/0069 (группировка в UI), 0070 (действия).
