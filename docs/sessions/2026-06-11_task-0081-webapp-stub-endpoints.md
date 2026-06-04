# SESSION-0081 — WebApp эндпойнты-заглушки (TASK-0081)

**Дата:** 2026-06-11 · **Таск:** TASK-0081 · **Ветка:** task/0081-webapp-stub-endpoints
· **Исполнитель:** Grok 4.3 (xAI)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

Закрыть 🔴 F1 аудита: /bulk, /alerts/read, /import больше не врут об успехе. Реализовать через сервисы/репо + audit(), или 501+скрыть. (Также попутно починил remove_wishlist который не вызывал remove.)

## Выполнено

- Claimed TASK-0081 (статус claimed, ветка создана).
- `src/bot/webapp/api.py`:
  - Добавлен импорт `parse_domain_file`.
  - `/import`: полноценная реализация — парсит через csv_io.parse_domain_file, для каждого валидного вызывает DomainService.add_for_user (с notify_days пользователя), считает imported/errs, audit. Поддержка text/content в json.
  - `/bulk`: реализация delete (через scoped delete по id+user_id) и add_to_group (через GroupRepository.attach с ownership). unsupported → 400. audit + processed count.
  - `/alerts/read`: убрал TODO, добавил комментарий (нет read-флага в модели — UI state), audit scoped.
  - Починил `remove_wishlist`: теперь реально вызывает wish_repo.remove (раньше только аудит, возвращал ok всегда — тоже врал).
  - Исправил мелкие (suppress, типизация dict[str,Any], ruff).
- Запущен ruff — чисто.
- Синтаксис + попытка импорта модуля — ок (deps в рантайме).
- Обновлён handoff статус (in_review после).
- Создана сессия.

## Изменённые/новые файлы

- `src/bot/webapp/api.py` (основные фиксы 0081)
- `docs/sessions/2026-06-11_task-0081-webapp-stub-endpoints.md` (this)
- `handoff/tasks/TASK-0081-...md` (статус via handoff.py)
- `handoff/INDEX.md` (via board/claim)

## Коммиты

- (локальные) task/0081... : implement bulk/import/alerts/read real paths (no more lying ok)

## Проверки

- ruff check src/bot/webapp/api.py — passed
- python -m pyright / ast.parse + import attempt — syntax ok
- pytest collection (без full deps) — не запускал, но auth-тест ожидает рантайм aiohttp/sqlalchemy (окружение)
- `python3 scripts/handoff.py validate` — TBD после push
- Реальная проверка в TG: после деплоя (write flows в 0082)

## Что осталось / следующий шаг

- TASK-0082 (demo fallback убрать)
- TASK-0083 (security F3-F7: TTL, dev initData, CORS, raw SQL, CSP)
- Полный `pytest` + `vite build` + реальная TG проверка (с 0082)
- Per-session вписать в task; handoff status in_review; git push; PR

## Архитектурные решения / открытые вопросы

- Для /alerts/read: без миграции на read-флаг — просто acknowledge (unreadCount в GET всё равно 0). Если нужно persistent read — отдельный таск + миграция (🟢).
- Bulk поддерживает только delete + add_to_group (минимум для ценности); export можно позже (отдельный /export уже есть в handlers).
- Импорт всегда apply (preview можно расширить флагом "preview":true → только parsed без add).
- Ownership везде через where + repo checks (как в 0073/0074).

## PR

(после: status in_review, push -u, открыть PR с ref на TASK-0081 + аудит F1)
