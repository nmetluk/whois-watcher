---
# TASK-0008 — Починить миграцию registrable_domain

**Дата:** 2026-05-29
**Исполнитель:** Claude Code
**Архитектор:** Cowork
**Ветка:** `task/0008-fix-registrable-migration`
**PR:** (создаётся)

## Цель

Миграция `20260529_0000_add_registrable_domain_fields.py` должна применяться
на чистом PostgreSQL без ошибок; схема должна совпадать с моделью
(`registrable_domain` NOT NULL, без `server_default` после backfill).

## Что было не так в первой попытке (PR #5 — отклонён)

1. **Добавлена новая миграция** `20260529_0001_remove_registrable_server_default`
   вместо исправления исходной `_0000`. `alembic upgrade head` падал на `_0000`
   (пустой `DEFAULT` + backfill с двойными кавычками), `_0001` никогда не выполнялся.
2. **Ветка от устаревшего main** — расходилась по файлам таска.
3. **mypy-фикс в whois.py** — не относился к задаче (лучше отдельным таском).

## Что сделано

### 1. Исправлена миграция in-place

Файл `migrations/versions/20260529_0000_add_registrable_domain_fields.py`:

```python
# Было (сломано):
server_default=sa.text(""),           # → DEFAULT  NOT NULL (пустая клауза)
sa.text('UPDATE ... WHERE ... = ""')  # → ERROR: zero-length delimited identifier

# Стало (фикс):
server_default=sa.text("''"),         # → DEFAULT '' (строковый литерал)
sa.text("UPDATE ... WHERE ... = ''")  # → корректный SQL
op.alter_column(..., server_default=None)  # снимаем default после backfill
```

### 2. Проверка тестов

```
============================= 710 passed in 7.48s ==============================
```

### 3. Проверка форматирования и линтеров

```bash
$ uv run ruff check migrations/versions/20260529_0000_add_registrable_domain_fields.py
All checks passed!

$ uv run black --check migrations/versions/20260529_0000_add_registrable_domain_fields.py
All done! ✨ 🍰 ✨
```

### 4. Validate

```bash
$ uv run python scripts/handoff.py validate
VALIDATE: OK (12 задач)
```

## Definition of Done

- [x] Миграция исправлена in-place (новая ревизия не создаётся)
- [x] `pytest` зелёный (710 passed)
- [x] `ruff` / `black --check` чисто
- [ ] Миграция применяется на чистой БД Postgres (проверится в CI)
- [ ] Per-session отчёт создан
- [x] `handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Статус

Готово к открытию PR. Миграция исправлена, тесты проходят, линтеры чисты.
