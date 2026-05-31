---
id: TASK-0034
title: Тесты success+diff→enqueue и baseline в check_subdomains (ADR 038)
status: open
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0028]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0034 — Тесты success/diff/enqueue в check_subdomains (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Источник находки — `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
> (finding 🟠 в разделе «Тесты»).

## Цель

Покрыть «склейку» ADR 038 в `check_subdomains`: на успешном refresh с
изменениями enqueue'ится `notify_subdomain_changes` с корректным payload, а на
первой проверке (baseline, `old_cache=None`) — **не** enqueue'ится. Сейчас
`tests/unit/test_check_subdomains_task.py` покрывает только off-by-one на
failure-ветке.

## Контекст / корень проблемы

`src/tasks/check_subdomains.py` при успехе: берёт `old_subdomains` ДО upsert,
upsert'ит свежий список, считает `compute_subdomain_diff(old, new)` и при
`diff.has_any_changes` зовёт `arq_redis.enqueue_job("notify_subdomain_changes",
registrable_domain=…, diff={"new":…,"removed":…})`. Эта связка (имена полей,
форма payload, отсутствие алерта на baseline) не покрыта — дрейф пройдёт
незаметно (CLAUDE.md «Защита от рассинхрона»).

## Изменения по файлам

- `tests/unit/test_check_subdomains_task.py` — добавить success-кейсы.
  Замокать `get_session`/repo (`MagicMock`/`create_autospec`), `fetch_subdomains`
  → `SubdomainEnumResult`; `old_cache` — `MagicMock(spec=SubdomainEnumCache)` с
  заданным `.subdomains`. Проверять вызовы `arq_redis.enqueue_job` (моки со
  `spec`/`autospec`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `old_cache=None` (baseline) + непустой `result.subdomains` → `enqueue_job`
  **не вызван**; в кэш записан baseline; `next_check_at` от success-интервала.
- `old_cache.subdomains=[a,b]`, новый `[b,c]` → `enqueue_job("notify_subdomain_changes",
  …, diff={"new":["c"],"removed":["a"]})` вызван ровно один раз.
- Нет изменений (old==new как множества) → `enqueue_job` не вызван.
- Redis-guard: `set(nx=True)` вернул `None`/`False` → ранний выход
  `already_in_progress`, ни fetch, ни enqueue.

## Требования к тестам

- Unit, без реальной БД/сети. Все инварианты выше — отдельными кейсами.
- (Опц., если поднимется Postgres-фикстура) интеграционный кейс на
  `SubdomainEnumCacheRepository.get_due_for_check`/`get_min_check_interval`
  с реальными данными — закрывает 🟡 из аудита.

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
- Связанные: TASK-0028 (реализация), TASK-0033, TASK-0035
