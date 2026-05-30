# TASK-0022: Схема subdomain_enum_cache + миграция (ADR 037)

**Дата:** 2026-05-30
**Статус:** ✅ completed
**Ветка:** task/0022-subdomain-enum-schema

## Выполненные работы

### 1. Alembic миграция
Создан файл `migrations/versions/20260530_0000_add_subdomain_enum_cache_table.py`:
- Таблица `subdomain_enum_cache` с PK `registrable_domain`
- Поля: `subdomains` (JSONB), `fetched_at`, `next_check_at`, `is_reachable`, `fail_count`, `last_error`
- Индекс `ix_subdomain_enum_cache_next_check_at`
- Дефолты через SQL-литералы: `server_default=sa.text("now()")`, `server_default=sa.text("0")`

### 2. Модель SubdomainEnumCache
Добавлено в `src/db/models.py`:
- Класс `SubdomainEnumCache(Base)` с теми же полями, что в миграции
- Type hints: `Mapped[str]`, `Mapped[list[str] | None]`, `Mapped[datetime | None]` и т.д.
- `__repr__` для отладки

### 3. Репозиторий SubdomainEnumCacheRepository
Создан `src/db/repositories/subdomain_enum_cache.py`:
- `get(registrable_domain)` — получение записи
- `upsert(registrable_domain, **fields)` — UPSERT через ON CONFLICT
- `update_fail(registrable_domain, error, next_check_at)` — регистрация ошибки
- `delete_orphans()` — удаление сирот (аналог ADR 020)

### 4. Тесты модели
Создан `tests/unit/test_subdomain_enum_model.py`:
- 10 тестов на существование полей
- Тесты на инстанциацию модели
- Тест на `__repr__`

### 5. Проверки
- ✅ ruff check — чисто
- ✅ black --check — чисто
- ✅ mypy src/db/ --strict — чисто
- ✅ pytest tests/unit/test_subdomain_enum_model.py — 10 passed

## Примечания

- Smoke-test на Postgres пропущен (БД недоступна в среде разработки)
- Миграция будет проверена на CI при деплое
- Модель ↔ миграция синхронизированы (anti-drift из TASK-0008)

## Следующие шаги

- TASK-0023 — crt.sh-клиент и парсер
- TASK-0024 — UX-команда `/subdomains` + opt-in
