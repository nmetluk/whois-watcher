# План разработки

Каждый этап — рабочий бот с расширяющимся функционалом. Двигаемся последовательно, не перескакиваем.

## Этап 0: Инфраструктура репозитория

- [ ] Создан репозиторий `whois-watcher` на GitHub, MIT-лицензия
- [ ] Коммит проектной документации (`CLAUDE.md`, `docs/`, `TODO.md`)
- [ ] `README.md` (заглушка с описанием)
- [ ] `.gitignore`, `.env.example`
- [ ] `pyproject.toml` (Poetry или PEP 621) со всеми зависимостями
- [ ] `Dockerfile` для бота и воркера
- [ ] `docker-compose.yml` (postgres, redis, bot, worker, scheduler)
- [ ] `docker-compose.dev.yml` (с volume-маунтами для разработки)
- [ ] `.pre-commit-config.yaml` (black, ruff, detect-secrets)
- [ ] Базовая структура папок `src/`, `tests/`, `migrations/`, `scripts/`

## Этап 1: Фундамент

- [ ] `src/config/settings.py` — pydantic-settings, все переменные
- [ ] `src/config/limits.py` — класс с лимитами
- [ ] `src/db/models.py` — все SQLAlchemy-модели (users, user_domains, whois_cache, sent_notifications, domain_changes, system_events)
- [ ] `alembic.ini` + initial migration
- [ ] `src/db/session.py` — async engine, session factory
- [ ] `src/db/repositories/` — UserRepository, DomainRepository, WhoisCacheRepository, NotificationRepository
- [ ] `src/locales/ru.py`, `src/locales/en.py` — словари ключей
- [ ] `src/utils/idn.py` — конвертация IDN ↔ punycode
- [ ] `src/utils/timezone.py` — работа с tz
- [ ] `src/utils/formatting.py` — форматирование дат, дней
- [ ] `src/bot/validators.py` — валидация доменов

## Этап 2: Бот без WHOIS-логики

- [ ] `src/bot/app.py` — сборка Bot и Dispatcher
- [ ] `src/bot/webhook.py` — FastAPI/aiohttp webhook-сервер
- [ ] `src/main.py` — entrypoint
- [ ] `src/bot/middlewares/user_register.py` — регистрация пользователя при первом сообщении
- [ ] `src/bot/middlewares/locale.py` — определение языка
- [ ] `src/bot/middlewares/rate_limit.py` — общий rate limit
- [ ] `src/bot/keyboards.py` — все inline-клавиатуры
- [ ] `src/bot/states.py` — FSM-состояния
- [ ] Хэндлеры:
  - [ ] `/start` (`src/bot/handlers/start.py`)
  - [ ] `/help`, `/cancel` (`src/bot/handlers/help_cancel.py`)
  - [ ] `/settings` (`src/bot/handlers/settings.py`)
  - [ ] `/stats` (`src/bot/handlers/stats.py`)
  - [ ] `/delete_me`, `/delete_me_confirm` (`src/bot/handlers/delete_me.py`)
  - [ ] Заглушки для остальных команд (отвечают "будет позже")
- [ ] Юнит-тесты на валидаторы, форматтеры, idn

## Этап 3: WHOIS-ядро

- [ ] `src/whois/rdap.py` — RDAP-клиент через `whoisit`
- [ ] `src/whois/whois_protocol.py` — TCP-запросы на 43 порт
- [ ] `src/whois/parser.py` — нормализация ответов в единую структуру
- [ ] `src/whois/client.py` — фасад: RDAP → WHOIS fallback
- [ ] `src/whois/scheduler.py` — расчёт `next_check_at` по адаптивному TTL
- [ ] `src/whois/diff.py` — сравнение старого и нового состояния
- [ ] Юнит-тесты на парсер (на фикстурах ответов разных регистраторов), scheduler, diff

## Этап 4: Слежение за доменами

- [ ] `src/services/domains.py` — бизнес-логика добавления/удаления
- [ ] `src/services/users.py` — бизнес-логика пользователя
- [ ] Хэндлеры:
  - [ ] `/whois <domain>` (`src/bot/handlers/whois.py`)
  - [ ] `/add <domain>` (`src/bot/handlers/add_remove.py`)
  - [ ] `/rmv <domain>` (там же)
  - [ ] `/list` (`src/bot/handlers/list_domains.py`) с пагинацией и фильтрами
  - [ ] `/check <domain>` (там же или отдельный файл)
  - [ ] Обработка плоского домена (`src/bot/handlers/plain_domain.py`)
  - [ ] Callback-хэндлеры для inline-кнопок
- [ ] `src/tasks/arq_config.py` — конфиг ARQ
- [ ] `src/tasks/check_domain.py` — задача проверки одного домена
- [ ] `src/worker.py` — entrypoint воркера
- [ ] Cron-задача в ARQ для отбора `next_check_at <= now()`
- [ ] Интеграционный тест: добавить домен → дождаться обновления в БД

## Этап 5: Уведомления

- [ ] `src/services/notifications.py` — выбор кому что слать, дедупликация
- [ ] `src/tasks/send_reminders.py` — рассылка по `notify_days`
- [ ] `src/tasks/send_change_notices.py` — уведомления о смене статусов
- [ ] `src/tasks/send_problem_notices.py` — уведомления о длительных WHOIS-проблемах
- [ ] Cron-задача (каждый час) для отбора пользователей с локальным `notify_at_hour`
- [ ] Логика `sent_notifications` с UNIQUE-защитой
- [ ] Хэндлеры:
  - [ ] `/notify <domain>` и `/unnotify <domain>` (`src/bot/handlers/notifications.py`)

## Этап 6: Импорт/экспорт и админ-канал

- [ ] `src/services/csv_io.py` — генерация и парсинг CSV
- [ ] Хэндлеры:
  - [ ] `/csv` (`src/bot/handlers/csv_export.py`)
  - [ ] `/download` (`src/bot/handlers/download.py`) с FSM
- [ ] `src/services/alerts.py` — отправка в админ-канал с дедупликацией
- [ ] Интеграция алертов в критичные места кода
- [ ] `src/tasks/daily_stats.py` — ежедневная сводка
- [ ] `src/tasks/cleanup.py` — чистка `whois_cache` (сироты), `system_events` (старые)

## Этап 7: Production-готовность

- [ ] Sentry SDK
- [ ] structlog с JSON-выводом в production
- [ ] Метрики (опционально: Prometheus exporter)
- [ ] Healthcheck endpoint
- [ ] Полный README.md (RU) с описанием, скриншотами, установкой
- [ ] `README.en.md` — английская версия
- [ ] `CONTRIBUTING.md`
- [ ] `PRIVACY.md`
- [ ] GitHub Actions:
  - [ ] CI: ruff, black, mypy, pytest на каждый PR
  - [ ] Docker build для тегов
- [ ] `docs/deployment.md` — пошаговая инструкция деплоя на VPS
- [ ] Релиз v0.1.0

## После MVP (будущие версии)

- [ ] Гранулярная настройка типов уведомлений на домен через `/settings`
- [ ] Поиск по списку (`/find <pattern>` или фильтр в `/list`)
- [ ] Уведомления об освобождении домена (для свободных)
- [ ] Регистрация домена через бот (партнёрка с регистраторами)
- [ ] Мониторинг SSL-сертификатов доменов
- [ ] Мониторинг доступности сайта (HTTP-проверки)
- [ ] Web-интерфейс (личный кабинет)
- [ ] Публичная API
- [ ] Командные/корпоративные аккаунты (если появится спрос)
