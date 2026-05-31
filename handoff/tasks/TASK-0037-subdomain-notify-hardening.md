---
id: TASK-0037
title: Hardening поддоменов — html.escape в нотификациях + кап интервала FSM (ADR 038)
status: in_review
milestone: v0.12.0
adr: 038
area: code
depends_on: [TASK-0029, TASK-0035]
branch: task/0037-subdomain-notify-hardening
owner: ""
session: docs/sessions/2026-05-31_task-0037-subdomain-notify-hardening.md
pr: #26
created: 2026-05-31
---

> ## ⛔ Ревью архитектора (2026-05-31) — changes requested (PR #26)
>
> Код корректен: `html.escape` на заголовке и в обеих секциях имён, лимит как
> поле `Limits.max_subdomain_check_interval_days` (`Field(365, ge=1)`), хэндлер
> читает через `get_limits()`, локали ru/en обновлены с паритетом. Escape
> покрыт тестом (`TestNotifySubdomainChangesHtmlEscaping`).
>
> **Блокирует мерж — один недостающий тест.** Инвариант таска «FSM:
> `interval > 365` → invalid, граничные `1`/`365` принимаются, `366`
> отклоняется» не покрыт. Добавить unit-тест на `on_subdomain_interval_input`
> в `tests/unit/test_notify_config_handler.py` (моки со `spec`/`autospec`):
> `1` и `365` → override записан; `366` и `0` → ветка invalid, `_persist` не
> вызван. После этого — снова в ревью, смержу.

# TASK-0037 — Hardening нотификаций/FSM поддоменов (ADR 038)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Источник — 🟢-находки аудита
> `handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`. **Включено в
> блокеры тега v0.12.0** (решение владельца 2026-05-31: влить все фиксы до
> релиза) — `TASK-0036` ждёт эту задачу.
>
> ⚠️ **Координация с TASK-0035 (в работе).** 0035 переписывает ту же функцию
> `notify_subdomain_changes` (батч `get_by_ids`, агрегация toggle'ов по
> пользователю). Чтобы не ловить конфликт — **стартовать после мержа 0035**
> (`depends_on: TASK-0035`): сделать `git pull --rebase origin main`, затем
> добавить `html.escape` поверх уже изменённой 0035 структуры цикла. Не
> начинать параллельно.

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

- `src/tasks/notify_subdomain_changes.py` — обернуть в `html.escape(...)`
  **каждую** интерполяцию недоверенного значения в HTML-текст (после
  структуры 0035): заголовок `f"<b>{registrable_domain}</b> —"` и имена
  поддоменов в обеих секциях (`f"  🆕 {subdomain}"`, `f"  ➖ {subdomain}"`).
  Счётчик `and_more` — int, экранирование не нужно. `import html` в начало.
- `src/bot/handlers/notify_config.py` — в `on_subdomain_interval_input`
  добавить верхнюю границу (`interval > max` → ветка invalid рядом с
  `interval < 1`). Лимит — **новым полем в pydantic-settings** `Limits`
  (`src/config/limits.py`), по образцу `ttl_*_days`, напр.
  `max_subdomain_check_interval_days: int = Field(365, ge=1, description=...)`
  (overridable через env, конвенция CLAUDE.md — не bare-константа). В хэндлере
  читать через инстанс настроек, как остальные лимиты.
- (опц.) `src/locales/{ru,en}.py` — уточнить текст `subdomain_interval_invalid`
  про допустимый диапазон `1…365` (ключ уже есть, правки в обоих языках —
  инвариант `test_all_ru_keys_present_in_en`).

**Вне области (не трогать в этом PR):** html.escape в whois/ssl/dns/email-
нотификациях (та же конвенция, но отдельным таском — держим PR маленьким).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `notify_subdomain_changes`: имя с HTML-метасимволами (напр.
  `"<b>x</b>.example.com"`) приходит в тексте экранированным
  (`&lt;b&gt;…`) — не как сырой HTML.
- FSM: `interval > 365` → сообщение invalid, override не записан; граничные
  `1` и `365` — принимаются; `366` — отклоняется.

## Требования к тестам

- Unit, моки со `spec`/`autospec`.
- **Регресс 0033:** существующие ассерты в
  `tests/unit/test_notify_subdomain_changes.py` сверяются с обычными
  ASCII-именами (`s1.example.com` и т.п.) — `html.escape` их не меняет,
  тесты должны остаться зелёными. Добавить **новый** кейс с метасимволом,
  не ломая старые.

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
