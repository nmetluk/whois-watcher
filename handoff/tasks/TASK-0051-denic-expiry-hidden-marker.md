---
id: TASK-0051
title: DENIC — значок «expiry скрыт реестром» в /list и подсказка
status: in_review
milestone: v0.14.0
adr: ""
area: code
depends_on: []
branch: task/0051-denic-expiry-hidden-marker
owner: grok-4.3
session: docs/sessions/2026-06-07_task-0051-denic-expiry-hidden-marker.md
pr: ""
created: 2026-06-04
---

# TASK-0051 — DENIC expiry-hidden marker (v0.14)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Отличать «реестр не отдаёт дату истечения» (`.de`/DENIC и подобные) от «нет
данных» в `/list` и карточке — отдельным значком + подсказкой, чтобы не вводить
в заблуждение.

## Контекст / корень проблемы

DENIC (`.de`) и ряд реестров не публикуют expiry в WHOIS/RDAP. Сейчас домен
показывается как «нет данных», что выглядит как ошибка, хотя это нормальное
поведение реестра.

## Изменения по файлам

- `src/services/formatters.py` (`format_list_row` / карточка) — для доменов,
  где реестр не отдаёт expiry, показывать отдельный значок (напр. `🔒`) +
  локализованную подсказку «дата скрыта реестром», а не «нет данных».
- Определение «expiry hidden» — по TLD/registry-сигналу (список known-no-expiry
  TLD в конфиг/util, начиная с `.de`; расширяемо). Не хардкодить в форматтере.
- `src/locales/{ru,en}.py` — строки значка/подсказки (паритет).

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `.de` без expiry → значок «скрыт реестром», не «нет данных».
- Обычный TLD без данных (реальная ошибка) → прежнее «нет данных».
- Локали ru/en паритетны.

## Требования к тестам

- Unit на `format_list_row`/хелпер классификации (моки со `spec`).

## Definition of Done

- [ ] Значок + подсказка; классификация в util/конфиге
- [ ] **Полный `pytest` зелёный**; `ruff`/`black`/`mypy`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- TODO.md (tech-debt: DENIC)
