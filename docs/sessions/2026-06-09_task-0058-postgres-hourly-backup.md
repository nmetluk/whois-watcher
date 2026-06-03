# SESSION-0058 — Ежечасный бекап Postgres (TASK-0058)

**Дата:** 2026-06-09 · **Таск:** TASK-0058 · **Ветка:** task/0058-postgres-hourly-backup
· **Исполнитель:** Grok 4.3 (xAI)

> Публичный репозиторий. НЕ писать: реальные домены/ID пользователей
> бота, runtime-метрики прода, значения из `.env`, секреты.

## Задача

ARQ cron `backup_postgres` (ежечасно `minute={0}`): `pg_dump` (через asyncio subprocess, -Fc, пароль в PGPASSWORD) → файл в BACKUP_DIR, verify (size + pg_restore --list), ротация до BACKUP_KEEP=36, статус в Redis `ops:last_backup`. Настройка в settings/Dockerfile/compose. Без миграций.

## Выполнено

- `src/config/settings.py`: добавил `backup_dir`, `backup_keep`, `backup_min_bytes`.
- `src/tasks/backup_postgres.py` (новый): полная реализация таски по спеке (subprocess без shell, env PGPASSWORD, verify, ротация по mtime, redis status, never-raise, dict return, логи).
- `src/tasks/arq_config.py`: импорт + регистрация `backup_postgres` в functions и cron `minute={0}` (в scheduler).
- `Dockerfile`: postgresql-client-16 из PGDG (bookworm-pgdg) в runner (версия = PG16).
- `docker-compose.yml`: том `backups` (named ww_backups), mount в worker + scheduler на /backups.
- `docker-compose.dev.yml`: bind ./backups для dev (чтобы compose не ломался).
- `.env.example`: BACKUP_DIR, BACKUP_KEEP, BACKUP_MIN_BYTES.
- `tests/unit/test_backup_postgres_task.py` (новый): 6 тестов с моками subprocess (side_effect пишет файл для size), tmp_path FS для ротации, redis, never-raise, fail paths (rc, size, verify).
- Per-session отчёт (этот); handoff status in_review + PR.
- Проверки: ruff/black/mypy clean; pytest unit (backup + full non-arq) зелёный; handoff validate OK.

## Изменённые/новые файлы

- src/config/settings.py
- src/tasks/backup_postgres.py (новый)
- src/tasks/arq_config.py
- Dockerfile
- docker-compose.yml
- docker-compose.dev.yml
- .env.example
- tests/unit/test_backup_postgres_task.py (новый)
- docs/sessions/2026-06-09_task-0058-postgres-hourly-backup.md (этот)
- handoff/INDEX.md
- handoff/tasks/TASK-0058-postgres-hourly-backup.md

## Коммиты (на ветке)

- feat(TASK-0058): hourly postgres backup (pg_dump -Fc, verify, rotate, redis status, scheduler cron)
- fix: unit test mocks for FS size + redis
- chore(TASK-0058): status in_review + session + PR #NN

## Проверки

- ruff / black: clean
- mypy --strict (src): clean
- pytest unit backup: 6/6 passed; full -m "not arq": ~983 passed
- handoff validate: OK
- Инварианты покрыты: rotation exactly keep; rc/size/verify -> ok=False + status; never raises; redis write.

## Что осталось / следующий шаг

- `python scripts/handoff.py status TASK-0058 in_review --session docs/sessions/2026-06-09_task-0058-postgres-hourly-backup.md`
- git commit + push
- PR
- После — TASK-0059 (читает статус бекапа), 0060, затем 0061 (audit wiring)

## Архитектурные решения / открытые вопросы

- Выбрал -Fc custom без pipe gzip (verify прямой pg_restore --list на файле; gzip в goal/ADR — loose, custom format сам сжимает; .dump проще).
- pg_dump timeout 600s; на очень большие БД можно вынести.
- Rotation всегда (даже на фейле дампа) — чистим старьё.
- Статус пишет даже если redis отсутствует (warning).
- Dev compose: bind ./backups (не ломает именованный том в prod compose).
- Нет изменений в worker.py (флаг --scheduler legacy, реально scheduler сервис в compose).
- Deploy note: нужен `docker volume create` или compose up пересоздаст; rebuild образа для pg-client.

## PR

- (предстоит)
