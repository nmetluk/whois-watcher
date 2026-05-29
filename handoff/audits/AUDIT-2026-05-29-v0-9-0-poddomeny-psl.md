# AUDIT-2026-05-29 — v0.9.0 поддомены/PSL

**Дата:** 2026-05-29 · **Объём:** v0.9.0 (TASK-0002…0005) — PSL, схема поддоменов, WHOIS-роутинг, UX
· **Аудитор:** claude-opus-4-7 · **Коммит:** `e78793b`

> Комплексный аудит выполняется в отдельной сессии после завершения
> крупного раздела. Каждый finding → новая задача в `handoff/tasks/`.
> Серьёзность: 🔴 critical · 🟠 high · 🟡 medium · 🟢 low/info.

## Резюме

Раздел v0.9.0 (поддомены/PSL) реализован в соответствии с ADR 035.
WHOIS keyed по registrable-домену, DNS/SSL — по поддомену, PSL в оффлайн-режиме.
Тесты покрывают edge cases (IDN, многоуровневые зоны), код проходит ruff/mypy/pytest.
Найден один **medium** finding по схеме (рассинхрон server_default в миграции/модели).
Рекомендация: **fix-then-go** — исправить finding до релиза v0.9.0.

## Безопасность

- **Supply-chain:** Новая зависимость `tldextract==5.3.1` из PyPI, hash проверен в uv.lock.
- **Оффлайн-режим:** `suffix_list_urls=()` отключает сетевой автофетч, bundled snapshot используется.
- **Private domains:** `include_psl_private_domains=False` — blogspot.com и пр. не считаются суффиксами.
- **Логирование:** WHOIS raw_data, контакты, registrant данные в логи не попадают.
- **Валидация:** Публичные суффиксы (co.uk, org.uk, ru) отклоняются `is_public_suffix_only()`.

Findings:
- 🟢 **low/info:** `cache_dir` по умолчанию в tldextract (homedir) — в headless/Docker без homedir
  может быть issue, но bundled snapshot работает без cache_dir. Не критично для v0.9.0.

## Архитектура

- **ADR 035 соблюдён:** WHOIS-джойны переключены на `UserDomain.registrable_domain`,
  DNS/SSL остаются keyed по `domain` (поддомену). Несколько поддоменов одного родителя
  делят один `whois_cache`-row (ADR 006 сохранён).
- **Модульность:** Чистый модуль `src/utils/domains.py` без сетевых вызовов, функции
  `registrable_domain()`, `is_subdomain()`, `is_public_suffix_only()` покрыты тестами.
- **Репозитории:** WHOIS-джойны (`list_with_whois`, `export_csv`, `list_with_whois_filtered`)
  используют `UserDomain.registrable_domain`.

Findings:
- 🟡 **medium:** Рассинхрон миграции/модели на `registrable_domain`:
  - Миграция `20260529_registrable_domain`: `server_default=sa.text("")`
  - Модель `UserDomain`: `registrable_domain: Mapped[str] = mapped_column(Text, nullable=False)`
  - **Проблема:** После того как TASK-0005 начал заполнять поле при вставке, server_default
    в БД остаётся. Если вставка пойдёт мимо кода (raw SQL, миграция), БД может создать строку
    с пустым registrable_domain, нарушив NOT NULL constraint на уровне приложения.
  - **Предлагаемый таск:** TASK-0008 — убрать server_default из миграции отдельной миграцией.

## Производительность

- **Парс домена:** `tldextract.TLDExtract(suffix_list_urls=())` — синхронный, без сети,
  только bundled PSL snapshot. Не блокирует event loop.
- **WHOIS-джойны:** Все используют `outerjoin(WhoisCache.domain == UserDomain.registrable_domain)`
  в одном запросе — нет N+1.
- **Индекс:** `ix_user_domains_registrable_domain` создан, используется для WHOIS-джойнов.
- **Кэш:** Общий `whois_cache`-row на родителя (ADR 006) — несколько поддоменов одного
  registrable-домена не плодят дубликаты в кэше.

Findings: нет.

## Тесты

- **Edge cases:** `test_utils_domains.py` покрывает IDN (кириллица), многоуровневые зоны
  (co.uk, org.uk), публичные суффиксы, поддомены всех уровней.
- **Offline mode:** `TestOfflineMode` проверяет отсутствие сетевых вызовов и использование
  bundled snapshot.
- **UX:** `test_subdomain_ux.py` проверяет баннер поддомена в /whois, пометку ↳ в /list.
- **Результат:** 74 passed, 0 failed.

Findings: нет.

## Кроссплатформенность

- **Пути:** `cache_dir=None` используется по умолчанию — tldextract сам находит bundled
  snapshot в установленном пакете (кроссплатформенно).
- **Разделители:** Никаких хардкодов путей/разделителей в `src/utils/domains.py`.
- **Инициализация:** TLDExtract создаётся на import, без сети — не зависит от ОС.

Findings: нет.

## Documentation

- **ADR 035:** Актуален коду — описывает PSL, registrable_domain, is_subdomain, оффлайн-режим.
- **STATE.md:** Обновлён 2026-05-29, описывает состояние v0.9.0 и отмечает долг на server_default.
- **CLAUDE.md:** Раздел "Стиль работы" не изменился, новые соглашения не добавлены — корректно.
- **SESSION_LOG:** `docs/sessions/2026-05-29_task-0005_subdomain_ux.md` описывает проделанную работу.

Findings: нет.

## Заведённые задачи по итогам

- [TASK-0008](../tasks/TASK-0008-fix-registrable-migration.md) — починить
  миграцию registrable_domain (🔴 эскалировано — см. дополнение ниже).

---

**Вердикт:** Fix-then-go — исправить TASK-0008, затем тег v0.9.0.

---

## Дополнение — повторный аудит 2026-05-29 (эскалация finding'а)

**Аудитор:** архитектор (Cowork) · **Коммит:** `9d51960` · сделано после
первичного аудита по запросу владельца.

Первичный аудит расценил проблему миграции как 🟡 **medium** («косметический
рассинхрон `server_default`»). Повторная проверка через offline-рендер
alembic показала, что это **🔴 critical: миграция вообще не применяется на
PostgreSQL.** Реальный SQL, отправляемый в БД:

```sql
ALTER TABLE user_domains ADD COLUMN registrable_domain TEXT DEFAULT  NOT NULL;   -- пустой DEFAULT
ALTER TABLE user_domains ADD COLUMN is_subdomain BOOLEAN DEFAULT false NOT NULL; -- корректно (контраст)
UPDATE user_domains SET registrable_domain = domain WHERE registrable_domain = "";
```

1. `server_default=sa.text("")` → `DEFAULT  NOT NULL` (пустая клауза) —
   невалидный DDL для Postgres. Соседний `is_subdomain` с `sa.text("false")`
   рендерится корректно (`DEFAULT false`) — наглядный контраст.
2. Backfill `WHERE registrable_domain = ""` — двойные кавычки в Postgres это
   **идентификатор нулевой длины** → `ERROR: zero-length delimited identifier`.

Предложенный первичным аудитом фикс (отдельной миграцией снять
`server_default`) **не решает проблему** — он надстраивается над миграцией,
которая не применяется. Корректный фикс — починить исходную миграцию
in-place (`''` вместо `""`, валидный default + снятие после backfill).

**Почему не поймано:** миграции не покрыты тестами (`conftest.py` к реальной
БД не подключается), sqlite молча принимает `""` как строку и маскирует баг.

**Скорректированный вердикт:** по-прежнему **fix-then-go**, но 🔴 — НЕ тегать
v0.9.0 до починки миграции. Дополнительные findings (повторный аудит):

- 🔴 **TASK-0008** (эскалирован) — починить миграцию registrable_domain.
- 🟠 **TASK-0009** — smoke-test Alembic-миграций на Postgres в CI (корневая
  причина, что баг прошёл «зелёный» CI; сервис postgres в `ci.yml` уже есть).
- 🟡🟢 **TASK-0010** — tldextract: явный `cache_dir=None` (дефолт — реальный
  путь, НЕ None, как ошибочно гласят код и оба аудита) + реальный no-network
  тест (текущий сеть не блокирует).
- 🟢 **TASK-0011** — доки: tldextract/PSL в `CLAUDE.md` и `architecture.md`.
- (forward) **TASK-0012** — дизайн ADR 036, domain intelligence v0.10.
