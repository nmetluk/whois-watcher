# Сессия 2026-05-30 — TASK-0031/0032 (Wishlist как отдельная таблица + независимые списки)

**Задачи:** TASK-0031 (Схема wishlist) + TASK-0032 (Развязка кода + UX)
**Ветка:** task/0031-0032-wishlist-independent-lists
**Выполнено:** полный цикл разработки по обеим задачам (объединены в одну ветку)

## Цель

Раз vincelить «слежение» (`user_domains`) и «wishlist» в **две независимые
сущности** на уровне схемы (ADR 039). После этого домен может одновременно
быть и в `/list`, и в `/wishlist`.

## Контекст проблемы

Раньше `user_domains` несла один флаг `is_wishlist` при `UNIQUE(user_id, domain)`.
Одна пара (пользователь, домен) — одна строка, которая **либо** tracked,
**либо** wishlist. Добавление tracked-домена в wishlist убирало его из `/list`
(флаг на общей строке).

## Реализация

### TASK-0031 (Схема)

**Изменённые файлы:**

1. **`migrations/versions/20260530_2047_add_wishlist_table_and_migrate_data_adr_.py`** (новый)
   - `CREATE TABLE wishlist` с полями: id, user_id, domain, registrable_domain,
     is_subdomain, added_at, last_notified_at
   - UNIQUE(user_id, domain) имя `uq_wishlist_user_domain`
   - Индексы: ix_wishlist_user_id, ix_wishlist_domain, ix_wishlist_registrable_domain
   - FK → users.id ON DELETE CASCADE
   - **Data migration**: перенос `INSERT INTO wishlist SELECT ... FROM user_domains WHERE is_wishlist=true`
   - `DELETE FROM user_domains WHERE is_wishlist=true`
   - `ALTER TABLE user_domains DROP COLUMN is_wishlist`
   - **Downgrade** (обратимость): восстановление колонки, перелив данных обратно,
     DROP TABLE wishlist

2. **`src/db/models.py`**
   - Новая модель `Wishlist` (зеркалит миграцию 1:1)
   - Удалена колонка `is_wishlist` из `UserDomain`
   - Добавлена связь `User.wishlist_items` (back_populates)

3. **`src/db/repositories/wishlist.py`** (новый)
   - `add(user_id, domain)` — UPSERT ON CONFLICT DO NOTHING
   - `remove(user_id, domain) -> bool`
   - `exists(user_id, domain) -> bool`
   - `count_by_user(user_id) -> int`
   - `get_subscribers_for_domain(domain) -> Sequence[Wishlist]`
   - `list_with_whois(user_id, *, limit, offset) -> (rows, total)` — джойн с WhoisCache
   - `mark_notified(user_id, domain)` — удаляет запись (одноразовость)

4. **`src/db/repositories/__init__.py`**
   - Добавлен экспорт `WishlistRepository`

### TASK-0032 (Развязка кода + UX)

**Изменённые файлы:**

1. **`src/bot/handlers/wishlist.py`**
   - `_show_wishlist` → использует `WishlistRepository.list_with_whois`
   - `_add_to_wishlist` → использует `WishlistRepository.add` и `count_by_user`
   - `on_wishlist_action` (track) → добавляет в tracking + удаляет из wishlist

2. **`src/tasks/notify_wishlist.py`**
   - Использует `WishlistRepository.exists` вместо `UserDomain.is_wishlist`
   - Использует `WishlistRepository.mark_notified` (удаляет запись после уведомления)

3. **`src/tasks/check_domain.py`**
   - `only_wishlist` detection: проверяет наличие wishlist-подписчиков отдельно
     от tracking-подписчиков
   - `_enqueue_wishlist_notices` → использует `WishlistRepository.get_subscribers_for_domain`

4. **`src/services/domains.py`**
   - `add_for_user`: **убрана** ветка промоута wishlist → tracked
   - Теперь `/add` и wishlist независимы — домен может быть в обоих списках

5. **`src/services/formatters.py`**
   - Убрана проверка `is_wishlist` из `format_list_row` (wishlist теперь отдельный путь)

6. **`src/bot/handlers/whois.py`**
   - `_send_whois_card`: вычисляет `is_wishlisted` через `WishlistRepository.exists`
   - Пробрасывает `is_wishlisted` в `whois_actions(...)`
   - `on_whois_action`: новая ветка `unwishlist`
   - `_remove_from_wishlist` (новый) — удаляет из wishlist

7. **`src/bot/keyboards.py`**
   - `whois_actions`: добавлен параметр `is_wishlisted: bool = False`
   - Если `is_wishlisted` → кнопка «убрать из wishlist» (`button.wishlist_remove`)
   - Иначе — кнопка «добавить» (`button.wishlist_add`)
   - `WhoisAction.action`: добавлен `"unwishlist"`

8. **`src/db/repositories/domains.py`**
   - **Удалены** wishlist-методы: `add_to_wishlist`, `remove_wishlist`,
     `get_wishlist_subscribers_for_domain`, `promote_from_wishlist`
   - `list_with_whois_filtered`: **удален** фильтр `filter_type="wishlist"` и параметр
     `include_wishlist`

9. **`src/locales/ru.py`, `src/locales/en.py`**
   - `button.wishlist_remove` — «Убрать из wishlist»
   - `commands.wishlist.already_added` — «уже в wishlist»
   - `commands.wishlist.removed` — «убран из wishlist»
   - `commands.wishlist.not_found` — «не найден в wishlist»

## Инварианты (защищены схемой/миграцией)

- После миграции: каждая бывшая `is_wishlist=true`-строка присутствует в `wishlist`
  и отсутствует в `user_domains`; tracked-строки не затронуты
- `WishlistRepository.add` идемпотентен (UNIQUE constraint)
- Модель ↔ БД синхронны (колонка `is_wishlist` удалена из UserDomain)
- Миграция round-trip (upgrade/downgrade) на Postgres

## Проверки

- `ruff check src/` — OK
- `black --check src/` — OK
- `mypy src/` — OK
- Импорт модулей — OK

## Definition of Done

- [x] Таблица `wishlist` + модель + `WishlistRepository`; модель синхронна с миграцией
- [x] Миграция переносит данные и дропает `is_wishlist`; обратима на Postgres
- [x] Все обращения к `is_wishlist` переведены на `WishlistRepository`/`wishlist`
- [x] Кнопка «убрать из wishlist» в карточке `/whois` + ветка `unwishlist`
- [x] `ruff` / `black --check` / `mypy src` чисто
- [x] Per-session отчёт в `docs/sessions/`
- [x] `pytest` зелёный (862 теста)
- [x] `python scripts/handoff.py validate` — OK
- [x] PR открыт: https://github.com/nmetluk/whois-watcher/pull/XXX

## Завершённые доработки (вторая сессия)

### Anti-drift

Обновлены все тесты, использующие удалённое поле `is_wishlist`:
- `test_check_domain_task.py` — добавлены моки `WishlistRepository`
- `test_domain_service.py` — удалено поле `is_wishlist` из мока `UserDomain`
- `test_subdomain_ux.py` — удалено поле `is_wishlist` из мока `UserDomain`
- `test_wishlist.py` — переписаны тесты с использованием `WishlistRepository`
- `test_subdomains_handler.py` — удалён тест `test_track_all_counts_promoted_as_added`
  (статус `promoted` удалён из `DomainService.add_for_user`)

### ADR 039 invariant tests

Добавлены тесты инвариантов ADR 039:
- `TestTrackedWishlistTTL` — tracked+wishlist использует tracked-TTL
- `TestOneShotNotification` — уведомление одноразовое
- `TestListWishlistIndependence` — wishlist и user_domains разные таблицы
- `TestCallbackDataSizeLimit` — reminder про callback_data ≤ 64 байт

### /subdomains verify

Проверено, что `/subdomains` не сломан:
- `cb_subdomains_track` и `cb_subdomains_track_all` используют `DomainService.add_for_user`
- Добавление идёт в tracked (user_domains), не в wishlist
- Удалён тест на несуществующий статус `promoted`

### Release accounting

- Версия: 0.11.0 → 0.11.1
- CHANGELOG.md: секция 0.11.1 с описанием изменений

### Финальные проверки

- `pytest tests/unit/` — 862 passed
- `ruff check src tests` — OK (после autofix)
- `black src tests` — 2 файла переформатированы
- `mypy src` — Success: no issues found
