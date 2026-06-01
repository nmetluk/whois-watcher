---
id: TASK-0048
title: v0.13 cleanup — callback-guard, on-demand-helper, SPF/DMARC ниты
status: in_review
milestone: v0.13.1
adr: 040
area: code
depends_on: [TASK-0041, TASK-0042]
branch: task/0048-v013-cleanup-followups
owner: grok
session: docs/sessions/2026-06-04_task-0048-v013-cleanup-followups.md
pr: "#33"
created: 2026-06-02
---

# TASK-0048 — v0.13 cleanup-пачка (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🟡/🟢 follow-up из аудита v0.13 — **не блокер тега**, можно после v0.13.0.
> Источник — `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`.

## Цель

Закрыть накопленные 🟡/🟢 ниты из аудита v0.13 одной пачкой.

## Объём (каждый пункт — отдельный коммит). Решения уже приняты — следовать.

1. 🟡 **callback_data ≤ 64 для `deep_email`/`subdomains`.** Эти две кнопки
   работают по **registrable-родителю** (enumeration/deep идут на eTLD+1), а
   хэндлеры всё равно делают `registrable_domain(...)`. **Решение:** в
   `whois_actions` (`src/bot/keyboards.py`) класть в callback этих двух кнопок
   `registrable_domain(domain)`, а не полный `domain` — короче и семантически
   верно. (`follow`/`unfollow`/`raw` **не трогать** — им нужен точный домен;
   их overflow — отдельный пре-существующий долг, вне области.)
   Хэндлеры `_show_subdomains_from_whois_card`/`_show_deep_email_from_whois_card`
   уже зовут `registrable_domain` — оставить (idempotent: registrable от
   registrable = он сам).
   **Тест:** построить callback для длинного домена (напр.
   `"a" * 60 + ".example.com"`) и проверить `len(pack().encode()) <= 64`.

2. 🟡 **Общий on-demand-helper.** Вынести в `whois.py` (или
   `src/bot/handlers/_card_helpers.py`) функцию-шаблон и переиспользовать в обоих
   хэндлерах кнопок. Предлагаемая сигнатура (callable-инъекция, чтобы не тащить
   зависимости):
   ```python
   async def _on_demand_card_view(
       *,
       query: CallbackQuery,
       lang: str,
       registrable: str,
       cached,                       # запись кэша или None
       is_fresh: bool,               # уже посчитанная свежесть
       render: Callable[[Any], str], # cached -> текст (только если is_fresh)
       reply_markup_factory,         # cached -> InlineKeyboardMarkup | None
       arq_redis: ArqRedis,
       job_name: str,                # "check_subdomains" | "check_email_deep"
       searching_text: str,          # локализованный «⏳ ищу…»
   ) -> None: ...
   ```
   Внутри: `if cached is not None and is_fresh: reply(render(cached), …)` иначе
   `enqueue_job(job_name, registrable)` + reply(searching_text). Оба
   существующих хэндлера должны только готовить аргументы и звать helper.

3. 🟢 **SPF root-lookup не считать в лимите 10.** В
   `src/email_intel/spf_resolver.py` корневой TXT-lookup домена не должен
   уменьшать бюджет (RFC 7208 §4.6.4: считаются только механизмы, вызывающие
   DNS — include/redirect/a/mx/ptr/exists; начальная проверка домена не
   считается). Сейчас `current_lookups = _lookups + 1` инкрементит на каждом
   уровне включая корень. **Решение:** не инкрементить за сам факт входа в
   домен; увеличивать счётчик только при переходе в `include`/`redirect`.
   Обновить тест на превышение (порог сместится на 1).

4. 🟢 **SPF `all` не в sources.** В сборке `terminal` отфильтровать токен
   механизма `all` (`-all`/`~all`/`?all`/`+all`, регистронезависимо) — он не
   источник, только модификатор результата.

5. 🟢 **DMARC compact через locale-ключ.** В `src/services/formatters.py`
   заменить `t("commands.whois.email_no_dmarc").split(":")[-1].strip()` на новый
   ключ `commands.whois.email_dmarc_none_compact` (напр. ru «нет», en «none»);
   добавить в ru и en (инвариант `test_all_ru_keys_present_in_en`).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `deep_email`/`subdomains` callback_data ≤ 64 байт на длинном домене; в
  callback — registrable.
- Оба хэндлера кнопок используют общий `_on_demand_card_view` (нет дублирующего
  кэш→freshness→enqueue кода).
- SPF: `sources` без `all`-механизма; `lookup_count` без учёта корневого
  lookup (тест превышения обновлён).
- DMARC compact-текст из ключа `email_dmarc_none_compact` (не split).

## Definition of Done

- [ ] Пункты 1–5 реализованы; тесты обновлены/добавлены
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`
- ADR 040
