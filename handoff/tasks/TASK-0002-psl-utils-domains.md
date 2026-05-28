---
id: TASK-0002
title: PSL — зависимость tldextract + src/utils/domains.py
status: completed
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0001]
branch: task/0002-psl-utils-domains
owner: ""
session: 2026-05-28_task-0002_psutils_domains
pr: "2"
created: 2026-05-29
---

# TASK-0002 — PSL: tldextract + src/utils/domains.py (подэтап 2a)

> Самодостаточно. Процесс — `handoff/README.md`. Дизайн — ADR 035
> (`docs/decisions.md`) и `PLAN_subdomains_wishlist.md` (Этап 2).
> Это первый из четырёх подэтапов v0.9.0; только чистая логика + тесты,
> без изменений схемы и UX (они в TASK-0003…0005).

## Цель

Добавить определение registrable-домена (eTLD+1) и классификацию
поддоменов/публичных суффиксов через PSL. Никаких сетевых вызовов в
горячем пути.

## Контекст / корень проблемы

Валидатор синтаксический, PSL нет → `a.pinbetting.ru` уходит в WHOIS
как самостоятельный домен. Нужен фундамент: чистый модуль, на который
обопрутся миграция (2b), WHOIS-роутинг (2c) и UX (2d).

## Изменения по файлам

- `pyproject.toml` — добавить `tldextract>=5,<6`; обновить `uv.lock`
  (`uv sync`). При необходимости — `[[tool.mypy.overrides]]` для
  `tldextract.*`.
- `src/utils/domains.py` (новый) — чистые функции, без сети/БД:
  - инициализация `TLDExtract` с bundled snapshot и **без сетевого
    автофетча** (`suffix_list_urls=()` или эквивалент, фиксированный
    `cache_dir`), `include_psl_private_domains=False`;
  - `split_domain(domain) -> DomainParts(subdomain, registrable, suffix)`;
  - `registrable_domain(domain) -> str` (eTLD+1);
  - `is_subdomain(domain) -> bool` (непустая subdomain-часть относительно
    registrable);
  - `is_public_suffix_only(domain) -> bool` (ввод == публичный суффикс);
  - все работают на punycode-форме (после `utils.idn.normalize_domain`).
- `src/bot/validators.py` — `is_valid_domain` дополнительно отклоняет
  `is_public_suffix_only` (PSL-логику не дублировать — звать хелпер).

## Миграции БД

Не требуется (только TASK-0003).

## Инварианты (защитить тестами)

- `registrable_domain`: `a.pinbetting.ru→pinbetting.ru`,
  `pinbetting.ru→pinbetting.ru`, `a.b.foo.co.uk→foo.co.uk`,
  `foo.org.uk→foo.org.uk`, IDN (`xn--…`), `пример.рф`.
- `is_subdomain`: `www.foo.org.uk→True`, `foo.org.uk→False`,
  `pinbetting.ru→False`, `a.pinbetting.ru→True`.
- `is_public_suffix_only`: `co.uk→True`, `org.uk→True`, `ru→True`,
  `pinbetting.ru→False`.
- tldextract **не ходит в сеть** (тест: мок/запрет сетевого вызова, либо
  проверка, что используется оффлайн-снапшот).

## Требования к тестам

- `tests/unit/test_utils_domains.py` — table-driven по инвариантам выше.
- Регрессия `is_valid_domain` на публичный суффикс.

## Definition of Done

- [ ] `tldextract` добавлен, `uv.lock` обновлён
- [ ] `src/utils/domains.py` реализован, оффлайн-режим PSL
- [ ] Тесты по инвариантам зелёные; `pytest` полный прогон
- [ ] `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR 035 (`docs/decisions.md`), `PLAN_subdomains_wishlist.md` (Этап 2, 2a)
