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
- **tldextract** — разбор доменов по Public Suffix List (PSL),
  определение registrable-домена (eTLD+1); bundled snapshot,
  оффлайн-режим (ADR 035)
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

### PSL / Domain Parsing (ADR 035)

Разбор доменов через Public Suffix List (tldextract). Определяет
registrable-домен (eTLD+1), классифицирует поддомены vs публичные
суффиксы. WHOIS-запросы идут на registrable-родителя, DNS/SSL — на
исходный домен (поддомен).

Инварианты:
- Полностью оффлайн — bundled snapshot, без сетевых вызовов
- Дисковый кэш отключён (`cache_dir=None`) для read-only сред
- PSL-данные доступны из bundled snapshot (`co.uk` → public suffix)

Модули:
- `src/utils/domains.py` — `split_domain`, `registrable_domain`,
  `is_subdomain`, `is_public_suffix_only`

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
  полные WHOIS-ответы с контактами
- **Runtime IP сервера** — НЕ логировать в structlog, но допускается
  в приватном админ-канале (ADR 019) через явный конфиг `SERVER_IP`
- Логировать: команды (без чувствительного), user_id, время операций,
  ошибки

### Конфиг

- Все настройки — через `pydantic-settings` в `src/config/settings.py`
- Лимиты — в `src/config/limits.py`, переопределяемые через env
- Никаких magic numbers — выносить в конфиг

### Защита от рассинхрона (anti-drift) — ОБЯЗАТЕЛЬНО

Три бага подряд (TASK-0008 миграция на sqlite vs Postgres; TASK-0017
несуществующие `notify_email_*`; TASK-0020 сигнатура `cmd_list`) имели общий
корень: **рассинхрон между вызывающим и вызываемым (сигнатура / поля схемы /
драйвер БД), скрытый слишком слабым тестом.** Чтобы не повторялось:

- **Мокать со `spec`/`autospec`.** Для моков внутренних объектов всегда
  `MagicMock(spec=...)` / `create_autospec(...)` (ORM-модели, `Settings`,
  переиспользуемые хэндлеры/функции). Голый `MagicMock` отдаёт любой атрибут и
  принимает любые аргументы — он маскирует и опечатки полей, и дрейф сигнатур.
- **Изменил сигнатуру переиспользуемой функции/хэндлера — `grep` все вызовы.**
  Особенно функции, которые дёргаются из нескольких мест (команды + callback'и).
  Покрыть хотя бы один тест на каждый callback/entry-путь, который упадёт при
  несовпадении аргументов (через `autospec`).
- **`getattr(obj, "field", default)` на ORM-объекте — красный флаг.** Молча
  вернёт `default`, если поле переименовано/не существует. Обращаться к полям
  напрямую (упадёт на отсутствующем) или проверять наличие поля в схеме.
- **Миграции — только на реальном Postgres.** sqlite принимает `""`/прочее
  иначе; миграционный smoke-тест на Postgres в CI обязателен (TASK-0009).

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

## Pre-commit hooks (обязательно после клонирования)

После клонирования репозитория **обязательно** установить hooks:

```bash
uv run pre-commit install
```

Это активирует автоматический прогон ruff / black / trim-trailing-whitespace
/ end-of-file-fixer / mixed-line-ending перед каждым коммитом. Без этого
формат-drift накапливается незаметно и ломает CI — именно так случилось
в подэтапе 2b: 8 красных CI-ранов подряд из-за дрейфа black-форматирования
в SSL-файлах (см. SESSION_LOG.md).

Конфигурация в `.pre-commit-config.yaml` пинит `python3.11` для языковой
среды; если на dev-машине стоит только 3.12, поставь и 3.11:

```bash
uv python install 3.11
```

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

## Workflow: handoff + PR (GitHub — источник правды)

Проект ведётся **двумя ролями** через публичный git. **GitHub —
единственный источник правды.** Каждый шаг выполняется в **отдельной
сессии** (возможно на разных ОС), поэтому контекст переносится через
файлы в репозитории, а не через память агента.

- **Архитектор** (Cowork) — проектирует, формирует файлы задач в
  `handoff/tasks/`, коммитит и **пушит их сам**, ревьюит и **мержит PR**.
- **Исполнитель** (Claude Code, имеет git PAT) — подхватывает задачу из
  `handoff/tasks/`, работает в ветке `task/NNNN-slug`, пишет
  per-session отчёт в `docs/sessions/`, открывает PR, пушит.

Жёсткие правила процесса:

- **Исполнителю запрещено писать в Google Drive / вне git** — только
  push в GitHub.
- **Один таск = одна ветка = один PR.** Прямой push в `main` — только
  архитектор (таски/доки).
- **Кроссплатформенность.** Служебные операции — через
  `scripts/handoff.py` (чистый Python stdlib). Никаких bash-only шагов
  в обязательном пути.
- **Минимум ручных команд** — повторяемое выносить в `handoff.py`/CI.
- **Каждый завершённый таск оставляет отчёт** в `docs/sessions/`.
- **После каждого крупного раздела — комплексный аудит** в отдельной
  сессии (безопасность, архитектура, перф, тесты, зависимости,
  кроссплатформенность) → `handoff/audits/`.

Полный контракт — `handoff/README.md`; подробности — `docs/workflow.md`;
живое состояние — `handoff/STATE.md`.

## Полезные ссылки

- **Архитектура:** `docs/architecture.md`
- **Команды бота:** `docs/commands.md`
- **Принятые решения (30 ADR):** `docs/decisions.md`
- **Развёртывание:** `docs/deployment.md`
- **План этапов:** `TODO.md`
- **Workflow (контракт):** `handoff/README.md`
- **Workflow (подробно):** `docs/workflow.md`
- **Состояние проекта:** `handoff/STATE.md`
- **Доска задач:** `handoff/INDEX.md`

Прочитай эти файлы при первой сессии. В них зафиксированы все
договорённости.

## Стиль работы

- Один промпт — одна логическая единица, не "сделай всё"
- Перед изменением — прочитай существующий код, не пиши с нуля
  если уже есть
- Тесты обязательны для парсеров, валидаторов, schedule-расчётов,
  бизнес-логики в сервисах
- После значимых изменений — `ruff`, `mypy`, `pytest`
- Если архитектурный вопрос возник — не решай молча, вынеси как
  открытый вопрос в per-session отчёт (`docs/sessions/`) и в
  `handoff/STATE.md`
- Real-world тесты в Telegram критически важны — UX-баги часто
  не ловятся unit-тестами
