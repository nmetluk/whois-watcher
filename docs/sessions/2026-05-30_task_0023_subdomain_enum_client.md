# TASK-0023: crt.sh-клиент и enumeration (ADR 037)

**Дата:** 2026-05-30
**Статус:** ✅ completed
**Ветка:** task/0023-subdomain-enum-client

## Выполненные работы

### 1. Пакет `src/subdomains/`
Создан новый пакет по образцу `src/email_intel/`:

- **`types.py`** — типы данных:
  - `SubdomainEnumResult` — результат enumeration
  - `SubdomainEnumError` — ошибка (graceful degradation)
  - `SubdomainEnumResultOrError` — union

- **`parser.py`** — чистая функция `parse_crtsh_response`:
  - Развертывание многострочных `name_value`
  - Punycode-конверсия (сначала idna.encode, затем lowercase)
  - Фильтрация wildcard (`*.`)
  - Отбрасывание самого registrable
  - Только поддомены запрошенного registrable

- **`scheduler.py`** — adaptive TTL:
  - Успех с поддоменами → 7 дней
  - Успех без поддоменов → 30 дней
  - Ошибка (fail_count < 3) → 1 час
  - Ошибка (fail_count ≥ 3) → 1 день

- **`client.py`** — async HTTP-клиент:
  - GET `https://crt.sh/?q=%25.<registrable>&output=json`
  - Таймаут 45s (graceful degradation)
  - Обработка 429 rate-limit
  - Обработка сетевых ошибок без исключений

### 2. ARQ-задача `check_subdomains`
Создан `src/tasks/check_subdomains.py`:
- Redis-guard `subdomain_check_in_progress:<registrable>`
- Успех → UPSERT в `subdomain_enum_cache`
- Ошибка → `update_fail` + пересчёт `next_check_at`
- Возвращает результат для хэндлера

### 3. Регистрация в ARQ
- Добавлена в `src/tasks/arq_config.py` (_build_functions)

### 4. Тесты
Создан `tests/unit/test_subdomains_parser.py`:
- 19 тестов на парсер
- Покрыты: dedup, wildcard, IDN/punycode, пустой ответ, registrable exclusion

### 5. Проверки
- ✅ ruff check — чисто
- ✅ black --check — чисто
- ✅ mypy src/subdomains/ --strict — чисто
- ✅ pytest — 19 passed

## Примечания

- Порядок punycode → lowercase важен для корректной работы с IDN
- `_is_subdomain_of` сохраняет lower() для defensive programming
- Таймауты crt.sh увеличены (30/45s) — сервис бывает медленным

## Следующие шаги

- TASK-0024 — UX-команда `/subdomains` + opt-in
