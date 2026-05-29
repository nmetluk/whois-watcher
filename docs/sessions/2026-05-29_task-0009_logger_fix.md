---
# TASK-0009 — Фикс логгеров и теста миграций

**Дата:** 2026-05-29
**Исполнитель:** Claude Code
**Архитектор:** Cowork
**Ветка:** `task/0009-migration-ci-smoke-test`
**PR:** #7

## Цель

Починить падение CI на `tests/unit/test_locales.py::TestT::test_missing_key_returns_key_and_warns`
и `tests/integration/test_migrations.py::test_migrations_roundtrip`.

## Шаг 1 — Диагностика ошибки CI

**Исходная проблема (из задания):** тест локалей падал после теста миграций,
потому что `migrations/env.py:19` вызывал `fileConfig(config.config_file_name)` с
дефолтным `disable_existing_loggers=True`, отключая логгер "src.locales".

**Фикс #1:** `disable_existing_loggers=False` в `migrations/env.py:19`
(коммит `9b9b063`).

**Найденная дополнительная проблема:** `tests/integration/test_migrations.py`
содержал фиктивную замену драйвера:

```python
# Строка 59 (до фикса):
sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
cfg.set_main_option("sqlalchemy.url", sync_url)
```

**Корень:**
1. `psycopg2` **не установлен** в зависимостях (только `asyncpg`)
2. `migrations/env.py:22` **перезаписывает** `sqlalchemy.url` на
   `settings.postgres_dsn` (который использует `asyncpg`)
3. Sync URL в тесте был вводящим в заблуждением — runtime использует asyncpg,
   и миграции тоже (env.py → `async_engine_from_config`)

**Фикс #2:** убрать фиктивную замену драйвера, оставить URL как есть
(коммит `b571dd6`).

## Что сделано

### Фикс #1: migrations/env.py

```python
# Было:
fileConfig(config.config_file_name)

# Стало:
fileConfig(config.config_file_name, disable_existing_loggers=False)
```

### Фикс #2: tests/integration/test_migrations.py

```python
# Было:
sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
cfg.set_main_option("sqlalchemy.url", sync_url)

# Стало:
cfg.set_main_option("sqlalchemy.url", db_url)
```

Обновлён docstring фикстуры `alembic_cfg` — теперь он корректно описывает
async execution.

### Проверка

```bash
# Тест локалей проходит (с env как в CI)
$ BOT_TOKEN="test:ci-bot-token" WEBHOOK_BASE_URL="https://ci.example.com" \
  WEBHOOK_SECRET="ci-webhook-secret" POSTGRES_HOST=localhost POSTGRES_PORT=5432 \
  POSTGRES_USER=whoiswatcher POSTGRES_PASSWORD=testpass POSTGRES_DB=whoiswatcher \
  uv run pytest tests/unit/test_locales.py::TestT::test_missing_key_returns_key_and_warns -v
PASSED [100%]

# Линтеры чисты
$ uv run ruff check src tests
All checks passed!
$ uv run black --check src tests
All done! ✨ 🍰 ✨
$ uv run mypy src
Success: no issues found in 116 source files

# Validate
$ uv run python scripts/handoff.py validate
VALIDATE: OK (13 задач)
```

Тест миграций падает локально с `InvalidPasswordError` — это ОЖИДАЕМО,
потому что Postgres недоступен. В CI Postgres service поднят, и тест
должен пройти.

## Коммиты

1. `9b9b063` — fix(TASK-0009): не гасить логгеры приложения в alembic env.py
   (disable_existing_loggers=False)
2. `b571dd6` — fix(test): убрать фиктивную замену asyncpg на psycopg2 в тесте
   миграций

## Definition of Done

- [x] `migrations/env.py` исправлен: `disable_existing_loggers=False`
- [x] `tests/integration/test_migrations.py` исправлен: убрана фиктивная замена
  драйвера на psycopg2 (который не установлен)
- [x] Тест локалей проходит локально с CI env
- [x] `ruff` / `black --check` / `mypy src` чисто
- [x] `handoff.py validate` OK
- [x] Изменения запушены в `task/0009-migration-ci-smoke-test`
- [ ] CI зелёный на PR #7 (ждём проверки)

## Статус

Два коммита запушены. Ожидаем зелёный CI — исправлены обе проблемы:
1) логгеры не гасятся alembic, 2) тест миграций использует правильный драйвер.
