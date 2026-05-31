---
id: TASK-0042
title: Карточка /whois — кнопка «Поддомены» (переиспользовать enumeration /subdomains)
status: in_review
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0040]
branch: task/0041-deep-email-button
owner: claude-code
session: docs/sessions/2026-05-31_task-0041-deep-email-button.md
pr: "#31"
created: 2026-05-31
---

> ## ⛔ Ревью архитектора (2026-05-31) — changes requested (PR #31)
>
> ⚠️ **Путаница имён:** ветка названа `task/0041-deep-email-button`, но содержит
> работу **по TASK-0042** (кнопка «Поддомены»). TASK-0041 (deep email) **не
> сделан** — два долга 0039 (`mx_hosts` для DANE + freshness-гейт deep) открыты.
>
> **Код 0042 принят по сути** — переиспользует `check_subdomains`/кэш/
> `subdomains_keyboard`, отдельное `reply`-сообщение, 7-дневный freshness-гейт.
> **Блокирует мерж до двух правок:**
> 1. **Нет тестов.** Добавить unit (моки со `spec`/`autospec`): (а) guard
>    callback_data ≤ 64 байт для `WhoisAction(action="subdomains", domain=...)`;
>    (б) хэндлер `_show_subdomains_from_whois_card` — путь «свежий кэш → список»
>    и путь «пусто/протух → enqueue `check_subdomains` + "ищу…"».
> 2. **Anti-drift.** `_is_subdomain_cache_fresh(cached: Any)` +
>    `getattr(cached, "fetched_at", None)` — нарушает конвенцию CLAUDE.md
>    (`getattr(orm,"field",default)` маскирует дрейф). Типизировать
>    `cached: SubdomainEnumCache | None`, обращаться к `.fetched_at` напрямую.
>
> **Ответы на вопросы исполнителя (из session-отчёта):**
> 1. **Единый helper — да, вынести сейчас.** 0041 (deep-email) повторит тот же
>    паттерн (кэш→freshness→list | enqueue+«ищу»). Сделать общий
>    `_on_demand_card_action(...)` и переиспользовать в обеих кнопках.
> 2. **Отдельное сообщение** (`reply`) — одобрено, карточку не редактируем.
> 3. **7 дней для subdomain-кэша — ок** (совпадает с success-TTL enumeration).
> 4. **Приоритет 0041 — да:** сначала закрыть два долга 0039 (`mx_hosts` +
>    freshness-гейт), затем кнопка/форматтер deep-email.
> 5. **Freshness-check — в общий helper (п.1)**, не в отдельный фасад; хэндлер ок.
>
> После правок 1–2 — снова в ревью, смержу как TASK-0042.

# TASK-0042 — Кнопка «🛰 Поддомены» в карточке /whois (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Зависит от TASK-0040 (карточка). Контекст — ADR 040; переиспользует ADR 037.

## Цель

Кнопка «🛰 Поддомены» в карточке `/whois`: по нажатию запускает тот же
on-demand enumeration-поток, что и команда `/subdomains` (crt.sh, «ищу…»,
список с opt-in-кнопками), но привязанный к карточке домена.

## Контекст / корень проблемы

ADR 037 уже реализовал `/subdomains` (on-demand crt.sh, кэш `subdomain_enum_cache`,
ARQ `check_subdomains`, UX-список с opt-in). ADR 040: вынести вход в этот поток
**кнопкой на карточке домена**, не дублируя логику — переиспользовать
существующий хэндлер/форматтер `/subdomains`.

## Изменения по файлам

- `src/bot/keyboards.py` — кнопка «🛰 Поддомены» в `whois_actions` (callback ≤64
  байт; вести на registrable-домен, как `/subdomains`).
- `src/bot/handlers/subdomains.py` — выделить общую функцию запуска enumeration
  (если сейчас завязана на message-команду) и вызвать её из callback карточки;
  не дублировать crt.sh-логику.
- `src/locales/{ru,en}.py` — строка кнопки; паритет ru/en.

## Миграции БД

Не требуется (всё уже есть в ADR 037).

## Инварианты (защитить тестами)

- callback_data ≤ 64 байт (guard-тест).
- Кнопка ведёт в тот же поток, что `/subdomains` (тот же результат/кэш) —
  никакой дублированной enumeration-логики.
- Поддомен/apex: enumeration идёт по registrable-родителю (ADR 035/037).

## Требования к тестам

- Unit на callback-хэндлер карточки (моки со `spec`/`autospec`); проверка
  переиспользования общей функции.

## Definition of Done

- [ ] Код реализован; кнопка ведёт в существующий enumeration-поток
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Реальная проверка в Telegram — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040; enumeration — ADR 037)
- Файлы: `src/bot/handlers/subdomains.py`, `src/bot/keyboards.py`
- Связанные: TASK-0040, TASK-0041
