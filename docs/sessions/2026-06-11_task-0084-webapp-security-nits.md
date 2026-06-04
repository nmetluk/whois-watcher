# SESSION-0084 — WebApp security nits (TASK-0084)

**Дата:** 2026-06-11 · **Таск:** TASK-0084 · **Ветка:** task/0084-webapp-security-nits
· **Исполнитель:** Grok 4.3 (xAI)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

🟢 Fast-follow F8–F10 из аудита v0.16 (0071): лимиты на группы (name/color/icon), фикс CORS Allow-Headers (убрать *), документировать replay-риск (F10, принятый из-за короткого TTL F3).

## Выполнено

- Claimed TASK-0084 (handoff.py).
- **F8 (группы длины/валидация):**
  - `src/bot/webapp/api.py`: в `create_group` — валидация name≤100, color ∈ a0..a7, icon≤32 (ранний 400).
  - `src/db/repositories/groups.py`: валидация в `create()` и `update()` (ValueError).
  - Обработка ValueError в API → 400.
- **F9 (CORS headers):**
  - `src/bot/webapp/api.py` cors_mw: `Access-Control-Allow-Headers` теперь явный `"X-Telegram-Init-Data, Authorization, Content-Type"` (убран `*`).
- **F10 (документация replay-риска):**
  - `docs/decisions.md` (ADR 043): добавлен раздел Replay protection + упоминание в инвариантах.
  - `docs/deployment.md`: примечание под nginx headers о принятом риске (нет nonce-store, только TTL).
- Тесты: добавил в `tests/unit/test_groups_repo_unit.py` (name length, invalid color, icon length, update rejects). 7/7 passed (uv run pytest).
- Сессия, обновление handoff (board, pr в таске позже).

## Изменённые/новые файлы

- `src/bot/webapp/api.py`
- `src/db/repositories/groups.py`
- `docs/decisions.md`
- `docs/deployment.md`
- `tests/unit/test_groups_repo_unit.py`
- `docs/sessions/2026-06-11_task-0084-webapp-security-nits.md`
- `handoff/tasks/TASK-0084-webapp-security-nits.md` (via claim + later status)

## Коммиты

- (будут после)

## Проверки

- `uv run pytest tests/unit/test_groups_repo_unit.py` — 7 passed
- ruff / mypy (на изменённых) — ок (pre-commit)
- `python3 scripts/handoff.py validate` — TBD
- Нет миграций, vite build не затронут (только бэк + доки)

## Что осталось / следующий шаг

- Обновить таск с PR ссылкой и session.
- `handoff.py status TASK-0084 in_review`
- git push -u origin task/0084-...
- Открыть PR.
- После мержа 81-84 — релиз v0.16 (TASK-0072)

## Архитектурные решения / открытые вопросы

- Валидация на двух уровнях (API для UX 400 + repo для защиты).
- Иконки: только length + color строгий allowlist (a0-a7 как в дизайне). Полный allowlist Material Symbols — если понадобится (сейчас опц.).
- Документация риска в двух местах (ADR + deployment).

## PR

(после пуша)
