---
id: TASK-0049
title: html.escape во всех change-нотификациях (defense-in-depth)
status: in_review
milestone: v0.14.0
adr: ""
area: code
depends_on: []
branch: task/0049-htmlescape-all-notifications
owner: grok-4.3
session: docs/sessions/2026-06-05_task-0049-htmlescape-all-notifications.md
pr: https://github.com/nmetluk/whois-watcher/pull/34
created: 2026-06-04
---

# TASK-0049 — html.escape во всех нотификациях (v0.14)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Долг из аудита v0.13 (вынесен «вне области» в TASK-0030/0037).

## Цель

Применить `html.escape` ко **всем** недоверенным значениям, интерполируемым в
`ParseMode.HTML` в change-нотификациях (как уже сделано в
`notify_subdomain_changes`, TASK-0037). Defense-in-depth.

## Контекст / корень проблемы

`ParseMode.HTML` используется в 9 task-файлах; `html.escape` есть только в
`notify_subdomain_changes` и `services/formatters.py`. Остальные интерполируют
домены/NS/issuer/значения напрямую — низкий риск (значения нормализованы), но
конвенция требует экранирования.

## Изменения по файлам

Обернуть в `html.escape(...)` интерполируемые значения (домены, NS, registrar,
issuer, email-записи, тексты ошибок и т.п.) в:
- `src/tasks/notify_changes.py`
- `src/tasks/notify_dns_changes.py`
- `src/tasks/notify_email_changes.py`
- `src/tasks/notify_problem.py`
- `src/tasks/notify_ssl_changes.py`
- `src/tasks/notify_wishlist.py`
- `src/tasks/send_reminders.py`
- `src/tasks/send_ssl_reminder.py`

(Не трогать `<b>`/`<code>`-разметку шаблонов — экранировать только подставляемые
значения.)

**Механика:** значения уходят в HTML-шаблоны локалей через `t(key, **kwargs)`,
а `t()` делает `template.format(**kwargs)`. Поэтому экранировать нужно **до**
передачи в `t()` — оборачивать сами значения в `format_args`/kwargs
(`html.escape(value)`), а не результат `t()`.

**Приоритетные поля (реальные векторы, не только `domain`):**
- 🔴 **issuer SSL-сертификата** (CN/O) — контролируется тем, кто выпустил серт,
  attacker-controllable; обязательно экранировать (`notify_ssl_changes`,
  `send_ssl_reminder`).
- **NS-записи** (DNS) — `notify_dns_changes`.
- **Сырые SPF/DKIM/DMARC-строки** — `notify_email_changes`.
- **registrar / NS / statuses** из WHOIS — `notify_changes`.
- `domain` — низкий риск (punycode/нормализован), но экранировать для
  единообразия.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Значение с HTML-метасимволами (напр. домен/issuer вида `<b>x</b>`) приходит
  в тексте экранированным (`&lt;b&gt;…`), не как сырой HTML.
- Существующая разметка шаблонов не ломается (обычные значения рендерятся как
  раньше).

## Требования к тестам

- На каждый изменённый нотификатор — хотя бы один тест с метасимвольным
  значением (моки со `spec`/`autospec`).

## Definition of Done

- [ ] `html.escape` во всех 8 файлах; тесты на метасимволы
- [ ] **Полный `pytest` зелёный**; `ruff`/`black --check`/`mypy src`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- Аудит v0.13: `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`
- Образец: `src/tasks/notify_subdomain_changes.py` (TASK-0037)
