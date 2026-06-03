# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.15.1] — 2026-06-09

Хотфикс v0.15.1: доставка on-demand результатов и глубокого e-mail (ADR 040).

### Fixed

- **On-demand кнопки (Поддомены, Глубокий e-mail) досылают результат** без повторного нажатия (TASK-0075). Кнопки на карточке /whois теперь передают deliver-контекст в ARQ-задачи; по завершении задачи результат отправляется в чат пользователя.
- **Первый /whois доставляет MX/SSL/DNS по готовности** (TASK-0076). Фоновые проверки (check_ssl/dns/email_intel) теперь досылают обновлённые блоки в чат (follow-up сообщения) вместо ожидания повторного запроса. Тексты доставки локализованы (ru/en) через `tasks.deliver.*`.
- **Диагностика глубокого e-mail** (TASK-0077). Добавлены диагностические логи (`mx_hosts`, старт сбора) и интеграционный тест на google.com для поимки причины пустого разбора по прод-логам. Системный DNS-резолвер оставлен как в `email_intel` (форс публичных nameservers откатан — риск при egress-ограничениях хоста).

### Internal

- Обновлены handoff-таски 0075–0078 (hotfix-стек v0.15.1).
- Слитые ветки: task/0075-fix-ondemand-button-delivery, task/0076-fix-whois-card-mx-freshness, task/0077-fix-deep-email-empty.
- Архитекторский follow-up: локализация доставки 0076, откат рискованного nameservers-хардкода 0077.

## [0.15.0] — 2026-06-09

Админ/ops-слой для эксплуатации прода (ADR 042): бекапы, отчёты, аудит-лог.
Без изменений пользовательского поведения.

### Added

- **Ежечасные бекапы Postgres.** ARQ cron `backup_postgres`: `pg_dump -Fc` →
  `BACKUP_DIR`, ротация (храним `BACKUP_KEEP=36` свежих), проверка валидности
  (`pg_restore --list`), статус в Redis `ops:last_backup`. Redis не бекапим
  (регенерируем).
- **Ежечасный ops-отчёт** в админ-канал: статистика за час (активные/lookups/
  новые домены/ошибки) + подтверждение успешного бекапа (или ❌ FAILED).
- **Дневной графический отчёт 21:00 МСК** (matplotlib): графики использования
  за ~14 дней. Текстовая сводка 06:00 сохранена.
- **Аудит-лог** (`audit_log`, retention 90 дней): записи об инцидентах для
  разбора нештатных ситуаций (фейлы задач, rate-limit, admin-действия,
  webhook/startup) через best-effort helper `audit()`.

### Internal

- Новая зависимость: `matplotlib` (backend Agg, headless). Dev:
  `postgresql-client-16` в worker-образе.
- Миграция `20260609_audit_log` (single-head, обратима).
- Новые настройки: `BACKUP_DIR`, `BACKUP_KEEP`, `BACKUP_MIN_BYTES`,
  `AUDIT_RETENTION_DAYS`. Новый docker-том `ww_backups` (worker/scheduler).

### Deploy

- ⚠️ Пересобрать образ (добавлен `postgresql-client-16`), создать том
  `ww_backups`, выставить `BACKUP_*`/`AUDIT_RETENTION_DAYS`.

## [0.14.0] — 2026-06-08

Стабилизационный релиз — погашение тех-долга, без новых пользовательских фич
(ADR 041). Все блокеры аудита v0.14 закрыты (TASK-0049…0054).

### Changed

- **FSM-состояния переехали в Redis** (`MemoryStorage` → `RedisStorage`,
  ADR 041): контекст диалогов (`/whois`-аргументы, редактирование дней/SSL-дней/
  интервала поддоменов, поиск по списку, настройки, скачивание) **переживает
  рестарт бота** и истекает по TTL (`REDIS_FSM_TTL`, дефолт 300 c). Тот же
  Redis, что ARQ; ключи неймспейснуты (`fsm:`).

### Security

- **`html.escape` во всех change-нотификациях** (whois/dns/ssl/email/problem/
  wishlist/reminders) — defense-in-depth. Особо: экранируется **issuer
  SSL-сертификата** (CN/O контролируются тем, кто выпустил сертификат), NS-записи,
  сырые email-политики, registrar. Раньше экранирование было только в
  subdomain-уведомлениях (TASK-0037).

### Added

- **Значок «🔒 expiry скрыт реестром»** в `/list` и карточке `/whois` для
  реестров без публикации даты истечения (DENIC `.de` и подобные) — вместо
  вводящего в заблуждение «нет данных». Список TLD конфигурируем.
- **Интеграционные тесты ARQ** на реальных Postgres+Redis (pytest-docker
  локально / сервисы в CI): `check_subdomains`, `check_email_deep` —
  UPSERT-семантика, redis-guard, enqueue (ловят дрейф, который моки скрывают).
- Документация: `MIGRATIONS.md` (гайд по миграциям) + нормы дедупликации
  админ-алертов (ADR 019).

### Internal

- Новые dev-зависимости: `fakeredis`, `pytest-docker`; `aiogram[redis]`.
- Конвенция CLAUDE.md: хотя бы один рендер-тест форматтера через настоящий
  `t()` (урок KeyError в deep-email).

## [0.13.0] — 2026-06-03

Deep email (SPF include-резолвинг + лимит lookups, MTA-STS, TLS-RPT, DANE/TLSA, BIMI) + on-demand deep-views в карточке `/whois` (ADR 040). Кнопки «✉️ Глубокий e-mail» и «🛰 Поддомены». Инлайн MX + статус SPF/DMARC. Фикс свежести карточки. Anti-SSRF + строгий TXT-матч для MTA-STS (TASK-0047). Все блокеры аудита v0.13 закрыты (0038–0042, 0045–0047).

### Added — Deep email + on-demand views (ADR 040)

- **Инлайн MX + статус** в первом сообщении `/whois`: MX-хосты + краткий режим SPF (с include) + политика DMARC (1–2 строки). «Здоровье почты с одного взгляда».
- **Кнопка «✉️ Глубокий e-mail»**: on-demand глубокий разбор (ARQ + кэш 10 мин). SPF с рекурсивным include/redirect (лимит 10 lookups по RFC 7208, флаг exceeds, перечень sources); MTA-STS (TXT + policy fetch: mode, mx[], max_age); TLS-RPT (rua); DANE/TLSA (top-N MX); BIMI (logo/VMC). Отдельное сообщение-карта почтовой зрелости. Graceful degradation на всех этапах.
- **Кнопка «🛰 Поддомены»**: on-demand, переиспользует существующий поток enumeration (ADR 037/crt.sh), без дублирования. Показ списка + opt-in «Отслеживать».
- **Фикс свежести**: пустой кэш SSL/DNS/email-intel/deep → плейсхолдер «⏳ собираю SSL/DNS/MX…» + явный хинт «🔄 Обновить» (вместо пустоты).
- **MTA-STS hardening (TASK-0047)**: строгий префиксный матч `v=STSv1` (без ложных срабатываний на подстроку «sts»); anti-SSRF — резолв A/AAAA + отсечение приватных/loopback/link-local/ULA/reserved/multicast IP **до** HTTPS GET; защита от DNS-rebinding (кастомный `_SafeMtaStsResolver` + `TCPConnector`, пин IP, `close()`).

### Internal

- Новые: `src/email_intel/{deep_client,deep_parser,deep_types}.py`; ARQ-задача `check_email_deep` (on-demand, redis-guard); таблица `email_deep_cache` (TASK-0039, миграция 20260531).
- Форматтер `format_email_deep` (с real-`t()` тестами, html.escape, exceeds).
- 22+ юнит-теста deep-парсеров/коллекторов (SPF циклы/лимит, MTA-STS режимы, graceful); тесты кнопок + freshness (TASK-0046); anti-drift (убраны `getattr` на ORM, TASK-0045).
- Моки со `spec`/`autospec`; правило CLAUDE.md о real-`t()` в рендер-тестах форматтеров (урок KeyError 'exceeds' в 0046).
- Alembic-head: `20260531_0000_add_email_deep_cache_table` (single-head, обратимая).

## [0.12.0] — 2026-05-31

Periodic subdomain monitoring (ADR 038) поверх enumeration (ADR 037). Все блокеры аудита v0.12 закрыты (TASK-0033–0037).

### Added — Мониторинг поддоменов (ADR 038)

- **Opt-in мониторинг** `track_subdomains` (per-domain toggle в ⚙️ Уведомления, default=false) + глобальный `User.subdomain_check_interval_days` (default 7) с per-domain override (`subdomain_check_interval_override`).
- **Scheduler** `subdomain_scheduler_tick` (cron каждые 5 мин, floor 1 день, выбирает минимальный интервал среди активных подписчиков `track_subdomains=true AND is_muted=false`).
- **Diff + уведомления**: `compute_subdomain_diff` (baseline-safe на `old=None`), fan-out `notify_subdomain_changes` (сигналы 🆕 new / ➖ removed, honoring `notify_subdomain_*` toggle'ы, `is_muted`, `is_blocked`, дедуп по user, обрезка 5 + "и ещё N", запись в журнал).
- **UX**: в конфигураторе `/whois` → ⚙️ Уведомления появилась секция поддоменов + отдельная FSM для редактирования интервала (1–365 дней).
- **Hardening по итогам аудита (TASK-0030)**:
  - Устранён N+1 в fan-out + ordering-independent агрегация toggle'ов по пользователю (TASK-0035, PR #25).
  - `html.escape` на `registrable_domain` и имена поддоменов в нотификациях (defense-in-depth, TASK-0037).
  - Верхний кап интервала в FSM через новое поле `Limits.max_subdomain_check_interval_days` (default 365, env-overridable) + dedicated unit-тест (TASK-0037, PR #26).
  - Полное покрытие fan-out инвариантов и success+enqueue пути (TASK-0033/0034, PR #23/#24) — моки со `spec`.

### Internal

- Новые ARQ-задачи: `subdomain_scheduler_tick`, `check_subdomains`, `notify_subdomain_changes`.
- Репозиторий `SubdomainEnumCacheRepository` + методы `get_due_for_check`, `get_min_check_interval`.
- Тесты: 923+ (рост за счёт 0033–0037), все с `MagicMock(spec=...)`.
- Alembic-head: `20260530_subdomain_monitor` (single-head, обратимая).

## [0.11.1] — 2026-05-30

Wishlist как независимый список (ADR 039, TASK-0031/0032).

### Added — Wishlist independent (ADR 039)

- **Независимые списки**: `/list` (tracked) и `/wishlist` (ожидание освобождения)
  теперь разделены на уровне схемы БД — отдельная таблица `wishlist`. Один домен
  может одновременно быть и в `/list`, и в `/wishlist`.
- **Команда `/wishlist`** — показать/добавить/удалить wishlist-домены. Поддержка
  пагинации, кнопок «🗑 Удалить» для каждого домена.
- **Уведомление об освобождении** — одноразовое (запись удаляется из wishlist после
  успешной отправки). Кнопки «📌 Начать отслеживать» / «OK» в уведомлении.
- **Scheduler**: wishlist-домены (только wishlist, без tracked) проверяются каждые
  24 часа независимо от `expires_at`. Если домен и в `/list`, и в `/wishlist` —
  используется tracked-TTL (adaptive), а не wishlist-режим.
- **Миграция**: данные из `user_domains.is_wishlist=true` перенесены в таблицу
  `wishlist`, колонка `is_wishlist` удалена из `user_domains`. Downgrade возвращает
  данные обратно.

### Internal

- `WishlistRepository` — новый репозиторий для таблицы `wishlist`. Методы:
  `add`, `remove`, `exists`, `count_by_user`, `get_subscribers_for_domain`,
  `list_with_whois`, `mark_notified`.
- Хэндлер `wishlist.py` — команда `/wishlist`, inline-кнопки удаления.
- Обновлены тесты: удалены проверки на удалённое поле `is_wishlist` в ORM,
  добавлены тесты инвариантов ADR 039.
- Удалён статус `promoted` из `DomainService.add_for_user` — промоут
  wishlist→tracked больше не существует (wishlist и tracking независимы).

## [0.11.0] — 2026-05-30

Subdomain enumeration через Certificate Transparency-логи (crt.sh),
[ADR 037](docs/decisions.md). On-demand, read-only с opt-in отслеживанием.
Реализовано подэтапами TASK-0022…0025.

### Added — Subdomain enumeration (crt.sh, ADR 037)

- **Команда `/subdomains <домен>`** — поиск поддоменов registrable-домена через
  CT-логи (crt.sh). Read-only список с именами поддоменов; **opt-in**: кнопки
  «📌 Отслеживать» (по одному) и «📌 Отслеживать все» берут выбранные на
  отслеживание через обычный `/add`-путь — авто-добавления нет, лимит портфеля
  соблюдён.
- **Подсистема enumeration** — параллельная WHOIS/SSL/DNS/email-intel (как
  ADR 030/032/036): таблица `subdomain_enum_cache` (одна запись на registrable,
  JSONB-список поддоменов), ARQ-задача `check_subdomains`, кэш с adaptive TTL.
- **Парсер crt.sh**: нормализация (lowercase, punycode/IDN через `idna`), dedup,
  отбрасывание wildcard (`*.`) и самого registrable, фильтр «только поддомены
  запрошенного registrable» (PSL, ADR 035).
- **Graceful degradation**: таймаут / недоступность / rate-limit crt.sh не валят
  команду — понятное сообщение; повторные `/subdomains` в окне TTL не бьют crt.sh.

### Internal

- `subdomain_enum_cache.update_fail` — UPSERT-семантика: фейл-трекинг
  (`fail_count`/`last_error`/`is_reachable`) персистится с первого фейла.
- Юнит-тесты scheduler (все ветки TTL + timezone-aware guard), парсера
  (dedup/wildcard/IDN/registrable-фильтр) и хэндлера (opt-in, длина callback
  ≤ 64 байт, graceful degradation).
- Периодический мониторинг новых поддоменов + алерты вынесены в v0.12 (ADR 038).

## [0.10.1] — 2026-05-30

### Fixed

- **Кнопка «📋 Мои домены» в `/start` снова работает.** Падала с `TypeError`:
  `handle_start_button` вызывал `cmd_list` без обязательных `redis` и `state`
  (они появились в `cmd_list` под FSM/сброс поиска, а start-кнопку не
  обновили). Теперь оба прокидываются через DI. Добавлен тест на
  `handle_start_button` (list/settings/check), которого раньше не было —
  именно его отсутствие скрыло баг (TASK-0020).

### Internal

- Конвенция **anti-drift** в `CLAUDE.md` и шаблоне аудита: моки внутренних
  объектов со `spec`/`autospec`, grep всех вызовов при смене сигнатуры
  переиспользуемого хэндлера, миграции — только на реальном Postgres.

## [0.10.0] — 2026-05-30

Domain intelligence: мониторинг почтовой инфраструктуры и политик
([ADR 036](docs/decisions.md)). Пятая ось наблюдения после WHOIS, SSL, DNS и
RIR/ASN. Реализовано подэтапами TASK-0015…0018.

### Added — Email/policy-записи (MX/SPF/DKIM/DMARC, ADR 036)

- **Подсистема email-intel** — параллельная WHOIS/SSL/DNS (как ADR 030/032):
  своя таблица `email_intel_cache`, ARQ-задачи (`check_email_intel`),
  scheduler с собственным TTL, уведомления.
- **Сбор + базовая диагностика**: MX (host+priority), SPF (наличие + режим
  `-all`/`~all`/`?all`/`+all`, флаг >1 записи = RFC-нарушение), DMARC
  (`p`/`sp`/`pct`), DKIM (пробинг распространённых селекторов). Рекурсивный
  разбор SPF `include` и полный аудит-движок намеренно отложены.
- **Блок email в карточке `/whois`** (после DNS/SSL); записи берутся у самого
  домена/поддомена (ADR 035).
- **Уведомления per-domain** об изменениях (MX/SPF/DMARC/DKIM, became
  unreachable/reachable); toggle'ы `track_email` / `notify_email_change`
  в `⚙️ Уведомления`; `is_muted` гасит. Первая загрузка не шлёт уведомление.
- **Локализация**: новые ключи ru/en для блока, toggle'ов и уведомлений.

### Database

- Новая таблица **`email_intel_cache`** (PK `domain`): scheduling-поля,
  `is_reachable`, `mx_records`/`dkim_selectors` (JSONB), `spf_record`/
  `spf_mode`, `dmarc_policy`/`dmarc_subpolicy`/`dmarc_pct`, failure-tracking.
  Индекс `ix_email_intel_cache_next_check_at`.
- 2 новые колонки в **`user_domains`**: `track_email`, `notify_email_change`
  (миграция `20260529_email_intel`).

### Added — операционное (входит также в hotfix v0.9.3)

- **Instance-тег в админ-канале (ADR 019)**: каждое сообщение начинается с
  `[label · domain · ip]` из конфига (`INSTANCE_NAME`, домен из
  `WEBHOOK_BASE_URL`, `SERVER_IP`) — различение деплоев (TASK-0019).

## [0.9.3] — 2026-05-30

### Added

- **Instance-тег в сообщениях админ-канала (ADR 019)** — hotfix-релиз от
  v0.9.2: каждое сообщение начинается с `[label · domain · ip]`. Новые
  env-переменные `INSTANCE_NAME`, `SERVER_IP` (TASK-0019).

### Changed

- Конвенция логирования (`CLAUDE.md`): runtime IP не логируется в structlog,
  но допускается в приватном админ-канале (ADR 019) через `SERVER_IP`.

## [0.9.2] — 2026-05-29

### Changed

- **tldextract hardening (ADR 035):** PSL-экстрактор инициализируется с
  явным `cache_dir=None` — дисковый кэш отключён (по умолчанию tldextract
  пишет в `~/.cache/python-tldextract/`, что ломается в read-only
  контейнерах). Поправлен неверный комментарий в `src/utils/domains.py`
  (TASK-0010).

### Tests

- Тест оффлайн-режима PSL теперь реально блокирует сеть
  (`socket.socket` / `getaddrinfo`) и падает, если кто-то вернёт сетевой
  автофетч — раньше проверка была номинальной (TASK-0010).

### Docs

- Добавлено описание подсистемы разбора доменов / PSL (`tldextract`,
  `src/utils/domains.py`, маршрутизация WHOIS на registrable) в `CLAUDE.md`
  и `docs/architecture.md` (TASK-0011).

## [0.9.1] — 2026-05-29

### Fixed

- **Миграция `20260529_registrable_domain` теперь применяется на PostgreSQL**
  — в v0.9.0 была дефектна из-за `server_default=sa.text("")` и backfill
  `WHERE registrable_domain = ""` (пустая строка не NULL). В v0.9.1 миграция
  исправлена: строковый литерал `''` в `server_default`, корректный backfill
  (`WHERE registrable_domain = ''`), снятие `server_default` после заполнения
  (TASK-0008).
- **`mypy`**: устранён type-narrowing в `src/bot/handlers/whois.py` — шаг
  `mypy` в CI снова зелёный (TASK-0013).
- **CI**: добавлен smoke-test Alembic-миграций на Postgres (`CI=1 pytest
  tests/integration/test_migrations.py`); alembic больше не гасит логгеры
  приложения (`disable_existing_loggers=False` в `migrations/env.py`);
  миграционный тест изолирован в subprocess для корректной teardown
  ресурсов (TASK-0009).

## [0.9.0] — 2026-05-29

**Примечание:** Миграция `20260529_registrable_domain` в v0.9.0 была дефектна
и не применялась на PostgreSQL. Исправлена в v0.9.1.

Поддержка поддоменов и зон 3-го уровня через Public Suffix List
([ADR 035](docs/decisions.md)). WHOIS берётся у registrable-родителя
(eTLD+1), а DNS и SSL отслеживаются у самого поддомена. Реализовано
подэтапами TASK-0002…0005.

### Added — Public Suffix List и registrable-домен (ADR 035, подэтапы 2a–2c)

- **Зависимость `tldextract`** с bundled-снапшотом PSL в оффлайн-режиме
  (без сетевого автофетча, `include_psl_private_domains=False`). Покрывает
  `co.uk`, `org.uk`, `com.br` и тысячи многоуровневых зон из коробки.
- **Модуль `src/utils/domains.py`**: `registrable_domain` (eTLD+1),
  `is_subdomain`, `is_public_suffix_only`, `split_domain` — чистые
  функции на punycode-форме, без сети.
- **WHOIS у родителя**: `a.pinbetting.ru` больше не показывается как
  «свободен», если занят `pinbetting.ru`. WHOIS-операции (кэш, scheduler,
  `lookup`) маршрутизируются по registrable-домену; несколько поддоменов
  одного родителя делят один `whois_cache`-row. DNS/SSL — по самому
  поддомену.

### Database

- Миграция `20260529_registrable_domain`: в `user_domains` добавлены
  `registrable_domain` (Text, индекс `ix_user_domains_registrable_domain`)
  и `is_subdomain`. Backfill существующих строк: `registrable_domain =
  domain`.

  **Примечание:** В v0.9.0 миграция была дефектна и не применялась на
  PostgreSQL. Исправлена в v0.9.1.

### Added — UX для поддоменов (TASK-0005, подэтап 2d)

- **Поддомены в `/whois`**: при вводе поддомена (например `a.pinbetting.ru`)
  показывается баннер «🔎 a.pinbetting.ru — поддомен pinbetting.ru.
  WHOIS показан для родителя», карточка WHOIS родителя, DNS/SSL-блоки
  для поддомена.
- **Поддомены в `/add`**: добавление поддомена создаёт запись с корректными
  `registrable_domain`, `is_subdomain=true`, `track_dns=true`,
  `track_ssl=true`. `notify_expiry` работает от родителя.
- **Поддомены в `/list`**: поддомены помечаются значком `↳` и показывают
  родительский expiry.
- **Отклонение публичного суффикса**: ввод чистого публичного суффикса
  (`co.uk`, `.ru` и т.п.) теперь возвращает специфичную ошибку
  `errors.public_suffix_not_domain` вместо общего `invalid_domain`.
- **Локализация**: новые ключи `commands.whois.subdomain_banner`,
  `commands.add.subdomain_added`, `errors.public_suffix_not_domain`,
  `subdomain_mark` в `/list` (ru/en).
- **Тесты**: покрыты валидация публичных суффиксов, определение поддоменов,
  разбиение доменов на компоненты, пометка поддоменов в `/list`.

### Changed

- **`format_list_row`**: теперь всегда передаёт `subdomain_mark` в шаблоны
  `row_known` и `row_unknown` для корректного отображения поддоменов.

## [0.8.1] — 2026-05-28

### Fixed — Wishlist ↔ tracking auto-promote (ADR 034)

- **Промоут wishlist → tracked**: `/add` на домен, лежащий в wishlist,
  теперь тихо конвертирует его в обычное отслеживание. Раньше такой домен
  застревал в лимбо: невидим в `/list` (скрывался как wishlist) и не
  конвертировался.
- **Новый метод `DomainRepository.promote_from_wishlist`**: `UPDATE ...
  WHERE is_wishlist=True` → `is_wishlist=False` + восстановление
  дефолтных флагов `notify_*`. SSL/DNS toggle'ы не трогаем.
- **Изменён `DomainService.add_for_user`**: теперь использует `get_for_user`
  вместо `exists` для различения wishlist/tracked. Новый статус
  `promoted` в `AddDomainResult`.
- **Локализация**: добавлен ключ `commands.add.promoted_from_wishlist`
  (ru/en).
- **Тесты**: покрыты все ветки промоута (idempotency, new domain, already
  tracked).

## [0.8.0] — 2026-05-22

### Added — DNS A/AAAA monitoring (Stage 14, [ADR 032](docs/decisions.md#032-dns-aaaaa-monitoring-как-параллельная-подсистема))

- **DNS-мониторинг** для всех отслеживаемых доменов: четвёртая ось
  наблюдения после WHOIS, SSL и RIR-инфраструктуры. Отдельная
  параллельная подсистема (`src/dns_monitor/`). Cron
  `dns_scheduler_tick` каждые 5 минут собирает due-домены,
  `check_dns` резолвит A/AAAA/NS через dnspython (цепочка external
  резолверов Cloudflare `1.1.1.1` + Google `8.8.8.8`).
- **Adaptive TTL** для DNS-проверок: `ns_mismatch_active` → 30 мин,
  `fail_count >= 10` → 24 ч, recent change без ASN-смены → 6 ч
  (likely CDN), новый домен → 1 ч, стабильный → 1 день.
- **DNS change-уведомления**: смена A-записей, смена AAAA-записей,
  смена NS-серверов, became unreachable / reachable. Отдельно —
  **расхождение DNS-NS vs WHOIS-NS** (critical security signal:
  классический индикатор угона домена или незавершённой миграции).
- **Per-domain DNS toggles**: `track_dns` (kill-switch, default true),
  `notify_dns_a_change`, `notify_dns_aaaa_change`,
  `notify_dns_ns_change` (гибрид: обычная смена + mismatch),
  `notify_dns_unreachable`. Все в едином конфигураторе
  `/whois → ⚙️ Уведомления`.
- **DNS-блок в карточке `/whois`**: A/AAAA/NS-записи с подсветкой
  совпадения (✓) или расхождения (🚨) DNS-NS с registry-NS.
  Компактные состояния для mx-only / no-dns / unreachable доменов.
  При первой проверке домена ставит `check_dns` без ожидания
  cron-тика.
- **Локали**: ~16 новых ключей ru/en для DNS-блока, уведомлений и
  конфигуратора.

### Database

- Новая таблица **`dns_cache`** (PK `domain`): scheduling-поля
  (`last_checked_at`, `last_successful_check_at`, `next_check_at`,
  `last_changed_at`), записи (`a_records`, `aaaa_records`,
  `ns_records` — все ARRAY(Text)), `asn_set` (ARRAY(Integer),
  placeholder в v0.8.0), `resolution_state`, `is_reachable`,
  `resolver_used`, `ns_mismatch_active`, failure-tracking
  (`fail_count`, `last_error`). Индекс `ix_dns_cache_next_check_at`.
- 5 новых колонок в **`user_domains`**: `track_dns`,
  `notify_dns_a_change`, `notify_dns_aaaa_change`,
  `notify_dns_ns_change`, `notify_dns_unreachable` (все bool,
  default true).
- Миграция `20260519_dns` (down_revision `20260517_ssl`).

### Dependencies

- `dnspython >= 2.6, < 3` — async DNS resolver.

### Architectural

- Новый ADR 032 — DNS monitoring rationale.
- **Out of scope в v0.8.0** (future work): DNSSEC валидация (v0.9),
  локальный unbound (v0.9), полноценная ASN-сборка (v0.8.x,
  зависит от rir2localdb endpoint `/v1/ip/{addr}/asn`), adaptive
  CDN learning (v0.8.x). ASN-фильтр в v0.8.0 — placeholder
  (`enrich_with_asn` возвращает пустой list), любая смена IP даёт
  уведомление.

## [0.7.2] — 2026-05-22

### Fixed

- **`/wishlist` без аргумента** снова показывает список wishlist-доменов
  (UX-регрессия из v0.7.1). FSM-prompt для пустого аргумента остаётся
  только у команд с единственной операцией: `/add`, `/rmv`, `/check`,
  `/notify`, `/unnotify`.

### Documentation

- **ADR 033** приведён в соответствие с реальностью: storage =
  `MemoryStorage`, TTL обеспечивается middleware `clear_state_on_command`
  вместо `RedisStorage(state_ttl=300)`. Добавлена секция Followup в
  ADR и пункт в TODO.md → Tech debt для миграции на RedisStorage в v0.8.x.

## [0.7.1] — 2026-05-22

### Changed

- Команды `/add`, `/rmv`, `/check`, `/notify`, `/unnotify`,
  `/wishlist` без аргумента теперь спрашивают домен и подтверждают
  inline-кнопками если он пришёл отдельным сообщением (ADR 033).

### Fixed

- Убрана сухая ошибка `errors.no_domain` при пустом аргументе у
  команд с обязательным доменом.

## [0.7.0] — 2026-05-19

### Added — RIR/ASN lookup integration (Stage 13, [ADR 031](docs/decisions.md#031-universal-rirasn-lookup-client-rir2localdb-integration))

- **Universal HTTP client to rir2localdb** (`src/rir_client/`) для
  определения allocation и RPSL информации по IP-адресам и ASN.
  Работает через `rir2localdb-serve.service` на этом же хосте
  (`host.docker.internal:18000`).
- **Pydantic-модели** для ответов API: `IPAllocation`, `ASNAllocation`,
  `RIRStatus` (с `latest_sync_run` и per-source freshness),
  `SyncRun`, `Source`. RPSL-блок оставлен `dict[str, Any]` — типизация
  отложена до v0.8.
- **Двухуровневая error model**: `RIRError` (returned) для
  `lookup_ip`/`lookup_asn`, `RIRUnreachable` (raised) для
  `healthcheck`/`get_status` — последние две используются в cron-задаче.
- **ARQ cron `rir_health_check`** каждые 30 минут — мониторит
  доступность сервиса и свежесть данных (`latest_sync_run.started_at`
  не старше 26 часов, `status == "success"`). При недоступности или
  stale data — critical alert в admin-канал с дедупликацией по
  title-константе (5 distinct failure modes, каждый дедуплится
  независимо).
- **Settings:** `RIR2LOCALDB_ENABLED`, `RIR2LOCALDB_URL`,
  `RIR2LOCALDB_TIMEOUT_SECONDS`, `RIR2LOCALDB_CONNECT_TIMEOUT_SECONDS`.

### Architectural

- Новый ADR 031 — universal RIR client. См.
  `docs/decisions.md#031`.
- Network topology — переиспользует extra_hosts из ADR 028 (тот же
  `host.docker.internal:172.28.0.1`). На хосте требуется ufw allow
  от `172.28.0.0/16` на порт 18000 (зеркало правила для 8043) —
  добавлено системой перед этим этапом.

### Note

Этот релиз **инфраструктурный**: RIR-клиент не используется в UI или
мониторинге бота. Закладывает фундамент для v0.8 (DNS A/AAAA monitoring
с ASN-фильтрацией для устранения шума от CDN round-robin).

## [0.6.1] — 2026-05-17

### Fixed

- **SSL bootstrap для существующих доменов**: `ssl_scheduler_tick` теперь
  на каждом тике вставляет заглушки в `ssl_cache` для всех `user_domains`
  с `track_ssl=true`, у которых ещё нет записи (`INSERT ... ON CONFLICT
  DO NOTHING`). Без этого SSL-мониторинг включался только для доменов,
  открытых пользователем через `/whois` после Stage 12 — существующие
  на момент апгрейда домены никогда бы не попали в очередь проверок.
- **Расширена классификация `no_https`**: `ConnectionRefusedError` на :443
  (порт закрыт) и OSError'ы вида "no address associated", "no such host",
  "nodename nor servname" теперь корректно классифицируются как «у домена
  нет HTTPS» вместо ложного `connection_refused → became_unreachable`.
  Это убирает ложные уведомления `became_reachable` для доменов которые
  никогда не имели HTTPS, но позже получили A-записи.

## [0.6.0] — 2026-05-17

### Added — SSL certificate monitoring (Stage 12, [ADR 030](docs/decisions.md#030-ssltls-сертификаты-как-параллельная-подсистема-мониторинга))

- **SSL certificate monitoring** для всех отслеживаемых доменов:
  отдельная подсистема, параллельная WHOIS-стеку. Cron `ssl_scheduler_tick`
  каждые 5 минут собирает due-домены, `check_ssl` делает TLS-handshake на
  :443 и парсит peer-сертификат (без chain validation — мы мониторим,
  а не проверяем доверие).
- **Adaptive TTL** для SSL-проверок: > 30 дней до истечения → раз в сутки,
  7–30 дней → каждые 6 ч, 1–7 дней → каждый час, ≤ 1 день / нет данных →
  каждые 4 ч. ``fail_count ≥ 10`` фиксирует интервал в 24 ч.
- **SSL reminders**: cron `ssl_reminders_scheduler` ежечасно ставит
  `send_ssl_expiry_reminder` для пользователей, у которых
  `(not_after - сегодня)` совпадает с одним из дней-предупреждения.
  Дедупликация через `sent_notifications.notification_type='ssl_expiry'`.
- **SSL change-уведомления**: смена issuer (CN или O), перевыпуск
  сертификата (`not_after_changed`), переход HTTPS-эндпоинта в
  unreachable / recoverable. Кейс `no_https` (DNS не резолвится, нет
  port 443) не считается падением SSL и не шлёт уведомлений.
- **Per-domain SSL toggles**: `track_ssl` (kill-switch, default true),
  `notify_ssl_expiry`, `notify_ssl_change_issuer`,
  `notify_ssl_days_override` (NULL → берём `User.notify_ssl_days_before`).
  Все настройки в одном конфигураторе `/whois → ⚙️ Уведомления`.
- **SSL-блок в карточке `/whois`**: дата истечения сертификата, дней до
  истечения, эмодзи серьёзности, издатель. При первой проверке домена —
  ставит `check_ssl` без ожидания cron-тика.
- **Локали**: 12 новых ключей ru/en для SSL-карточки, уведомлений и
  конфигуратора.

### Database

- Новая таблица **`ssl_cache`** (PK `domain`): scheduling-поля
  (`last_checked_at`, `last_successful_check_at`, `next_check_at`),
  reachability (`is_reachable`, `has_certificate`), cert-метаданные
  (`not_before`, `not_after`, `issuer_cn/o`, `subject_cn/alt_names`,
  `serial_number`, `fingerprint_sha256`, `signature_algorithm`),
  failure-tracking (`fail_count`, `last_error`). Индексы
  `ix_ssl_cache_next_check_at`, `ix_ssl_cache_not_after`.
- 4 новые колонки в **`user_domains`**: `track_ssl` (bool, default true),
  `notify_ssl_expiry` (bool, default true), `notify_ssl_change_issuer`
  (bool, default true), `notify_ssl_days_override` (int[], nullable).
- 1 новая колонка в **`users`**: `notify_ssl_days_before` (int[],
  default `{14,7,3,1}`).
- Миграция `20260517_ssl` (down_revision `20260517_pernotif`).

### Dependencies

- `cryptography >= 42.0, < 46.0` — парсинг X.509-сертификатов (был
  транзитивной зависимостью, зафиксирован как прямая для ясности).

## [0.5.0] — 2026-05-17

### Added

- **Per-domain notification toggle for owner (registrant) changes** —
  ``notify_registrant_change`` (раньше шёл через
  ``notify_registrar_change``-mapping, см. ADR 029).
- **Per-domain notification toggle for fetch problems** — ``notify_problem``.
- **Per-domain kill-switch** — ``is_muted`` boolean. Заменяет computed
  «все toggle'ы выключены»; при unmute индивидуальные настройки
  сохраняются.
- **Inline notification configurator UI** в карточке /whois: кнопка
  «⚙️ Уведомления» открывает интерактивный конфигуратор с toggle'ами
  всех 6 типов уведомлений, mute/unmute, и FSM-редактором списка дней
  предупреждения. Toggle перерисовывает клавиатуру через
  ``edit_message_reply_markup`` — без флуда в чат.

### Changed

- «Muted»-индикатор в /list теперь читает поле ``is_muted`` напрямую
  (раньше вычислялся как «все 4 toggle'а выключены»).
- Уведомления о смене владельца отделены от уведомлений о смене
  регистратора — пользователи, выключившие registrar_change, продолжат
  получать registrant-уведомления (default включён).
- ``expiry_scheduler`` SQL: добавлен фильтр ``ud.is_muted = false``.

### Database

- 3 новые колонки в ``user_domains``: ``is_muted`` (bool, default false),
  ``notify_registrant_change`` (bool, default true), ``notify_problem``
  (bool, default true). Миграция ``20260517_pernotif``, дефолты
  backwards-compat: поведение для существующих пользователей
  не меняется.

### Documentation

- Новый ADR 029 (per-domain notification settings — extended) +
  обновление CHANGELOG.

## [0.4.0] — 2026-05-17

### Changed

- WHOIS lookups now route through internal proxy gateway running on the
  host (`host.docker.internal:8043` from containers). The proxy handles
  RDAP, generic WHOIS, and RU-specific upstream via a dedicated RU-VDS.
  See [ADR 028](docs/decisions.md#028-whois-proxy-gateway-as-primary-lookup).
- 24-hour positive caching on proxy side reduces load on registries and
  improves response times.
- New `DataSource` literal values: `proxy_rdap`, `proxy_whois`,
  `proxy_whois_ru`, `proxy_none` — track which upstream the proxy used.

### Added

- `src/whois/proxy_client.py` — HTTP/JSON client for the proxy gateway
  (`lookup_via_proxy`, `proxy_healthcheck`, `ProxyUnreachable`).
- Proxy health monitoring: ARQ cron `proxy_health_check` runs every
  15 minutes, pings `/healthz`, sends critical alert to admin channel
  if the proxy is down.
- Source attribution in WHOIS data: `proxy_rdap`, `proxy_whois`,
  `proxy_whois_ru`, `proxy_none` to track upstream and cache status.
- Automatic fallback to direct RDAP/WHOIS:43 lookup when proxy is
  unreachable — bot remains functional during proxy downtime.
- Docker compose network configured to reach host-side proxy: pinned
  subnet `172.28.0.0/16`, explicit gateway in `extra_hosts`, and ufw
  allow rule (`ufw allow from 172.28.0.0/16 to any port 8043 proto tcp`)
  on the host. Docker's `host-gateway` magic doesn't work for
  user-defined compose networks — see ADR 028 for the trap.
- New [ADR 028](docs/decisions.md#028-whois-proxy-gateway-as-primary-lookup):
  WHOIS proxy gateway as primary lookup.

### Removed

- `WHOIS_SERVER_OVERRIDES` env variable and its validator (replaced by
  the proxy gateway).
- `server_overrides=` parameter of `whois_protocol.query_whois`.
- [ADR 023](docs/decisions.md#023-whois-server-overrides-per-tld-deprecated-in-v040)
  marked DEPRECATED (kept for historical reference).

### Fixed

- `.ru` / `.рф` / `.su` domains now consistently return full WHOIS data
  from non-RU IP addresses (previously blocked by TCI).

### Documentation

- Cross-referenced `scripts/deploy.sh` across README, ADR 027,
  CONTRIBUTING for long-term discoverability (back-dated to v0.3.x but
  landed after the v0.3.0 tag).

## [0.3.0] — 2026-05-17

### Added

- **Hidden `/version` command** with build info: short output for
  everyone (version + commit + build time), extended report for
  `ADMIN_USER_IDS` (uptime, Postgres/Redis health, storage counters,
  stack versions, GitHub commit link). Not registered in the BotFather
  menu and not mentioned in `/help`.
- **Search by substring in `/list`** via the new `🔍 Поиск` button and
  FSM input — supports both punycode and Unicode variants («пример»
  finds `xn--…`).
- **New `/list` filters:** `🚨 С проблемами` (critical EPP statuses —
  `clientHold`, `pendingDelete`, `serverHold`, `BLOCKED`, `failed`)
  and `💀 Истёкшие` (`expires_at < now()`).
- **Wishlist:** `/wishlist <domain>` or the inline button
  «🎯 Хочу когда освободится» in the `/whois` card. The bot re-checks
  wishlist domains every 24 hours and sends a one-shot notification
  when the domain becomes available, then auto-removes the
  subscription. Filter `🎯 Wishlist` in `/list` shows the active
  wishlist.
- **One-command deployment:** `scripts/deploy.sh` — clean working tree
  check → git pull → build info regen → docker build → alembic upgrade
  → recreate services → health verification.
- **`APP_VERSION` baked into build info** at deploy time: read from
  `pyproject.toml` via `tomllib` and written to `_build_info.py`
  alongside git metadata, so `/version` reports a real version in
  containers (where `importlib.metadata` returns `unknown` due to
  `uv sync --no-install-project`).

### Fixed

- **`/list` "CSV" button now exports the file directly** instead of
  responding with a hint to use the `/csv` command. Both entry points
  now share the same `send_user_csv_file` helper.
- **No bogus change notifications on first fetch after `/add`** —
  `compute_diff` was treating the NULL → real-value transition from
  the placeholder `whois_cache` row (inserted by `add_for_user` before
  `check_domain` ran) as a real change. Guard now also requires
  `old_data.is_registered=True`.
- **`/list` pagination no longer resets the active filter** when
  paging prev/next — state is persisted in Redis `list_state:{user_id}`
  (TTL 30 min) along with the search query.

### Database

- `user_domains.is_wishlist BOOLEAN NOT NULL DEFAULT false` (migration
  `20260517_wishlist`). Existing rows are unaffected.
- New `notification_type='wishlist_available'` value used in
  `sent_notifications` for audit logging.

## [0.2.0] — 2026-05-17

### Added — Enhanced WHOIS display (Stage 8)

- **Owner section in `/whois` card** — extracts `registrant`, `admin`,
  `tech`, `abuse`, `billing` contacts from both RDAP (entities + vCard +
  RFC 9537 `redacted[]`) and textual WHOIS (thick gTLD, TCINET `.ru`,
  NIC.it dotted keys, AFNIC, DENIC). Shows owner organization with
  country, or honest "hidden (private individual)" / "hidden (privacy
  protected)" labels when registry redacts data.
- **Localized status names** — raw EPP codes (`clientTransferProhibited`,
  `pendingDelete`) are translated to human-readable text with severity
  highlighting (critical → warning → info → normal). Unknown codes fall
  back to a humanized form (`clientHold` → "Client hold"). Trivial
  `ok`/`active` are hidden when other statuses are present.
- **Registrant change notifications** — new `notify` types: `registrant`
  (organization changed), `registrant_privacy_revealed` (was hidden,
  now public), `registrant_privacy_hidden` (was public, now hidden).
  Email/phone changes are intentionally ignored to avoid notification
  noise. Subscribed via the existing `notify_registrar_change` flag —
  no new per-domain switch.
- **Human-readable "full WHOIS" file** — the "Full response" button now
  returns a `.txt` with a structured header (domain / timeline /
  registrar / contacts / status / nameservers / DNSSEC) **plus** the
  raw source data: pretty-printed JSON for RDAP, original text for
  WHOIS:43. Replaces the previous Python `repr(dict)` for RDAP domains.

### Changed

- `WhoisData` gains `contacts: list[WhoisContact]` and `registrant` /
  `admin` / `tech` convenience properties.
- `whois_cache` schema adds denormalized `registrant_*` columns and a
  JSONB `contacts_data` column (migration `20260516_registrant`,
  additive; existing rows fill on next scheduled check).
- Sentry `before_send` masks `registrant*`, `admin_email`, `admin_phone`,
  `tech_email`, `tech_phone`, `contacts_data` keys — public WHOIS data
  shouldn't sit in error trackers.

### Migration notes

- `alembic upgrade head` adds nullable columns. Existing cached domains
  show no Owner section until the next plan-driven `check_domain` run
  fills the new fields. To force-refresh a specific domain, press the
  "🔄 Обновить" button in its `/whois` card.

## [0.1.0] — 2026-05-16

First public release. MVP feature set, production-ready infrastructure.

### Added

- WHOIS lookup for any domain via RDAP, with WHOIS:43 fallback
- Domain tracking with adaptive re-check schedule (30 / 7 / 2 / 1 days
  to expiry → corresponding check interval)
- Shared WHOIS cache across all users (one record per domain)
- Expiry reminders at configurable days before expiration
- Change notifications for registrar, name servers, and EPP status flags
- `/csv` — export user portfolio as UTF-8 BOM CSV
- `/download` — bulk import from TXT/CSV with FSM-driven preview and
  rate-limiting (`MAX_DOWNLOADS_PER_DAY`, file size, per-user limit)
- `/whois`, `/add`, `/rmv`, `/list` (paginated + filters), `/check`,
  `/notify`, `/unnotify`, `/settings`, `/stats`, `/delete_me` commands
- Bilingual UI (Russian / English) with auto-detection from Telegram
- Per-user timezone and reminder time (`notify_at_hour`)
- IDN support (`.рф`, `.中国`, ...) via punycode normalization
- WHOIS parser support for `.com`, `.net`, `.org`, `.info`, `.io`,
  `.ru`, `.рф`, `.de`, `.it`, `.kz`, and many more
- WHOIS referral following for thin-WHOIS registries (Verisign etc.):
  second query to the registrar's WHOIS server for full data
- `WHOIS_SERVER_OVERRIDES` env: per-TLD WHOIS server override for hosts
  where default servers are unreachable (community mirrors for `.ru`)
- IANA discovery for unknown TLDs — parses both `refer:` and `whois:` keys
- Admin Telegram channel for system alerts (ADR 019) with Redis dedup;
  daily summary, cleanup cron jobs
- `/admin` command for operators (stats, manual alert)
- Sentry SDK integration with `before_send` filter that strips
  `*token*`/`*password*`/`*secret*`/auth headers and bulk WHOIS payloads
- structlog production logging: JSON renderer in `production`,
  ConsoleRenderer in `development`; `bind_log_context` for request/task
  scoped fields (`telegram_id`, `user_id`, `update_id`, `domain`)

### Infrastructure

- PostgreSQL 16 + Redis 7 + ARQ workers
- Three independent processes: bot (webhook), worker, scheduler
- Docker Compose deployment, Nginx + Let's Encrypt
- Webhook (not long polling), `X-Telegram-Bot-Api-Secret-Token` verified
- 328 tests passing; mypy strict; ruff and black clean
- GitHub Actions CI for lint + type-check + tests on every push and PR
