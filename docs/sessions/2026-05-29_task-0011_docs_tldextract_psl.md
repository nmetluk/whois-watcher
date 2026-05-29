# TASK-0011 — Session Report

**Дата:** 2026-05-29
**Таск:** TASK-0011 — Доки — добавить tldextract/PSL в CLAUDE.md и architecture.md
**Ветка:** task/0011-docs-tldextract-psl
**PR:** https://github.com/nmetluk/whois-watcher/pull/11
**Статус:** done

## Кратко

Документация для новой подсистемы PSL/tldextract (ADR 035). До этого
`tldextract` не упоминался в основной документации, несмотря на то что
является core-зависимостью.

## Выполненные изменения

### 1. CLAUDE.md — Технологический стек

Добавлен `tldextract` после `idna`:

```markdown
- **tldextract** — разбор доменов по Public Suffix List (PSL),
  определение registrable-домена (eTLD+1); bundled snapshot,
  оффлайн-режим (ADR 035)
```

### 2. CLAUDE.md — Архитектурные подсистемы

Добавлен новый раздел «PSL / Domain Parsing (ADR 035)» после WHOIS Lookup:

- Описание функций: `split_domain`, `registrable_domain`, `is_subdomain`,
  `is_public_suffix_only`
- Инварианты: оффлайн, `cache_dir=None`, bundled PSL-данные
- Роутинг: WHOIS → registrable-родитель, DNS/SSL → исходный домен

### 3. docs/architecture.md

Добавлен раздел «Разбор доменов / PSL (ADR 035)» после схемы БД:

- Описание модуля `src/utils/domains.py`
- Инварианты (оффлайн, cache_dir=None)
- Роутинг WHOIS с примерами (`www.example.co.uk` → `example.co.uk`)
- Ссылка на ADR 035

## Проверка

- `handoff.py validate` — OK
- Документация соответствует фактическому коду в `src/utils/domains.py`

## Нет обсуждаемых вопросов

Задача выполнена без открытых вопросов.
