# SESSION-0053 — Доки: MIGRATIONS.md + нормы алертов (TASK-0053)

**Дата:** 2026-06-08 · **Таск:** TASK-0053 · **Ветка:** task/0053-docs-migrations-alerts
· **Исполнитель:** Grok 4.3 (xAI)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

Закрыть два docs-долга: гайд по миграциям (MIGRATIONS.md) и описание норм дедупликации алертов (ADR 019).

## Выполнено

- Создан `MIGRATIONS.md` в корне:
  - Процесс: autogenerate, правка, down_revision от head, single-head.
  - Правило SQL-литералов в server_default (sa.text("''"), sa.text("false")) — урок TASK-0008.
  - Backfill с SQL, снятие default после.
  - Round-trip на Postgres (TASK-0009).
  - Чек-лист перед PR.
  - Примеры из реальных миграций (registrable, email_deep).
- Обновлён `docs/decisions.md` (ADR 019):
  - Детали дедупа: ключ `alert:<hash>`, TTL `Limits.alert_dedup_ttl_minutes` (10 мин).
  - Hash от (severity, title, details[:200]).
  - Нормы по severity: critical (редкие 1-2/час), anomaly (при всплесках), info/daily (1/окно).
  - Ссылка на реализацию в `src/services/alerts.py`.
- Обновлён `CLAUDE.md`: ссылка на `MIGRATIONS.md` в разделе команд.
- Обновлён `TODO.md`: отмечены как done.
- Ссылки добавлены где нужно.

## Изменённые/новые файлы

- `MIGRATIONS.md` (новый)
- `docs/decisions.md`
- `CLAUDE.md`
- `TODO.md`
- `docs/sessions/2026-06-08_task-0053-docs-migrations-alerts.md` (этот)

## Коммиты (на ветке)

- feat(TASK-0053): MIGRATIONS.md + documented alert dedup norms in ADR 019

## Проверки

- `handoff.py validate`: OK (55 задач).
- Доки консистентны, ссылки работают.
- Нет кода-изменений (только docs).

## Что осталось / следующий шаг

- Per-session отчёт (этот).
- `handoff.py status in_review --session ...`
- `git push -u`, открыть PR.
- После merge — `handoff.py done`.

## Архитектурные решения / открытые вопросы

- MIGRATIONS.md в корне (рядом с README/CLAUDE) — легко найти.
- Нормы алертов добавлены прямо в ADR 019 (где уже было краткое описание).
- Не трогали код алертов/миграций — только документация.

## PR

- TBD
