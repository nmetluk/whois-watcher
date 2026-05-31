---
id: TASK-0046
title: Тесты deep-email — format_email_deep + кнопка «Глубокий e-mail»
status: done
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0041]
branch: task/0046-deep-email-button-tests
owner: claude-code
session: docs/sessions/2026-06-02_task-0046-deep-email-button-tests.md
pr: ""
created: 2026-06-01
completed: 2026-06-02
---

> ## ✅ Ревью архитектора (2026-06-02, круг 2) — merged
>
> Круг 1 вскрыл 🔴 рантайм-краш `format_email_deep` → `KeyError: 'exceeds'`
> (шаблон `spf_stats="lookups: {count}{exceeds}"` без передачи `exceeds`; `t()`
> роняет KeyError на пропуске). Закрыто: шаблон → `"lookups: {count}"` (ru+en),
> мёртвый ключ `"exceeds"` удалён, плюс **real-`t()` тест**
> `test_format_email_deep_spf_exceeds_with_real_t` (фикстура мока t() переведена
> с `autouse` на класс-scoped; новый тест идёт без мока, проверяет SPF
> exceeds=True/False через настоящий `t()`) — ловит этот класс багов. Краш с
> TASK-0041 устранён. Остальные тесты (none/full/truncation/empty/DANE/escape;
> хэндлер fresh-vs-enqueue; callback≤64) на месте.

# TASK-0046 — Тесты deep-email (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Follow-up из ревью TASK-0041 (круг 3): код смержен, тестов не было.

## Цель

Покрыть юнит-тестами `format_email_deep` и хэндлер кнопки «✉️ Глубокий e-mail»,
которые в TASK-0041 ушли в main без тестов (DoD-промах, anti-drift CLAUDE.md).

## Контекст / корень проблемы

`src/services/formatters.py::format_email_deep` (~144 строки) десериализует
JSONB из `email_deep_cache` и рендерит разбор (SPF/MTA-STS/TLS-RPT/DANE/BIMI).
`src/bot/handlers/whois.py::_show_deep_email_from_whois_card` — freshness gate
по `email_deep_cache.next_check_at`, иначе enqueue `check_email_deep` + «ищу».
Логика рабочая, но не защищена тестами — дрейф полей JSONB/сигнатур пройдёт
незаметно.

## Изменения по файлам

- `tests/unit/test_format_email_deep.py` (новый):
  - `cache=None` → `deep_email.no_data`.
  - Полный кэш (все секции) → присутствуют заголовки секций, значения
    экранированы (`html.escape` — подать значение с `<`/`&`).
  - SPF: `exceeds_limit=True` → пометка ⚠️; усечение sources >8 → «(+N)».
  - Пустые секции (`spf=None`, `mta_sts=None`, …) — раздел не падает, секция
    пропускается/«не настроено».
  - DANE per-MX: смешанные `host_tlsa` (часть True/False) → корректные значки.
- `tests/unit/test_whois_deep_email_button.py` (новый):
  - Свежий `email_deep_cache` (`next_check_at > now`) → рендер из кэша, без
    enqueue.
  - Пусто/протух → `enqueue_job("check_email_deep", registrable)` + «ищу…».
  - callback_data ≤ 64 байт (guard) для `WhoisAction(action="deep_email", …)`.
  - Моки со `spec`/`autospec` (CallbackQuery/Message/User/EmailDeepCache).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `format_email_deep(None)` → no-data; значения экранированы; пустые секции не
  ломают рендер.
- Хэндлер: свежий кэш → без enqueue; пусто/протух → enqueue + «ищу».
- callback_data ≤ 64 байт.

## Definition of Done

- [ ] Тесты добавлены; `pytest` зелёный (полный прогон)
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Реализация: TASK-0041 (`format_email_deep`, `_show_deep_email_from_whois_card`)
- CLAUDE.md → «Защита от рассинхрона (anti-drift)»
