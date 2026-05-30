---
id: TASK-0025
title: Fast-follow по TASK-0023 — тесты scheduler, update_fail upsert, мелочи (ADR 037)
status: done
milestone: v0.11.0
adr: 037
area: code
depends_on: [TASK-0023]
branch: task/0025-subdomain-enum-followup
owner: claude
session: docs/sessions/2026-05-30_task_0025_subdomain_enum_followup.md
pr: "18"
created: 2026-05-30
---

# TASK-0025 — Fast-follow по subdomain enumeration (ADR 037)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> **Должен лечь до тега v0.11.0** (закрывает долги ревью TASK-0023).

## Цель

Закрыть замечания ревью TASK-0023, не блокировавшие мерж, но обязательные
до релиза v0.11.0.

## Контекст

TASK-0023 (PR #16) смержен функционально готовым. Ревью выявило три долга,
вынесенных в этот fast-follow, чтобы не блокировать UX-таск (TASK-0024).

## Изменения по файлам

1. **Тесты scheduler (обязательно, CLAUDE.md).**
   `src/subdomains/scheduler.py::calculate_next_subdomain_check` — чистый
   schedule-расчёт без теста. CLAUDE.md требует тесты на schedule-расчёты.
   - `tests/unit/test_subdomains_scheduler.py`: все 4 ветки TTL
     (есть поддомены → 7д; нет → 30д; fail 1..2 → 1ч; fail ≥3 → 1д),
     проверка timezone-aware, ошибка на naive `now`.

2. **`update_fail` теряет первый фейл.**
   `src/db/repositories/subdomain_enum_cache.py::update_fail` делает `UPDATE`
   по `registrable_domain`; если строки ещё нет (первая enumeration сразу
   упала — row создаётся только в success-ветке `check_subdomains`), апдейт
   затрагивает 0 строк → `fail_count`/`last_error`/`next_check_at` теряются.
   - Переписать на UPSERT (`pg_insert … on_conflict_do_update`): при INSERT
     `fail_count=1`, при конфликте — `fail_count = subdomain_enum_cache.fail_count + 1`,
     писать `last_error`, `next_check_at`, `is_reachable=False`.
   - Тест в `tests/` (юнит или integration): первый фейл создаёт строку с
     `fail_count=1`; повторный — инкремент.

3. **Мелочи в `src/subdomains/client.py`.**
   - Удалить неиспользуемую константу `QUERY_TIMEOUT` (используется только
     `TOTAL_TIMEOUT`), убрать из `__all__`.
   - Унифицировать `error_type`-строки с docstring `types.py`
     (`timeout`, `unavailable`, `rate_limit`, `parse_error`): сейчас встречаются
     рассинхронные `parser_error` / `internal_error`. Привести к единому набору
     (либо расширить перечень в docstring `SubdomainEnumError` и придерживаться его).

## Миграции БД

Не требуется (схема TASK-0022).

## Инварианты (защитить тестами)

- Scheduler: 4 TTL-ветки + timezone-aware guard покрыты.
- `update_fail`: первый фейл персистится (`fail_count=1`), повторный инкрементит.
- `error_type` — закрытый согласованный набор.

## Требования к тестам

- `tests/unit/test_subdomains_scheduler.py` (новый).
- Тест на `update_fail` upsert-семантику. Моки — со `spec`/`autospec`.

## Definition of Done

- [x] Scheduler покрыт тестами; `update_fail` — upsert; client-мелочи закрыты
- [x] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [x] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- TASK-0023 (origin), ADR 037; образец upsert — `SubdomainEnumCacheRepository.upsert`.

---

## Ревью v1 — один фикс до мержа (2026-05-30)

PR #18: `update_fail`→UPSERT ✅, `error_type` унифицирован ✅, `QUERY_TIMEOUT`
убран ✅, тесты scheduler (11) ✅. Один дефект — **off-by-one в передаче
`fail_count` в scheduler**, ломает backoff (то, ради чего делался upsert).

**`src/tasks/check_subdomains.py`, ветка ошибки** — сейчас в scheduler уходит
счётчик ДО инкремента, а `update_fail` сохранит `current+1`:

```diff
                 current_fail_count = old_cache.fail_count if old_cache else 0
                 next_check_at = calculate_next_subdomain_check(
                     has_subdomains=False,
-                    fail_count=current_fail_count,
+                    fail_count=current_fail_count + 1,
                 )
```

Почему важно: scheduler трактует `fail_count=0` как success-ветку (см. ваш же
`test_zero_fail_count_is_success_path`). При первом фейле (`old_cache=None` → 0)
получается `has_subdomains=False` → `next_check_at = now + 30 дней` вместо 1 часа;
дальше всё смещено на 1 (3-й фейл → 1ч вместо 1 дня). `current+1` = счётчик
ПОСЛЕ фейла, согласован с тем, что пишет `update_fail` (INSERT `fail_count=1`).

В v0.11 (on-demand) баг спящий (`next_check_at` на фейле командой не читается —
freshness по `fetched_at`), но логика неверна и выстрелит в v0.12-мониторинге.
Поскольку 0025 — последняя задача перед тегом v0.11.0, чиним до мержа.

**Тест (guard):** при первом фейле (`old_cache=None`) `check_subdomains`
передаёт в scheduler `fail_count=1` (или `next_check_at ≈ now + 1ч`). Замокать
`fetch_subdomains` → `SubdomainEnumError` и проверить аргумент/результат.

Дорабатывать в той же ветке `task/0025-subdomain-enum-followup`.
