# Миграции БД (Alembic)

Этот документ описывает процесс работы с миграциями Alembic в проекте.

## Общие правила

- Все изменения схемы БД — только через миграции.
- Миграции должны быть reversible (downgrade должен возвращать схему в исходное состояние).
- Поддерживается только single-head (одна цепочка ревизий). При конфликте `down_revision` — исправляй вручную.
- `down_revision` всегда указывает на актуальный head (проверяй `ls migrations/versions/ | tail -1` или `alembic current`).
- Перед PR — обязательно round-trip на Postgres (см. ниже).

## Создание миграции

1. Внеси изменения в модель (`src/db/models.py`).

2. Сгенерируй миграцию:
   ```bash
   uv run alembic revision --autogenerate -m "краткое описание (TASK-XXXX)"
   ```

3. Отредактируй сгенерированный файл в `migrations/versions/`:
   - Проверь `down_revision`.
   - Для колонок NOT NULL с дефолтом **всегда** используй SQL-литералы:
     ```python
     server_default=sa.text("''"),        # строка
     server_default=sa.text("false"),     # булево
     ```
     **Не** `server_default=""` или `server_default=False` — на Postgres это ломает миграцию (урок TASK-0008).
   - Backfill существующих строк — через `op.execute(sa.text("UPDATE ... SET x = ... WHERE x = ''"))`.
   - После backfill сними default:
     ```python
     op.alter_column("table", "column", server_default=None)
     ```
   - Добавляй индексы/ограничения явно.

4. Убедись, что downgrade корректен.

## Проверка миграции (обязательно перед PR)

1. Локально (с Postgres):
   ```bash
   uv run alembic upgrade head
   uv run alembic downgrade base
   uv run alembic upgrade head
   ```

2. В CI: smoke-test миграций на эфемерном Postgres (TASK-0009, `test_migrations.py` — запускается при `CI=1`).

3. Полный прогон тестов:
   ```bash
   uv run pytest
   ```

4. Валидация handoff:
   ```bash
   uv run python scripts/handoff.py validate
   ```

5. Проверка, что схема совпадает с моделью (NOT NULL, без лишних defaults после backfill).

## Чек-лист перед PR

- [ ] `down_revision` от актуального head.
- [ ] single-head (нет branching).
- [ ] SQL-литералы в server_default и backfill (sa.text("''"), sa.text("false")).
- [ ] Миграция reversible.
- [ ] Round-trip прошёл (upgrade → downgrade → upgrade) на Postgres.
- [ ] `alembic upgrade head` в CI (через smoke-test) зелёный.
- [ ] Полный `pytest` зелёный.
- [ ] `handoff.py validate` OK.
- [ ] Нет изменений в `alembic.ini` или `env.py` без причины.

## Примеры

- Исправленная миграция registrable: `migrations/versions/20260529_0000_add_registrable_domain_fields.py`
  - Использует `sa.text("''")`, backfill с `''`, снятие default.
- Миграция email_deep: `20260531_0000_add_email_deep_cache_table.py` (down_revision на предыдущий head, SQL-литералы).

## Полезные команды

```bash
# Текущий head
uv run alembic current

# Список ревизий
uv run alembic history --verbose

# Применить/откатить
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic downgrade base
```

См. также:
- TASK-0008 (фикс миграции registrable)
- TASK-0009 (CI smoke-test)
- CLAUDE.md (миграции на реальном Postgres)
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`
