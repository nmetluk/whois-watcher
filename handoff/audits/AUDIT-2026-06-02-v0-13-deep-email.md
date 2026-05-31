# AUDIT-2026-06-02 — v0.13 deep email + on-demand views (ADR 040)

**Дата:** 2026-06-02 · **Объём:** углублённый почтовый слой + on-demand
deep-views в карточке `/whois` (ADR 040), TASK-0038…0042/0045/0046
· **Аудитор:** архитектор (Cowork) · **Коммит:** `4e7c30b` (main)

> Комплексный аудит в отдельной сессии после раздела v0.13 (конвенция
> CLAUDE.md). Серьёзность: 🔴 critical · 🟠 high · 🟡 medium · 🟢 low/info.
> 🔴/🟠 findings → отдельные таски.

## Резюме

Подсистема в целом здорова: deep-сбор строго **on-demand** (нет фонового
трафика/cron), миграция `email_deep_cache` — единственный alembic-head и
обратима, парсеры/резолвер — чистые с инъекцией DNS/HTTP, graceful degradation,
`html.escape` в форматтере, чувствительное не логируется. Покрытие тестами
выросло (deep-парсеры 22, форматтер 9 вкл. real-`t()`-guard, хэндлер 3) — и уже
поймало реальный краш (KeyError `exceeds`, закрыт в TASK-0046). **Главный риск —
новая SSRF-поверхность**: MTA-STS HTTPS-fetch ходит на user-influenced хост
`mta-sts.<domain>` без отсечения приватных/зарезервированных IP. Вердикт —
**fix-then-go**: закрыть 🟠 SSRF (+ слишком широкий TXT-матч, та же область)
перед тегом v0.13.0; 🟡/🟢 — fast-follow.

**Верификация:** локальный `pytest`/`ruff`/`mypy` в песочнице аудита не
запускается (нет Python 3.11, сеть ограничена). Состояние тестов — чтением +
зелёный CI PR'ов. Перед тегом — подтвердить зелёный CI.

## Безопасность

- **MTA-STS HTTPS-fetch** (`src/email_intel/deep_client.py::_fetch_mta_sts`):
  https-only, путь захардкожен (`/.well-known/mta-sts.txt`),
  `allow_redirects=False` (RFC 8461), лимит тела 16KB (`content.read(MAX)`),
  total timeout, никогда не raise. Тело не отдаётся юзеру сырым — парсится в
  mode/mx/max_age. ✅ хорошая база.
- **Логирование (ADR 019):** в deep-подсистеме логируется только `domain`
  (публично), статусы, тексты ошибок. Ни токенов, ни контактов, ни IP. ✅
- **html.escape** во всех ветках `format_email_deep` (sources/mx/rua/host/mode). ✅
- **Findings:**
  - 🟠 **SSRF через MTA-STS.** Хост `mta-sts.<domain>` формируется из
    пользовательского домена (бот публичный, любой может запросить deep-email
    для произвольного домена). Перед HTTPS GET **нет отсечения приватных/
    зарезервированных IP** — атакующий, контролирующий DNS своего домена, может
    указать `mta-sts.attacker.tld → 169.254.169.254 / 10.0.0.0/8 / 127.0.0.1` и
    заставить прод-хост ходить во внутреннюю сеть. Слепой вектор (тело не
    эхо-ится, https-only, no-redirect, size/timeout), но reachable=True/False +
    тайминги дают сигнал. → **TASK-0047** (пре-резолв хоста и отказ на
    RFC1918/loopback/link-local/ULA до GET; либо коннектор, блокирующий
    приватные IP).
  - 🟡 **Слишком широкий TXT-матч MTA-STS.** `if "v=sts1" in txt.lower() or
    "sts" in txt.lower()` — подстрока «sts» в любом TXT (`hosts`, `costs`,
    `tests`) ложно считается MTA-STS → лишний HTTPS-fetch и **расширение
    SSRF-триггера**. Чинить вместе с 0047: матчить `v=STSv1` корректно. → TASK-0047.

## Архитектура

Соответствует ADR 040.

- **On-demand only:** `check_email_deep` зарегистрирован в `functions`, но **не**
  в cron — фонового трафика нет (в отличие от периодического email-intel
  ADR 036). ✅
- **Переиспользование:** кнопка «Поддомены» ходит в существующий
  `check_subdomains`/кэш (ADR 037), не дублируя enumeration. ✅
- **Кэш deep** с коротким TTL (10 мин) + redis-guard — повтор не бьёт сеть. ✅
- **Findings:**
  - 🟡 (debt) общий on-demand-helper для кнопок карточки так и не вынесен —
    `_show_subdomains_from_whois_card` и `_show_deep_email_from_whois_card`
    дублируют паттерн (кэш→freshness→render | enqueue+«ищу»). Рекомендация из
    ревью 0042/0041 — вынести; не блокер. → TASK-0048.

## Производительность

- Горячий путь async (DNS — `dns.asyncresolver`, HTTP — `aiohttp`), нет
  блокировок loop, нет N+1. SPF-резолвер защищён от циклов + лимит lookups. ✅
- **Findings:**
  - 🟢 SPF: корневой lookup домена учитывается в лимите 10 (RFC 7208 §4.6.4
    корень не считает) — чуть строже, безопасно. → TASK-0048.
  - 🟢 SPF: механизм `all` (`-all`/`~all`) попадает в `sources`, хотя источником
    не является — косметика вывода. → TASK-0048.

## Тесты

- **Хорошо:** `test_deep_email.py` (22: SPF include/redirect/цикл/лимит,
  MTA-STS режимы, graceful), `test_format_email_deep.py` (9 вкл. **real-`t()`**
  guard на SPF exceeds), `test_whois_deep_email_button.py` (3: fresh→render,
  stale→enqueue, callback≤64), `test_check_email_deep_task.py`. Моки со
  `spec`/`autospec`. ✅
- **Anti-drift:** урок TASK-0046 (мок-`t()` спрятал KeyError) закреплён новым
  правилом в CLAUDE.md (рендер-тест форматтера через настоящий `t()`). ✅
- **Findings:**
  - 🟡 **callback_data guard только на коротком домене.** Кнопки `deep_email`/
    `subdomains` несут полный `domain` в `WhoisAction`; на длинном FQDN (карточка
    поддомена) пара action+domain может превысить 64 байта Telegram (урок
    TASK-0024). Guard-тест есть, но на `example.com`. Покрыть max-длинным
    доменом; при переполнении — перейти на idx/registrable. (Дефект общий для
    всех whois-card-действий — follow/unfollow/raw — не только v0.13.) → TASK-0048.

## Кроссплатформенность

- Служебка — `scripts/handoff.py` (stdlib). Подсистема путей ОС не трогает. ✅

## Документация

- ADR 040 в `docs/decisions.md` актуален и совпадает с кодом. ✅
- 🟢 **DMARC compact-текст** (`src/services/formatters.py`, инлайн TASK-0040):
  `t("commands.whois.email_no_dmarc").split(":")[-1].strip()` — хрупко при смене
  формата строки. Вынести в отдельный locale-ключ. → TASK-0048.

## Вердикт по тегу v0.13.0

**FIX-THEN-GO.** Фич-код полный и протестирован, краш (KeyError) уже закрыт.
**Перед тегом закрыть 🟠 TASK-0047** (SSRF MTA-STS + узкий TXT-матч) — публично
достижимый SSRF из прод-хоста во внутреннюю сеть нежелательно отпускать в
прод, фикс дешёвый и локальный. 🟡/🟢 (TASK-0048: callback-guard, on-demand-
helper, SPF-нит, DMARC-split) — fast-follow, можно после тега.

## Заведённые задачи по итогам

- **TASK-0047** 🟠 — MTA-STS hardening: отсечение приватных/зарезервированных IP
  до HTTPS GET (anti-SSRF) + корректный матч `v=STSv1` TXT.
- **TASK-0048** 🟡/🟢 — cleanup-пачка: callback-guard на длинном домене, общий
  on-demand-helper, SPF root-lookup/`all`-в-sources, DMARC compact через
  locale-ключ.
