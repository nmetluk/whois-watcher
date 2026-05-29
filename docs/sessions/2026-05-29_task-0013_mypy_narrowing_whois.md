# Session: TASK-0013 mypy narrowing в whois.py

**Дата:** 2026-05-29
**Агент:** Claude Code
**Таск:** TASK-0013
**Ветка:** task/0013-mypy-narrowing-whois
**PR:** https://github.com/nmetluk/whois-watcher/pull/8

## Что сделано

Исправлен mypy type-narrowing в `src/bot/handlers/whois.py`, функция `_send_whois_card`.

### Проблема

После раннего `return` по `result.data is None` шли вызовы `is_subdomain()` и `registrable_domain()`, которые сбрасывали mypy-narrowing. Тернарник `lookup_domain = parent if is_sub else result.data.domain` приводил к ошибкам `Item "None" has no attribute "domain"`.

### Решение

Заменён тернарник на явный if/else:
```python
if is_sub:
    parent = registrable_domain(domain_input)
    lookup_domain = parent
else:
    lookup_domain = result.data.domain
```

Mypy теперь понимает, что в обеих ветках `lookup_domain` имеет тип `str` (не `str | None`).

## Проверка

- `mypy src` — 116 source files, success
- `pytest` — 710 passed
- `ruff check` / `black --check` — чисто
- CI (PR #8) — зелёный ✓

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Исходный фикс: коммит `fc6bc96` (ветка `task/0008-registrable-server-default-fix`)
