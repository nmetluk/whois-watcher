---
id: TASK-0059
title: Ежечасный ops-отчёт в админ-канал (статистика + статус бекапа)
status: open
milestone: v0.15.0
adr: 042
area: code
depends_on: [TASK-0058]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0059 — Ежечасный ops-отчёт (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 042. Зависит от TASK-0058 (статус бекапа в `ops:last_backup`).

## Цель

ARQ cron `hourly_ops_report` (`minute={0}`): краткая статистика за последний час
+ статус последнего бекапа → компактное сообщение в админ-канал.

## Изменения по файлам

- `src/tasks/hourly_ops_report.py` — задача: собрать за последний час
  (active users `last_active_at >= now()-1h`, lookups, новые домены, кол-во
  ошибок/алертов из `audit_log`/`system_events`); прочитать `ops:last_backup`
  из Redis; сформировать текст: «📟 Ops (час): users N · lookups M · +домены K ·
  ошибки E | 💾 бекап ✅ <size>/❌ <error>»; отправить в admin channel.
- `src/services/alerts.py` — добавить метод `send_ops(text)` (severity `ops`,
  **без дедупа** — контент меняется ежечасно), либо параметр `dedup=False`.
- `src/tasks/arq_config.py` — регистрация + cron `minute={0}`.
- Локали не нужны (админ-канал технический; язык — по усмотрению, можно ru).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Бекап отсутствует/упал (`ops:last_backup` нет или ok=False) → отчёт шлёт
  «бекап FAILED», **не крашится**.
- Отчёт обходит дедуп (две подряд разные минуты → два сообщения).
- `admin_channel_id` не задан → тихо no-op (как AlertService).
- Только агрегаты, без чувствительного (ADR 019).

## Требования к тестам

- Unit с моками сессии/redis/alerts (со `spec`): happy + backup-failed + no-channel.

## Definition of Done

- [ ] Задача + `send_ops`; cron зарегистрирован
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 042; `src/services/alerts.py`, `src/tasks/daily_stats.py` (образцы)
- Связанные: TASK-0058
