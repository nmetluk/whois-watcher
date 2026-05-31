---
id: TASK-0028
title: Diff + scheduler мониторинга поддоменов + интеграция в check_subdomains (ADR 038)
status: done
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0027]
branch: task/0028-subdomain-monitor-diff-scheduler
owner: claude-code
session: docs/sessions/2026-05-30_task_0028_subdomain_monitor_diff_scheduler.md
pr: "#20"
created: 2026-05-30
completed: 2026-05-30
---

# TASK-0028 — Diff + scheduler мониторинга поддоменов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Фоновое обнаружение новых/исчезнувших поддоменов: чистый diff, периодический
scheduler (по образцу `ssl_scheduler_tick`), интеграция в `check_subdomains`.

## Изменения по файлам

- `src/subdomains/diff.py` (новый) — чистая функция
  `compute_subdomain_diff(old: list[str] | None, new: list[str]) -> SubdomainDiff`
  с полями `new: list[str]`, `removed: list[str]`.
  - **`old=None` → пустой diff** (baseline, НЕ алертим; инвариант как
    `compute_ssl_diff(old=None)`, ADR 030).
  - Игнор порядка/дубликатов (работа на set; вход уже нормализован, ADR 037).
- `src/subdomains/scheduler.py` — расширить `calculate_next_subdomain_check`:
  принять интервал успеха параметром (вместо хардкода 7д) — `success_interval_days`
  (= `min(интервалов подписчиков)`, floor 1д). Backoff при фейлах не менять.
- `src/tasks/subdomain_scheduler.py` (новый, образец `ssl_scheduler_tick`):
  - **Bootstrap**: registrable c ≥1 подписчиком `track_subdomains=true` без
    записи в `subdomain_enum_cache` → заглушка `next_check_at=now()`,
    `ON CONFLICT DO NOTHING`.
  - **Выборка due**: registrable с подписчиками `track_subdomains=true AND
    is_muted=false`, у которых `next_check_at <= now()` (репозиторий —
    `get_due_for_check`, как у SSL).
  - **Enqueue** `check_subdomains` (self-guard уже есть, ADR 037).
  - Зарегистрировать cron в `arq_config` (`_build_cron_jobs`), интервал тика —
    как у `ssl_scheduler_tick`.
- `src/tasks/check_subdomains.py`:
  - На success ДО перезаписи кэша получить старый `subdomains`, посчитать
    `compute_subdomain_diff(old, new)`; при изменениях — enqueue
    `notify_subdomain_changes` (реализация уведомления — TASK-0029; здесь только
    enqueue с payload registrable + diff).
  - `next_check_at` на success считать с `success_interval_days =
    min(интервалов подписчиков registrable)` (helper в репозитории/сервисе:
    интервал = `COALESCE(ud.subdomain_check_interval_override,
    u.subdomain_check_interval_days)`; min по подписчикам `track_subdomains=true`).

## Миграции БД

Не требуется (схема TASK-0027 + `subdomain_enum_cache` ADR 037).

## Инварианты (защитить тестами)

- `compute_subdomain_diff(old=None,…)` → пустой; new/removed считаются верно;
  порядок/дубликаты не влияют.
- Scheduler берёт только `track_subdomains=true AND is_muted=false`.
- `success_interval_days = min(интервалов)` с floor 1д.
- check_subdomains enqueue'ит notify только при непустом diff.

## Требования к тестам

- `tests/unit/test_subdomain_diff.py` (baseline/new/removed/порядок).
- Тест расчёта интервала (min) и scheduler-выборки (моки со `spec`/`autospec`).

## Definition of Done

- [ ] diff + scheduler + интеграция; cron зарегистрирован; enqueue notify при diff
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 038; образцы — `src/tasks/ssl_scheduler.py`, `src/ssl/diff.py`
  (`compute_ssl_diff`), `SSLCacheRepository.get_due_for_check`.
