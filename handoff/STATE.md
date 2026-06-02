# STATE — живой снимок состояния проекта

> Носитель контекста между сессиями. Любой агент читает это вторым
> (после `handoff/README.md`), чтобы понять «где мы сейчас». Обновляется:
> архитектором — после merge крупных кусков; исполнителем — раздел
> «Последняя сессия». Дата последнего обновления — обязательна.

**Обновлено:** 2026-06-08 (v0.14 стабилизация: 0049–0053 влиты, аудит 0054 — вердикт GO; осталось TASK-0055 релиз v0.14.0) · **Релиз на main:** v0.13.0 · **Последний ADR:** 041

## Где мы сейчас

Бот в проде, четыре оси наблюдения работают: WHOIS, SSL, DNS (A/AAAA/NS),
RIR/ASN-фундамент. Введён новый рабочий процесс (handoff + PR), заменивший
ручной промпт + Telegram + монолитный SESSION_LOG.

## Активный план

Источник: `PLAN_subdomains_wishlist.md` в корне репо.

| Этап | Релиз | ADR | Состояние |
|------|-------|-----|-----------|
| Багфикс wishlist ↔ tracked | v0.8.1 | 034 ✅ | TASK-0001 done, **релиз v0.8.1 выпущен** |
| Поддомены / PSL / DNS-SSL у поддомена | v0.9.0 | 035 ✅ | код done; аудит выявил 🔴 в миграции → блок тега до TASK-0008 (0008-0011) |
| Email/policy-записи (MX/SPF/DKIM/DMARC) | v0.10 | 036 ✅ | **релиз v0.10.0 выпущен** (тег → b081c9a, TASK-0015…0018) |
| Instance-тег в админ-алертах | v0.9.3 | 019 | **релиз v0.9.3 выпущен** (hotfix от v0.9.2, TASK-0019); также в v0.10.0 |
| Subdomain enumeration (CT-логи/crt.sh, on-demand) | v0.11 | 037 ✅ | дизайн готов; исполнение TASK-0022…0024 |
| Мониторинг новых поддоменов + алерты | v0.12 | 038 ✅ | TASK-0027/0028/0029 done (PR #19/#20/#21); осталось TASK-0030 (аудит) → релиз v0.12.0 |
| Багфикс wishlist — независимые списки + кнопка удаления | v0.11.1 | 039 ✅ | TASK-0031/0032 done, **релиз v0.11.1 выпущен** |
| Deep email + on-demand views (MX инлайн, кнопки) | v0.13 | 040 ✅ | **релиз v0.13.0 выпущен** (TASK-0038…0042/0045–0047 + 0044; все блокеры аудита закрыты) |

ADR 034 и 035 дописаны в `docs/decisions.md`. Цепочка зависимостей
v0.9.0: 0002→0003→0004→0005→0006 (аудит); все depend на TASK-0001.

## Ключевые активные решения

- Wishlist-фикс (ADR 034, v0.8.1): `/add` на wishlist-домен **тихо промоутит**
  в tracked. **Уточнено ADR 039 (v0.11.1):** один флаг `is_wishlist` на общей
  строке делал списки взаимоисключающими (домен пропадал из `/list` при
  добавлении в wishlist). Решение — **отдельная таблица `wishlist`**, списки
  полностью независимы; домен может быть в обоих. Плюс парная кнопка
  «убрать из wishlist» в карточке `/whois`.
- Поддомены: WHOIS берётся у registrable-родителя (eTLD+1 через
  **tldextract**), DNS/SSL — у самого поддомена. PSL в **оффлайн-режиме**
  с bundled snapshot (без сети в горячем пути), `include_psl_private_domains=False`.
- Процесс: GitHub = источник правды; исполнитель пишет только в git;
  один таск = ветка `task/NNNN-slug` = PR; merge — архитектор.

## Следующий шаг

🟢 **ТЕКУЩЕЕ (2026-05-30):** На main готова вся подсистема **email-intel**
(ADR 036, TASK-0015…0018: схема, парсеры MX/SPF/DKIM/DMARC, ARQ-задачи/
scheduler/уведомления, UX `/whois` + toggle'ы + локали) и **instance-тег**
админ-алертов (TASK-0019). main pyproject пока 0.9.2 (версия легитимно
отстаёт от фич).

Выпущен **hotfix v0.9.3** (тег `v0.9.3` → `e055d67`) — ТОЛЬКО instance-тег,
отдельной веткой `release/0.9.3` от `v0.9.2` (без email-intel/миграции, чтобы
ops-фикс можно было катить в прод изолированно).

✅ **Релиз v0.10.0** (`b081c9a`): email-intel (MX/SPF/DKIM/DMARC, ADR 036).
✅ **Релиз v0.10.1** (`772bf58`): hotfix — кнопка «Мои домены» в `/start`
падала (`cmd_list` без `redis`/`state`, дрейф сигнатуры, TASK-0020) +
**anti-drift конвенция** в `CLAUDE.md`/шаблоне аудита (моки со `spec`/`autospec`,
grep вызовов при смене сигнатуры, миграции на Postgres).

✅ **ADR 037 написан** (TASK-0021, design — done): subdomain enumeration через
**crt.sh**, v0.11 = **on-demand** команда `/subdomains` (read-only список +
opt-in через `/add`, авто-добавления нет, лимит 50k); запрос через ARQ + кэш
`subdomain_enum_cache` + graceful degradation. Периодический мониторинг новых
поддоменов + алерты → v0.12 (ADR 038).

✅ **TASK-0022 смержен** (PR #15 → `940eea1`): схема `subdomain_enum_cache`
(PK registrable, JSONB subdomains, scheduling/reachability/failure-поля),
модель, репозиторий, миграция от head `20260529_email_intel` (дефолты
SQL-литералами now()/0, урок TASK-0008). Round-trip покрыт CI-smoke на Postgres.

✅ **TASK-0023 смержен** (PR #16 → merge-commit `8ed53cd`): `src/subdomains/`
(client/parser/scheduler/types) + ARQ-задача `check_subdomains` (redis-guard
`ctx[sync_redis]`, upsert/update_fail, graceful degradation), регистрация в
`arq_config` (functions, on-demand без cron). Парсер: dedup/wildcard/IDN-punycode/
registrable-фильтр, 19 юнит-тестов. Ревью-долги вынесены в **TASK-0025**.

✅ **TASK-0024 смержен** (PR #17 → merge-commit `57e4e41`): команда
`/subdomains` — список поддоменов (имена в тексте + на кнопках) + opt-in через
`DomainService.add_for_user`. Прошёл два круга ревью: callback переведён на
`idx` (фикс переполнения лимита Telegram 64б — на длинных FQDN было до 65+б,
стало ≤45б), статусы `added/added_pending/promoted` = успех (track и track_all),
убран неиспользуемый `redis`-параметр. Тесты: guard `callback≤64`, success-пути
`added_pending`/`promoted`, track_all `promoted`.

✅ **TASK-0025 смержен** (PR #18 → merge-commit `79c1f7f`): fast-follow по
долгам 0023 — юнит-тесты `scheduler` (11, все TTL-ветки + tz-guard),
`update_fail` → UPSERT (первый фейл персистится: `fail_count=1`/инкремент,
`is_reachable=False`), `error_type` унифицирован (`parse_error`/`unavailable`),
`QUERY_TIMEOUT` удалён. Ревью v1: исправлен off-by-one в `check_subdomains`
(`fail_count=current+1` — счётчик ПОСЛЕ фейла) + guard-тесты на первый/второй
фейл (`next_check_at ≈ 1ч`).

**🟢 Вся v0.11 (ADR 037, subdomain enumeration) закрыта на main**: ~~0022~~ ✅
(схема) → ~~0023~~ ✅ (crt.sh-клиент/парсер/ARQ) → ~~0024~~ ✅ (UX /subdomains
+ opt-in) → ~~0025~~ ✅ (fast-follow). Открытых задач — 0. `handoff.py validate`
зелёный.

✅ **Релиз v0.11.0 выпущен** (тег `v0.11.0` → `0d175ec`): bump pyproject
`0.10.1→0.11.0`, секция `[0.11.0]` в `CHANGELOG.md`. Аннотированный тег на
текущем main. Осталось — **деплой** (`bash scripts/deploy.sh`).

✅ **ADR 038 написан** (TASK-0026, design — done): периодический мониторинг
новых/исчезнувших поддоменов поверх `subdomain_enum_cache` (ADR 037), по образцу
SSL/DNS. Решения: per-domain `track_subdomains` (**default false** — явный
opt-in, crt.sh-нагрузка), сигнал new+removed (`notify_subdomain_new/removed`,
оба default true), частота per-user (`User.subdomain_check_interval_days`=7 +
per-domain override), scheduler по образцу `ssl_scheduler_tick`
(`next_check_at = now + min(интервалов подписчиков)`, floor 1д), diff
`compute_subdomain_diff` (baseline `old=None`→пусто), fan-out
`notify_subdomain_changes`.

Заведены таски v0.12: **TASK-0027** (схема toggles+interval) → **0028**
(diff + scheduler + интеграция в check_subdomains) → **0029** (уведомления +
UX toggles/FSM-интервал + локали) → **0030** (комплексный аудит). Цепочка
последовательная. После 0030 — релиз v0.12.0.

✅ **Релиз v0.11.1 выпущен** (тег `v0.11.1` → `9b0c940`): багфикс wishlist по
отзывам (ADR 039). Корень — `is_wishlist` как флаг на общей строке
`user_domains` делал tracking и wishlist взаимоисключающими (домен пропадал из
`/list` при добавлении в wishlist). Решение — отдельная таблица `wishlist`
(полная независимость) + кнопка «убрать из wishlist» в `/whois`. **TASK-0031**
(схема + миграция переноса + drop `is_wishlist`) и **TASK-0032** (развязка всех
вызовов + UX-кнопка + локали) смержены одним PR **#22** (merge `47b038c`).
Миграция `20260530_wishlist` переносит данные и дропает колонку, downgrade
обратим. CI зелёный (в т.ч. migration round-trip на Postgres).

**Следующий шаг**: **деплой v0.11.1** (`bash scripts/deploy.sh`) — выкатить
багфикс в прод. Затем разблокировать стек v0.12 (см. ниже).

✅ **v0.12 код влит на main** (2026-05-31): мониторинг новых/исчезнувших
поддоменов (ADR 038). Стек 0027→0028→0029 ребейзнут на пост-v0.11.1 main и
смержен по очереди: **TASK-0027** (PR #19 → `f59720d`, схема toggles +
`User.subdomain_check_interval_days`, миграция `20260530_subdomain_monitor`),
**TASK-0028** (PR #20 → `dd06625`, `compute_subdomain_diff` baseline-safe +
scheduler floor 1д + интеграция в `check_subdomains`), **TASK-0029** (PR #21 →
`f87632b`, fan-out `notify_subdomain_changes` + toggle'ы/FSM в `/whois` + локали).
Alembic-head единственный (`20260530_subdomain_monitor`). По ходу ревью
поймано и исправлено: multi-head (down_revision миграции не был перецелен на
`20260530_wishlist`) и пустое уведомление (гард по `len(lines)`, а не по toggle'ам).

✅ **TASK-0030 — аудит v0.12 проведён** (2026-05-31, отчёт
`handoff/audits/AUDIT-2026-05-31-v0-12-subdomain-monitor.md`). Рантайм-код
здоров (миграция single-head/обратима, нагрузка на crt.sh ограничена, diff
baseline-safe, нет sensitive-логирования, hot path async). Вердикт —
**fix-then-go**: главный риск в тестах, а не в коде. Заведены: 🟠 **TASK-0033**
(тесты fan-out `notify_subdomain_changes` — дедуп/mute/toggle'ы/blocked/журнал),
🟠 **TASK-0034** (тесты success+diff→enqueue и baseline-no-enqueue в
`check_subdomains`), 🟡 **TASK-0035** (N+1 в fan-out + ordering-зависимый дедуп
toggle'ов — follow-up, не блокер).

✅ **Блокеры аудита закрыты** (2026-05-31): 🟠 **TASK-0033** (PR #23 → тесты
fan-out `notify_subdomain_changes`: дедуп/mute/toggle'ы/blocked/Forbidden/
обрезка/журнал) и 🟠 **TASK-0034** (PR #24 → тесты success+diff→enqueue и
baseline-no-enqueue в `check_subdomains`) смержены в main архитектором. Оба
покрытия — со `spec`/`autospec` (anti-drift), ассерты сверены с локалями.

**Следующий шаг (релизная цепочка v0.12.0):** по решению владельца
(2026-05-31) **все** фиксы аудита влиты в v0.12.0. Смержены архитектором:
🟠 **0033** (PR #23) ✅, 🟠 **0034** (PR #24) ✅, 🟡 **0035** (PR #25 →
устранён N+1 + ordering-independent агрегация toggle'ов, проверено код-ревью:
один батчевый `get_by_ids`, `effective_notify_* = any(...)`, any-muted
исключает юзера; 0033-инварианты сохранены) ✅. ✅ **Все фиксы аудита смержены** (2026-05-31): 🟠 0033 (PR #23), 🟠 0034
(PR #24), 🟡 0035 (PR #25), 🟢 **0037** (PR #26 → html.escape в нотификациях +
FSM-cap интервала через `Limits`; прошёл второй круг ревью — добавлен
FSM-cap тест). **Все блокеры v0.12.0 закрыты.**

✅ **Релиз v0.12.0 выпущен и задеплоен** (2026-05-31): TASK-0036 (PR #27)
смержен архитектором, `pyproject` 0.12.0, секция CHANGELOG `[0.12.0]`,
аннотированный тег `v0.12.0` запушен, **GitHub Release опубликован владельцем**,
**деплой в прод выполнен владельцем**.

✅ **Новый раздел спроектирован — v0.13.0, ADR 040** (2026-05-31, решение
владельца): углублённый почтовый слой + on-demand deep-views в карточке
`/whois`. Объём: deep email (SPF include-резолвинг + лимит 10 lookups,
MTA-STS, TLS-RPT, DANE/TLSA, BIMI), инлайн **MX + краткий статус** SPF/DMARC
в первом сообщении, кнопки «Глубокий e-mail» и «Поддомены» (on-demand, «⏳
ищу…»), фикс «свежести» карточки (пустой кэш → плейсхолдер, а не пусто — это и
была причина «не вижу почту»).

Заведена цепочка: **TASK-0038** (deep-парсеры/коллекторы) → **0039** (on-demand
ARQ + кэш `email_deep_cache`) → **0040** (инлайн MX+статус + фикс свежести) →
**0041** (кнопка «Глубокий e-mail») → **0042** (кнопка «Поддомены»,
переиспользует ADR 037) → **0043** (аудит v0.13) → **0044** (релиз v0.13.0).
Цепочка последовательная (depends_on проставлены).

✅ **v0.13 фич-код влит и протестирован** (2026-06-02): 0038 (deep-парсеры) →
0039 (ARQ+кэш `email_deep_cache`) → 0040 (инлайн MX+freshness) → 0041
(кнопка deep-email + `format_email_deep`) → 0042 (кнопка «Поддомены») → 0045
(anti-drift) → 0046 (тесты + фикс краша KeyError `exceeds`). Все смержены.

✅ **Аудит v0.13 проведён** (TASK-0043, архитектор, отчёт
`handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`). Вердикт **fix-then-go**.
Подсистема здорова (on-demand only, single alembic-head, graceful, html.escape,
тесты со spec). Заведены: 🟠 **TASK-0047** (SSRF MTA-STS: отсечение приватных IP
до HTTPS GET + строгий TXT-матч `v=STSv1`) — **блокер тега**; 🟡/🟢 **TASK-0048**
(callback-guard, on-demand-helper, SPF/DMARC ниты) — fast-follow v0.13.1.
В CLAUDE.md добавлено правило: хотя бы один рендер-тест форматтера через
настоящий `t()` (урок 0046).

✅ **TASK-0047 закрыт и смержен** (2026-06-03): MTA-STS anti-SSRF +
DNS-rebinding (кастомный `TCPConnector`/`_SafeMtaStsResolver` + `close()`),
строгий TXT-матч `v=STSv1`, независимые A/AAAA. Happy-path тест исполнитель не
вывез (затык в моке aiohttp); архитектор применил корректный тест и смержил.

✅ **Релиз v0.13.0 выпущен** (TASK-0044): bump 0.12.0→0.13.0, CHANGELOG `[0.13.0]`,
тег `v0.13.0`, подготовка к деплою. Все блокеры аудита (0043/0047) закрыты;
фича-код + тесты + anti-drift в main.

✅ **TASK-0048 закрыт** (PR #33, cleanup: callback→registrable для
subdomains/deep_email, общий `_on_demand_card_view`, SPF lookup-счёт по RFC 7208
+ фильтр `all` из sources, DMARC compact через locale-ключ). Стале-ассерт
`-all in sources` в `test_spf_recursive_include` поправлен архитектором при
мерже (исполнитель не прогнал полный pytest — суит был бы красный).

✅ **Спроектирован v0.14 — стабилизация/тех-долг** (2026-06-04, выбор владельца).
ADR 041 (FSM `MemoryStorage`→`RedisStorage`). Заведены таски: **0049**
(html.escape во всех 8 нотификаторах), **0050** (FSM→Redis, ADR 041), **0051**
(DENIC-значок «expiry скрыт реестром»), **0052** (интеграционные тесты ARQ на
pytest-docker + бенчмарк scheduler), **0053** (доки: MIGRATIONS.md + нормы
алертов), **0054** (аудит v0.14), **0055** (релиз v0.14.0). 0049–0053
независимы; 0054 depends на них; 0055 на 0054.

✅ **v0.14 стабилизация — код готов и проаудирован** (2026-06-08): смержены
**0049** (html.escape во всех нотификациях), **0050** (FSM→Redis, ADR 041),
**0051** (DENIC-значок), **0052** (интеграц-тесты ARQ на Postgres+Redis),
**0053** (доки). **Аудит 0054** —
`handoff/audits/AUDIT-2026-06-08-v0-14-stabilization.md`, вердикт **GO**
(🔴/🟠 нет; 🟢 → TASK-0056, опц. v0.14.1).

✅ **Релиз v0.14.0 выпущен** (2026-06-08, TASK-0055, архитектором напрямую):
bump `pyproject` 0.13.0→0.14.0, секция CHANGELOG `[0.14.0]`, тег `v0.14.0`.
v0.13.0 в проде (задеплоен ранее). Деплой v0.14.0 — `bash scripts/deploy.sh`
после зелёного CI.

**Следующий шаг:** деплой v0.14.0; опц. 🟢 **TASK-0056** (v0.14.1 cleanup).
Дальше — крупные фичи v1.0 (web-дашборд,
публичный API, орг-аккаунты, Prometheus).

---

История ниже — для контекста (аудит v0.9.0 и патчи v0.9.1/v0.9.2):

Аудит v0.9.0 (TASK-0006/0007) завершён. Отчёт + дополнение:
`handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`.

✅ **Релиз v0.9.1 выпущен** (тег `v0.9.1` → `b1a6cd9`): миграция registrable
в починенном виде, CI smoke-test миграций, mypy зелёный. Тег `v0.9.0` оставлен
как есть (исторически содержит дефектную миграцию). Критичная часть аудита
закрыта. Смержены:
**TASK-0008** (PR #6) — миграция `..._0000` починена in-place (`''`, валидный
default + DROP DEFAULT; SQL валиден для Postgres); **TASK-0013** (PR #8) — mypy
narrowing в whois.py, шаг `mypy` снова зелёный; **TASK-0009** (PR #7) — smoke-test
миграций на Postgres в CI + `env.py disable_existing_loggers=False`, тест
изолирован через subprocess. CI на main зелёный.

История фиксов (для контекста): первичный аудит занизил баг миграции до medium;
повторный эскалировал до 🔴. PR #5 (band-aid `..._0001`) отклонён. В ходе
TASK-0009 всплыли две неочевидные связки через глобальное состояние:
alembic `fileConfig` гасил логгер локалей (→ caplog-тест) и in-process
`asyncio.run`+asyncpg тёк сокетами/event loop (→ `filterwarnings=error` ронял
сторонний тест) — обе закрыты.

⚠️ **Тег `v0.9.0` уже опубликован и указывает на коммит `c3abd78` со СЛОМАННОЙ
миграцией** (фиксы влиты позже). Переписывать опубликованный тег не будем —
выпускаем патч **v0.9.1** на текущий main (**TASK-0014**: bump pyproject 0.9.0→
0.9.1, секция CHANGELOG [0.9.1], исправить ложную фразу в [0.9.0], тег v0.9.1).
Прод (по этому STATE) на v0.8.1 — сломанный v0.9.0, скорее всего, не
деплоился.

✅ **Релиз v0.9.2 выпущен** (тег `v0.9.2` → `1ea7170`): TASK-0010 (tldextract
`cache_dir=None` + реальный no-network тест) и TASK-0011 (доки tldextract/PSL).
Весь раздел v0.9.x закрыт.

✅ **ADR 036 написан** (TASK-0012, design — done). Решения: v0.10 = только
email/policy-записи (**MX/SPF/DKIM/DMARC**, сбор + базовая диагностика),
параллельная подсистема `email_intel_cache` + per-domain toggle'ы (стиль
ADR 029); subdomain enumeration вынесен в **v0.11** (источник — CT-логи/crt.sh,
будущий ADR 037).

Заведены исполнительские таски v0.10: **TASK-0015** (схема/миграция) →
**0016** (парсеры MX/SPF/DKIM/DMARC + diff) → **0017** (ARQ-задачи/scheduler/
уведомления) → **0018** (UX `/whois` + toggle'ы + локали). Цепочка
последовательная (каждый depends на предыдущем). После 0018 — релиз v0.10.0.

## Последняя сессия

**2026-05-29 — повторный аудит v0.9.0 (эскалация)**

После первичного аудита (TASK-0006/0007, вывод «один medium») по запросу
владельца проведён повторный проход. Offline-рендером alembic подтверждено,
что миграция registrable_domain **не применяется на Postgres** — finding
эскалирован medium → 🔴 critical. TASK-0008 переписан и расширен (починка
миграции, не косметика). Заведены TASK-0009/0010/0011 (CI-тест миграций,
tldextract hardening, доки) и forward-таск TASK-0012 (ADR 036).
Дополнение к отчёту — в `handoff/audits/AUDIT-2026-05-29-v0-9-0-poddomeny-psl.md`.

## Открытые вопросы

Закрыты дефолтами в ADR 035: PSL — оффлайн bundled snapshot без сетевого
автофетча; `include_psl_private_domains=False`; поддомены в `/list` со
значком `↳`. Новых открытых вопросов нет.
