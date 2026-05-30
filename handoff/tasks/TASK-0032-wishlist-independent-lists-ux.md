---
id: TASK-0032
title: Развязка wishlist↔tracking по коду + кнопка «убрать из wishlist» (ADR 039)
status: in_review
milestone: v0.11.1
adr: 039
area: code
depends_on: [TASK-0031]
branch: ""
owner: ""
session: ""
pr: 22
created: 2026-05-30
---

# TASK-0032 — Независимые списки + удаление из wishlist (ADR 039)

> Тело самодостаточно. Перед стартом (см. `handoff/README.md`):
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Зависит от **TASK-0031** (таблица `wishlist`, `WishlistRepository`,
> упразднение `is_wishlist`). Если 0031 решено вести одним PR вместе с этой —
> работать в общей ветке (см. примечание в TASK-0031). Статусы — только через
> `handoff.py status`.

## Цель

Перевести весь код с флага `user_domains.is_wishlist` на таблицу `wishlist`
так, чтобы слежение и wishlist стали **полностью независимы**, и добавить в
карточку `/whois` парную кнопку «убрать из wishlist» (по аналогии с
follow/unfollow). Закрывает оба UX-дефекта из ADR 039.

## Контекст / корень проблемы

Два бага (подтверждены ручной проверкой, негативные отзывы):

1. Добавление tracked-домена в wishlist убирало его из `/list` (флаг на общей
   строке). После TASK-0031 списки разнесены по таблицам — нужно перевести
   все вызовы.
2. Из карточки `/whois` нельзя убрать домен из wishlist: есть только кнопка
   добавления (`whois_actions`, `show_wishlist`), нет `unwishlist`-действия и
   проверки членства. У слежения парная кнопка есть (follow/unfollow).

## Изменения по файлам

Anti-drift: начать с `grep -rn "is_wishlist" src tests` — закрыть **все**
точки; после задачи ссылок на поле остаться не должно.

**Сервис/бизнес-логика**
- `src/services/domains.py` (`add_for_user`): убрать ветку промоута через
  `promote_from_wishlist`/`is_wishlist`. Теперь `/add` и wishlist независимы —
  добавление в слежение не смотрит на wishlist (домен может быть в обоих).
  Поведение «`/add` на домен из wishlist» = обычное добавление в tracking,
  wishlist-запись НЕ трогаем. Статус `promoted` в `AddDomainResult`
  (`src/services/results.py`) больше не нужен по этому пути — оценить, не
  ломает ли это вызовы `/subdomains` (там тоже используется `promoted` для
  track_all из ADR 037; **сохранить** статус, если он нужен subdomain-флоу —
  grep `promoted`). Решение зафиксировать в отчёте.

**Wishlist-команда и shortcut**
- `src/bot/handlers/wishlist.py`:
  - `_add_to_wishlist` → через `WishlistRepository.add` (не
    `DomainRepository.add_to_wishlist`); лимит — `WishlistRepository.count_by_user`
    против `limits.max_domains_per_user`; bootstrap whois_cache + enqueue check
    как сейчас.
  - `_show_wishlist` → `WishlistRepository.list_with_whois` (вместо
    `list_with_whois_filtered(filter_type="wishlist")`).
  - `on_wishlist_action` (кнопка `track` из уведомления «освободился»):
    добавляет домен в **tracking** (`DomainService.add_for_user`) и убирает
    из wishlist (`WishlistRepository.remove`) — это осознанный переход
    «слежу вместо ожидания»; одноразовость сохраняется.
- `src/bot/handlers/whois.py` (`_add_to_wishlist_shortcut`) — на новый
  `WishlistRepository`.

**Карточка /whois — кнопка удаления (баг 2)**
- `src/bot/keyboards.py` (`whois_actions`): добавить параметр
  `is_wishlisted: bool = False`. Если `is_wishlisted` → кнопка
  «убрать из wishlist» (`WhoisAction(action="unwishlist", domain=...)`,
  локаль `button.wishlist_remove`); иначе — текущая «добавить»
  (`button.wishlist_add`). Параметр `show_wishlist` оставить (скрывает обе).
  Поправить раскладку рядов (`builder.adjust`).
- `src/bot/handlers/whois.py` (`_send_whois_card`): вычислить
  `is_wishlisted = await WishlistRepository(session).exists(user.id, lookup_domain)`
  и пробросить в `whois_actions(...)`.
- `src/bot/handlers/whois.py` (`on_whois_action`): новая ветка
  `action == "unwishlist"` → `WishlistRepository.remove` + ответ
  `commands.wishlist.removed`. (Допустимо без confirm-диалога — удаление из
  wishlist неопасно; следовать UX follow/unfollow, который тоже без confirm.)

**WHOIS-проверка / уведомления об освобождении**
- `src/tasks/check_domain.py`:
  - `_enqueue_wishlist_notices` — брать подписчиков из
    `WishlistRepository.get_subscribers_for_domain`, не из
    `user_domains`-`subscribers`.
  - `only_wishlist`-логика (влияет на TTL/scheduler): домен считать
    «registered/tracked» для планирования, если есть хоть один tracking-
    подписчик в `user_domains`; wishlist-only (есть только в `wishlist`)
    сохраняет прежнее поведение. Свести оба источника подписчиков.
- `src/tasks/notify_wishlist.py`: проверка актуальности и удаление —
  через `WishlistRepository` (`exists`/`mark_notified`/`remove`), не
  `DomainRepository.get_for_user().is_wishlist`. Одноразовость: после
  отправки `remove` из `wishlist`.

**Форматирование / фильтры списка**
- `src/services/formatters.py`: рендер wishlist-строки (`row_wishlist`) —
  адаптировать под `(Wishlist, WhoisCache|None)` (или ввести
  `format_wishlist_row`).
- `src/bot/handlers/list_domains.py` / `src/services/results.py`: убрать
  `"wishlist"` из `_VALID_FILTERS`/`ListFilter` **или** перенаправить фильтр
  `wishlist` на `WishlistRepository` (решить: проще убрать пункт «🎯 Wishlist»
  из подменю фильтров `/list`, оставив отдельную команду `/wishlist`).
  Зафиксировать выбор в отчёте; обновить `list_filters` в `keyboards.py`.
- CSV-экспорт (`src/services/csv_io.py`/`results.py`, `iter_all_with_whois`):
  убедиться, что экспорт портфеля (tracking) не зависел от `is_wishlist`;
  если wishlist нужно экспортировать — отдельно (не в этой задаче, отметить).

**Локали**
- `src/locales/ru.py`, `src/locales/en.py`: новые ключи
  `button.wishlist_remove` (ru: «🎯 Убрать из wishlist»), `commands.wishlist.removed`
  (ru: «🎯 <b>{domain}</b> убран из wishlist.»). Снять/переиспользовать ставшие
  лишними ключи промоута, если путь промоута удалён. Инвариант
  `test_all_ru_keys_present_in_en` должен оставаться зелёным.

## Миграции БД

Не требуется (схема — в TASK-0031). Если 0031+0032 ведутся одним PR — миграция
из 0031.

## Инварианты (защитить тестами)

- Добавление в wishlist **не удаляет** домен из `/list`; tracked-домен
  одновременно в `/list` и в `/wishlist`.
- unfollow и удаление из wishlist независимы (одно не трогает другое).
- Карточка `/whois`: домен в wishlist → кнопка «убрать из wishlist»; не в
  wishlist → «добавить»; обе скрыты при `show_wishlist=False`. follow/unfollow
  работает параллельно и независимо.
- Уведомление об освобождении одноразовое: после отправки запись удалена из
  `wishlist`; повторный `/wishlist <domain>` снова ставит в очередь.
- Лимит wishlist считается по таблице `wishlist`, независимо от tracking.
- `grep is_wishlist` по `src/` и `tests/` — пусто.

## Требования к тестам

- `whois_actions`: вариант с `is_wishlisted=True` рендерит `unwishlist`-кнопку,
  с `False` — `wishlist`-кнопку; callback_data ≤ 64 байта на длинном IDN.
- `on_whois_action`: ветки `wishlist` (add) и `unwishlist` (remove) — со
  `spec`/`autospec` на сервис/репозиторий (anti-drift сигнатур, CLAUDE.md).
- `_send_whois_card`: `is_wishlisted` корректно прокинут (мок репозитория).
- `add_for_user` больше не конвертирует/не зависит от wishlist; домен,
  лежащий в wishlist, после `/add` есть в обоих списках.
- `notify_wishlist`/`_enqueue_wishlist_notices`: подписчики из таблицы
  `wishlist`; одноразовость; tracked+wishlist-домен планируется как tracked.
- Регрессия кнопки `track` из `on_wishlist_action`.

## Definition of Done

- [ ] Все обращения к `is_wishlist` переведены на `WishlistRepository`/`wishlist`
- [ ] Кнопка «убрать из wishlist» в карточке `/whois` + ветка `unwishlist`
- [ ] `pytest` зелёный (полный прогон), новые сценарии покрыты
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Локали ru/en синхронны (`test_all_ru_keys_present_in_en`)
- [ ] Per-session отчёт в `docs/sessions/` вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] Бамп `pyproject.toml` + запись в `CHANGELOG.md` (цель — патч на текущей
      релизной линии, см. примечание TASK-0031; согласовать с архитектором)
- [ ] PR открыт по шаблону, CI зелёный

## Ссылки

- ADR: `docs/decisions.md#039`
- Зависит от: **TASK-0031** (схема/репозиторий)
- Контекст: TASK-0001 / ADR 034 (промоут wishlist→tracked), ADR 029
  (карточка/toggle'ы), ADR 030 (параллельная подсистема), ADR 037
  (`promoted` в subdomain-флоу — не сломать)
