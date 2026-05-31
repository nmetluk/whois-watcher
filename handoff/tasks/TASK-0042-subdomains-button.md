---
id: TASK-0042
title: Карточка /whois — кнопка «Поддомены» (переиспользовать enumeration /subdomains)
status: done
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0040]
branch: task/0041-deep-email-button
owner: claude-code
session: docs/sessions/2026-05-31_task-0041-deep-email-button.md
pr: "#31"
created: 2026-05-31
completed: 2026-05-31
---

> ## ✅ Ревью архитектора (2026-05-31) — merged (PR #31)
>
> ⚠️ Ветка названа `task/0041` по ошибке — содержит работу **TASK-0042**
> (кнопка «Поддомены»). TASK-0041 (deep email) ещё не сделан.
>
> Переиспользует `check_subdomains`/кэш/`subdomains_keyboard`, отдельное
> `reply`-сообщение, 7-дневный freshness-гейт. Тесты добавлены во втором круге
> (`test_whois_subdomains_button.py`: callback-пути fresh/stale, длинный домен).
> **Anti-drift долг не закрыт** (исполнитель понял правку наоборот — `getattr`
> на ORM остался и закреплён тестом). По решению владельца — **смержено + вынес
> правку в follow-up [[TASK-0045]]** (типизировать `SubdomainEnumCache|None`,
> прямой доступ к `.fetched_at`/`.subdomains` вместо `getattr`).
>
> **Ответы на вопросы исполнителя:** (1) единый on-demand-helper — да, вынести
> (0041 переиспользует); (2) отдельное сообщение — одобрено; (3) 7 дней — ок;
> (4) приоритет 0041: сначала долги 0039 (`mx_hosts`+freshness); (5) freshness —
> в общий helper.

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
