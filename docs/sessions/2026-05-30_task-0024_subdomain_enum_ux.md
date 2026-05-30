# TASK-0024: UX-команда /subdomains + opt-in (ADR 037)

**Дата:** 2026-05-30
**Статус:** ✅ completed
**Ветка:** task/0024-subdomain-enum-ux

## Выполненные работы

### 1. Хэндлер `/subdomains`
Создан `src/bot/handlers/subdomains.py`:

- **Команда `/subdomains <domain>`** — поиск поддоменов через crt.sh
- Валидация домена (ADR 035, guard на публичный суффикс)
- Запрос по registrable-домену
- Проверка кэша `subdomain_enum_cache`:
  - Свежий (≤7 дней) — рендер списка с кнопками
  - Устарел/пуст — enqueue ARQ-задачи `check_subdomains`, ответ «ищу…»
- Лимит отображения 50 поддоменов с понятным сообщением

### 2. Callback-хэндлеры
Три callback для inline-кнопок:

- **`refresh`** — заново запустить проверку (enqueue `check_subdomains`)
- **`track`** — отслеживать конкретный поддомен (идёт через `/add` путь)
- **`track_all`** — отслеживать все найденные поддомены с лимитом 50k

### 3. Inline-клавиатура
Добавлен `SubdomainAction` CallbackData и `subdomains_keyboard`:
- Кнопка на каждый поддомен «📌 Отслеживать»
- Кнопка «📌 Отслеживать все»
- Кнопка «🔄 Обновить»

### 4. Локали
Добавлены строки в `src/locales/ru.py` и `en.py`:
- `commands.subdomains.searching` — «ищу…»
- `commands.subdomains.header` — список с количеством/датой
- `commands.subdomains.empty` — ничего не найдено
- `commands.subdomains.no_cache` — кэш пуст
- `commands.subdomains.unavailable` — crt.sh недоступен
- `commands.subdomains.invalid_domain` — некорректный домен
- `commands.subdomains.public_suffix` — публичный суффикс
- `commands.subdomains.button_track`/`button_track_all`/`button_refresh`
- `commands.subdomains.too_many` — превышен лимит
- `commands.subdomains.track_all_result` — статистика добавления

Обновлены `help.body` в обеих локалях (добавлена команда).

### 5. Регистрация роутера
- Добавлен в `src/bot/handlers/__init__.py` (ROUTERS)
- Обновлён `docs/commands.md`:
  - Добавлена команда в BotFather список
  - Добавлен раздел с описанием `/subdomains`

### 6. Тесты
Создан `tests/unit/test_subdomains_handler.py`:
- Валидация домена (без аргументов, публичный суффикс)
- Кэш — свежесть (функция `_is_cache_fresh`)
- Callback-хэндлеры (refresh, track, track_all)

### 7. Проверки
- ✅ ruff check — чисто
- ✅ black --check — чисто
- ✅ mypy src/bot/handlers/subdomains.py — чисто
- ✅ pytest tests/unit/test_subdomains_handler.py — 7 passed
- ✅ pytest tests/unit/ — 849 passed

## Технические детали

- TTL кэша для «свежести» — 7 дней (соответствует scheduler)
- Lim `_MAX_DISPLAY_SUBDOMAINS = 50`
- Opt-in идёт через существующий `/add` путь (DomainService)
- Лимит 50k соблюдён при «track all»
- Mypy `# type: ignore[union-attr]` на `callback.message.edit_text`

## Примечания

- Команда не падает на мусорном вводе
- Graceful degradation при недоступности crt.sh
- Кнопки используют keyword-only параметр `lang` в клавиатуре
- Инвариант `test_all_ru_keys_present_in_en` не нарушен

## Следующие шаги

- Реальный тест в Telegram для проверки UX
- TASK-0022-0024 вместе → релиз v0.11.0
