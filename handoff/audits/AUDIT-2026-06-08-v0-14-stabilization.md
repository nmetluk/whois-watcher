# AUDIT-2026-06-08 — v0.14 стабилизация / тех-долг (ADR 041)

**Дата:** 2026-06-08 · **Объём:** стабилизационный релиз v0.14 —
FSM→RedisStorage (ADR 041), html.escape во всех нотификациях, DENIC-значок,
интеграционные тесты ARQ, доки. TASK-0049…0053
· **Аудитор:** архитектор (Cowork) · **Коммит:** `94e63be` (main)

> Комплексный аудит в отдельной сессии после раздела (конвенция CLAUDE.md).
> Серьёзность: 🔴 critical · 🟠 high · 🟡 medium · 🟢 low/info.

## Резюме

Стабилизационный релиз без новых пользовательских фич — гасит накопленный долг
v0.10–0.13. Качество исполнения высокое: FSM-state переехал в Redis с TTL и
namespacing (есть интеграционный тест persist-after-restart + expiry на
fakeredis), `html.escape` доведён до всех 9 нотификаторов с real-`t()`-тестом,
появились **настоящие** интеграционные тесты ARQ на Postgres+Redis (в CI),
написаны MIGRATIONS.md и нормы алертов. 🔴/🟠 находок нет — только 🟢 (унаследо-
ванный `getattr`-на-ORM и неподключённый settings-список). **Вердикт: GO** —
тег v0.14.0 можно ставить; 🟢 — опциональный follow-up.

**Верификация:** локальный `pytest` в песочнице недоступен (нет Python 3.11);
проверено чтением + отчёты исполнителя (973 теста зелёные) + интеграционные
тесты идут в CI. Перед тегом — подтвердить зелёный CI.

## Безопасность

- **html.escape (TASK-0049):** доведён до всех нотификаторов; приоритетные
  векторы закрыты — **SSL issuer** (attacker-controllable CN/O), DNS NS/A,
  registrar. Экранирование делается **до** `t()` (на значениях). Тест escape —
  через настоящий `t()` (метачар domain+registrar). ✅
- **FSM/Redis (ADR 041):** ключи неймспейснуты `DefaultKeyBuilder(prefix="fsm")`
  — не конфликтуют с ARQ (`arq:`). Чувствительного в Redis не пишется (только
  FSM-контекст флоу: домены/дни — не секреты). Логирования секретов нет. ✅
- Findings: нет.

## Архитектура

- **FSM→Redis** — единственное архитектурное изменение, по ADR 041: `storage`
  инъектируем в `create_dispatcher` (тесты → `MemoryStorage`, прод →
  `RedisStorage.from_url(settings.redis_url, state_ttl/data_ttl=redis_fsm_ttl)`).
  Чисто, без обхода конвенций. ✅
- **DENIC (TASK-0051):** классификация вынесена в `utils/domains.
  is_expiry_hidden_by_registry` (PSL-suffix, graceful), не хардкод в форматтере. ✅
- Findings:
  - 🟢 **`Settings.no_expiry_tlds` не подключён.** Поле объявлено
    (default `["de"]`), но форматтеры зовут `is_expiry_hidden_by_registry(domain)`
    без проброса settings → фактически используется дефолт
    `KNOWN_NO_EXPIRY_SUFFIXES={"de"}`. Две точки правды; settings-поле инертно.
    Либо прокинуть settings в форматтеры, либо убрать поле. → TASK-0056.

## Производительность

- FSM-операции — Redis (быстрее консистентны при нескольких воркерах);
  интеграционный бенчмарк scheduler упомянут как опциональный в 0052. ✅
- Findings: нет (бенчмарк 100K — опциональный пункт 0052, не блокер).

## Тесты

- **Интеграционные тесты ARQ (TASK-0052)** — реальные Postgres+Redis через
  pytest-docker (локально) / github-services (CI, оба сервиса уже в `ci.yml`);
  `check_subdomains`/`check_email_deep` гоняются по-настоящему (upsert,
  redis-guard, enqueue). Маркеры `integration`/`arq`. Это прямой ответ на риск
  «моки прячут дрейф». ✅
- **FSM-storage тест** на fakeredis: persist через «рестарт» + expiry по TTL. ✅
- **html.escape** — real-`t()`-тест (по правилу CLAUDE.md). ✅
- Полный прогон: по отчётам исполнителя 973 теста зелёные; mypy-долги починены
  по ходу. Подтвердить финально на CI.
- Findings: нет.

## Кроссплатформенность

- Служебка — `scripts/handoff.py` (stdlib). pytest-docker/fakeredis — dev-only. ✅

## Документация

- `MIGRATIONS.md` (single-head, down_revision от head, SQL-литералы/урок 0008,
  round-trip, чек-лист) + нормы дедупликации алертов ADR 019. ✅
- Локали ru/en — паритет новых ключей подтверждён. ✅
- Findings: нет.

## Anti-drift

- Новых `getattr(orm, "field", default)` v0.14 не вносит.
- 🟢 **Унаследованный `getattr`-на-ORM** в `format_email_deep`
  (`getattr(cache, "fetched_at", None)`, из 0041) + пре-существующие в
  `csv_io.py` и `whois_facade.py` (`cache.expires_at`). Не из v0.14, но это тот
  самый smell из CLAUDE.md. Рекомендуется точечный sweep на прямой
  типизированный доступ. → TASK-0056.

## Вердикт по тегу v0.14.0

**GO.** Стабилизационный релиз качественный, 🔴/🟠 нет. Тег v0.14.0 ставить
после подтверждения зелёного CI. 🟢-находки (TASK-0056: подключить/убрать
`no_expiry_tlds`, sweep `getattr`-на-ORM) — опциональный follow-up, не блокер.

## Заведённые задачи по итогам

- **TASK-0056** 🟢 (опц., v0.14.1) — подключить `Settings.no_expiry_tlds` в
  форматтеры (или убрать поле) + sweep `getattr`-на-ORM (`format_email_deep`,
  `csv_io`, `whois_facade`) на прямой типизированный доступ.
