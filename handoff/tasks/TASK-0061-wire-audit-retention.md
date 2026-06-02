---
id: TASK-0061
title: Вписать audit() в инцидент-точки + retention 90 дней
status: open
milestone: v0.15.0
adr: 042
area: code
depends_on: [TASK-0057]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0061 — audit() в инцидент-точки + retention (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Зависит от TASK-0057 (`audit()` helper + таблица).

## Цель

Вписать `audit()` в ключевые инцидент-точки и добавить cron-очистку `audit_log`
старше 90 дней.

## Изменения по файлам

- Инцидент-точки (категория → где):
  - `task_failure` — в ARQ-задачах в ветке `except Exception` (общий хелпер или
    точечно в check_*/notify_*/scheduler'ах): записать level=error, category,
    message, context={task, domain/registrable, error_type}.
  - `rate_limit` — где ловится превышение лимитов (whois/add/download).
  - `admin_action` — в админ-хэндлерах (если есть: бан/анбан/рассылка/настройки).
  - `webhook`/`startup` — аномалии запуска/вебхука (рядом с существующими
    `AlertService.send_critical`/`send_info`).
  - Не спамить: только инциденты/значимое, не каждый штатный вызов.
- `src/tasks/cleanup.py` — добавить `cleanup_old_audit_log`
  (`DELETE FROM audit_log WHERE created_at < now() - interval '90 days'`),
  взять период из `settings.audit_retention_days` (дефолт 90).
- `src/config/settings.py` — `audit_retention_days: int = Field(90, ge=1)`.
- `src/tasks/arq_config.py` — зарегистрировать cron очистки (рядом с
  `cleanup_old_events`, раз в сутки).

## Миграции БД

Не требуется (таблица из TASK-0057).

## Инварианты (защитить тестами)

- `audit()` вызывается в except-ветках задач (тест: спровоцировать ошибку →
  audit записан, исключение всё равно обработано как раньше).
- retention-cleanup удаляет только старше N дней.
- audit() best-effort: сбой записи не ломает основной поток.

## Требования к тестам

- Unit (моки со `spec`): вызов audit в инцидент-точке; cleanup SQL.

## Definition of Done

- [ ] audit() вписан в инцидент-точки; retention-cron добавлен
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 042; TASK-0057; `src/tasks/cleanup.py`, `src/services/alerts.py`
