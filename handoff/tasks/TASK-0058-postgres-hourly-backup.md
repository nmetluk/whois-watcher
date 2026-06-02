---
id: TASK-0058
title: Ежечасный бекап Postgres (pg_dump, ротация 36, verify)
status: open
milestone: v0.15.0
adr: 042
area: code
depends_on: []
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-08
---

# TASK-0058 — Ежечасный бекап Postgres (ADR 042)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 042.

## Цель

ARQ cron `backup_postgres` (ежечасно): `pg_dump` → gzip → `BACKUP_DIR`, ротация
до 36 файлов, проверка валидности, запись статуса для ежечасного отчёта.

## Изменения по файлам

- `src/tasks/backup_postgres.py` — задача:
  - `pg_dump` через `asyncio.create_subprocess_exec` (НЕ shell=True; аргументы
    списком), формат custom (`-Fc`) или plain+gzip. Параметры подключения из
    `settings` (host/port/db/user/password).
  - Файл `BACKUP_DIR/ww-<UTC-timestamp>.dump(.gz)`.
  - **Verify:** rc==0, файл существует и size > порога; `pg_restore --list`
    (для `-Fc`) rc==0. Иначе ok=False + last_error.
  - **Ротация:** оставить `BACKUP_KEEP` (=36) свежих по mtime, остальные удалить.
  - Записать статус в Redis `ops:last_backup` (JSON: ts, ok, size, path, error;
    через `ctx["sync_redis"]`).
  - Никогда не бросать наружу (ARQ-таска возвращает dict-статус, логирует).
- `src/config/settings.py` — `backup_dir: str` (дефолт `/backups`),
  `backup_keep: int = Field(36, ge=1)`, `backup_min_bytes: int` (порог).
- `src/tasks/arq_config.py` — регистрация `backup_postgres` + cron `minute={0}`.
- `Dockerfile` — добавить `postgresql-client-16` в runner (PostgreSQL apt repo,
  версия = PG16; pin). Проверить, что `pg_dump`/`pg_restore` в PATH воркера.
- `docker-compose.yml` — новый именованный том `backups` → монтировать в
  `worker`/`scheduler` на `BACKUP_DIR`.
- `.env.example` — новые переменные.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Ротация держит ровно `BACKUP_KEEP` файлов (unit: мок файловой системы/tmpdir).
- Verify: rc≠0 или пустой файл → ok=False, статус записан.
- Статус пишется в Redis (мок).
- Задача не бросает наружу при сбое pg_dump.

## Требования к тестам

- Unit с моками subprocess/FS/redis (со `spec`). (Опц.) интеграц. на pytest-docker.

## Definition of Done

- [ ] Задача + конфиг + Dockerfile(pg-client) + том; cron зарегистрирован
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Деплой-заметка: образ пересобрать (pg-client), том создать
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR 042; `src/tasks/check_subdomains.py` (redis-guard/ctx как образец)
- Связанные: TASK-0059 (ежечасный отчёт читает `ops:last_backup`)
