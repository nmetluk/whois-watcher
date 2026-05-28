# Сессия 2026-05-28 — TASK-0001 (wishlist ↔ tracked bugfix)

**Задача:** TASK-0001 — Багфикс wishlist ↔ tracked (авто-промоут)
**Ветка:** task/0001-wishlist-tracked-fix
**Выполнено:** полный цикл разработки, тесты зелёные

## Описание проблемы

`/add` на домен, который уже лежит у пользователя в wishlist, возвращал
`already_tracked` и не конвертировал его в обычное отслеживание. Домен
застревал в лимбо: невидим в `/list` (скрывался как wishlist) и не
виден в `/wishlist`.

## Реализация

### Изменённые файлы

1. **`src/db/repositories/domains.py`**
   - Добавлен метод `promote_from_wishlist(user_id, domain) -> bool`
   - `UPDATE ... WHERE user_id, domain, is_wishlist=True`
   - Восстанавливает дефолтные флаги `DEFAULT_NOTIFICATION_FLAGS`
   - SSL/DNS toggle'ы не трогаем

2. **`src/services/domains.py`**
   - `add_for_user` теперь использует `get_for_user` вместо `exists`
   - Логика: None → вставка; wishlist → промоут; tracked → already_tracked
   - Промоут идемпотентен: повторный `/add` → `already_tracked`

3. **`src/services/results.py`**
   - Добавлен статус `"promoted"` в `AddStatus`

4. **`src/bot/handlers/add_remove.py`**
   - Обработка статуса `"promoted"` с локализацией

5. **`src/locales/ru.py`, `src/locales/en.py`**
   - Ключ `commands.add.promoted_from_wishlist`

6. **`tests/unit/test_promote_wishlist.py`**
   - 5 тестов покрывают все ветки промоута

7. **`tests/unit/test_domain_service.py`**
   - Обновлены существующие тесты для новой логики `get_for_user`

### Проверки

- `ruff check src/` — OK
- `black --check src/` — OK
- `mypy src/` — OK
- `pytest tests/unit/test_promote_wishlist.py` — 5 passed
- `pytest tests/unit/test_domain_service.py` — 16 passed
- `python scripts/handoff.py validate` — OK

### Релиз

- Версия обновлена: 0.8.0 → 0.8.1
- Запись в `CHANGELOG.md` добавлена

## Следующие шаги

- Открыть PR: `git push origin task/0001-wishlist-tracked-fix`
- После мержа обновить `handoff/TASK-0001-*.md` (статус, PR, session)
