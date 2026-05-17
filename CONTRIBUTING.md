# Вклад в проект

Спасибо за интерес к Whois Watcher! Этот документ описывает, как сделать
свой вклад.

## Как помочь

- **Сообщить о баге** — создайте issue с описанием проблемы и шагами
  воспроизведения
- **Предложить фичу** — сначала issue для обсуждения, потом PR
- **Улучшить документацию** — README, `docs/`, комментарии в коде
- **Перевод** на другой язык — см. `src/locales/`
- **Pull Request** — процесс ниже

## Прежде чем писать код

1. Прочитайте `CLAUDE.md` — там зафиксированы все архитектурные решения
   и соглашения
2. Прочитайте `docs/architecture.md` и `docs/decisions.md`
3. Проверьте `TODO.md` — возможно, задача уже в плане
4. Откройте issue для обсуждения, если вносите значимые изменения

## Локальное окружение

Нужны: Python 3.11+, [uv](https://github.com/astral-sh/uv), Docker с Compose.

```bash
git clone https://github.com/nmetluk/whois-watcher.git
cd whois-watcher

cp .env.example .env
# заполните BOT_TOKEN, WEBHOOK_BASE_URL, WEBHOOK_SECRET, POSTGRES_PASSWORD

uv sync                              # установка зависимостей в .venv/
docker compose up -d postgres redis  # БД и Redis
uv run alembic upgrade head          # миграции

uv run python -m src.main            # запустить бота
uv run python -m src.worker          # в другом терминале — воркер
```

## Процесс Pull Request

1. **Форкните** репозиторий
2. **Создайте ветку** от `main`: `feature/имя-фичи` или `fix/имя-бага`
3. **Пишите код** по соглашениям ниже
4. **Запустите** проверки локально (см. далее)
5. **Откройте PR** с описанием изменений
6. Дождитесь ревью и CI (GitHub Actions)

## Соглашения о коде

- **Форматирование:** `black` (line-length 100)
- **Линтер:** `ruff` (конфиг в `pyproject.toml`)
- **Type hints везде**, `mypy --strict` для `src/`
- **Docstrings** Google-style для публичных функций в `services/`,
  `whois/`, `tasks/`
- **Async везде**, никаких блокирующих вызовов
- **Доступ к БД** только через репозитории в `src/db/repositories/`
- **Тексты сообщений** только через локали в `src/locales/`
- **Тесты обязательны** для парсеров, валидаторов, бизнес-логики
- **Логирование** через `structlog`, секреты в логи не попадают (см.
  `src/observability.py` `before_send`)

## Запуск проверок локально

```bash
# Все проверки сразу (через pre-commit)
uv run pre-commit run --all-files

# По отдельности
uv run ruff check src tests
uv run black --check src tests
uv run mypy src
uv run pytest
```

CI запускает то же самое в [GitHub Actions](.github/workflows/ci.yml) на
каждый push и pull request.

## Структура коммитов

Используем [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — новая фича
- `fix:` — исправление бага
- `docs:` — документация
- `refactor:` — рефакторинг без изменения поведения
- `test:` — добавление/изменение тестов
- `chore:` — рутина (зависимости, конфиги)
- `ci:` — изменения CI/CD

Пример: `feat: granular notification settings per domain`.

Тело коммита — на русском или английском, на ваш выбор. Главное —
объяснять «почему», а не пересказывать diff.

## Локализация

Если добавляете новый текст:

1. Добавьте ключ в `src/locales/ru.py` **и** `src/locales/en.py`
2. Используйте через `t(key, lang)`
3. Никогда не хардкодьте текст в хэндлерах

## Self-hosting

Если запускаете бот на своём сервере, для обновления используйте
один скрипт:

```bash
bash scripts/deploy.sh
```

Скрипт проверит чистоту дерева, подтянет последние коммиты, регенерирует
build info, пересоберёт образы, накатит миграции и убедится, что все
контейнеры стартовали healthy. Полные инструкции по первичному
развёртыванию — в [docs/deployment.md](docs/deployment.md).

## Безопасность

Если нашли уязвимость — **не открывайте публичный issue**. Свяжитесь
приватно через GitHub Security Advisory:
https://github.com/nmetluk/whois-watcher/security/advisories/new

## Лицензия

Контрибьютя в проект, вы соглашаетесь с тем, что ваш код будет
распространяться под лицензией MIT.
