# AUDIT-2026-05-31 — v0.12 мониторинг поддоменов (ADR 037+038)

**Дата:** 2026-05-31 · **Объём:** подсистема periodic subdomain monitoring
(ADR 037 enumeration + ADR 038 мониторинг/алерты), TASK-0027…0029
· **Аудитор:** архитектор (Cowork) · **Коммит:** `3fa2d12` (main)

> Комплексный аудит в отдельной сессии после завершения раздела v0.12
> (конвенция CLAUDE.md). Серьёзность: 🔴 critical · 🟠 high · 🟡 medium ·
> 🟢 low/info. Каждый 🔴/🟠 finding → отдельный таск в `handoff/tasks/`.

## Резюме

Рантайм-код подсистемы здоров: миграция чистая (единственный alembic-head,
валидные SQL-дефолты, обратима), нагрузка на crt.sh ограничена (floor 1д,
per-registrable кэш, redis-guard, batch 500, opt-in `default false`), diff
baseline-safe, чувствительное не логируется, горячий путь полностью async.
**Главный риск — не в коде, а в тестах:** ключевые инварианты ADR 038
(fan-out не дублирует/honoring toggle'ов и mute; success+diff→enqueue;
baseline не алертит на интеграционном уровне) фактически **не покрыты** —
ровно та слабость, что в прошлом дала три прод-бага (см. CLAUDE.md
«Защита от рассинхрона»). Вердикт: **fix-then-go** — закрыть два 🟠
тест-гэпа (малый объём) перед тегом v0.12.0; 🟡 — follow-up, не блокеры.

**Замечание о верификации:** локальный прогон `pytest`/`ruff`/`mypy` в
песочнице аудита невозможен (нет Python 3.11, venv собран под macOS, сеть
ограничена). Состояние тестов оценено чтением исходников + статусом CI
(зелёный по STATE.md). Перед тегом исполнитель обязан подтвердить полный
зелёный прогон на CI.

## Безопасность

Чисто. Замечаний-блокеров нет.

- **Логирование (ADR 019):** `check_subdomains`, `subdomain_scheduler_tick`,
  `notify_subdomain_changes`, `client.py` логируют только `registrable_domain`
  (публичные данные), статусы и числа. Ни `BOT_TOKEN`, ни контактов WHOIS,
  ни IP, ни заметок пользователей. ✅
- **Fan-out не течёт чужие домены:** `notify_subdomain_changes` шлёт каждому
  подписчику только событие по его registrable; текст не содержит данных
  других пользователей. ✅
- **Нагрузка на crt.sh ограничена:** opt-in `track_subdomains default false`;
  scheduler floor 1 день, adaptive-backoff при фейлах (1ч → 1д при ≥3),
  кэш per-registrable (один запрос обслуживает всех подписчиков), redis-guard
  `subdomain_check_in_progress:<reg>` (TTL 60с) против дублей, `BATCH_LIMIT=500`
  на тик. Клиент: `ClientTimeout(total=45)`, обработка 429/4xx/сетевых без
  исключений наружу. ✅
- **Findings:**
  - 🟢 `notify_subdomain_changes` интерполирует `registrable_domain` и имена
    поддоменов в сообщение с `ParseMode.HTML` **без `html.escape`**
    (строки `f"<b>{registrable_domain}</b>"`, `f"  🆕 {subdomain}"`).
    Практически безопасно: парсер (`parse_crtsh_response`) прогоняет каждое имя
    через `idna.encode(...).decode("ascii")` → на выходе только ASCII
    `[a-z0-9.-]`, HTML-метасимволов быть не может; `registrable_domain`
    приходит из tldextract (punycode). Это к тому же сложившаяся конвенция
    проекта (whois/ssl-нотификации тоже не экранируют). Рекомендация —
    defense-in-depth: добавить `html.escape` (дёшево, снимает зависимость
    безопасности от инварианта нормализации).

## Архитектура

Соответствует ADR 037/038. Подсистема параллельна SSL/DNS, как и задумано.

- **Параллельность:** своя таблица `subdomain_enum_cache` (PK registrable),
  свой `subdomain_scheduler_tick` (cron каждые 5 мин, по образцу
  `ssl_scheduler_tick`), своя ARQ-задача `check_subdomains` + fan-out
  `notify_subdomain_changes`. Доступ к БД только через репозитории. ✅
- **Реконсиляция shared-cache vs per-user интервал:** `get_min_check_interval`
  берёт `COALESCE(ud.subdomain_check_interval_override,
  u.subdomain_check_interval_days)` среди подписчиков `track_subdomains=true
  AND is_muted=false`, возвращает `max(1, min(...))` (floor 1д), дефолт 7 при
  отсутствии подписчиков. Самый «частый» подписчик задаёт темп — точно по
  ADR 038. ✅
- **Baseline:** `compute_subdomain_diff(old=None)` → пустой diff;
  `check_subdomains` берёт `old_subdomains = old_cache.subdomains if old_cache
  else None` ДО upsert и не enqueue'ит notify на первой проверке. ✅
- **Bootstrap идемпотентен:** `INSERT … ON CONFLICT (registrable_domain)
  DO NOTHING`, заглушка `next_check_at=now()`. ✅
- **Findings:**
  - 🟡 **Дедуп fan-out зависит от порядка строк и может молча игнорировать
    per-domain toggle'ы.** `get_subscribers_by_registrable` возвращает **все**
    `UserDomain`-строки registrable; цикл дедупит по `user_id`. Если у одного
    пользователя под одним registrable несколько отслеживаемых строк (apex
    `example.com` + поддомен `www.example.com`, оба `track_subdomains=true`) с
    **разными** `notify_subdomain_new/removed`, применяются toggle'ы лишь
    **первой** успешно отправленной строки, остальные строки этого юзера
    скипаются. Инвариант ADR 038 «honoring per-domain toggle'ов» нарушается в
    этом сценарии. → **TASK-0035** (агрегировать toggle'ы по пользователю:
    `OR` по строкам, либо явно решить семантику per-registrable).

## Производительность

Горячий путь async, индексы на месте, кэш-инварианты соблюдены.

- **Индекс:** `ix_subdomain_enum_cache_next_check_at` присутствует;
  `get_due_for_check` сортирует/фильтрует по `next_check_at` → индекс
  используется. ✅
- **Async:** sync I/O / `time.sleep` / блокировок loop в подсистеме нет;
  crt.sh через `aiohttp`, БД через async-сессии. ✅
- **Findings:**
  - 🟡 **N+1 в fan-out.** `notify_subdomain_changes` в цикле по подписчикам
    зовёт `user_repo.get_by_ids([user_id])` (один запрос на подписчика) и
    создаёт `NotificationRepository(session)` внутри цикла. Для registrable с
    N подписчиками — N+1 запросов к БД. Объём низкий (opt-in `default false`),
    но фикс тривиален: собрать `user_id` всех подписчиков и сделать один
    `get_by_ids(ids)` + map; репозиторий вынести из цикла. → **TASK-0035**
    (объединено с дедуп-фиксом — тот же файл/функция).

## Тесты

Чистые функции покрыты хорошо; интеграционные «склейки» ADR 038 — нет.
Это прямой конфликт с anti-drift-конвенцией (слабый тест маскирует дрейф).

- **Хорошо:** `test_subdomain_diff.py` (9 кейсов: baseline/new/removed/both/
  порядок/дубли/пустые), `test_subdomains_scheduler.py` (13: TTL-ветки, floor,
  tz-guard, fail-cap), `test_subdomain_enum_model.py`/`test_user_domain_model.py`
  (поля/дефолты), `test_subdomains_parser.py` (dedup/wildcard/IDN). ✅
- **Anti-drift:** в `test_check_subdomains_task.py` старый кэш мокается со
  `MagicMock(spec=SubdomainEnumCache)` — корректно. ✅
- **Findings:**
  - 🟠 **Fan-out `notify_subdomain_changes` практически не покрыт.**
    `test_notify_subdomain_changes.py` содержит только (1) пустой diff → ранний
    return и (2) «функция вызываема», который **глотает исключения** и
    утверждает лишь, что это ошибка БД-подключения. Не покрыты ключевые
    инварианты ADR 038: дедуп одного пользователя, гашение `is_muted`,
    honoring `notify_subdomain_new/removed`, skip `is_blocked`, обрезка `[:5]`+
    `and_more`, запись в журнал. → **TASK-0033**.
  - 🟠 **Success+diff→enqueue путь `check_subdomains` не покрыт.** Тесты
    проверяют только off-by-one на failure-ветке. Нет теста, что при успехе с
    изменениями enqueue'ится `notify_subdomain_changes` с корректным payload
    (`{"new":…,"removed":…}`), а на baseline (`old_cache=None`) — **не**
    enqueue'ится. Это «склейка», где дрейф полей/сигнатуры пройдёт незаметно. →
    **TASK-0034**.
  - 🟡 **Фильтрующие инварианты репозитория не проверены.**
    `test_subdomain_enum_cache_repo.py::test_get_due_for_check_returns_sequence`
    утверждает лишь тип результата; фильтр «`track_subdomains=true AND
    is_muted=false` И `next_check_at<=now()`» в `get_due_for_check` и логика
    `get_min_check_interval` не проверены данными (нужен Postgres-интеграционный
    тест). Интеграционных тестов подсистемы нет. → покрыть в рамках TASK-0033/34
    или отдельным интеграционным кейсом (необязательно для тега).
  - 🟢 UX ADR 038 (toggle'ы `⚙️ Уведомления`, FSM интервала) тестами не
    покрыт — `test_subdomain_ux.py` про PSL/`↳`, не про новый конфигуратор.
    UX-баги ловятся ручным тестом в Telegram (конвенция CLAUDE.md), но
    smoke-тест на рендер клавиатуры/локали был бы полезен.

## Кроссплатформенность

- Служебка — `scripts/handoff.py` (stdlib). Подсистема путей ОС не трогает,
  хардкода разделителей нет, всё через БД/Redis/HTTP. ✅
- 🟢 FSM-интервала валидирует нижнюю границу (`interval < 1` → invalid), но
  **верхней нет**: ввод вроде `99999999999` пройдёт `int()` и упрётся в DB при
  записи (`Integer` = int4, max 2147483647 → ошибка persist). Добавить разумный
  кап (напр. ≤ 365) в `on_subdomain_interval_input`. (low)

## Документация

- ADR 037/038 в `docs/decisions.md` — актуальны, совпадают с кодом.
  `STATE.md` отражает влитый стек v0.12 и статус «осталось TASK-0030 →
  v0.12.0». CHANGELOG `Unreleased` готов под тег. ✅
- 🟢 Housekeeping (не в git, локально): пустые каталоги `src 2/`, `tests 2/` в
  корне рабочей копии — артефакты file-sync (untracked, нулевые), на репозиторий
  не влияют. Удалить локально.

## Вердикт по тегу v0.12.0

**FIX-THEN-GO.** Рантайм-код безопасен и нагрузочно-корректен — для **показа
MVP** подсистему можно демонстрировать как есть. Но **тег v0.12.0 не ставить**,
пока не закрыты 🟠 TASK-0033 и TASK-0034: тест-гэпы на fan-out и
success→enqueue нарушают собственную anti-drift-конвенцию проекта (которая
появилась после трёх прод-багов от слабых тестов). Объём фиксов малый.
🟡 TASK-0035 (N+1 + дедуп-toggle) и 🟢-замечания (html.escape, кап интервала) —
follow-up, можно после тега.

## Заведённые задачи по итогам

- **TASK-0033** 🟠 — реальные тесты fan-out `notify_subdomain_changes`
  (дедуп/mute/toggle'ы/blocked/обрезка/журнал).
- **TASK-0034** 🟠 — тесты success+diff→enqueue и baseline-no-enqueue в
  `check_subdomains`.
- **TASK-0035** 🟡 — fan-out: устранить N+1 (`get_by_ids` батчем, репозиторий
  из цикла) + агрегировать per-domain toggle'ы по пользователю (дедуп
  ordering-independent).
