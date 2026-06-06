# 2026-06-06 — TASK-0094: «свободен» никогда не отдаётся из кэша бота (ADR 046)

**Дата:** 2026-06-06 · **Таск:** TASK-0094 · **Ветка:** main (прямой фикс
архитектора, по решению владельца) · **Исполнитель:** architect (Cowork)

## Контекст

Повтор класса инцидента 0091 **после** деплоя ADR 045: владелец проверил
свободный домен ботом, зарегистрировал — бот продолжил отвечать
«свободен». Требование владельца: ответ «свободен» не кешировать ни на
одном слое, всегда live-запрос.

## Диагностика (где «свободен» жил в кэшах)

1. **Бот, `whois_facade.get_or_fetch`** — главный остаточный дефект:
   `_is_fresh()` смотрел только на `fetched_at` (окно 6ч,
   `whois_cache_fresh_hours`), не различая free/занят. Tracked/wishlist
   свободный домен попадает в `whois_cache` (upsert в
   `check_domain._handle_success` безусловный) → `/whois` и карточки
   отдавали «свободен» из кэша вообще без live (и без RDAP-кросс-чека
   045 — он живёт только в live-пути).
2. **whoisd-прокси/relay** — негативы кешируются до 1ч
   (`RU_UPSTREAM_TTL_NEG=3600` в юнитах, поверх NO_DATA_TTL=600 из
   2ae4442); ветка RDAP-404 (gTLD), возможно, всё ещё TTL_OK=24h →
   TASK-0095 (infra).

## Сделано (этот репо)

- `src/services/whois_facade.py` — fresh-ветка отдаёт кэш только если
  `_cache_to_data(...).is_registered` (предикат тот же, что при рендере:
  `expires_at` или `registrar`); иначе всегда live. Stale-fallback для
  free-записей не работает и раньше не работал (гард
  `expires_at is not None`) — закреплено комментарием и тестом.
- `tests/unit/test_whois_facade.py` — `TestFreeNeverServedFromCache`,
  4 теста: fresh-free → live обязателен; live-free → отдаём live;
  live-сбой при free-кэше → ошибка, не stale-«свободен»; контроль
  fresh-registered без live.
- ADR 046 (`docs/decisions.md`), CHANGELOG (Unreleased → Fixed),
  TASK-0094 (done) + TASK-0095 (open, infra) в handoff.

## Верификация

- `pytest tests/unit/test_whois_facade.py` — 13 passed (9 + 4 новых).
- Смежные: `test_free_verification` (16), `test_whois_parser`,
  `test_whois_scheduler` — passed.
- `ruff check`, `black --check` — чисто. mypy — CI (в песочнице нет 3.11;
  тесты прогнаны на 3.10 с shim `datetime.UTC`/`typing.Self`).
- Известные падения `test_free_verification` в чистой песочнице — от
  отсутствия `dnspython`, не от фикса.

## Хвосты / следующий шаг

- TASK-0095 (исполнитель, infra): whois-proxy + хосты — негативы ≤60с
  (дедуп), RDAP-404 ветка, чистка env в юнитах.
- Деплой бота (вместе с накопленным 0085–0094) — по процедуре
  `docs/deployment.md` (бекап БД обязателен).
- Real-world после деплоя: свободный → зарегистрировать → /whois через
  пару минут показывает «занят» (negative-окно ≤60с после 0095).

## Ссылки

- ADR 046, ADR 045; TASK-0091/0092/0093 (история инцидента)
