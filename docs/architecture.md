# Архитектура Whois Watcher

## Общая схема

Три независимых процесса, общающихся через PostgreSQL и Redis:

```
                       Telegram Bot API
                              │
                              ▼ webhook
                       ┌─────────────┐
                       │    Nginx    │  (SSL termination)
                       └──────┬──────┘
                              │
                              ▼
                       ┌─────────────┐
                       │     Бот     │  (aiogram, webhook-сервер)
                       └──────┬──────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        ┌─────────┐    ┌──────────┐    ┌─────────────┐
        │ Postgres│    │  Redis   │◄───┤  Воркеры    │
        │         │    │          │    │   (ARQ)     │
        └─────────┘◄───┴──────────┘    └─────────────┘
              ▲                              ▲
              │                              │
              └──────────────────────┬───────┘
                                     │
                              ┌──────┴──────┐
                              │ Планировщик │  (ARQ cron)
                              └─────────────┘
                                     │
                                     ▼
                         WHOIS / RDAP серверы
```

## Процессы

### 1. Бот (webhook-сервер)

Принимает обновления от Telegram через webhook. Не делает долгих операций — только пишет в БД и ставит задачи в очередь.

- Стартует через `src/main.py`
- Использует aiogram 3.x
- Webhook принимает FastAPI/aiohttp (выбрать при реализации)
- Проверяет `X-Telegram-Bot-Api-Secret-Token` для верификации
- Middleware: регистрация пользователя, локаль, rate limit

### 2. Воркеры (ARQ)

Выполняют фоновые задачи:
- `check_domain(domain)` — WHOIS/RDAP-запрос, обновление кэша, проверка изменений
- `send_reminder(user_id, domain, days_before)` — отправка одного напоминания
- `send_change_notice(user_id, domain, change_type, old, new)` — уведомление о смене статуса
- `send_problem_notice(user_id, domain)` — уведомление о длительных WHOIS-проблемах
- `cleanup_orphan_cache()` — удаление записей `whois_cache`, на которые никто не подписан
- `cleanup_old_events()` — чистка `system_events` старше N дней

Несколько процессов параллельно, лимит конкурентности на WHOIS-запросы — `MAX_CONCURRENT_WHOIS`.

Стартует через `src/worker.py`.

### 3. Планировщик

Cron-задачи через ARQ:

- **Каждые 5 минут:** выбрать из `whois_cache` записи с `next_check_at <= now()` и поставить их в очередь
- **Каждый час:** пройти по `users`, для каждого вычислить, какие напоминания нужно отправить **сейчас** (с учётом часового пояса и `notify_at_hour`), поставить в очередь
- **Раз в сутки (03:00 UTC):** ежедневная сводка в админ-канал
- **Раз в сутки (04:00 UTC):** очистка сиротских записей `whois_cache` и старых событий

## Поток данных

### Добавление домена пользователем

```
User → /add example.com
  ↓
Хэндлер: валидация, проверка лимитов
  ↓
INSERT user_domains
  ↓
Проверка whois_cache:
  - Если есть и свежий → ответить сразу с датой
  - Если нет → INSERT whois_cache (next_check_at = now), enqueue check_domain
  ↓
Бот отвечает: "Добавлен, проверяю..." (если данных ещё нет)
  ↓
Воркер: check_domain → RDAP/WHOIS → UPDATE whois_cache
  ↓
Воркер: send_message пользователю с результатом
```

### Периодическая проверка

```
Планировщик (каждые 5 мин):
  SELECT domain FROM whois_cache WHERE next_check_at <= now() LIMIT N
  ↓
  для каждого: enqueue check_domain
  ↓
Воркер: check_domain
  ↓ lookup_domain (ADR 028):
      ├── HTTP GET 127.0.0.1:8043/q/<domain>   ← WHOIS proxy gateway (primary)
      │       └── прокси сам решает upstream: RDAP / WHOIS:43 / RU-relay
      └── fallback (если /healthz упал): lookup_direct
              ├── RDAP через whoisit
              └── WHOIS:43 (raw socket + парсер)
  ↓ парсинг (ответ прокси уже в виде dict/text)
  ↓ сравнение с текущими значениями (для notify_change)
  ↓ UPDATE whois_cache (новые expires_at, next_check_at и т.д.)
  ↓ если есть изменения и подписчики — enqueue send_change_notice
```

### Рассылка напоминаний об истечении

```
Планировщик (каждый час):
  Для пользователей, у которых сейчас "9 утра" по их таймзоне:
    SELECT необходимые напоминания (см. SQL в docs/commands.md)
    Для каждого → enqueue send_reminder
  ↓
Воркер: send_reminder
  ↓ INSERT sent_notifications (с UNIQUE-защитой от дублей)
  ↓ Bot.send_message
```

## Схема базы данных

### users

Пользователи бота.

```sql
CREATE TABLE users (
    id              bigserial PRIMARY KEY,
    telegram_id     bigint UNIQUE NOT NULL,
    username        text,
    language        text NOT NULL DEFAULT 'ru',
    timezone        text NOT NULL DEFAULT 'Europe/Moscow',  -- UTC+3 дефолт
    notify_days     int[] NOT NULL DEFAULT '{30,7,1}',
    notify_at_hour  int NOT NULL DEFAULT 9,                 -- час локального времени для рассылки
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_active_at  timestamptz NOT NULL DEFAULT now(),
    is_blocked      boolean NOT NULL DEFAULT false
);

CREATE INDEX ON users(telegram_id);
```

### user_domains

Домены, отслеживаемые пользователями. Many-to-many между users и доменами.

```sql
CREATE TABLE user_domains (
    id                       bigserial PRIMARY KEY,
    user_id                  bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain                   text NOT NULL,                 -- punycode-форма
    notify_days              int[],                          -- NULL = берём из users
    notify_expiry            boolean NOT NULL DEFAULT true,
    notify_ns_change         boolean NOT NULL DEFAULT false,
    notify_registrar_change  boolean NOT NULL DEFAULT true,
    notify_status_change     boolean NOT NULL DEFAULT true,
    last_problem_notified_at timestamptz,
    note                     text,
    added_at                 timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, domain)
);

CREATE INDEX ON user_domains(user_id);
CREATE INDEX ON user_domains(domain);
```

### whois_cache

Общий кэш WHOIS-данных. Одна запись на домен, обслуживает всех подписчиков.

```sql
CREATE TABLE whois_cache (
    domain                    text PRIMARY KEY,             -- punycode
    expires_at                timestamptz,
    created_at_registrar      timestamptz,                  -- дата регистрации домена
    updated_at_registrar      timestamptz,
    registrar                 text,
    status                    text[],
    name_servers              text[],
    raw_data                  jsonb,                         -- сырой ответ для отладки
    fetched_at                timestamptz,
    last_successful_fetch_at  timestamptz,
    next_check_at             timestamptz,
    fail_count                int NOT NULL DEFAULT 0,
    last_error                text
);

CREATE INDEX ON whois_cache(next_check_at) WHERE next_check_at IS NOT NULL;
CREATE INDEX ON whois_cache(expires_at);
```

### sent_notifications

Журнал отправленных уведомлений для дедупликации.

```sql
CREATE TABLE sent_notifications (
    id                bigserial PRIMARY KEY,
    user_id           bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    domain            text NOT NULL,
    notification_type text NOT NULL,           -- 'expiry', 'ns_change', 'registrar_change', 'status_change', 'problem'
    days_before       int,                     -- только для type='expiry'
    expires_at        timestamptz,             -- снапшот для корректной дедупликации после продления
    sent_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, domain, notification_type, days_before, expires_at)
);

CREATE INDEX ON sent_notifications(user_id, domain);
```

### domain_changes

История изменений по доменам — для аналитики и истории "что менялось".

```sql
CREATE TABLE domain_changes (
    id          bigserial PRIMARY KEY,
    domain      text NOT NULL,
    change_type text NOT NULL,                  -- 'expires_at', 'registrar', 'ns', 'status'
    old_value   jsonb,
    new_value   jsonb,
    detected_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON domain_changes(domain, detected_at DESC);
```

### system_events

Журнал системных событий для алертов и аналитики.

```sql
CREATE TABLE system_events (
    id          bigserial PRIMARY KEY,
    event_type  text NOT NULL,                  -- 'whois_failed', 'rate_limit_hit', etc.
    severity    text NOT NULL,                  -- 'info', 'warning', 'error', 'critical'
    details     jsonb,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX ON system_events(event_type, created_at DESC);
CREATE INDEX ON system_events(severity, created_at DESC) WHERE severity IN ('error', 'critical');
```

## Разбор доменов / PSL (ADR 035)

Модуль `src/utils/domains.py` отвечает за разбор доменов через Public Suffix List (tldextract):

- `split_domain(domain)` — разбивает домен на subdomain, registrable и suffix
- `registrable_domain(domain)` — возвращает registrable-домен (eTLD+1)
- `is_subdomain(domain)` — проверяет, является ли домен поддоменом
- `is_public_suffix_only(domain)` — проверяет, является ли домен публичным суффиксом

**Инварианты:**
- Полностью оффлайн — bundled snapshot из tldextract, без сетевых вызовов
- Дисковый кэш отключён (`cache_dir=None`) для работы в read-only контейнерах
- PSL-данные доступны из bundled snapshot (`co.uk` → public suffix, `example.co.uk` → registrable)

**Роутинг WHOIS:**
Запросы WHOIS всегда выполняются для registrable-домена (eTLD+1), а не для поддоменов. Например:
- `www.example.co.uk` → WHOIS для `example.co.uk`
- `a.b.foo.com` → WHOIS для `foo.com`

DNS/SSL-проверки выполняются для исходного домена (включая поддомены).

Подробнее см. ADR 035 в `docs/decisions.md`.

## Адаптивный TTL проверок

После каждой успешной проверки `next_check_at` пересчитывается:

| Дней до истечения | Интервал до следующей проверки |
|-------------------|--------------------------------|
| > 90              | 30 дней                        |
| 30–90             | 7 дней                         |
| 7–30              | 2 дня                          |
| < 7               | 1 день                         |
| < 0 (истёк)       | 1 день (ещё 45 дней)           |

Значения в `src/config/limits.py`.

После 45 дней с момента истечения без признаков продления — `next_check_at = NULL`, перестаём проверять.

При ошибке WHOIS:
- 1 фейл → повтор через 15 минут
- 2-3 фейла → повтор через 1-2 часа
- 4-5 фейлов → повтор через 6-12 часов
- 5+ фейлов и `last_successful_fetch_at` старше 5 дней → уведомить пользователя (раз в 7 дней)

## Кэширование

### whois_cache (Postgres)
Долгое хранение. Истина для всех решений по `expires_at`.

### Redis (опциональный hot-cache)
Для `/whois` и `/check` — можно хранить готовый отрендеренный ответ на 10-30 минут, чтобы не дёргать БД при частых проверках одного домена.

### Дедупликация запросов
Если домен уже в очереди на проверку, новые запросы на тот же домен не ставятся (Redis-флаг `check_pending:<domain>` на время выполнения).

## Rate limiting

Реализуется через middleware aiogram + Redis-счётчики (sliding window).

См. `src/config/limits.py` для всех значений. Ключи Redis:
- `rate:user:{user_id}:cmd_minute` — общие команды/минуту
- `rate:user:{user_id}:add_hour` — `/add`/час
- `rate:user:{user_id}:download_day` — `/download`/сутки
- `rate:whois:{domain}` — глобальный cooldown WHOIS-запросов на домен

## Безопасность

- `BOT_TOKEN` и все секреты — только из `.env`, никогда в коде/коммитах
- Webhook secret обязателен (`X-Telegram-Bot-Api-Secret-Token`)
- Nginx терминирует SSL, бот слушает по HTTP внутри Docker-сети
- БД и Redis недоступны снаружи — только внутри Docker-сети
- Fail2ban на хосте для SSH

## Масштабирование

Стартовая конфигурация (до ~10K пользователей):
- 1 VPS, 2 vCPU / 4 GB RAM
- Все компоненты в docker-compose
- ~$15/мес

При росте:
- Postgres на отдельный сервер
- 2-4 воркера на отдельной машине
- Балансировщик перед ботом (но webhook идёт на один URL, так что нужен sticky или один экземпляр бота с горизонтально масштабируемыми воркерами)
- Redis Sentinel для HA

Партиционирование `sent_notifications` и `system_events` по дате — при росте.
