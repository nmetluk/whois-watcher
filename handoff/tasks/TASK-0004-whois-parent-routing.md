---
id: TASK-0004
title: Маршрутизация WHOIS на registrable-родителя (facade/scheduler)
status: open
milestone: v0.9.0
adr: 035
area: code
depends_on: [TASK-0003]
branch: ""
owner: ""
session: ""
pr: ""
created: 2026-05-29
---

# TASK-0004 — WHOIS-роутинг на родителя (подэтап 2c)

> Самодостаточно. Процесс — `handoff/README.md`. Дизайн — ADR 035.
> Опирается на схему из TASK-0003.

## Цель

WHOIS-проверки и постановка задач идут по registrable-домену
(eTLD+1), а не по полному поддомену. Один `whois_cache`-row на родителя
обслуживает все его поддомены.

## Контекст / корень проблемы

После TASK-0003 схема знает родителя, но фасад/планировщик ещё ставят
проверки и пишут кэш по `UserDomain.domain`. Для поддоменов это создаст
лишние/пустые `whois_cache`-строки и ложную «свободу».

## Изменения по файлам

- `src/services/whois_facade.py` — `get_or_fetch` / `enqueue_check` и
  конвертеры работают по registrable. Точка входа из хэндлеров
  (`/whois`, `/add`) должна вычислять registrable через
  `utils.domains.registrable_domain` и передавать его в фасад.
- `src/services/domains.py` — `add_for_user` / `lookup_for_user`:
  WHOIS-операции по registrable; `user_domains.domain` хранит исходный
  ввод (поддомен), `registrable_domain` — родителя.
- `src/whois/scheduler.py` — планирование `next_check_at` по записям
  `whois_cache` (они уже keyed по registrable) — убедиться, что нет
  планирования по полному поддомену.
- DNS/SSL планировщики (`dns_scheduler`, `ssl_scheduler`) — по-прежнему
  по `UserDomain.domain` (поддомену). Не менять.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- `/whois a.pinbetting.ru` при занятом `pinbetting.ru` использует
  `whois_cache` родителя, «свободен» не показывается.
- `enqueue_check` для поддомена ставит проверку по `pinbetting.ru`, не по
  `a.pinbetting.ru`.
- Два поддомена одного родителя инициируют максимум одну WHOIS-проверку
  родителя (дедуп через общий кэш).
- DNS/SSL поддомена планируются по самому поддомену (регресс-тест).

## Требования к тестам

- `tests/unit/` на фасад/сервис: registrable-роутинг, отсутствие
  дублирующих whois_cache-строк для поддоменов.

## Definition of Done

- [ ] WHOIS facade/scheduler работают по registrable
- [ ] DNS/SSL планирование по поддомену не задето (регресс-тест зелёный)
- [ ] `pytest` полный прогон; `ruff`/`black`/`mypy` чисто
- [ ] Per-session отчёт в `docs/sessions/`, вписан в `session:`
- [ ] `python scripts/handoff.py validate` проходит
- [ ] PR открыт, CI зелёный

## Ссылки

- ADR 035, `PLAN_subdomains_wishlist.md` (Этап 2, 2c)
- Зависит от: TASK-0003
