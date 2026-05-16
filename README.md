# Whois Watcher

[![CI](https://github.com/nmetluk/whois-watcher/actions/workflows/ci.yml/badge.svg)](https://github.com/nmetluk/whois-watcher/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

[English version →](README.en.md)

Бесплатный Telegram-бот, который следит за вашими доменами и присылает
напоминания об истечении регистрации. Бот спрашивает WHOIS у регистратора,
сравнивает с прошлым состоянием и шлёт уведомления, когда что-то меняется
или подходит срок продления.

## Возможности

- Проверка WHOIS любого домена через RDAP, с fallback на WHOIS:43
- Слежение за списком доменов (до 50 000 на пользователя)
- Напоминания об истечении за 30, 7 и 1 день — интервалы настраиваются
- Уведомления о смене регистратора, NS-серверов, статусов
- Импорт списка доменов из TXT/CSV (`/download`) и экспорт в CSV (`/csv`)
- Поддержка IDN (`.рф`, `.中国` и т. п.) — на стороне ввода и в выгрузке
- Два языка интерфейса: русский и английский, автоопределение
- Часовые пояса пользователя, настраиваемое время рассылки
- Полностью бесплатно, без рекламы и тарифов

## Быстрый старт

### Для пользователей

Откройте [@whois_watcher_bot](https://t.me/whois_watcher_bot) в Telegram
и отправьте `/start`. Никаких регистраций, оплат, личных данных — только
домены, за которыми хотите следить.

### Для разработчиков

Нужны: Python 3.11+, [uv](https://github.com/astral-sh/uv),
Docker с Compose.

```bash
git clone https://github.com/nmetluk/whois-watcher.git
cd whois-watcher

cp .env.example .env
# заполните BOT_TOKEN (получить у @BotFather),
# WEBHOOK_BASE_URL и WEBHOOK_SECRET

uv sync
docker compose up -d postgres redis
uv run alembic upgrade head

# запустить процессы локально (для прода — docker compose up -d)
uv run python -m src.main           # бот (webhook-сервер)
uv run python -m src.worker         # воркер и планировщик
```

Полная инструкция деплоя на VPS — в [docs/deployment.md](docs/deployment.md).

## Команды бота

| Команда | Что делает |
|---------|------------|
| `/start` | Начало работы |
| `/whois <домен>` | Показать WHOIS |
| `/add <домен>` | Добавить на слежение |
| `/rmv <домен>` | Снять со слежения |
| `/list` | Список доменов с фильтрами и пагинацией |
| `/csv` | Экспорт всех доменов в CSV |
| `/download` | Массовый импорт из TXT/CSV |
| `/notify <домен>` / `/unnotify <домен>` | Включить/выключить уведомления |
| `/settings` | Часовой пояс, язык, дни напоминаний |
| `/stats` | Сводка по портфелю |
| `/check <домен>` | Принудительная проверка (раз в сутки) |
| `/help` | Справка |
| `/delete_me` | Удалить все мои данные |

Полная спецификация поведения — в [docs/commands.md](docs/commands.md).

## Документация

- [Архитектура](docs/architecture.md) — три процесса, кэш, адаптивный TTL
- [Команды бота](docs/commands.md) — спецификация UX
- [Развёртывание](docs/deployment.md) — пошагово на VPS
- [Принятые решения (ADR)](docs/decisions.md) — почему так, а не иначе
- [Политика конфиденциальности](PRIVACY.md)
- [Вклад в проект](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Стек

- **Python 3.11+**, asyncio везде
- **aiogram 3.x** через webhook (не long polling)
- **SQLAlchemy 2.0 async** + asyncpg, Alembic для миграций
- **ARQ** — очередь задач на Redis
- **whoisit** для RDAP, нативный TCP-клиент для WHOIS:43 с referral following
- **pydantic v2** + pydantic-settings
- **structlog** — JSON-логи в production, ConsoleRenderer в dev
- **Sentry** SDK (опционально) с фильтром секретов в `before_send`
- PostgreSQL 16, Redis 7, Docker Compose, Nginx + Let's Encrypt

## Лицензия

MIT. См. [LICENSE](LICENSE).

## Вклад

Issues, PR и обсуждения приветствуются — см. [CONTRIBUTING.md](CONTRIBUTING.md).
Если нашли уязвимость, пишите приватно (контакт в `CONTRIBUTING.md`),
не открывайте публичный issue.
