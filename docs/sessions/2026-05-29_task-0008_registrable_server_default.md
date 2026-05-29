---
# TASK-0008 — Убрать server_default с registrable_domain

**Дата:** 2026-05-29
**Исполнитель:** Claude Code
**Архитектор:** Cowork
**Ветка:** `task/0008-registrable-server-default-fix`
**PR:** https://github.com/nmetluk/whois-watcher/pull/5

## Цель

Убрать рассинхрон между миграцией и моделью: колонка `registrable_domain`
в миграции имеет `server_default=""`, но модель его не имеет.

## Что сделано

### 1. Миграция уже существовала

Миграция `20260529_0001_remove_registrable_server_default.py` уже была
создана ранее. Проверена корректность:

```python
def upgrade() -> None:
    op.alter_column("user_domains", "registrable_domain", server_default=None)

def downgrade() -> None:
    op.alter_column(
        "user_domains", "registrable_domain", server_default=sa.text("")
    )
```

- `revision: 20260529_remove_registrable_server_default`
- `down_revision: 20260529_registrable_domain` (верная ссылка)
- Логика: убирает `server_default=sa.text("")` с колонки

### 2. Проверка тестов

```
============================= 710 passed in 7.29s ==============================
```

Все тесты проходят. Существующие тесты `test_domain_service.py` покрывают
заполнение `registrable_domain` при вставке.

### 3. Проверка форматирования и линтеров

```bash
$ uv run ruff check src migrations/versions/
All checks passed!

$ uv run black --check src migrations/versions/
All done! ✨ 🍰 ✨
115 files would be left unchanged.
```

### 4. mypy

Ошибки в `src/bot/handlers/whois.py` (передача `str | None` вместо `str`).
Это существующие проблемы, не связанные с TASK-0008.

### 5. Миграция на чистой БД

Не проверена локально (нет доступа к Docker daemon). Будет проверена в CI.

### 6. Validate

```bash
$ uv run python scripts/handoff.py validate
VALIDATE: OK (8 задач)
```

## Definition of Done

- [x] Код реализован по спецификации (миграция уже существовала)
- [x] `pytest` зелёный (710 passed)
- [x] `ruff` / `black --check` чисто
- [x] `mypy src` — есть ошибки, но не связанные с задачей
- [ ] Миграция применяется на чистой БД (проверится в CI)
- [x] Per-session отчёт создан
- [x] `handoff.py validate` проходит
- [ ] PR открыт по шаблону, CI зелёный

## Статус

Готово к открытию PR. Миграция существует, тесты проходят, линтеры чисты.
