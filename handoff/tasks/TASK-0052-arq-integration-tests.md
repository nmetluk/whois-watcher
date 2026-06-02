---
id: TASK-0052
title: Интеграционные тесты ARQ-тасок на реальных Postgres+Redis (pytest-docker)
status: done
milestone: v0.14.0
adr: ""
area: code
depends_on: []
branch: task/0052-arq-integration-tests
owner: grok-4.3
session: docs/sessions/2026-06-08_task-0052-arq-integration-tests.md
pr: https://github.com/nmetluk/whois-watcher/pull/37
created: 2026-06-04
completed: 2026-06-08
---

> ## ✅ Ревью архитектора (2026-06-08) — merged
>
> pytest-docker + маркеры `integration`/`arq`; conftest: CI → github-services
> (postgres+redis уже в ci.yml), локально → pytest-docker compose. Реальные
> `check_subdomains`/`check_email_deep` против настоящих Postgres+Redis (upsert,
> redis-guard, enqueue). Тесты исполняются в CI (`pytest -v`, сервисы есть).

# TASK-0052 — Интеграционные тесты ARQ (v0.14)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Покрыть ключевые ARQ-задачи **интеграционными** тестами через реальные
Postgres+Redis (`pytest-docker`), а не только юнит-моками — ловить рассинхрон
схемы/драйвера/redis-семантики, который моки маскируют.

## Контекст / корень проблемы

Сейчас ARQ-задачи (`check_subdomains`, `check_email_intel`, `check_email_deep`,
scheduler'ы) покрыты юнит-тестами с моками сессии/redis. Это пропускает баги
интеграции (реальный UPSERT/индексы, redis-guard, TTL). Migration round-trip уже
есть в CI; нужен слой реальных прогонов задач.

## Изменения по файлам

- `tests/integration/` — новые тесты на `pytest-docker` (Postgres 16 + Redis 7),
  фикстуры поднятия контейнеров + применение миграций (`alembic upgrade head`).
- Покрыть **репрезентативный набор** (не все): хотя бы
  `check_subdomains` (upsert/update_fail/diff→enqueue), `check_email_deep`
  (кэш/TTL/redis-guard), один scheduler-tick (выборка due по индексу).
- `pyproject.toml`/CI — `pytest-docker` в dev-зависимости; отдельный CI-джоб
  (или маркер `@pytest.mark.integration`), чтобы не замедлять юнит-прогон.
- (опц.) **Бенчмарк** `scheduler_tick` на ~100K строк — скрипт/тест с
  таймингом выборки `next_check_at <= now()`; результат — в session-отчёт.

## Миграции БД

Не требуется (тесты применяют существующие миграции).

## Инварианты (защитить тестами)

- Задачи реально пишут/читают Postgres и Redis (не моки); поведение совпадает
  с юнит-ожиданиями.
- Redis-guard реально предотвращает дубль (через настоящий Redis).

## Definition of Done

- [ ] Интеграционные тесты на pytest-docker для ≥3 представительных задач
- [ ] CI-джоб/маркер настроен; **полный прогон зелёный**
- [ ] (опц.) бенчмарк scheduler зафиксирован в отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- TODO.md (tech-debt: интеграционные тесты, бенчмарк scheduler)
- CLAUDE.md → миграции/anti-drift
