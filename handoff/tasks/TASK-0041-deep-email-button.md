---
id: TASK-0041
title: Карточка /whois — кнопка «Глубокий e-mail» (on-demand)
status: done
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0039, TASK-0040]
branch: task/0041-deep-email-button
owner: claude-code
session: docs/sessions/2026-06-01_task-0041-deep-email-button.md
pr: ""
created: 2026-05-31
completed: 2026-06-01
---

> ## ✅ Ревью архитектора (2026-06-01, круг 3) — merged
>
> Закрыто: ребейз на main (0045 не откатывается), `format_email_deep`
> реализован (formatters.py — JSONB→разбор SPF/MTA-STS/TLS-RPT/DANE/BIMI,
> `html.escape`), заглушка убрана, локали ru/en, долги 0039 (mx_hosts→DANE +
> freshness gate), `getattr` нет. Стале-комментарий «заглушка» снят архитектором
> при мерже.
> **Тесты deep-email отсутствуют** → по решению владельца merge + follow-up
> [[TASK-0046]] (unit на `format_email_deep` + deep-хэндлер).

> ## ⛔ Ревью архитектора (2026-06-01, круг 2) — changes requested (всё ещё НЕ готово)
>
> Исполнитель снова сообщил «готово», но блокер №1 не закрыт + ветка устарела.
> - 🔴 **Ветка не отребейзена → мерж откатит TASK-0045.** Дифф удаляет
>   `docs/sessions/2026-06-01_task-0045-getattr-antidrift.md`, откатывает файл
>   TASK-0045 и **заново вносит `getattr`** в `whois.py` (стр. 529/533/572 —
>   хэндлер поддоменов). **Сначала** `git fetch && git rebase origin/main`
>   (или merge main), убедиться, что 0045 НЕ откатывается (grep getattr пуст).
> - 🔴 **`format_email_deep` не реализован (блокер №1 круга 1 — НЕ закрыт).**
>   `src/services/formatters.py` не тронут; в `whois.py` всё ещё
>   `# TODO … заглушка` (стр. 618) и «заглушка, будет доработана» (стр. 580).
>   Кнопка показывает заглушку, не разбор. **Это и есть суть задачи** — без
>   форматтера фича не существует.
> - 🔴 **Нет тестов на deep-email** (блокер №2 круга 1 — НЕ закрыт).
> - ✅ Поправлено: `getattr` в deep-хэндлере убран; `.replace()`-хак на локалях
>   убран; долги 0039 (mx_hosts + freshness gate) закрыты.
>
> **Приоритет: (1) ребейз на main без отката 0045; (2) реализовать
> `format_email_deep` + убрать заглушку; (3) тесты.** Детали — в круге 1 ниже.
>
> ---
>
> ## ⛔ Ревью архитектора (2026-06-01, круг 1) — changes requested (НЕ готово)
>
> Заявлено «готово», но это **WIP-заглушка**, не законченная фича. Что есть:
> - ✅ **Долг 0039 #1 (mx_hosts→DANE)** закрыт: `check_email_deep` читает MX из
>   `email_intel_cache` и зовёт `fetch_deep_email(domain, mx_hosts=...)`
>   (сигнатура 0038 уже принимает `mx_hosts`).
> - ✅ **Долг 0039 #2 (freshness gate)** присутствует — но через `getattr`.
>
> **Блокеры мержа:**
> 1. **Фича-заглушка.** В свежем-кэш-пути захардкожен текст «(TASK-0041 в
>    разработке)…» вместо реального вывода. **Нет `format_email_deep`** —
>    кнопка не показывает разбор. Реализовать форматтер: SPF (sources/
>    lookup_count/exceeds_limit), MTA-STS (mode/mx/max_age/reachable), TLS-RPT,
>    DANE (per-MX), BIMI; десериализовать JSONB из `email_deep_cache` и
>    рендерить; `html.escape` на значениях.
> 2. **Нет тестов.** Добавить unit: хэндлер (свежий кэш→рендер, пусто/протух→
>    enqueue+«ищу»), `format_email_deep`, прокидывание mx_hosts в
>    `check_email_deep`. Моки со `spec`/`autospec`.
> 3. **Anti-drift `getattr`.** `getattr(cached, "next_check_at", None)` — то же
>    нарушение, что чинит [[TASK-0045]]. Типизировать `EmailDeepCache | None`,
>    обращаться к `.next_check_at` напрямую.
> 4. **Хардкод/хак строк.** Захардкоженный русский текст + `t(...searching)
>    .replace("Поддомены","Глубокий e-mail")` — сломается в EN. Завести
>    отдельные locale-ключи (searching/header deep email), паритет ru/en.
> 5. **(Рекомендация) общий on-demand-helper** — вынести и переиспользовать в
>    обеих кнопках (subdomains + deep), как договорились в ревью 0042.
>
> После 1–4 (5 желательно) — снова в ревью.

# TASK-0041 — Кнопка «✉️ Глубокий e-mail» (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> Зависит от TASK-0039 (ARQ + кэш deep) и TASK-0040 (карточка). Контекст — ADR 040.
>
> ⚠️ **Имя ветки.** Ветка `task/0041-deep-email-button` на origin по ошибке
> содержит работу TASK-0042 (PR #31). Для этого таска завести **отдельную**
> ветку (напр. `task/0041-deep-email-button-v2`) **после** мержа 0042 и
> `git pull --rebase origin main`. Переиспользовать общий on-demand-helper,
> который добавит TASK-0042 (см. ревью 0042). Обязательно закрыть два долга
> 0039: прокинуть `mx_hosts` из `email_intel_cache` в deep-сбор (иначе DANE
> пустой) и freshness-гейт `email_deep_cache.next_check_at` перед enqueue.

## Цель

Кнопка «✉️ Глубокий e-mail» в карточке `/whois`: по нажатию — «⏳ ищу…», запуск
`check_email_deep` (TASK-0039), затем сообщение с углублённым разбором
(SPF include/lookups, MTA-STS, TLS-RPT, DANE/TLSA, BIMI). Паттерн `/subdomains`.

> **Долги из ревью TASK-0039 (обязательно закрыть здесь):**
> 1. **DANE сейчас пустой** — `check_email_deep` зовёт `fetch_deep_email(domain)`
>    без `mx_hosts`. Прокинуть MX из базового `email_intel_cache` в deep-сбор
>    (расширить сигнатуру `check_email_deep`/`fetch_deep_email` `mx_hosts`-
>    параметром или читать MX из `email_intel_cache` внутри задачи).
> 2. **Freshness-гейт** — перед enqueue `check_email_deep` хэндлер проверяет
>    `email_deep_cache.next_check_at`: если кэш свежий — показать сразу из кэша,
>    не бить сеть; пусто/протух — «⏳ ищу…» + enqueue.

## Контекст / корень проблемы

ADR 040: deep email — on-demand за кнопкой. UX-поток уже отлажен в `/subdomains`
(callback с idx ≤64 байт, «ищу…», досыл результата) — переиспользовать стиль.

## Изменения по файлам

- `src/bot/keyboards.py` — добавить кнопку в `whois_actions` (новый `action` в
  `WhoisAction` или отдельный CallbackData; callback ≤64 байт — домен/idx, урок
  TASK-0024).
- `src/bot/handlers/whois.py` (или новый `handlers/email_deep.py`) — callback-
  хэндлер: ack «⏳ ищу…», enqueue `check_email_deep`, по готовности показать
  результат (или сразу из свежего кэша; пустой → enqueue + «ищу»).
- `src/services/formatters.py` — `format_email_deep(result, lang)` —
  человекочитаемый разбор; `html.escape` на значениях.
- `src/locales/{ru,en}.py` — строки deep-email + кнопка; паритет ru/en.

## Миграции БД

Не требуется (кэш — в TASK-0039).

## Инварианты (защитить тестами)

- callback_data ≤ 64 байт (guard-тест).
- Пустой deep-кэш → «ищу…» + enqueue; наполненный → форматированный разбор.
- SPF: показано число lookups и флаг превышения; MTA-STS: mode; недоступность
  записей — «не настроено», не ошибка.
- Значения экранированы.

## Требования к тестам

- Unit на callback-хэндлер (моки со `spec`/`autospec`) и `format_email_deep`.

## Definition of Done

- [ ] Код реализован; кнопка работает on-demand
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Реальная проверка в Telegram — в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- ADR: `docs/decisions.md` (ADR 040)
- Образец UX: `src/bot/handlers/subdomains.py`, `src/bot/keyboards.py`
  (`whois_actions`, `SubdomainAction`)
- Связанные: TASK-0039, TASK-0040, TASK-0042
