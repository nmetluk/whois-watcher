---
id: TASK-0037
title: Hardening поддоменов — html.escape в нотификациях + кап интервала FSM (ADR 038)
status: open
milestone: v0.12.1
adr: 038
area: code
depends_on: [TASK-0029]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-31
---

# TASK-0037 — Hardening нотификаций/FSM поддоменов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Источник — 🟢-находки аудита
> `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`. **Не блокер
> тега v0.12.0** — follow-up.

## Цель

Закрыть два мелких 🟢-замечания аудита: defense-in-depth-экранирование в
уведомлениях и верхний кап интервала проверки в FSM.

## Контекст / корень проблемы

1. **html.escape (defense-in-depth).** `src/tasks/notify_subdomain_changes.py`
   интерполирует `registrable_domain` и имена поддоменов в сообщение с
   `ParseMode.HTML` без экранирования. Сейчас безопасно: парсер
   (`parse_crtsh_response`) прогоняет имена через
   `idna.encode(...).decode("ascii")` → только ASCII `[a-z0-9.-]`. Но
   безопасность держится на инварианте нормализации — лучше явно
   `html.escape`. (Та же конвенция применима к whois/ssl-нотификациям —
   при желании выровнять заодно.)
2. **Кап интервала FSM.** `src/bot/handlers/notify_config.py::
   on_subdomain_interval_input` валидирует только нижнюю границу
   (`interval < 1` → invalid). Без верхней границы ввод вроде `99999999999`
   пройдёт `int()` и упрётся в DB при записи (`Integer` = int4,
   max 2147483647 → ошибка persist). Добавить разумный кап (напр. ≤ 365).

## Изменения по файлам

- `src/tasks/notify_subdomain_changes.py` — `html.escape(...)` для
  `registrable_domain` и имён поддоменов перед вставкой в HTML-текст.
- `src/bot/handlers/notify_config.py` — в `on_subdomain_interval_input`
  добавить верхнюю границу (`interval > MAX_DAYS` → invalid); вынести
  `MAX_DAYS` в `src/config/limits.py` (без magic numbers, конвенция CLAUDE.md).
- (опц.) `src/locales/{ru,en}.py` — уточнить текст `subdomain_interval_invalid`
  про допустимый диапазон.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `notify_subdomain_changes`: имя с HTML-метасимволами (если вдруг просочится)
  экранируется — тест на `html.escape`-вызов/результат.
- FSM: `interval > MAX_DAYS` → сообщение invalid, override не записан;
  граничные `1` и `MAX_DAYS` — принимаются.

## Требования к тестам

- Unit, моки со `spec`/`autospec`.

## Definition of Done

- [ ] Код реализован по спецификации
- [ ] `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/` и вписан в `session:`
- [ ] `handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR: `docs/decisions.md` (ADR 038)
- Аудит: `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`
- Связанные: TASK-0029 (реализация), TASK-0035 (fan-out N+1/дедуп)
