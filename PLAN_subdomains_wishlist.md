# План доработок: wishlist-фикс, поддомены, domain intelligence

> Планирующий документ (архитектор). Источник истины по итогам — ADR в
> `docs/decisions.md`. Этот файл — спека для исполняющего Claude Code:
> что делать, в каком порядке, какие инварианты и тесты. Дробить на
> отдельные промпты по подэтапам (одна логическая единица — один промпт).

Базис: `main` = **v0.8.0**, `Unreleased` пуст, последний ADR — **033**.
Новые ADR: **034** (wishlist-фикс), **035** (поддомены/PSL), **036**
(domain intelligence, roadmap).

| Этап | Релиз | ADR | Суть |
|------|-------|-----|------|
| 1 | v0.8.1 | 034 | Багфикс: wishlist ↔ tracked, авто-промоут |
| 2 | v0.9.0 | 035 | PSL/tldextract, поддомены: WHOIS у родителя + DNS/SSL у поддомена |
| 3 | v0.10+ | 036 | MX/SPF/DKIM/DMARC, перечисление поддоменов (roadmap, design-only) |

---

## Этап 1 — Багфикс wishlist ↔ tracked (v0.8.1, ADR 034)

### Симптом
Домен, добавленный в wishlist, не виден в `/list`, и его нельзя
перевести в отслеживание: `/add` отвечает «уже отслеживается», но домен
нигде не показывается.

### Корень
`UserDomain` — одна таблица и для tracked, и для wishlist (флаг
`is_wishlist`). Пути рассинхронизированы:

- `DomainService.add_for_user` (`src/services/domains.py`) проверяет
  `DomainRepository.exists()` — она **не различает** `is_wishlist`.
  Для wishlist-строки возвращает `already_tracked` и **не снимает**
  `is_wishlist`, флаги `notify_*` остаются выключенными.
- `list_with_whois_filtered` с `include_wishlist=False` (дефолт `/list`)
  **прячет** строки `is_wishlist=True`.

Итог: строка существует, но невидима в обоих UX и не конвертируется.
Тот же дефект бьёт по кнопке `track` из wishlist-уведомления
(`on_wishlist_action` → `add_for_user`), если строка ещё не удалена.

### Решение (выбрано: авто-промоут, разделы раздельны)
`/add` на wishlist-домен **тихо конвертирует** его в обычное
отслеживание. Разделы `/list` и `/wishlist` остаются строго
раздельными (никаких бейджей в `/list`).

### Изменения

**`src/db/repositories/domains.py`**
- Новый метод `promote_from_wishlist(user_id, domain) -> bool`: один
  `UPDATE ... WHERE user_id, domain, is_wishlist=True` →
  `is_wishlist=False` + восстановить дефолты уведомлений
  (`DEFAULT_NOTIFICATION_FLAGS`). Возвращает `True`, если строка была
  wishlist и обновлена.
- Расширить `DEFAULT_NOTIFICATION_FLAGS` либо явно перечислить в
  `promote_from_wishlist` все актуальные toggle'ы, которые гасит
  `add_to_wishlist`: `notify_expiry`, `notify_ns_change`,
  `notify_registrar_change`, `notify_status_change`. (SSL/DNS toggle'ы
  `add_to_wishlist` не трогает — они остаются на server_default `true`,
  их восстанавливать не нужно.)
- Заменить точечную семантику: `exists()` оставить, но `add_for_user`
  должен сначала получить строку через `get_for_user`, чтобы прочитать
  `is_wishlist`.

**`src/services/domains.py` → `add_for_user`**
- Вместо `if await exists(...)` → `row = await get_for_user(...)`.
- Если `row is None` → текущая ветка вставки (без изменений).
- Если `row` есть и `row.is_wishlist` → вызвать `promote_from_wishlist`,
  вернуть новый статус `AddDomainResult(status="promoted", ...)`.
- Если `row` есть и не wishlist → как сейчас, `already_tracked`.

**`src/services/results.py`**
- Добавить литерал `"promoted"` в тип статуса `AddDomainResult`.

**`src/bot/handlers/add_remove.py`**
- Обработать ветку `status == "promoted"` → новый локаль-ключ
  `commands.add.promoted_from_wishlist`.

**`src/locales/{ru,en}.py`**
- `commands.add.promoted_from_wishlist` — «Домен {domain} переведён из
  списка ожидания в отслеживание» / EN-аналог.

**Миграция:** не требуется (схема не меняется).

### Инварианты (защитить тестами)
- `add_for_user` на wishlist-строку → `is_wishlist=False`, флаги
  `notify_*` = дефолты, статус `promoted`.
- После промоута домен виден в `/list` (filter `all`) и **не виден** в
  `/wishlist` (filter `wishlist`).
- `add_for_user` на обычную tracked-строку → `already_tracked` (без
  изменения флагов).
- Промоут идемпотентен: повторный `/add` → `already_tracked`.
- Лимит `max_domains_per_user` при промоуте не пересчитывается
  (строка уже учтена в `count_by_user`).

### Тесты
- `tests/unit/` — `promote_from_wishlist` (репозиторий, на реальной БД
  через фикстуры), `add_for_user` все ветки (None / wishlist / tracked).
- Регрессия на путь кнопки `track` из `on_wishlist_action`.

---

## Этап 2 — Поддомены и зоны 3-го уровня (v0.9.0, ADR 035)

### Симптом
`/add a.pinbetting.ru` → «домен свободен», хотя `pinbetting.ru` занят.
Валидатор синтаксический, PSL нет; WHOIS уходит по полному поддомену,
получает «not found» → ложная «свобода».

### Решение (выбрано)
- **WHOIS/expiry** — по registrable-домену (eTLD+1, напр. `pinbetting.ru`).
- **DNS (A/AAAA/NS) и SSL** — по самому поддомену (`a.pinbetting.ru`).
- Разделение «юзерских» уровней 3–4 от публичных зон (`org.uk`, `co.uk`,
  `com.br`, …) — через **PSL**, источник: **tldextract** (встроенный
  PSL + автообновление).

### Новая зависимость
- `pyproject.toml`: добавить `tldextract>=5,<6`. Обновить `uv.lock`
  (`uv sync`). mypy: `tldextract` имеет типы; при нужде добавить в
  `[[tool.mypy.overrides]]`.
- tldextract по умолчанию ходит в сеть за свежим PSL и кэширует.
  В нашем окружении сетевой доступ ограничен и не хочется I/O в горячем
  пути → инициализировать `TLDExtract(suffix_list_urls=..., cache_dir=...)`
  с **bundled snapshot** как fallback и явным контролем обновления
  (cron/ручной), чтобы парс домена был **синхронным и без сети**.
  Решение зафиксировать в ADR 035.

### Новый модуль `src/utils/domains.py`
Чистые функции, без сети/БД (как `validators.py`):
- `split_domain(domain) -> DomainParts(subdomain, registrable, suffix)`.
- `registrable_domain(domain) -> str` — eTLD+1 (`a.pinbetting.ru` →
  `pinbetting.ru`; `a.foo.org.uk` → `foo.org.uk`).
- `is_subdomain(domain) -> bool` — непустая `subdomain`-часть **относительно
  registrable** (т.е. `www.foo.org.uk` — поддомен, `foo.org.uk` — нет).
- `is_public_suffix_only(domain) -> bool` — ввод == публичный суффикс
  (`co.uk`, `org.uk`) → не registrable, отклонять.
- Все работают на punycode-форме (после `normalize_domain`).

### Изменения схемы (`src/db/models.py` + Alembic)
`UserDomain`:
- `registrable_domain: Mapped[str]` (Text, NOT NULL, индекс) — eTLD+1,
  вычисляется при добавлении. Для apex == `domain`.
- `is_subdomain: Mapped[bool]` (server_default `false`).

WHOIS-стек джойнится по registrable, DNS/SSL — по `domain`.

**Миграция:**
- Добавить колонки.
- Backfill: `registrable_domain = domain`, `is_subdomain = false` для
  всех существующих строк (на момент миграции поддоменов в проде нет —
  проверить; если есть, backfill пересчитать batch-скриптом).
- Индекс `ix_user_domains_registrable`.

### Маршрутизация WHOIS на родителя
Сейчас связка идёт по `WhoisCache.domain == UserDomain.domain`. Меняем
на registrable там, где это WHOIS:
- `list_with_whois*`, `iter_all_with_whois`, `get_user_stats`:
  `outerjoin(WhoisCache, WhoisCache.domain == UserDomain.registrable_domain)`.
- `whois_cache` остаётся keyed по registrable → несколько поддоменов
  одного родителя **делят один** whois_cache-row (модель общего кэша,
  ADR 006, сохраняется).
- WHOIS scheduler/facade ставит проверку по registrable, не по поддомену.
- `notify_expiry` для поддомена работает от whois_cache родителя.

DNS/SSL — без изменений ключа: `dns_cache`/`ssl_cache` keyed по
`UserDomain.domain` (т.е. по поддомену), проверки идут по поддомену.
Это именно то, что нужно: A/AAAA/NS и сертификат — у поддомена свои.

### UX
- **`/whois a.pinbetting.ru`**: баннер «🔎 `a.pinbetting.ru` — поддомен
  `pinbetting.ru`. WHOIS показан для родителя.» + карточка родителя
  (expiry/registrar/status). DNS- и SSL-блоки — для **поддомена**.
  Inline-кнопки: «Следить за DNS», «Следить за SSL» поддомена.
- **`/add a.pinbetting.ru`**: создаёт строку с `domain=a.pinbetting.ru`,
  `registrable_domain=pinbetting.ru`, `is_subdomain=true`,
  `track_dns=true`, `track_ssl=true`, `notify_expiry` привязан к родителю.
- **Ввод чистого публичного суффикса** (`co.uk`) → `errors.invalid_domain`
  с пояснением «это зона, не домен».
- Карточка `/list` для поддомена: помечать значком (напр. `↳`) и
  показывать expiry родителя.

### `src/bot/validators.py`
- Оставить `is_valid_domain` синтаксическим, но добавить отклонение
  `is_public_suffix_only`.
- Не смешивать PSL-логику в `validators`; PSL — в `utils/domains.py`,
  валидатор зовёт хелпер.

### Локали
- `whois.subdomain_banner`, `commands.add.subdomain_added`,
  `errors.public_suffix_not_domain`, подпись `↳` в списке. ru + en.

### Инварианты (тесты)
- `registrable_domain`: table-driven — `a.pinbetting.ru→pinbetting.ru`,
  `pinbetting.ru→pinbetting.ru`, `a.b.foo.co.uk→foo.co.uk`,
  `foo.org.uk→foo.org.uk`, IDN (`xn--…`), `рф`-зоны.
- `is_subdomain`: `www.foo.org.uk→True`, `foo.org.uk→False`,
  `pinbetting.ru→False`, `a.pinbetting.ru→True`.
- `is_public_suffix_only`: `co.uk→True`, `org.uk→True`, `ru→True`,
  `pinbetting.ru→False`.
- `/add` поддомена → корректные `registrable_domain`/`is_subdomain`,
  DNS/SSL keyed по поддомену, WHOIS-джойн ловит row родителя.
- `/whois` поддомена → баннер + карточка родителя; «свободен» **не**
  показывается, если родитель занят.
- Два поддомена одного родителя делят один whois_cache-row.
- tldextract парсит **без сети** (тест на отсутствие сетевого вызова).

### Риски / нюансы
- tldextract и сеть: жёстко зафиксировать оффлайн-режим + bundled PSL,
  иначе блокировки/латентность в хэндлере. → ADR 035.
- Backfill `registrable_domain` для существующих строк — проверить, что
  поддоменов в проде нет; иначе batch-пересчёт.
- `private domains` PSL (напр. `blogspot.com`): решить, считать ли их
  суффиксом. По умолчанию tldextract включает private list — для нашей
  задачи (registrable у регистратора) лучше `include_psl_private_domains=False`.
  Зафиксировать в ADR.

---

## Этап 3 — Domain intelligence (roadmap, v0.10+, ADR 036, design-only)

Профессиональные инструменты для админов. Дизайн сейчас, реализация —
отдельными релизами. `dnspython` уже в зависимостях; `check_dns` уже
**запрашивает** MX (`RECORD_TYPES`), но не сохраняет.

### 3a. MX + email-auth (ближайший, v0.10.0)
- Хранить MX в `dns_cache` (новые колонки `mx_records`,
  `mx_last_changed_at`). Уведомление о смене MX (новый toggle
  `notify_dns_mx_change`).
- Валидация email-политик через TXT-резолв (dnspython):
  - **SPF** — `v=spf1` в TXT apex; парс механизмов, флаг наличия/`-all`.
  - **DMARC** — TXT `_dmarc.<domain>`; политика `p=none/quarantine/reject`.
  - **DKIM** — TXT `<selector>._domainkey.<domain>`; селектор не выводится
    из DNS напрямую → стартуем с набора популярных селекторов
    (`default`, `google`, `selector1/2`, `k1`, `mail`) + ручной ввод
    селектора пользователем.
- Блок «📧 Почта/Email-auth» в карточке `/whois`: MX, SPF/DMARC/DKIM
  статус (✓/⚠️/✗) с краткой оценкой посты.
- Уведомления о деградации политики (например, DMARC `reject→none`).

### 3b. Перечисление поддоменов (v0.11+, тяжёлый)
- Источник: **CT-логи** (crt.sh / Certificate Transparency) — пассивно,
  без брутфорса. Опционально DNS-перебор популярных имён.
- Новая подсистема `src/subdomains/` (по образцу `dns_monitor/`):
  своя таблица `discovered_subdomains`, свой scheduler/TTL, rate-limits
  к внешним источникам, opt-in на домен.
- Уведомления: «обнаружен новый поддомен», «сменилась A-запись
  поддомена». Связать со слежением DNS из Этапа 2.
- Объём большой → отдельный ADR-черновик и поэтапная декомпозиция перед
  стартом. Здесь только фиксируем направление.

### Вопросы к проработке перед стартом 3b
- Лимиты/квоты на перечисление (защита от тысяч поддоменов в портфеле).
- Приватность: CT-логи публичны, но storage discovered-данных — описать
  в `PRIVACY.md`.
- Нагрузка на внешние источники и кэширование.

---

## Порядок работ (для исполняющего Claude Code)

1. **v0.8.1 / ADR 034** — багфикс wishlist. Один промпт: репозиторий +
   сервис + локали + тесты. Без миграции. → `ruff`, `mypy`, `pytest`,
   запись в `SESSION_LOG.md`, бамп `pyproject.toml` до 0.8.1, CHANGELOG.
2. **v0.9.0 / ADR 035** — поддомены. Дробить:
   - 2a: dep `tldextract` + `src/utils/domains.py` + тесты (чистая логика).
   - 2b: миграция схемы + backfill + правка WHOIS-джойнов.
   - 2c: маршрутизация WHOIS-родителя в facade/scheduler.
   - 2d: UX `/whois` + `/add` + `/list` + локали + тесты.
3. **ADR 036** — записать дизайн 3a/3b как принятое направление; код —
   отдельными релизами.

## Конвенции (напоминание из CLAUDE.md)
- async-only; БД только через репозитории; тексты — только локали;
  миграции — Alembic (никаких `CREATE TABLE` в коде); type hints,
  `mypy --strict`; тесты обязательны для парсеров/валидаторов/логики;
  не реализовывать платные тарифы.

## Открытые вопросы (вынести в SESSION_LOG.md при старте)
- ADR 035: режим tldextract — bundled snapshot + ручное/cron обновление
  PSL vs сетевой автофетч. Рекомендация: оффлайн + snapshot.
- ADR 035: `include_psl_private_domains` — рекомендация `False`.
- Этап 2: показывать ли поддомены в общем `/list` со значком `↳` или
  только в карточке родителя (текущая рекомендация — показывать `↳`).
