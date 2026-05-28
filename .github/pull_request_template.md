<!-- PR по одной задаче. Заголовок: fix(scope): краткое (TASK-NNNN) -->

## Задача

TASK-NNNN — <название>. Майлстоун: vX.Y.Z. ADR: NNN (если есть).

## Что сделано

-

## Проверки (Definition of Done)

- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff check src tests` / `black --check src tests` / `mypy src` чисто
- [ ] Миграция применяется на чистой БД (если схема менялась)
- [ ] `python scripts/handoff.py validate` проходит
- [ ] Per-session отчёт в `docs/sessions/` создан и вписан в `session:` таска
- [ ] `handoff/INDEX.md` пересобран (`handoff.py board`)
- [ ] `CHANGELOG.md` / `pyproject.toml` обновлены (если релиз)

## Session-отчёт

`docs/sessions/SESSION-NNNN-...md`

## Заметки для ревью

-
