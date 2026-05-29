---
id: TASK-0013
title: Починить mypy type-narrowing в whois.py (красный CI с TASK-0005)
status: claimed
milestone: v0.9.0
adr: ""
area: code
depends_on: []
branch: task/0013-mypy-narrowing-whois
owner: claude
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0013 — mypy narrowing в whois.py (🟠 блокирует зелёный CI)

> 🟠 high — **приоритет: мержить ПЕРВЫМ**, до PR #7 (TASK-0009), иначе ни один
> PR не получит зелёный CI. Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.

## Цель

Шаг `mypy src` в CI снова зелёный: `src/bot/handlers/whois.py` проходит
`mypy --strict` без ошибок.

## Контекст / корень проблемы

Введено в TASK-0005. В `_send_whois_card` после проверки
`if result.error is not None or result.data is None: ... return` идут вызовы
`is_subdomain(...)` / `registrable_domain(...)`. Вызовы **сбрасывают**
mypy-narrowing атрибута `result.data`, поэтому строка
`lookup_domain = parent if is_sub else result.data.domain` даёт
`error: Item "None" of "... | None" has no attribute "domain"`.

`.github/workflows/ci.yml` содержит шаг `Mypy type check` (`uv run mypy src`),
значит **main красный по mypy с момента мержа TASK-0005** (в STATE отмечено
«зелёный CI не подтверждён»). Фикс был в отклонённом PR #5 (коммит `fc6bc96`),
но при разбиении PR #5 не получил своего таска и потерялся — заводим его
явно.

## Изменения по файлам

- `src/bot/handlers/whois.py`, функция `_send_whois_card`, сразу после
  раннего `return` по `result.data is None`:
  - Добавить `assert result.data is not None  # mypy narrowing` — этого
    достаточно, чтобы сузить тип. Эквивалентный/доп. вариант (как в `fc6bc96`)
    — заменить тернарник явным `if is_sub: lookup_domain = registrable_domain(domain_input)`
    `else: lookup_domain = result.data.domain`.
  - Не менять поведение — только удовлетворить narrowing.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- Поведение `/whois` для apex и поддомена не меняется (покрыто
  `tests/unit/test_subdomain_ux.py` / `test_formatters_whois_card.py`).

## Требования к тестам

- Отдельный тест не нужен; гарантия — зелёный `mypy src`. Проверить, что
  существующие тесты whois-карточки остаются зелёными.

## Definition of Done

- [ ] `mypy src` зелёный (особенно `whois.py`)
- [ ] `pytest` зелёный, `ruff` / `black --check` чисто
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `handoff.py validate` проходит; PR открыт, CI **зелёный**
- [ ] Смержен до того, как PR #7 (TASK-0009) ребейзится

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`
- Исходный фикс: коммит `fc6bc96` (ветка `task/0008-registrable-server-default-fix`)
- Связанные: TASK-0009 (CI smoke-test миграций — его CI зависит от этого фикса)
