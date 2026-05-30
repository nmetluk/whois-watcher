---
id: TASK-0029
title: Уведомления о новых/исчезнувших поддоменах + UX toggles/интервал + локали (ADR 038)
status: done
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0028]
branch: task/0029-subdomain-monitor-notify-ux
owner: claude-code
session: docs/sessions/2026-05-30_task_0029_subdomain_monitor_notify_ux.md
pr: "#21"
created: 2026-05-30
completed: 2026-05-30
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

---

## Ревью v1 — один фикс до мержа (2026-05-30)

Стек 0027/0028/0029 (PR #19/#20/#21) проверен — качество высокое, схема/diff/
scheduler/интеграция/fan-out корректны, локали ru/en симметричны. Один баг в
`src/tasks/notify_subdomain_changes.py`.

**Пустое уведомление, когда изменился только выключенный тип.** Гард «оба
toggle выключены → skip» не ловит случай, где включённый toggle пуст:

- diff = только `removed`; юзер `notify_subdomain_removed=False`,
  `notify_subdomain_new=True` → блок `new` пропущен (нет new-элементов),
  блок `removed` пропущен (toggle off), гард
  `not notify_new and not notify_removed` = `False` → **уходит сообщение из
  одного заголовка `<b>example.com</b> —` без тела.** Симметрично для new-only
  при `notify_subdomain_new=False`.

Это не редкость: кто отключил «исчезнувшие» (они шумнее), будет получать пустые
«домен —» при любых удалениях.

**Фикс — гард по факту добавленного контента, не по toggle'ам.** Заменить
```python
if not user_domain.notify_subdomain_new and not user_domain.notify_subdomain_removed:
    continue
```
на проверку, что в сообщение реально добавлен контент, например:
```python
if len(lines) == 1:   # только заголовок «<b>domain</b> —», тела нет
    continue
```
(гард поставить ПЕРЕД формированием `text_body`/отправкой).

**Тесты (обязательно — сейчас покрыты только empty-diff + exists):**
- removed-only при `notify_subdomain_removed=False`, `notify_subdomain_new=True`
  → `bot.send_message` НЕ вызывается (нет пустого сообщения).
- new-only при `notify_subdomain_new=False` → НЕ вызывается.
- new-only при `notify_subdomain_new=True` → вызывается, в тексте есть поддомен.
- mute / дедуп одному user (если ещё не покрыто).
Моки со `spec`/`autospec` (anti-drift, CLAUDE.md).

Дорабатывать в той же ветке `task/0029-subdomain-monitor-notify-ux`.
