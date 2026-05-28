---
id: TASK-0003
title: Схема user_domains (registrable_domain, is_subdomain) + WHOIS-джойны
status: done
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0002]
branch: task/0003-subdomain-schema-whois-joins
owner: claude-code
session: docs/sessions/2026-05-29_task-0003_subdomain_schema.md
pr: 3
created: 2026-05-29
---

# TASK-0003 — Схема поддоменов + переключение WHOIS-джойнов (подэтап 2b)

> Самодостаточно. Процесс — `handoff/README.md`. Дизайн — ADR 035.
> Опирается на `src/utils/domains.py` из TASK-0002.

## Цель

Хранить registrable-домен и признак поддомена в `user_domains`; WHOIS
связывается с кэшем по registrable, а не по полному имени.

## Контекст / корень проблемы

Сейчас связь идёт по `WhoisCache.domain == UserDomain.domain`. Для
поддомена это промах: WHOIS должен браться у родителя (eTLD+1). DNS/SSL
остаются по самому поддомену (их ключ менять НЕ нужно).

## Изменения по файлам

- `src/db/models.py` → `UserDomain`:
  - `registrable_domain: Mapped[str]` (Text, NOT NULL, индекс
    `ix_user_domains_registrable`) — eTLD+1; для apex == `domain`.
  - `is_subdomain: Mapped[bool]` (server_default `false`).
- `migrations/versions/` — новая Alembic-миграция:
  - добавить колонки + индекс;
  - backfill существующих строк: `registrable_domain = domain`,
    `is_subdomain = false` (проверить, что поддоменов в проде нет; иначе
    batch-пересчёт через `utils.domains.registrable_domain`).
- `src/db/repositories/domains.py` — во всех WHOIS-джойнах заменить
  `WhoisCache.domain == UserDomain.domain` на
  `== UserDomain.registrable_domain`:
  `list_with_whois`, `list_with_whois_filtered`, `iter_all_with_whois`,
  `get_user_stats`. DNS/SSL-репозитории НЕ трогать.
- Заполнение `registrable_domain`/`is_subdomain` при вставке —
  делегировать `utils.domains` (точка вставки появится в TASK-0005/2d;
  здесь — дефолты на уровне схемы + backfill, чтобы существующие строки
  и тесты были консистентны).

## Миграции БД

Да. Применяется на чистой БД и на снапшоте с данными без потерь
(backfill идемпотентен).

## Инварианты (защитить тестами)

- Для apex-домена `registrable_domain == domain`, `is_subdomain == False`.
- WHOIS-джойн для строки с `registrable_domain=pinbetting.ru` находит
  `whois_cache`-row родителя.
- Два поддомена одного родителя ссылаются на один `whois_cache`-row.
- `/stats` и `/list` считают/сортируют по родительскому expiry.

## Требования к тестам

- Тест миграции: upgrade на чистой БД, проверка колонок/индекса.
- Репозиторий: джойны возвращают данные родителя для subdomain-строк.

## Definition of Done

- [ ] Миграция добавляет колонки+индекс, backfill корректен
- [ ] WHOIS-джойны переключены на `registrable_domain`
- [ ] `alembic upgrade head` на чистой БД без ошибок
- [ ] `pytest` полный прогон зелёный; `ruff`/`black`/`mypy` чисто
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR 035, `PLAN_subdomains_wishlist.md` (Этап 2, 2b)
- Зависит от: TASK-0002 (`src/utils/domains.py`)
