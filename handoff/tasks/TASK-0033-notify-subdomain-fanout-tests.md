---
id: TASK-0033
title: Реальные тесты fan-out notify_subdomain_changes (ADR 038)
status: open
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0029]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0033 — Тесты fan-out notify_subdomain_changes (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Источник находки — `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
> (finding 🟠 в разделе «Тесты»).

## Цель

Покрыть инварианты рассылки `notify_subdomain_changes` реальными тестами, а
не smoke-«функция вызываема». Сейчас `tests/unit/test_notify_subdomain_changes.py`
проверяет лишь пустой diff и факт вызываемости (с глотанием исключений) —
ключевая логика fan-out не покрыта вовсе.

## Контекст / корень проблемы

`src/tasks/notify_subdomain_changes.py` рассылает уведомления подписчикам
registrable. Логика, которая сейчас **не тестируется** и где дрейф полей/
сигнатур пройдёт незаметно (см. CLAUDE.md «Защита от рассинхрона»):

- дедуп: одному `user_id` — одно сообщение;
- `is_muted` гасит уведомление;
- honoring `notify_subdomain_new` / `notify_subdomain_removed` по отдельности;
- skip `user.is_blocked`; пометка `is_blocked=True` на `TelegramForbiddenError`;
- обрезка списка `[:5]` + строка `…and_more` при >5;
- запись в журнал `record_sent` (`subdomain_new` / `subdomain_removed`).

## Изменения по файлам

- `tests/unit/test_notify_subdomain_changes.py` — заменить «smoke»-тест
  реальными кейсами. Замокать `get_session`, `DomainRepository`,
  `UserRepository`, `NotificationRepository`, `bot` — **со `spec`/`autospec`**
  (голый `MagicMock` маскирует дрейф). Подавать поддельных подписчиков
  (`UserDomain`-моки со `spec=UserDomain`) и пользователей (`spec=User`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Два подписчика-строки одного `user_id` → ровно один `bot.send_message`.
- `is_muted=True` → подписчик пропущен.
- `notify_subdomain_new=False, notify_subdomain_removed=True` → в тексте только
  removed-секция (и наоборот); оба `False` → сообщение не отправляется.
- `user.is_blocked=True` → пропуск; `TelegramForbiddenError` при отправке →
  `update_settings(user_id, is_blocked=True)`.
- >5 new → показаны 5 + `and_more(count=N-5)`.
- `record_sent` вызван с корректным `notification_type` для каждой включённой
  секции.

## Требования к тестам

- Unit, без реальной БД/сети (моки со `spec`/`autospec`).
- Покрыть все инварианты выше отдельными кейсами.

## Definition of Done

- [ ] Тесты реализованы по спецификации
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` и вписан в `session:`
- [ ] `handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 038)
- Аудит: `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
- Связанные: TASK-0029 (реализация), TASK-0034, TASK-0035
