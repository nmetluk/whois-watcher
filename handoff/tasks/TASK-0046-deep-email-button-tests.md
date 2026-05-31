---
id: TASK-0046
title: Тесты deep-email — format_email_deep + кнопка «Глубокий e-mail»
status: in_review
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0041]
branch: task/0046-deep-email-button-tests
owner: claude-code
session: docs/sessions/2026-06-02_task-0046-deep-email-button-tests.md
pr: ""
created: 2026-06-01
---

> ## ⛔ Ревью архитектора (2026-06-02) — changes requested (🔴 найден реальный краш)
>
> Тесты по структуре ок (spec-моки, none/full/exceeds/truncation/empty/DANE/
> escape; хэндлер fresh-vs-enqueue; callback≤64), **но вскрыт и НЕ закрыт
> рантайм-баг:**
>
> 🔴 **`format_email_deep` падает с `KeyError: 'exceeds'`.** Шаблон
> `deep_email.spf_stats = "lookups: {count}{exceeds}"`, а `format_email_deep`
> зовёт `t("deep_email.spf_stats", lang, count=lookup_count)` **без `exceeds`**.
> `t()` делает `template.format(**kwargs)` и намеренно роняет KeyError на
> пропущенном placeholder. → Кнопка deep-email крашится на любом домене с SPF.
> Баг уже в main (с TASK-0041).
> **Фикс:** убрать `{exceeds}` из шаблона `deep_email.spf_stats` (ru+en) — код
> уже дописывает `exceeds_text` отдельно через `+ exceeds_text`. И **удалить
> мёртвый ключ `"exceeds": ""`** из ru/en (он ничего не чинит: `.format(**kwargs)`
> не читает соседние ключи LOCALE).
>
> 🔴 **Тесты форматтера мокают `t()`** (`side_effect=lambda …: f"[{key}]"`) —
> реальный `.format()` не выполняется, поэтому этот класс багов (рассинхрон
> шаблон/аргументы) тесты пропускают. **Добавить хотя бы один тест с РЕАЛЬНЫМ
> `t()`** (без мока), прогоняющий SPF-секцию с `exceeds_limit=True` и `False` —
> он должен поймать KeyError до фикса и проходить после.
>
> После фикса бага + real-`t()` теста — снова в ревью.

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
