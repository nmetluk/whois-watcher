---
id: TASK-0081
title: 🔴 WebApp — эндпойнты-заглушки врут об успехе (bulk/alerts-read/import)
status: done
milestone: v0.16.0
adr: 043
area: code
depends_on: []
branch: task/0081-webapp-stub-endpoints
owner: ""
session: docs/sessions/2026-06-11_task-0081-webapp-stub-endpoints.md
pr: https://github.com/nmetluk/whois-watcher/pull/55
created: 2026-06-10
---

# TASK-0081 — Заглушки не должны возвращать «успех» (ADR 043)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🔴 Блокер релиза v0.16 (аудит 0071, F1).

## Проблема (подтверждена по коду)

`src/bot/webapp/api.py`: `POST /bulk`, `POST /alerts/read`, `POST /import`
помечены `# TODO ... stub`, но возвращают `{"ok": true, ...}`. Фронт показывает
«готово»/«N обработано»/«импортировано», хотя **ничего не выполнено**. Для
`/import` особенно опасно — пользователь думает, что домены добавлены.

## Цель

Никакой эндпойнт не отдаёт «успех» без выполнения. Два допустимых пути на выбор
(по каждому эндпойнту):

- **Реализовать** через существующие сервисы/репозитории + `audit()`:
  - `/bulk` — массовые действия через `DomainService`/репозитории (toggle/add to
    group/remove/export), ownership-скоуп, лимиты;
  - `/import` — `src/services/csv_io` (превью+применение) + `DomainService`,
    лимит 50k, валидация доменов;
  - `/alerts/read` — через `NotificationRepository` (или `audit_log`), scoped.
- **Либо** — если не успеваем в v0.16 — вернуть `501 Not Implemented` и **скрыть**
  действие во фронте (кнопку/пункт) до реализации. Не показывать success-toast.

Рекомендация: `/alerts/read` и `/import` реализовать (нужны для MVP-ценности),
`/bulk` — реализовать минимум (toggle/remove/add-to-group) или 501+hide.

## Инварианты (тестами)

- Реализованные роуты: ownership-скоуп по `user.id`, `audit()` на мутациях,
  лимиты; невалидный вход → 4xx.
- `/import`: невалидный CSV → ошибка (не «успех»); счётчик `imported`
  соответствует реально добавленным.
- Если выбран 501-путь — роут отдаёт 501, фронт не рендерит действие.

## Definition of Done

- [ ] Ни один stub не отдаёт ложный success; реализовано или 501+hide
- [ ] **Полный `pytest` зелёный** + тесты новых путей; `ruff`/`black`/`mypy`;
      фронт `vite build`
- [ ] Реальная проверка в Telegram; per-session отчёт; `handoff.py validate`; PR

## Ссылки

- ADR 043; `src/bot/webapp/api.py`, `src/services/{domains,csv_io}.py`,
  `src/db/repositories/notifications.py`; аудит
  `handoff/audits/AUDIT-2026-06-10-v0-16-webapp-security.md` (F1).
