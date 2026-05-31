---
id: TASK-0040
title: Карточка /whois — MX + краткий e-mail-статус инлайн + фикс свежести
status: in_review
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0018]
branch: task/0040-whois-card-inline-mx-freshness
owner: ""
session: docs/sessions/2026-05-31_task-0040-whois-card-inline-mx-freshness.md
pr: ""
created: 2026-05-31
---

# TASK-0040 — /whois: инлайн MX+статус + фикс свежести (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Контекст — ADR 040, раздел «Расклад карточки» + «Фикс свежести».

## Цель

(1) Вынести **MX + краткий статус почты** (режим SPF, политика DMARC) в первое
сообщение карточки `/whois` рядом с DNS/SSL, компактно. (2) Починить «свежесть»:
при пустом кэше показывать плейсхолдер «⏳ собираю…» + хинт нажать 🔄, а не
пустоту.

## Контекст / корень проблемы

Сейчас `format_email_block` (`src/services/formatters.py`) возвращает `None`,
пока `last_successful_check_at is None`, а хэндлер `/whois`
(`src/bot/handlers/whois.py`) при первом запросе только enqueue'ит
`check_email_intel` и отвечает синхронно → почта (и на первый раз SSL/DNS) в
сообщении не видна, карточка не авто-обновляется. Это причина «не вижу почту».

## Изменения по файлам

- `src/services/formatters.py`:
  - Сделать почтовую строку **компактной и приоритетной**: MX-хосты (top-3) +
    1 строка статуса (SPF режим + DMARC policy). Полный DKIM/детали — убрать из
    инлайна (уезжают в deep-email, TASK-0041).
  - Для пустого/ещё-не-собранного кэша SSL/DNS/email возвращать **плейсхолдер**
    («⏳ собираю SSL/DNS/MX, нажмите 🔄 Обновить») вместо `None`. Вынести помощник
    `format_pending_block`/общий хинт.
  - `html.escape` для интерполируемых значений (как TASK-0037).
- `src/bot/handlers/whois.py` — учесть плейсхолдеры в сборке `body_parts`
  (показывать pending-строку, когда соответствующий кэш пуст и задача
  заэнкьюена).
- `src/locales/{ru,en}.py` — новые ключи (pending-хинт, компактный статус);
  паритет ru/en (инвариант `test_all_ru_keys_present_in_en`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Пустой email-кэш → инлайн показывает плейсхолдер, не пусто.
- Наполненный кэш → MX top-3 + статус (SPF режим, DMARC policy) в одну-две
  строки; >3 MX → «(+N)».
- Значения экранированы `html.escape`.
- Существующие тесты форматтеров не сломаны (обновить ассерты под новую
  компактную форму).

## Требования к тестам

- Unit на `format_email_block`/pending-помощник (моки кэша со `spec`).

## Definition of Done

- [ ] Код реализован; формат карточки обновлён
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Реальная проверка в Telegram (карточка с пустым и наполненным кэшем) —
  отметить в session-отчёте (UX-баги не ловятся unit-тестами, конвенция CLAUDE.md)
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Файлы: `src/services/formatters.py:300` (`format_email_block`),
  `src/bot/handlers/whois.py:186-195`
- Связанные: TASK-0041 (deep-email button), TASK-0042 (subdomains button)
