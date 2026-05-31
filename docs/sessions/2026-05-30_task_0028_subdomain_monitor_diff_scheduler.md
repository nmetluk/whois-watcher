# Сессия 2026-05-30: TASK-0028 — Diff + scheduler мониторинга поддоменов (ADR 038)

## Задача

TASK-0028 — фоновое обнаружение новых/исчезнувших поддоменов: чистый diff,
периодический scheduler (по образцу `ssl_scheduler_tick`), интеграция в
`check_subdomains`.

## Выполнено

### 1. `src/subdomains/diff.py` (новый)

Чистая функция `compute_subdomain_diff(old, new)`:
- `old=None` → пустой diff (baseline, не алертим)
- `SubdomainDiff` dataclass с `new` и `removed` list[str]
- Игнорирует порядок/дубликаты (работа на set)

### 2. `src/subdomains/scheduler.py`

Расширен `calculate_next_subdomain_check`:
- Добавлен параметр `success_interval_days` (default 7)
- Floor 1 день для интервала

### 3. `src/db/repositories/subdomain_enum_cache.py`

Добавлены методы:
- `get_due_for_check(limit)` — выборка due registrable-доменов с подписчиками
  `track_subdomains=true AND is_muted=false`
- `get_min_check_interval(registrable_domain)` — минимум интервалов от подписчиков
  (с fallback 7 дней, floor 1)

### 4. `src/tasks/subdomain_scheduler.py` (новый)

ARQ cron-задача `subdomain_scheduler_tick`:
- **Bootstrap**: создаёт заглушки в `subdomain_enum_cache` для registrable с подписчиками
- **Выборка**: due registrable через `get_due_for_check`
- **Enqueue**: ставит `check_subdomains` для каждого

### 5. `src/tasks/check_subdomains.py`

Интеграция diff:
- Берёт старый `subdomains` ДО upsert
- Вызывает `compute_subdomain_diff(old, new)`
- При `has_any_changes` — enqueue `notify_subdomain_changes` (реализация в TASK-0029)
- Считает `success_interval_days` через `get_min_check_interval`

### 6. `src/tasks/arq_config.py`

- Импорт `subdomain_scheduler_tick`
- Cron запись: каждые 5 минут, как WHOIS/SSL/DNS

### 7. Тесты

**`tests/unit/test_subdomain_diff.py`** (новый):
- 9 тестов для `compute_subdomain_diff`
- baseline, new, removed, порядок, дубликаты

**`tests/unit/test_subdomains_scheduler.py`**:
- 5 новых тестов для параметра `success_interval_days`
- custom interval, floor 1, default 7, override при фейлах/отсутствии

**`tests/unit/test_subdomain_enum_cache_repo.py`**:
- 4 новых теста для `get_due_for_check` и `get_min_check_interval`

### 8. Проверки

- `ruff check --fix` — OK (unused imports удалены)
- `black` — OK
- `mypy src` — OK (исправлен `field(default_factory=list)`)
- `pytest` — 31 passed

## Следующие шаги

TASK-0028 → TASK-0029 (notify UX), TASK-0030 (audit v0.12).

## Артефакты

- Ветка: `task/0028-subdomain-monitor-diff-scheduler`
- PR: (будет открыт после коммита)
