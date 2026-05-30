---
id: TASK-0018
title: UX email-intel — блок в /whois, toggle'ы, локали (ADR 036)
status: done
milestone: v0.10.0
adr: 036
area: code
depends_on: [TASK-0017]
branch: task/0018-email-intel-ux-locales
owner: claude
session: docs/sessions/2026-05-30_task-0018_email_intel_ux_locales.md
pr: ""
created: 2026-05-29
completed: 2026-05-30
---

# TASK-0018 — UX email-intel (ADR 036)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Показать email/policy-данные в карточке `/whois` и дать управление
уведомлениями; всё через локали.

## Контекст

ADR 036, раздел UX. По образцу SSL/DNS-блоков в карточке `/whois` и
inline-конфигуратора `⚙️ Уведомления` (ADR 029).

## Изменения по файлам

- `src/services/formatters.py` (или новый `formatters_*`) — блок email-intel
  в карточке `/whois` после DNS/SSL: MX, SPF (с пометкой режима `all` и
  RFC-нарушения при >1 записи), DMARC (policy), DKIM (найденные селекторы).
  Аккуратная отрисовка «не настроено»/«не отвечает» (не как ошибка).
- `src/bot/handlers/whois.py` — bootstrap email-intel при показе (enqueue
  `check_email_intel`, если кэша нет; redis-guard), как уже сделано для
  SSL/DNS. Записи берутся у самого домена (ADR 035).
- `src/bot/keyboards.py` + `states.py` + конфигуратор `⚙️ Уведомления` —
  toggle'ы `track_email` / `notify_email_change`.
- `src/locales/ru.py`, `src/locales/en.py` — **все** новые строки (баннеры,
  подписи блока, тексты уведомлений). Помнить про инвариант: каждый RU-ключ
  имеет EN-эквивалент (тест `test_all_ru_keys_present_in_en`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `test_all_ru_keys_present_in_en` зелёный (новые ключи в обоих языках).
- Рендер блока корректен при: нет записей, частичные данные, «не отвечает».
- Хэндлер не падает на мусорном/IDN-вводе (ADR 035 guard).

## Требования к тестам

- `tests/unit/test_format_email_block.py`, `test_notify_config_handler`
  (расширить), `test_locales` (новые ключи). Real-world проверка в Telegram
  желательна (UX-баги часто не ловятся юнит-тестами).

## Definition of Done

- [ ] Блок email в `/whois`; toggle'ы в конфигураторе; локали ru/en полные
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный
- [ ] После 0015–0018 — релиз v0.10.0 (bump + CHANGELOG + тег)

## Ссылки

- ADR 036; ADR 029 (toggle'ы/конфигуратор); ADR 035 (роутинг/guard)
