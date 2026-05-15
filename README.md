# Whois Watcher

🌐 Публичный бесплатный Telegram-бот для проверки WHOIS-данных доменов и автоматических напоминаний об их истечении.

[English version](README.en.md)

## Возможности

- 🔍 **Проверка WHOIS** любого домена через RDAP/WHOIS
- 👁 **Слежение** за неограниченным* числом ваших доменов
- 🔔 **Напоминания** об истечении регистрации (за 30, 7, 1 день — настраивается)
- 📋 **Список доменов** с фильтрами и сортировкой
- 📥 **Массовый импорт** доменов из файла (TXT/CSV)
- 📤 **Экспорт** в CSV
- ⚡ **Уведомления** о смене регистратора, NS-серверов, статусов
- 🌍 **Часовые пояса** и настраиваемое время рассылки
- 🇷🇺🇬🇧 **Два языка** интерфейса (русский и английский)
- 🆓 **Полностью бесплатно**, открытый исходный код

\* до 50 000 доменов на одного пользователя

## Статус

🚧 В активной разработке. См. [TODO.md](TODO.md) для плана и текущего прогресса.

## Архитектура

Три независимых процесса: бот (webhook-сервер aiogram), воркеры (ARQ для фоновых задач), планировщик (cron). Общаются через PostgreSQL и Redis. Общий кэш WHOIS на всех пользователей с адаптивным TTL.

Подробности — в [docs/architecture.md](docs/architecture.md).

## Стек

- Python 3.11+, aiogram 3.x (webhook)
- SQLAlchemy 2.0 async + asyncpg, Alembic
- ARQ, whoisit, idna
- PostgreSQL 16, Redis 7
- Docker + docker-compose, Nginx, Let's Encrypt

## Быстрый старт (разработка)

```bash
git clone https://github.com/your-username/whois-watcher.git
cd whois-watcher

cp .env.example .env
# заполните BOT_TOKEN и остальные переменные

docker-compose up -d postgres redis
poetry install
poetry run alembic upgrade head
poetry run python -m src.main
```

Подробности — в [docs/deployment.md](docs/deployment.md) (TODO).

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начало работы |
| `/whois <домен>` | Проверить WHOIS |
| `/add <домен>` | Добавить на слежение |
| `/rmv <домен>` | Снять со слежения |
| `/list` | Список ваших доменов |
| `/csv` | Экспорт в CSV |
| `/download` | Массовый импорт |
| `/notify <домен>` / `/unnotify <домен>` | Управление уведомлениями |
| `/settings` | Настройки |
| `/stats` | Статистика |
| `/check <домен>` | Принудительная проверка |
| `/help` | Справка |
| `/delete_me` | Удалить все мои данные |

Полная спецификация — в [docs/commands.md](docs/commands.md).

## Вклад в проект

См. [CONTRIBUTING.md](CONTRIBUTING.md) (TODO).

## Конфиденциальность

См. [PRIVACY.md](PRIVACY.md) (TODO).

## Лицензия

MIT. См. [LICENSE](LICENSE).
