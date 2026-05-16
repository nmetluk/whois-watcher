# CLAUDE.md

Этот файл — инструкция для Claude Code при работе с репозиторием `whois-watcher`. Прочитай его перед началом любой сессии.

## О проекте

**Whois Watcher** — публичный бесплатный Telegram-бот для проверки WHOIS-данных доменов и автоматических напоминаний об их истечении. Открытый исходный код, MIT-лицензия.

Целевая аудитория: владельцы доменов (от одного до десятков тысяч в портфеле), системные администраторы, домейнеры.

## Технологический стек

- **Python 3.11+** (async везде, синхронных вызовов в горячем пути быть не должно)
- **aiogram 3.x** — Telegram-бот через **webhook** (не long polling)
- **SQLAlchemy 2.0 async** + **asyncpg** — работа с БД
- **Alembic** — миграции
- **ARQ** — очередь задач на Redis
- **whoisit** — RDAP-клиент (основной путь)
- **python-whois** или прямые TCP-запросы — fallback для TLD без RDAP
- **idna** — поддержка IDN-доменов
- **pydantic v2** + **pydantic-settings** — конфиг и валидация
- **structlog** — логирование
- **Sentry SDK** — отлов ошибок (опционально)

**Инфраструктура:**
- PostgreSQL 16, Redis 7
- Docker + docker-compose
- Nginx как reverse proxy, Let's Encrypt для SSL

## Архитектурные принципы

См. `docs/architecture.md` для деталей. Кратко:

1. **Три независимых процесса:** бот (webhook-сервер), воркеры ARQ, планировщик
2. **Webhook**, не long polling — для масштабирования
3. **Общий кэш WHOIS** на всех пользователей через таблицу `whois_cache` — один домен = один запрос для всех
4. **Адаптивный TTL** проверок: чем ближе истечение, тем чаще проверяем (30 / 7 / 2 / 1 день)
5. **RDAP как основной протокол**, WHOIS на 43 порту как fallback
6. **Уведомления о смене статусов** доменов (регистратор, NS, status-флаги) заложены в архитектуру
7. **Админский канал** в Telegram для алертов и аномалий, с дедупликацией через Redis

## Структура проекта

```
whois-watcher/
├── CLAUDE.md                   # этот файл
├── README.md / README.en.md
├── LICENSE                     # MIT
├── CONTRIBUTING.md
├── PRIVACY.md
├── TODO.md                     # план этапов
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── pyproject.toml
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── alembic.ini
│
├── docs/
│   ├── architecture.md         # архитектура
│   ├── commands.md             # спецификация команд бота
│   ├── decisions.md            # лог принятых решений (ADR)
│   └── deployment.md
│
├── migrations/versions/        # Alembic миграции
│
├── src/
│   ├── main.py                 # entrypoint бота (webhook server)
│   ├── worker.py               # entrypoint воркеров ARQ
│   ├── config/
│   │   ├── settings.py         # pydantic-settings
│   │   └── limits.py           # лимиты
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── repositories/       # паттерн репозитория
│   ├── bot/
│   │   ├── app.py
│   │   ├── webhook.py
│   │   ├── handlers/           # один файл = одна или несколько связанных команд
│   │   ├── keyboards.py
│   │   ├── middlewares/
│   │   ├── states.py           # FSM
│   │   └── validators.py
│   ├── whois/
│   │   ├── client.py           # фасад: RDAP → WHOIS fallback
│   │   ├── rdap.py
│   │   ├── whois_protocol.py
│   │   ├── parser.py
│   │   ├── scheduler.py        # расчёт next_check_at
│   │   └── diff.py             # сравнение для уведомлений
│   ├── tasks/
│   │   ├── arq_config.py
│   │   ├── check_domain.py
│   │   ├── send_reminders.py
│   │   ├── send_change_notices.py
│   │   ├── cleanup.py
│   │   └── daily_stats.py
│   ├── services/
│   │   ├── users.py
│   │   ├── domains.py
│   │   ├── notifications.py
│   │   ├── csv_io.py
│   │   └── alerts.py           # отправка в админ-канал
│   ├── locales/
│   │   ├── ru.py
│   │   └── en.py
│   └── utils/
│       ├── idn.py
│       ├── timezone.py
│       └── formatting.py
│
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
│
└── scripts/
```

## Соглашения о коде

### Стиль
- **Форматирование:** `black` (line-length 100)
- **Линтер:** `ruff`
- **Type hints везде**, проверяется `mypy --strict` для `src/`
- **Docstrings:** Google-style, обязательны для публичных функций модулей `services/`, `whois/`, `tasks/`

### Async
- Все I/O-операции **только async**. Никаких `requests`, `time.sleep`, синхронных запросов к БД
- Если нужна CPU-bound операция — `asyncio.to_thread` или executor
- Не блокируем event loop никогда

### База данных
- Доступ к БД **только через репозитории** в `src/db/repositories/`. В хэндлерах и сервисах не должно быть прямого SQL или прямых ORM-запросов
- Миграции через Alembic, никаких `CREATE TABLE` в коде
- Foreign keys и индексы — обязательны
- `ON DELETE CASCADE` где уместно (например, `user_domains.user_id`)

### Telegram-бот
- Хэндлеры — тонкие, бизнес-логика в `services/`
- Все тексты сообщений — через локали (`src/locales/`), не хардкодить
- Inline-клавиатуры собирать в `src/bot/keyboards.py`
- FSM-состояния — в `src/bot/states.py`
- Валидация доменов — через `src/bot/validators.py`, не дублировать

### Логирование
- Через `structlog`
- Никогда не логировать: `BOT_TOKEN`, содержимое личных заметок пользователей, полные WHOIS-ответы с контактными данными
- Логировать: команды и их параметры (без чувствительного), ID пользователя, время операций, ошибки

### Конфиг
- Все настройки — через `pydantic-settings` в `src/config/settings.py`
- Лимиты — отдельный класс в `src/config/limits.py`, можно переопределять через env
- Никаких magic numbers в коде — выносить в конфиг

## Что НЕ делать

- ❌ Не коммитить `.env` (только `.env.example`)
- ❌ Не использовать синхронные библиотеки в хэндлерах и тасках
- ❌ Не писать SQL в хэндлерах — только через репозитории
- ❌ Не хардкодить тексты сообщений — только через локали
- ❌ Не использовать long polling — только webhook
- ❌ Не делать прямые HTTP-запросы к Telegram API — только через `aiogram.Bot`
- ❌ Не использовать `print()` — только `structlog`
- ❌ Не игнорировать type hints, не использовать `Any` без причины
- ❌ Не реализовывать платные тарифы — проект полностью бесплатный
- ❌ Не делать long polling даже временно для тестов — поднимать webhook через ngrok локально
- ❌ Не передавать `Bot` или `Dispatcher` через глобальные переменные — через DI

## Команды для разработки

```bash
# Установка зависимостей (включая dev-группу)
uv sync

# Запуск окружения
docker-compose up -d postgres redis
docker-compose --profile dev up

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

# Pre-commit на все файлы
pre-commit run --all-files
```

## Полезные ссылки в проекте

- **Архитектура:** `docs/architecture.md`
- **Команды бота:** `docs/commands.md`
- **Принятые решения и почему:** `docs/decisions.md`
- **План этапов:** `TODO.md`

Прочитай эти файлы при первой сессии. В них зафиксированы все договорённости, которых надо придерживаться.

## Стиль работы

- Один промпт — одна логическая единица (хэндлер, миграция, сервис), не "сделай всё"
- Перед изменением — прочитай существующий код, не пиши с нуля если уже есть
- Тесты — обязательно для парсеров, валидаторов, расчёта `next_check_at`, бизнес-логики в сервисах
- После значимых изменений — запускай линтер и тесты, прежде чем считать задачу выполненной
- Если архитектурный вопрос возник — не решай молча, спроси
