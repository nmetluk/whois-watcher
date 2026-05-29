---
id: TASK-0010
title: Hardening tldextract — cache_dir, комментарий, no-network тест
status: open
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0007]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0010 — Hardening tldextract (offline-инвариант ADR 035)

> 🟡 medium + 🟢 low. Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Инициализация PSL детерминированно оффлайн и без записи на диск; инвариант
«парс без сети» реально защищён тестом, а не декларацией.

## Контекст / корень проблемы

`src/utils/domains.py:31-36` создаёт `tldextract.TLDExtract(suffix_list_urls=())`.
Комментарий на строке 33 (и оба аудита вслед за ним) утверждает
«`cache_dir=None` используется по умолчанию» — **это неверно**: дефолтный
`cache_dir` tldextract — реальный путь в user-cache
(`~/.cache/python-tldextract/...`, проверено). В read-only контейнере попытка
записи снапшота даёт warning. Тест `TestOfflineMode.test_no_network_calls`
(`tests/unit/test_utils_domains.py`) сеть **не блокирует** — лишь вызывает
функции (сам признаёт «базовая проверка»), так что инвариант ADR 035
«tldextract парсит без сетевого вызова (тест на отсутствие сети)» де-факто
не проверяется.

## Изменения по файлам

- `src/utils/domains.py`:
  - Передать `cache_dir=None` (или `False`) в `TLDExtract(...)` явно, чтобы
    отключить дисковый кэш (snapshot уже bundled, сеть отключена).
  - Поправить комментарий: дефолтный cache_dir — НЕ None; мы задаём None
    намеренно для read-only/контейнерных сред.
- `tests/unit/test_utils_domains.py`:
  - Дополнить `test_no_network_calls` реальной блокировкой сети: monkeypatch
    `socket.socket` (и при необходимости `socket.getaddrinfo`) на функцию,
    бросающую исключение, затем убедиться, что `registrable_domain` /
    `split_domain` отрабатывают на bundled snapshot без обращения к сети.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Парс домена не открывает сетевых соединений (socket заблокирован в тесте).
- PSL-данные доступны из bundled snapshot (`co.uk` → public suffix,
  `example.co.uk` → registrable).
- Дисковый кэш не используется (cache_dir отключён).

## Требования к тестам

- Тест с блокировкой `socket.socket` должен проходить и падать, если кто-то
  вернёт сетевой автофетч.

## Definition of Done

- [ ] `cache_dir=None` задан явно, комментарий исправлен
- [ ] No-network тест реально блокирует сокеты и зелёный
- [ ] `pytest` зелёный, `ruff` / `black --check` / `mypy src` чисто
- [ ] Per-session отчёт в `docs/sessions/`
- [ ] `handoff.py validate` проходит; PR открыт, CI зелёный

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- ADR 035: `docs/decisions.md` (раздел «Оффлайн-режим PSL»)
