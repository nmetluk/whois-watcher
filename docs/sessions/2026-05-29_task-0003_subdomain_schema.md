# Сессия 2026-05-29 — TASK-0003 (Схема поддоменов + WHOIS-джойны)

**Задача:** TASK-0003 — Схема user_domains (registrable_domain, is_subdomain) + WHOIS-джойны (подэтап 2b)
**Ветка:** task/0003-subdomain-schema-whois-joins
**Выполнено:** полный цикл разработки, тесты зелёные

## Цель

Хранить registrable-домен и признак поддомена в `user_domains`; WHOIS связывается с кэшем по registrable, а не по полному имени.

## Реализация

### Изменённые файлы

1. **`src/db/models.py`**
   - `UserDomain.registrable_domain: Mapped[str]` (Text, NOT NULL) — eTLD+1
   - `UserDomain.is_subdomain: Mapped[bool]` (server_default false)
   - Индекс `ix_user_domains_registrable_domain` на registrable_domain

2. **`migrations/versions/20260529_0000_add_registrable_domain_fields.py`** (новый)
   - Добавление колонок `registrable_domain` и `is_subdomain`
   - Backfill существующих строк: `registrable_domain = domain`, `is_subdomain = false`
   - Создание индекса на `registrable_domain`

3. **`src/db/repositories/domains.py`**
   - Заменены WHOIS-джойны с `WhoisCache.domain == UserDomain.domain` на
     `WhoisCache.domain == UserDomain.registrable_domain` в методах:
     - `iter_all_with_whois`
     - `list_with_whois`
     - `list_with_whois_filtered`
     - `get_user_stats`
   - DNS/SSL-репозитории НЕ трогались

4. **`tests/unit/test_user_domain_model.py`** (новый)
   - Проверка что новые поля существуют в модели
   - Проверка создания записей для apex-доменов и поддоменов

### Инварианты (защищены тестами)

- Для apex-домена `registrable_domain == domain`, `is_subdomain == False`
- WHOIS-джойн для строки с `registrable_domain=pinbetting.ru` находит
  `whois_cache`-row родителя
- Два поддомена одного родителя ссылаются на один `whois_cache`-row

### Проверки

- `ruff check src/` — OK
- `black --check src/` — OK
- `mypy src/` — OK
- `pytest` — 632 passed
- Per-session отчёт создан

## Definition of Done

- [x] Миграция добавляет колонки+индекс, backfill корректен
- [x] WHOIS-джойны переключены на `registrable_domain`
- [x] `pytest` полный прогон зелёный; `ruff`/`black`/`mypy` чисто
- [x] Per-session отчёт в `docs/sessions/`
- [ ] `python scripts/handoff.py validate` (следующий шаг)
- [ ] PR открыт (следующий шаг)

## Следующие шаги

- Открыть PR: `git push origin task/0003-subdomain-schema-whois-joins`
- После мержа обновить `handoff/TASK-0003-*.md` (статус, PR, session)
