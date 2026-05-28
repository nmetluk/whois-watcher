# Сессия 2026-05-29 — TASK-0004 (WHOIS-роутинг на родителя)

**Задача:** TASK-0004 — Маршрутизация WHOIS на registrable-родителя (подэтап 2c)
**Ветка:** task/0004-whois-parent-routing
**Выполнено:** полный цикл разработки, тесты зелёные

## Цель

WHOIS-проверки и постановка задач идут по registrable-домену (eTLD+1),
а не по полному поддомену. Один `whois_cache`-row на родителя обслуживает
все его поддомены.

## Реализация

### Изменённые файлы

1. **`src/services/domains.py`**
   - Добавлен импорт `registrable_domain as get_registrable_domain` из `src.utils.domains`
   - `add_for_user`: WHOIS-операции (кэш, enqueue_check) работают по registrable-домену
   - `lookup_for_user`: WHOIS-запрос идёт по registrable-домену
   - В `user_domains` по-прежнему пишется исходный домен (поддомен или apex)

2. **`src/services/whois_facade.py`**
   - Без изменений (работает с переданным domain, теперь это registrable)
   - `_cache_to_data` возвращает данные для переданного домена

3. **`src/whois/scheduler.py`**
   - Без изменений (чистые функции для расчёта TTL, не работают с доменами)

4. **`src/dns_monitor/scheduler.py`, `src/ssl/scheduler.py`**
   - Без изменений (DNS/SSL планирование по поддомену, как и требовалось)

### Инварианты (защищены тестами)

- `/whois a.pinbetting.ru` использует кэш родителя `pinbetting.ru`
- `enqueue_check` для поддомена ставит проверку по registrable
- Два поддомена одного родителя инициируют одну WHOIS-проверку
- DNS/SSL поддомена планируются по самому поддомену (регресс-тест зелёный)

### Проверки

- `ruff check src/` — OK
- `black --check src/` — OK
- `mypy src/` — OK
- `pytest` — 687 passed
- Per-session отчёт создан

## Definition of Done

- [x] WHOIS facade/scheduler работают по registrable
- [x] DNS/SSL планирование по поддомену не задето (регресс-тест зелёный)
- [x] `pytest` полный прогон; `ruff`/`black`/`mypy` чисто
- [x] Per-session отчёт в `docs/sessions/`
- [ ] `python scripts/handoff.py validate` (следующий шаг)
- [ ] PR открыт (следующий шаг)

## Следующие шаги

- Открыть PR: `git push origin task/0004-whois-parent-routing`
- После мержа обновить `handoff/TASK-0004-*.md` (статус, PR, session)
