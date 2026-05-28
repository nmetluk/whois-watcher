# Сессия 2026-05-28 — TASK-0002 (PSL: tldextract + domains.py)

**Задача:** TASK-0002 — PSL: зависимость tldextract + src/utils/domains.py (подэтап 2a)
**Ветка:** task/0002-psl-utils-domains
**Выполнено:** полный цикл разработки, тесты зелёные

## Цель

Добавить определение registrable-домена (eTLD+1) и классификацию поддоменов/публичных суффиксов через Public Suffix List. Никаких сетевых вызовов в горячем пути.

## Реализация

### Изменённые файлы

1. **`pyproject.toml`**
   - Добавлена зависимость `tldextract>=5.0,<6.0`
   - Добавлен mypy override для `tldextract.*`

2. **`src/utils/domains.py`** (новый)
   - Чистые функции, без сети/БД
   - Инициализация `TLDExtract` с bundled snapshot, `suffix_list_urls=()` — оффлайн-режим
   - `DomainParts(subdomain, registrable, suffix)` — dataclass для компонентов домена
   - `split_domain(domain) -> DomainParts` — разбор через PSL
   - `registrable_domain(domain) -> str` — eTLD+1
   - `is_subdomain(domain) -> bool` — проверка на поддомен
   - `is_public_suffix_only(domain) -> bool` — проверка на публичный суффикс
   - Все функции работают на punycode-форме (после `utils.idn.normalize_domain`)

3. **`src/bot/validators.py`**
   - `is_valid_domain` дополнительно отклоняет публичные суффиксы через PSL
   - Импорт `is_public_suffix_only` из `src.utils.domains`

4. **`tests/unit/test_utils_domains.py`** (новый)
   - Table-driven тесты для всех инвариантов
   - Проверка на популярных доменах, ccTLD (co.uk, org.uk), IDN (пример.рф)
   - Класс `TestOfflineMode` — проверка что tldextract не ходит в сеть

5. **`tests/unit/test_validators.py`**
   - Добавлены кейсы: `co.uk`, `org.uk`, `ru`, `com` — публичные суффиксы теперь отклоняются

### Инварианты (защищены тестами)

- `registrable_domain`: `a.pinbetting.ru→pinbetting.ru`, `pinbetting.ru→pinbetting.ru`, `a.b.foo.co.uk→foo.co.uk`, `foo.org.uk→foo.org.uk`, IDN
- `is_subdomain`: `www.foo.org.uk→True`, `foo.org.uk→False`, `pinbetting.ru→False`, `a.pinbetting.ru→True`
- `is_public_suffix_only`: `co.uk→True`, `org.uk→True`, `ru→True`, `pinbetting.ru→False`
- tldextract **не ходит в сеть** — используется bundled snapshot

### Проверки

- `ruff check src/` — OK
- `black --check src/` — OK
- `mypy src/` — OK
- `pytest` — 687 passed
- `python scripts/handoff.py validate` — TODO (проверить после открытия PR)

## Definition of Done

- [x] `tldextract` добавлен, `uv.lock` обновлён
- [x] `src/utils/domains.py` реализован, оффлайн-режим PSL
- [x] Тесты по инвариантам зелёные; `pytest` полный прогон
- [x] `ruff` / `black --check` / `mypy src` чисто
- [x] Per-session отчёт создан
- [ ] PR открыт (следующий шаг)
- [ ] CI зелёный (после открытия PR)

## Следующие шаги

- Открыть PR: `git push origin task/0002-psl-utils-domains`
- После мержа обновить `handoff/TASK-0002-*.md` (статус, PR, session)
