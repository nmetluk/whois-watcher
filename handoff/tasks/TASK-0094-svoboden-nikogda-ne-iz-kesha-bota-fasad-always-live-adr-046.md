---
id: TASK-0094
title: 🔴 «Свободен» никогда не из кэша бота — фасад always-live (ADR 046)
status: done
milestone: v0.17.0
adr: 046
depends_on: [TASK-0092]
area: code
branch: main (прямой фикс архитектора, по решению владельца)
owner: architect
session: docs/sessions/2026-06-06_task-0094-free-never-cached.md
pr: —
created: 2026-06-06
---

# TASK-0094 — «Свободен» никогда не отдаётся из кэша бота (ADR 046)

> Повтор класса инцидента 0091 **после** ADR 045: свободный домен
> проверили ботом → зарегистрировали → бот продолжал отвечать «свободен».
> RDAP-верификация (0092) защищает только live-путь; кэш бота отдавал
> «свободен» как «свежий» до 6 часов вообще без live-запроса.

## Цель

Ответ «домен свободен» бот даёт ТОЛЬКО по результату live-запроса
(с RDAP-кросс-чеком ADR 045). Из `whois_cache` «свободен» не отдаётся
никогда — ни как fresh, ни как stale-fallback.

## Корень проблемы

`src/services/whois_facade.py::get_or_fetch` — `_is_fresh()` смотрел
только на `fetched_at` (окно `whois_cache_fresh_hours`, 6ч), не различая
free/занят. Tracked/wishlist-домен со свободным статусом попадает в
`whois_cache` через `check_domain._handle_success` (upsert безусловный) —
и `/whois`, текстовые запросы, карточки отдавали кэшированное «свободен».

## Сделано (прямой фикс архитектора в main)

- `src/services/whois_facade.py`: в fresh-ветке `get_or_fetch` кэш
  отдаётся только если `_cache_to_data(...).is_registered` — предикат
  тот же, что при рендере (`expires_at` или `registrar`). Иначе — live.
  Stale-fallback для free-записей и раньше не работал (гард
  `expires_at is not None`) — закреплено комментарием и тестом.
- Placeholder-записи после `/add` (все поля NULL) подпадают под тот же
  предикат → live, а не «свободен» из пустой записи.
- `tests/unit/test_whois_facade.py` — 4 новых теста
  (`TestFreeNeverServedFromCache`): fresh-free → live обязателен (и
  возврат live-данных «занят»); live подтвердил free → отдаём live;
  live упал при free-кэше → ошибка, НЕ stale-«свободен»; контроль —
  registered из кэша по-прежнему без live.
- ADR 046 в `docs/decisions.md`, CHANGELOG (Unreleased → Fixed).

## Инварианты (защищены тестами)

- Кэш-запись с `expires_at IS NULL AND registrar IS NULL` никогда не
  возвращается как ответ — ни fresh, ни stale.
- Registered-домены из свежего кэша отдаются без live (стоимость
  фикса — live-запросы только по свободным доменам).
- Сбой live при free-кэше → `FacadeResult(error=...)`, не «свободен».

## DoD

- [x] `pytest tests/unit/test_whois_facade.py` — 13 passed (9 старых + 4 новых)
- [x] Смежные: `test_free_verification` (16), `test_whois_parser`,
      `test_whois_scheduler` — зелёные
- [x] `ruff` / `black --check` чисто (mypy — CI: в песочнице нет 3.11)
- [ ] Real-world после деплоя: /whois на свободный домен → зарегистрировать
      → повторный /whois в течение минут показывает «занят»
- [ ] Деплой (вместе с TASK-0095 — прокси-слой)

## Ссылки

- ADR: `docs/decisions.md` → 046 (и 045 — RDAP-кросс-чек)
- Связанные: TASK-0091 (диагностика), TASK-0092 (RDAP-verify),
  TASK-0093 (короткий TTL негативов — заменяется TASK-0095),
  TASK-0095 (infra: прокси/relay TTL 0 + дедуп 60с)
