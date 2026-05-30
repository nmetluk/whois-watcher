---
id: TASK-0031
title: Схема — отдельная таблица wishlist + миграция переноса (ADR 039)
status: done
milestone: v0.11.1
adr: 039
area: code
depends_on: []
branch: ""
owner: ""
session: docs/sessions/2026-05-30_task-0031-0032-wishlist-independent-lists.md
pr: 22
created: 2026-05-30
---

# TASK-0031 — Схема wishlist как отдельная таблица (ADR 039)

> Тело самодостаточно. Перед стартом (обязательно, см. `handoff/README.md`):
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> `down_revision` сверить с **актуальным** alembic-head на свежем main
> (НЕ полагаться на этот файл — head мог уйти вперёд).
> Майлстоун `v0.11.1` — патч поверх текущей релизной линии; если на свежем
> main линия другая, скорректировать bump-цель в TASK-0032 и сообщить
> архитектору. Статусы — только через `handoff.py status` (без `completed`).

## Цель

Развязать «слежение» (`user_domains`) и «wishlist» в **две независимые
сущности** на уровне схемы: завести таблицу `wishlist`, перенести в неё
существующие wishlist-строки и упразднить флаг `user_domains.is_wishlist`.
После этого домен сможет одновременно быть и в `/list`, и в `/wishlist`.

## Контекст / корень проблемы

Сейчас `user_domains` несёт один флаг `is_wishlist` при
`UNIQUE(user_id, domain)`. Одна пара (пользователь, домен) — одна строка,
которая **либо** tracked, **либо** wishlist. `add_to_wishlist` UPSERT-ом
переводит tracked-строку в `is_wishlist=True`, а `/list` фильтрует
`is_wishlist.is_(False)` → домен молча исчезает из портфеля. Модель в
принципе не выражает «домен в обоих списках». Полное обоснование — ADR 039
(`docs/decisions.md#039`).

Эта задача — **только схема/миграция/репозиторий**. Перенос всех вызовов
кода на новую таблицу и UX (кнопка «убрать из wishlist») — в **TASK-0032**,
которая зависит от этой.

## Изменения по файлам

- **Новая Alembic-миграция** (`migrations/versions/...`):
  - `CREATE TABLE wishlist`:
    - `id` BIGINT PK autoincrement
    - `user_id` BIGINT FK → `users.id` `ON DELETE CASCADE`, NOT NULL
    - `domain` TEXT NOT NULL (punycode)
    - `registrable_domain` TEXT NOT NULL (для WHOIS-джойна, ADR 035)
    - `is_subdomain` BOOLEAN NOT NULL `server_default false`
    - `added_at` TIMESTAMPTZ NOT NULL `server_default now()`
    - `last_notified_at` TIMESTAMPTZ NULL
    - `UNIQUE(user_id, domain)` имя `uq_wishlist_user_domain`
    - индексы: `ix_wishlist_user_id`, `ix_wishlist_domain`,
      `ix_wishlist_registrable_domain`
  - **Перенос данных** (data migration в том же ревижене, после create):
    `INSERT INTO wishlist (user_id, domain, registrable_domain, is_subdomain,
    added_at) SELECT user_id, domain, registrable_domain, is_subdomain,
    added_at FROM user_domains WHERE is_wishlist = true;`
    затем `DELETE FROM user_domains WHERE is_wishlist = true;`
  - `ALTER TABLE user_domains DROP COLUMN is_wishlist;`
  - **downgrade обязан быть обратимым**: вернуть колонку `is_wishlist`
    (`server_default false`), перелить строки из `wishlist` обратно в
    `user_domains` (с `is_wishlist=true`, гася `notify_*` как делал старый
    `add_to_wishlist`), затем `DROP TABLE wishlist`.
- `src/db/models.py`:
  - новая модель `Wishlist` (зеркалит миграцию 1:1: FK, UNIQUE, индексы);
  - **удалить** колонку `is_wishlist` из `UserDomain`.
- `src/db/repositories/`:
  - новый `WishlistRepository` (по образцу dns/ssl-репозиториев,
    `BaseRepository`): `add(user_id, domain)` (UPSERT
    `ON CONFLICT DO NOTHING` по `uq_wishlist_user_domain`,
    заполнять `registrable_domain`/`is_subdomain` через
    `src/utils/domains.py`), `remove(user_id, domain) -> bool`,
    `exists(user_id, domain) -> bool`, `count_by_user(user_id) -> int`,
    `get_subscribers_for_domain(domain) -> Sequence[Wishlist]`,
    `list_with_whois(user_id, *, limit, offset) -> (rows, total)`
    (джойн `Wishlist` ↔ `whois_cache` по `registrable_domain`, как
    `DomainRepository.list_with_whois`), `mark_notified(user_id, domain, *, at)`.
  - экспорт в `src/db/repositories/__init__.py`.
  - **Из `DomainRepository` удалить** wishlist-методы (`add_to_wishlist`,
    `remove_wishlist`, `get_wishlist_subscribers_for_domain`,
    `promote_from_wishlist`) и фильтр `is_wishlist` в
    `list_with_whois_filtered` (ветки `filter_type=="wishlist"` и
    `include_wishlist`). **Внимание:** на эти методы есть вызовы из сервиса/
    хэндлеров/задач — их перенос делает **TASK-0032**. Чтобы не валить main,
    эту чистку `DomainRepository` синхронизировать с TASK-0032 (либо оставить
    методы временно нерабочими помечёнными, либо вести обе в одной ветке —
    решает исполнитель; предпочтительно: depends_on гарантирует порядок, в
    этой задаче колонку дропаем, а вызовы чинит 0032 в своей ветке от
    обновлённого main). Согласовать с архитектором при `claim`, если ломается
    компиляция/тесты.

> Примечание по последовательности: `DROP COLUMN is_wishlist` ломает любой
> код, всё ещё читающий поле. Возможны два пути: (а) объединить 0031+0032 в
> одну ветку/PR (тогда схема и развязка едут вместе) либо (б) держать
> совместимость в 0031 минимально и доделать в 0032. Исполнитель выбирает
> (а) или (б) и фиксирует в per-session отчёте. Рекомендация архитектора —
> **(а)**: один атомарный PR безопаснее для public main (нет промежуточного
> «красного» состояния).

## Миграции БД

Требуется. Новая таблица + перенос данных + DROP COLUMN. **Уроки прошлого:**
- дефолты — валидным SQL-литералом (`server_default text("false")`,
  `now()`), не Python-значением (TASK-0008);
- применить и откатить на **Postgres** (smoke-тест TASK-0009 в CI);
- `down_revision` = фактический head на свежем main; после добавления —
  убедиться, что head единственный.

## Инварианты (защитить тестами)

- После миграции: каждая бывшая `is_wishlist=true`-строка присутствует в
  `wishlist` и отсутствует в `user_domains`; tracked-строки не затронуты.
- `WishlistRepository.add` идемпотентен (повторный add — без дубля,
  `UNIQUE`).
- Модель ↔ БД синхронны (нет рассинхрона `server_default`/полей; колонки
  `is_wishlist` в модели не осталось).
- Миграция round-trip (upgrade/downgrade) на Postgres зелёная.

## Требования к тестам

- Репозиторий `WishlistRepository` на реальной БД через фикстуры:
  add/remove/exists/count/get_subscribers/list_with_whois.
- Модель `Wishlist`: наличие полей/индексов/UNIQUE.
- Миграционный round-trip покрыт общим smoke-тестом (TASK-0009); при
  необходимости — отдельная проверка переноса данных.

## Definition of Done

- [ ] Таблица `wishlist` + модель + `WishlistRepository`; модель синхронна с миграцией
- [ ] Миграция переносит данные и дропает `is_wishlist`; обратима на Postgres
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] PR открыт по шаблону, CI зелёный (в т.ч. migration smoke на Postgres)

## Ссылки

- ADR: `docs/decisions.md#039`
- Образцы: ADR 030 (SSL как параллельная подсистема), репозитории
  `dns`/`ssl`, `DomainRepository.list_with_whois`
- Связанные таски: **TASK-0032** (развязка вызовов + UX), контекст —
  TASK-0001/ADR 034
