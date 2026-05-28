---
id: TASK-0001
title: Багфикс wishlist ↔ tracked (авто-промоут)
status: done
milestone: v0.8.1
adr: 034
area: code
depends_on: []
branch: task/0001-wishlist-tracked-fix
owner: claude-code
session: docs/sessions/2026-05-28_task-0001_wishlist-tracked-fix.md
pr: branch task/0001-wishlist-tracked-fix (FF-merged)
created: 2026-05-28
---

# TASK-0001 — Багфикс wishlist ↔ tracked (авто-промоут)

> Самодостаточно. Контекст процесса — `handoff/README.md`, состояние —
> `handoff/STATE.md`, полный план — `PLAN_subdomains_wishlist.md` (Этап 1).

## Цель

`/add` на домен, который уже лежит у пользователя в wishlist, **тихо
конвертирует** его в обычное отслеживание (промоут). Разделы `/list` и
`/wishlist` остаются строго раздельными.

## Контекст / корень проблемы

`UserDomain` — одна таблица для tracked и wishlist (флаг `is_wishlist`).
`DomainService.add_for_user` (`src/services/domains.py`) проверяет
`DomainRepository.exists()`, которая **не различает** `is_wishlist`: для
wishlist-строки возвращает `already_tracked` и не снимает флаг. При этом
`/list` (filter `all`, `include_wishlist=False`) такие строки прячет.
Домен застревает: невидим в `/list` и не конвертируется. Тот же дефект
бьёт по кнопке `track` из wishlist-уведомления
(`on_wishlist_action` → `add_for_user`).

## Изменения по файлам

- `src/db/repositories/domains.py` — новый метод
  `promote_from_wishlist(user_id, domain) -> bool`: один `UPDATE ...
  WHERE user_id, domain, is_wishlist=True` → `is_wishlist=False` +
  восстановить дефолты `DEFAULT_NOTIFICATION_FLAGS` (`notify_expiry`,
  `notify_ns_change`, `notify_registrar_change`, `notify_status_change`).
  Возвращает True, если строка была wishlist и обновлена. SSL/DNS
  toggle'ы не трогаем (их `add_to_wishlist` не гасит).
- `src/services/domains.py` → `add_for_user`: вместо `if await exists(...)`
  получить строку через `get_for_user`. None → текущая вставка; есть и
  `is_wishlist` → `promote_from_wishlist`, вернуть статус `promoted`;
  есть и не wishlist → `already_tracked` как сейчас.
- `src/services/results.py` — добавить литерал `"promoted"` в статус
  `AddDomainResult`.
- `src/bot/handlers/add_remove.py` — ветка `status == "promoted"` →
  локаль-ключ `commands.add.promoted_from_wishlist`.
- `src/locales/ru.py`, `src/locales/en.py` — ключ
  `commands.add.promoted_from_wishlist`.

## Миграции БД

Не требуется (схема не меняется).

## Инварианты (защитить тестами)

- `add_for_user` на wishlist-строку → `is_wishlist=False`, флаги
  `notify_*` = дефолты, статус `promoted`.
- После промоута домен виден в `/list` (filter `all`) и НЕ виден в
  `/wishlist` (filter `wishlist`).
- `add_for_user` на обычную tracked-строку → `already_tracked` (флаги
  без изменений).
- Промоут идемпотентен: повторный `/add` → `already_tracked`.
- Лимит `max_domains_per_user` при промоуте не пересчитывается.

## Требования к тестам

- `tests/unit/`: `promote_from_wishlist` (репозиторий на реальной БД через
  фикстуры), `add_for_user` все ветки (None / wishlist / tracked /
  повторный промоут).
- Регрессия пути кнопки `track` из `on_wishlist_action`.

## Definition of Done

- [ ] Код реализован по спецификации
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] Бамп `pyproject.toml` → 0.8.1, запись в `CHANGELOG.md` (Unreleased→0.8.1)
- [ ] PR открыт, CI зелёный

## Ссылки

- План: `PLAN_subdomains_wishlist.md` (Этап 1)
- ADR: завести `docs/decisions.md` ADR 034 (wishlist ↔ tracked)
- Затронутые: `src/services/domains.py`, `src/db/repositories/domains.py`,
  `src/bot/handlers/wishlist.py` (контекст)
