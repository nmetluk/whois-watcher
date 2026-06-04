# SESSION-0083 — WebApp security hardening (TASK-0083)

**Дата:** 2026-06-11 · **Таск:** TASK-0083 · **Ветка:** task/0083-webapp-security-hardening
· **Исполнитель:** Grok 4.3

## Задача

Закрыть 🟠 F3–F7 из аудита 0071: TTL→1h, dev-fallback только в development, OPTIONS до auth, raw SQL→repo, CSP в nginx + доки.

## Выполнено

- Claim + branch.
- settings.py: webapp_initdata_ttl default 3600 (F3); .env.example обновлён.
- auth.py: _extract_init_data(..., allow_dev_fallback=...), гейт по settings.environment (F4); в _auth_mw — OPTIONS short-circuit до validate (F5, preflight проходит).
- domains.py: добавил remove_by_id(user_id, ud_id) scoped.
- api.py: remove_domain теперь зовёт repo.remove_by_id (F6, убран raw sa_delete + commit); bulk уже использовал scoped delete.
- docs/deployment.md: добавил CSP заголовок в пример nginx https-сервера + комментарий (F7).
- ruff на изменённых — warnings pre-existing (не наши).
- Сессия, status in_review, board.

## Изменённые файлы

- src/config/settings.py
- src/bot/webapp/auth.py
- src/db/repositories/domains.py
- src/bot/webapp/api.py
- docs/deployment.md
- docs/sessions/...
- handoff/...

## Проверки

- ruff чист по новым участкам
- mypy имеет pre-existing untyped-decorator (роуты)
- handoff validate OK
- Логика: dev initData не пройдёт в prod; preflight не 401; delete через repo.

## Следующий шаг

- TASK-0084 (мелочи F8+)
- Полный регресс + TG smoke (cross-origin preflight если применимо, TTL в логах)
- Релиз 008? (или 0072)
