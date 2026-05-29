---
id: TASK-0011
title: Доки — добавить tldextract/PSL в CLAUDE.md и architecture.md
status: claimed
milestone: v0.9.2
adr: 035
area: docs
depends_on: [TASK-0007]
branch: task/0011-docs-tldextract-psl
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0011 — Документация подсистемы PSL (tldextract)

> 🟢 low. Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

`CLAUDE.md` и `docs/architecture.md` отражают новую core-зависимость
`tldextract` и подсистему разбора доменов / PSL (ADR 035).

## Контекст / корень проблемы

`grep tldextract` по `CLAUDE.md` и `docs/architecture.md` — 0 совпадений.
В то же время `tldextract` — теперь core-зависимость (`pyproject.toml`,
`uv.lock`), а `src/utils/domains.py` — отдельная подсистема разбора доменов
с инвариантами (оффлайн PSL, registrable vs поддомен). Доки отстали от кода.

## Изменения по файлам

- `CLAUDE.md`:
  - В разделе «Технологический стек» добавить строку про `tldextract` — PSL,
    registrable-домен (eTLD+1), оффлайн bundled snapshot.
  - В «Архитектурные подсистемы» — короткий пункт про разбор доменов / PSL
    (`src/utils/domains.py`, ADR 035): WHOIS у registrable, DNS/SSL у
    поддомена.
- `docs/architecture.md`:
  - Описать модуль `src/utils/domains.py` и роутинг WHOIS на registrable;
    сослаться на ADR 035.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Документация-only; тестов нет. Сверить тексты с фактическим кодом.

## Требования к тестам

- Не требуется.

## Definition of Done

- [ ] `CLAUDE.md` и `docs/architecture.md` упоминают tldextract/PSL и
      соответствуют коду
- [ ] Per-session отчёт в `docs/sessions/`
- [ ] `handoff.py validate` проходит; PR открыт

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- ADR 035: `docs/decisions.md`
