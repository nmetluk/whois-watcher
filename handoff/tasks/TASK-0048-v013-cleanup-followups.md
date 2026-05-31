---
id: TASK-0048
title: v0.13 cleanup — callback-guard, on-demand-helper, SPF/DMARC ниты
status: open
milestone: v0.13.1
adr: 040
area: code
depends_on: [TASK-0041, TASK-0042]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-06-02
---

# TASK-0048 — v0.13 cleanup-пачка (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🟡/🟢 follow-up из аудита v0.13 — **не блокер тега**, можно после v0.13.0.
> Источник — `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`.

## Цель

Закрыть накопленные 🟡/🟢 ниты из аудита v0.13 одной пачкой.

## Объём (каждый пункт — отдельный коммит)

1. 🟡 **callback_data guard на длинном домене.** Кнопки `deep_email`/
   `subdomains` (и существующие follow/unfollow/raw) несут полный `domain` в
   `WhoisAction` → на длинном FQDN пара action+domain может превысить 64 байта
   Telegram (урок TASK-0024). Добавить guard-тест с max-длинным доменом; при
   реальном переполнении — перейти на idx/registrable для этих действий.
2. 🟡 **Общий on-demand-helper.** Вынести из `whois.py` общий хелпер для
   «кэш→freshness→render | enqueue+ищу» и переиспользовать в
   `_show_subdomains_from_whois_card` и `_show_deep_email_from_whois_card`
   (сейчас дублируют паттерн).
3. 🟢 **SPF root-lookup.** `src/email_intel/spf_resolver.py`: корневой lookup
   домена не должен считаться в лимите 10 (RFC 7208 §4.6.4 считает только
   include/redirect/a/mx/ptr/exists). Скорректировать счётчик или задокументировать
   намеренную строгость.
4. 🟢 **SPF `all` в sources.** Отфильтровать механизм `all` (`-all`/`~all`/
   `?all`/`+all`) из `sources` — он не источник.
5. 🟢 **DMARC compact через locale-ключ.** `src/services/formatters.py`:
   заменить `t("commands.whois.email_no_dmarc").split(":")[-1].strip()` на
   отдельный locale-ключ (ru/en паритет).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- callback_data ≤ 64 байт на max-длинном домене.
- SPF: sources без `all`-механизма; lookup_count по скорректированному правилу.
- DMARC compact-текст из явного ключа (не split).

## Definition of Done

- [ ] Пункты 1–5 реализованы; тесты обновлены/добавлены
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`
- ADR 040
