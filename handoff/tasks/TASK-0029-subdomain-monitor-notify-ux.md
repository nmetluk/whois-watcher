---
id: TASK-0029
title: Уведомления о новых/исчезнувших поддоменах + UX toggles/интервал + локали (ADR 038)
status: open
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0028]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-30
---

# TASK-0029 — Уведомления + UX мониторинга поддоменов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Fan-out уведомлений о diff + конфигурирование мониторинга в карточке `/whois`.

## Изменения по файлам

- `src/tasks/notify_subdomain_changes.py` (новый, образец
  `notify_ssl_changes`): принимает registrable + diff (new/removed), рассылает
  **всем** подписчикам registrable с `track_subdomains=true`, honoring
  `notify_subdomain_new` / `notify_subdomain_removed` и `is_muted`. Не дублирует
  одному пользователю. Текст security-стиль: «🆕 новый поддомен `X`» /
  «➖ исчез поддомен `Y`» (через сервис/formatter, не хардкод).
  - Зарегистрировать задачу в `arq_config` (`_build_functions`).
- `src/bot/keyboards.py` — в `_TOGGLE_FIELDS` (inline-конфигуратор
  `⚙️ Уведомления`) добавить:
  `("track_subdomains", "notify_config.type.track_subdomains")`,
  `("notify_subdomain_new", ...)`, `("notify_subdomain_removed", ...)`.
- Кнопка-FSM «интервал проверки поддоменов» — по образцу `edit_ssl_days`
  (ADR 029): кнопка в `notify_config_keyboard`, состояние в `src/bot/states.py`,
  хэндлер редактирования `User.subdomain_check_interval_days` /
  `UserDomain.subdomain_check_interval_override`. Валидация: целое ≥ 1.
- `src/locales/ru.py`, `en.py` — **все** новые строки (toggle-подписи, текст
  уведомлений new/removed, prompt интервала, ошибки валидации). Инвариант
  `test_all_ru_keys_present_in_en`.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Уведомление уходит только подписчикам `track_subdomains=true`, honoring
  per-type toggle и `is_muted`; нет дублей одному user.
- `notify_subdomain_new=false` гасит «новые», `notify_subdomain_removed=false`
  — «исчезнувшие».
- FSM интервала: валидный ввод сохраняется, мусор/0/отрицательное → ошибка.
- `test_all_ru_keys_present_in_en` зелёный.
- Моки хэндлеров/сервисов — со `spec`/`autospec`; покрыть callback toggle и
  FSM-путь (anti-drift, CLAUDE.md).

## Требования к тестам

- `tests/unit/test_notify_subdomain_changes.py` (fan-out, toggles, mute, дедуп).
- Тест FSM интервала + toggle-callback.

## Definition of Done

- [ ] Уведомления fan-out + toggles + FSM интервала + локали ru/en
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate` OK; PR, CI зелёный

## Ссылки

- ADR 038; образцы — `src/tasks/notify_ssl_changes.py`, `notify_config_keyboard`
  + `_TOGGLE_FIELDS`, `edit_ssl_days`-FSM (ADR 029/030).
