---
id: TASK-0060
title: Дневной графический отчёт 21:00 МСК (matplotlib) + сохранить 06:00
status: in_review
milestone: v0.15.0
adr: 042
area: code
depends_on: []
branch: task/0060-daily-graph-report
owner: grok-4.3
session: docs/sessions/2026-06-09_task-0060-daily-graph-report.md
pr: ""
created: 2026-06-08
---

# TASK-0060 — Дневной графический отчёт (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 042.

## Цель

ARQ cron `daily_graph_report` (21:00 МСК = `hour={18}` UTC): графики
использования за ~14 дней → PNG в админ-канал. Текстовая сводка 06:00
(`send_daily_summary`) **остаётся** как есть.

## Готовые факты (сверено архитектором)

- Источник метрик — те же таблицы, что в `src/tasks/daily_stats.py`:
  per-day ряды через `GROUP BY date_trunc('day', <ts>)` за N=14 дней:
  - новые пользователи: `users.created_at`;
  - активные: `users.last_active_at`;
  - новые домены: `user_domains.added_at`;
  - уведомления: лог отправленных (тот, что `daily_stats` читает для
    `notification_type` — взять оттуда таблицу/колонку `sent_at`);
  - события/ошибки: `system_events.created_at` (+ severity).
  - **lookups/день** — уточнить источник: `system_events` с `event_type`
    lookup'а, либо счётчик в `whois_cache`/логах; если явного нет — взять
    ближайший прокси и отметить в session-отчёте.
- `matplotlib.use("Agg")` **до** `import matplotlib.pyplot` (headless, без
  DISPLAY). Рендер CPU-bound → `asyncio.to_thread`.
- Cron в проде исполняется в scheduler-сервисе; фото шлёт `bot` из ctx в
  `settings.admin_channel_id`.

## Изменения по файлам

- `pyproject.toml` — `matplotlib>=3.8,<4.0` в основные deps.
- `src/services/charts.py` — функции построения PNG (matplotlib **Agg**,
  `matplotlib.use("Agg")` до pyplot; headless). Графики: lookups/день,
  активные/день, новые домены/день, уведомления/день за N=14 дней. Данные —
  `GROUP BY date_trunc('day', <ts>)` за период (created_at/added_at/sent_at/
  system_events). CPU-bound рендер — через `asyncio.to_thread`.
- `src/tasks/daily_graph_report.py` — собрать ряды, построить PNG (в память,
  `io.BytesIO`), отправить как фото в `admin_channel_id` через `bot`.
- `src/tasks/arq_config.py` — регистрация + cron `hour={18}, minute={0}`.
- `send_daily_summary` (06:00) — **не трогать**.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Рендер headless (Agg) — тест строит график без DISPLAY, получает непустой PNG.
- Пустые данные (нет строк за период) → не падает (пустой/placeholder график).
- Cron в 18:00 UTC (= 21:00 МСК).
- `admin_channel_id` не задан → no-op.

## Требования к тестам

- Unit на `charts.py` (рендер → bytes, len>0; пустой ряд). Задача — с моками
  сессии/bot (со `spec`).

## Definition of Done

- [ ] charts.py + задача + cron; 06:00-сводка сохранена
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Реальная проверка: график пришёл в тестовый канал — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 042; `src/tasks/daily_stats.py` (источник метрик/SQL)
