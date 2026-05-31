---
id: TASK-0045
title: Anti-drift — убрать getattr на ORM в subdomains-button freshness
status: done
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0042]
branch: task/0045-subdomains-button-getattr-antidrift
owner: claude-code
session: "docs/sessions/2026-06-01_task-0045-getattr-antidrift.md"
pr: ""
created: 2026-05-31
completed: 2026-06-01
---

> ## ✅ Ревью архитектора (2026-06-01) — merged
>
> `_is_subdomain_cache_fresh(cached: SubdomainEnumCache | None)` типизирован,
> прямой доступ `.fetched_at`/`.subdomains` (None-guard по `cached is None`),
> `getattr` на ORM убран полностью (grep чистый). Тест-фабрика → `MagicMock(
> spec=SubdomainEnumCache)`, `test_uses_getattr_defensively` удалён. Anti-drift
> по CLAUDE.md соблюдён.

# TASK-0045 — Убрать getattr на ORM (subdomains button, ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Follow-up из ревью PR #31 (TASK-0042). Маленькая правка, не блокер релиза.

## Цель

Привести freshness-логику кнопки «Поддомены» в соответствие с anti-drift-
конвенцией CLAUDE.md: убрать `getattr(orm, "field", default)` на объекте
`SubdomainEnumCache`, обращаться к полям напрямую через типизированную ссылку.

## Контекст / корень проблемы

В `src/bot/handlers/whois.py` (TASK-0042) freshness-проверка subdomain-кэша
использует `getattr`:

- `_is_subdomain_cache_fresh(cached: Any)` → `getattr(cached, "fetched_at", None)`
- в `_show_subdomains_from_whois_card`: `getattr(cached, "subdomains", None)`,
  `getattr(cached, "fetched_at", None)`

`cached` в проде — всегда `None` либо реальный `SubdomainEnumCache`. CLAUDE.md
(«Защита от рассинхрона») прямо запрещает `getattr(orm, "field", default)` —
он молча вернёт default при переименовании поля и замаскирует дрейф (здесь:
кнопка тихо станет считать кэш несвежим и всегда пере-enqueue'ить). Исполнитель
в первом круге понял правку наоборот (добавил getattr + тест
`test_uses_getattr_defensively`, закрепивший паттерн); по решению владельца
0042 смержен, правка вынесена сюда.

## Изменения по файлам

- `src/bot/handlers/whois.py`:
  - `_is_subdomain_cache_fresh(cached: SubdomainEnumCache | None) -> bool` —
    типизировать; внутри обращаться к `cached.fetched_at` напрямую (None-guard
    по `cached is None`, не по `getattr`).
  - В `_show_subdomains_from_whois_card` — `cached.subdomains` / `cached.fetched_at`
    напрямую (cached уже типа `SubdomainEnumCache | None` из репозитория).
- `tests/unit/test_whois_subdomains_button.py`:
  - убрать/переписать `test_uses_getattr_defensively` (не закреплять getattr);
    оставить кейсы none/fresh/stale на типизированном объекте
    (`MagicMock(spec=SubdomainEnumCache)`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `_is_subdomain_cache_fresh(None)` → False; свежий (<7д) → True; протух → False.
- Нет `getattr(...)` на ORM-объекте в этом коде (grep чистый).
- `mypy src` проходит при прямом доступе к полям (типизированный параметр).

## Definition of Done

- [ ] getattr на ORM убран; прямой типизированный доступ
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Ревью: TASK-0042 (тело файла), session 2026-05-31_task-0041-deep-email-button
- CLAUDE.md → «Защита от рассинхрона (anti-drift)»
