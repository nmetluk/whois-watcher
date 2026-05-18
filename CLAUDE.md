# CLAUDE.md

Этот файл — инструкция для Claude Code при работе с репозиторием 
`whois-watcher`. Прочитай его перед началом любой сессии.

## О проекте

**Whois Watcher** — публичный бесплатный Telegram-бот для проверки 
WHOIS-данных доменов и автоматических напоминаний об их истечении. 
Открытый исходный код, MIT-лицензия. Public repository.

Текущая версия — см. `pyproject.toml`. История релизов — `CHANGELOG.md`.

Целевая аудитория: владельцы доменов (от одного до десятков тысяч в 
портфеле), системные администраторы, домейнеры.

## Технологический стек

- **Python 3.11+** (async везде, синхронных вызовов в горячем пути 
  быть не должно)
- **aiogram 3.x** — Telegram-бот через **webhook** (не long polling)
- **SQLAlchemy 2.0 async** + **asyncpg** — работа с БД
- **Alembic** — миграции
- **ARQ** — очередь задач на Redis
- **whoisit** — RDAP-клиент (через proxy gateway)
- **cryptography** — парсинг X.509-сертификатов (SSL monitoring)
- **idna** — поддержка IDN-доменов
- **pydantic v2** + **pydantic-settings** — конфиг и валидация
- **structlog** — логирование (JSON в production, ConsoleRenderer в dev)
- **Sentry SDK** — отлов ошибок (опционально), с фильтром секретов 
  в `before_send`

**Инфраструктура:**

- PostgreSQL 16, Redis 7
- Docker + docker-compose (включая `docker-compose.dev.yml` для 
  локальной разработки)
- Nginx как reverse proxy, Let's Encrypt для SSL
- WHOIS proxy gateway на хосте (см. ADR 028)
- Pre-commit hooks (`.pre-commit-config.yaml`)

## Архитектурные подсистемы

Бот состоит из нескольких независимых подсистем. Каждая описана 
в соответствующем ADR (`docs/decisions.md`).

### WHOIS Lookup (ADR 028)

Основной путь: HTTP-клиент к собственному proxy gateway на хосте 
(`host.docker.internal:8043`). Proxy решает — RDAP, прямой WHOIS:43, 
или RU-relay через VDS в РФ для `.ru/.рф/.su`. Кэширует 24h.

Fallback при падении proxy: прямой RDAP + WHOIS:43 через 
`src.whois.client.lookup_direct`.

Модули:
- `src/whois/proxy_client.py` — клиент к proxy
- `src/whois/client.py` — direct fallback (RDAP + WHOIS:43)
- `src/whois/rdap.py`, `whois_protocol.py`, `parser.py`
- `src/whois/scheduler.py` — adaptive TTL
- `src/whois/diff.py` — сравнение для уведомлений

### SSL Certificate Monitoring (ADR 030)

**Параллельная** подсистема к WHOIS-стеку. Своя таблица `ssl_cache`, 
свои cron-задачи, свой scheduler с TTL отличным от WHOIS (короче — 
LE-сертификаты живут 90 дней).

Технические инварианты (защищены тестами):
- `verify_mode=CERT_NONE` — мониторим, не валидируем доверие
- `CONNECT_TIMEOUT=10s` обязателен
- `no_https` ≠ unreachable (DNS-фейлы не считаются падением)
- `compute_ssl_diff(old=None, ...)` → пустой diff
- `became_unreachable` — только переход, не повтор
- `is_muted` гасит и SSL-уведомления

Модули:
- `src/ssl/{client,types,scheduler,diff}.py`
- `src/tasks/{check_ssl,ssl_scheduler,ssl_reminders_scheduler,send_ssl_reminder,notify_ssl_changes}.py`

### Per-domain notifications (ADR 029)

6 toggle'ов на каждый `UserDomain` + `is_muted` kill-switch. Inline-
конфигуратор `⚙️ Уведомления` в карточке `/whois` с FSM для 
редактирования списка дней. SSL имеет собственные toggle'ы 
(`track_ssl`, `notify_ssl_*`) и собственный FSM для SSL-дней.

Per-user defaults: `notify_days_before` (WHOIS, default `{30,7,1}`), 
`notify_ssl_days_before` (SSL, default `{14,7,3,1}`).

### Admin alerts (ADR 019)

Приватный Telegram-канал для критических ошибок и аномалий. 
Дедупликация через Redis. См. `src/services/alerts.py`.

## Структура проекта

```
whois-watcher/
├── CLAUDE.md, README.md, README.en.md, LICENSE, CONTRIBUTING.md
├── PRIVACY.md, TODO.md, CHANGELOG.md
├── SESSION_LOG.md                   # журнал сессий Claude Code
├── PROMPT_FOR_CLAUDE.md             # workflow-инструкция
├── .env.example, .gitignore, .pre-commit-config.yaml
├── pyproject.toml, uv.lock, alembic.ini
├── Dockerfile, docker-compose.yml, docker-compose.dev.yml
│
├── .github/workflows/               # CI + Telegram-нотификации
│
├── docs/
│   └── architecture.md, commands.md, decisions.md, deployment.md
│
├── migrations/versions/             # Alembic
│
├── scripts/
│   ├── deploy.sh                    # однокомандный деплой
│   ├── send-session-log.sh          # helper для SESSION_LOG.md
│   └── generate_build_info.sh
│
├── src/
│   ├── main.py                      # entrypoint бота (webhook)
│   ├── worker.py                    # entrypoint ARQ-воркеров
│   ├── observability.py             # Sentry + structlog setup
│   ├── _build_info.py               # auto-generated, gitignored
│   │
│   ├── config/{settings,limits}.py
│   ├── db/{models,session}.py
│   ├── db/repositories/             # паттерн репозитория
│   │
│   ├── bot/
│   │   ├── app.py, webhook.py
│   │   ├── handlers/                # /whois, /add, /list, etc.
│   │   ├── keyboards.py, states.py, validators.py
│   │   └── middlewares/
│   │
│   ├── whois/                       # WHOIS lookup (см. подсистемы)
│   ├── ssl/                         # SSL monitoring (см. подсистемы)
│   │
│   ├── tasks/                       # ARQ-задачи
│   │   ├── arq_config.py
│   │   ├── check_domain.py, check_ssl.py
│   │   ├── scheduler.py, ssl_scheduler.py
│   │   ├── expiry_scheduler.py, ssl_reminders_scheduler.py
│   │   ├── send_reminders.py, send_ssl_reminder.py
│   │   ├── send_change_notices.py, notify_changes.py
│   │   ├── notify_ssl_changes.py, notify_problem.py
│   │   ├── notify_wishlist.py, daily_stats.py, cleanup.py
│   │   └── proxy_health.py
│   │
│   ├── services/
│   │   ├── users.py, domains.py, notifications.py
│   │   ├── whois_facade.py, formatters.py, formatters_full.py
│   │   ├── results.py, csv_io.py, alerts.py
│   │
│   ├── locales/{ru,en}.py
│   └── utils/{idn,timezone,formatting,build_info,version}.py
│
└── tests/{unit,integration,conftest.py}
```

## Соглашения о коде

### Стиль

- **Форматирование:** `black` (line-length 100)
- **Линтер:** `ruff`
- **Type hints везде**, проверяется `mypy --strict` для `src/`
- **Pre-commit hooks** через `.pre-commit-config.yaml`

### Async

- Все I/O — async. Никаких `requests`, `time.sleep`, sync-запросов к БД
- CPU-bound через `asyncio.to_thread`
- Не блокируем event loop

### База данных

- Доступ к БД **только через репозитории** в `src/db/repositories/`
- Никаких прямых SQL/ORM в хэндлерах
- Миграции через Alembic, никаких `CREATE TABLE` в коде
- FK и индексы — обязательны
- `ON DELETE CASCADE` где уместно

### Telegram-бот

- Хэндлеры — тонкие, бизнес-логика в `services/`
- Все тексты — через локали, не хардкодить
- Inline-клавиатуры в `src/bot/keyboards.py`
- FSM — в `src/bot/states.py`
- Валидация доменов — через `src/bot/validators.py`

### Логирование

- Через `structlog`
- НИКОГДА не логировать: `BOT_TOKEN`, personal notes пользователей, 
  полные WHOIS-ответы с контактами, runtime IP сервера
- Логировать: команды (без чувствительного), user_id, время операций, 
  ошибки

### Конфиг

- Все настройки — через `pydantic-settings` в `src/config/settings.py`
- Лимиты — в `src/config/limits.py`, переопределяемые через env
- Никаких magic numbers — выносить в конфиг

## Что НЕ делать

- ❌ Не коммитить `.env` (только `.env.example`)
- ❌ Не использовать синхронные библиотеки в хэндлерах/тасках
- ❌ Не писать SQL в хэндлерах — только через репозитории
- ❌ Не хардкодить тексты — только через локали
- ❌ Не использовать long polling — только webhook
- ❌ Не делать прямые HTTP-запросы к Telegram API — только через 
  `aiogram.Bot`
- ❌ Не использовать `print()` — только `structlog`
- ❌ Не игнорировать type hints, не использовать `Any` без причины
- ❌ Не реализовывать платные тарифы — проект полностью бесплатный
- ❌ Не передавать `Bot`/`Dispatcher` через глобальные переменные — DI

## Команды для разработки

```bash
# Зависимости
uv sync

# Окружение
docker compose up -d postgres redis
docker compose --profile dev up

# Миграции
alembic revision --autogenerate -m "описание"
alembic upgrade head

# Тесты
pytest                            # все
pytest tests/unit/                # только юнит
pytest -k "test_whois"            # по паттерну
pytest --cov=src                  # с покрытием

# Линтер и формат
ruff check src tests
black src tests
mypy src

# Pre-commit
pre-commit run --all-files

# Деплой на сервер
bash scripts/deploy.sh
```

## Workflow с двумя Claude'ами

Проект ведётся **двумя Claude'ами** через публичный git:

- **Планирующий Claude** — в Claude.ai чате с пользователем. 
  Анализирует, проектирует, пишет промпты с детальными 
  спецификациями. Читает репо через web_fetch.
- **Исполняющий Claude Code** — на сервере. Получает промпт, 
  выполняет задачи, пишет код, запускает тесты, коммитит, пушит.

После каждой задачи **Claude Code добавляет запись в `SESSION_LOG.md`** 
по шаблону из `PROMPT_FOR_CLAUDE.md`. Push в `SESSION_LOG.md` 
триггерит GitHub Action, который шлёт уведомление в Telegram-канал.

Пользователь видит уведомление → шлёт точку в чат → планирующий 
Claude фетчит SESSION_LOG.md и анализирует.

Детали — см. `PROMPT_FOR_CLAUDE.md`.

## Полезные ссылки

- **Архитектура:** `docs/architecture.md`
- **Команды бота:** `docs/commands.md`
- **Принятые решения (30 ADR):** `docs/decisions.md`
- **Развёртывание:** `docs/deployment.md`
- **План этапов:** `TODO.md`
- **Workflow:** `PROMPT_FOR_CLAUDE.md`

Прочитай эти файлы при первой сессии. В них зафиксированы все 
договорённости.

## Стиль работы

- Один промпт — одна логическая единица, не "сделай всё"
- Перед изменением — прочитай существующий код, не пиши с нуля 
  если уже есть
- Тесты обязательны для парсеров, валидаторов, schedule-расчётов, 
  бизнес-логики в сервисах
- После значимых изменений — `ruff`, `mypy`, `pytest`
- Если архитектурный вопрос возник — не решай молча, спроси 
  в SESSION_LOG.md как открытый вопрос
- Real-world тесты в Telegram критически важны — UX-баги часто 
  не ловятся unit-тестами
