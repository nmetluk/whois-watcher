# STATE — живой снимок состояния проекта

> Носитель контекста между сессиями. Любой агент читает это вторым
> (после `handoff/README.md`), чтобы понять «где мы сейчас». Обновляется:
> архитектором — после merge крупных кусков; исполнителем — раздел
> «Последняя сессия». Дата последнего обновления — обязательна.

**Обновлено:** 2026-06-10 (✅ security-аудит v0.16 webapp (0071): FIX-THEN-GO, 2🔴+5🟠 → таски 0081–0084) · **Релиз на main:** v0.15.2 · **Последний ADR:** 043

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

✅ **Спроектирован v0.15 — админ/ops-слой** (2026-06-08, выбор владельца, план
изменён). **ADR 042.** Решения: бекапы Postgres ежечасно `pg_dump` локально
(ротация 36, verify); ежечасный ops-отчёт в админ-канал (статистика + статус
бекапа); дневной графический отчёт 21:00 МСК (matplotlib) + старая текстовая
сводка 06:00 остаётся; аудит-лог `audit_log` (retention 90д). Таски:
**0057** (схема audit_log) → **0058** (бекапы) → **0059** (ежечасный отчёт) →
**0060** (дневные графики) → **0061** (вписать audit() + retention) → **0062**
(аудит v0.15) → **0063** (релиз). 0057/0058/0060 независимы.

🔜 **Следующий этап после v0.15 — WebApp-слой (ADR 043, TASK-0064):** дизайн от
дизайнера (ссылка в теле TASK-0064), забрать + спроектировать когда дойдём.

✅ **v0.15 админ/ops-слой — код готов и проаудирован** (2026-06-09): смержены
0057 (audit_log + `audit()`), 0058 (ежечасный pg_dump, ротация 36, verify),
0059 (ops-отчёт + статус бекапа), 0060 (дневные графики 21:00 МСК), 0061
(audit() в инцидент-точки + retention 90д). Конфликты `arq_config`/settings/.env
разрешены union. **Аудит 0062** (`AUDIT-2026-06-09-v0-15-admin-ops.md`) — вердикт
**GO**, 🔴/🟠 нет; 🟢 → TASK-0065 (офсайт/шифрование бекапов). Этот слой закрывает
пробел, вызвавший недавнюю потерю данных (бекапов не было).

✅ **Релиз v0.15.0 выпущен** (2026-06-09, TASK-0063, архитектором): bump
0.14.0→0.15.0, CHANGELOG `[0.15.0]`, тег `v0.15.0`.

✅ **WebApp спроектирован — v0.16, ADR 043** (2026-06-09). Дизайн дизайнера
импортирован в `design/webapp/v1/` (Telegram mini-app, PIN Voice, 6 экранов, RU).
Решения: расширяем aiohttp-webhook под-роутером `/api/webapp`; auth через
Telegram `initData` (HMAC + auth_date TTL, stateless); фронт React+Vite (токены
PIN Voice as-is), nginx (static + proxy); health-score на бэке; PII-скоуп.
Таски: **0066** (backend auth+read API) → **0067** (frontend foundation) →
**0068** (список+карточка) → **0069** (дашборд/календарь/алерты/«Ещё») →
**0070** (write-действия) → **0071** (аудит, security-heavy) → **0072** (релиз).
Можно отгрузить read-only (0066–0069) первой вехой, действия (0070) — следом.

⚠️ **Найдено при подготовке тасков:** модели «групп/тегов» в БД нет, а дизайн её
требует → заведён **TASK-0073** (схема групп) как зависимость грейс-фул-
группировки. initData-валидация в 0066 уточнена точным алгоритмом Telegram.

⚠️ **v0.16: интеграция сорвана — возврат на консолидацию (2026-06-09).**
Исполнитель сдал 0066–0070, но как **5 независимых снимков от main**, которые
переписывают одни и те же фронт-файлы по-разному (не git-стек). Нет цельной
собираемой ветки: 0070 откатывает фронт до фундамента без экранов, 0069 без
части компонентов 0068, backend дублирован в 0066/0070. Слить нельзя, аудит
бессмысленен. **0066–0070 → blocked**, заведён **TASK-0074** (консолидация в
ОДНУ сборочную ветку: backend read+write+auth + полный консистентный фронт,
`vite build` + `pytest` зелёные). 0073 (схема групп) по-прежнему нужен.
Урок процесса: webapp надо было вести стеком (один таск = ветка от свежего
main/предыдущего), а не параллельными снимками.

✅ **TASK-0074 консолидация смержена** (2026-06-09, PR #49 → `fa83c87`).
Одна сборочная ветка от свежего main: backend `src/bot/webapp/` (auth.py —
точный initData HMAC + TTL replay-guard; api.py — read-роуты + write
toggle/add/remove/wishlist/settings с **ownership-скоупом по `user_id`** и
`audit()` на мутациях; `add` через `DomainService` для лимитов; health_score;
mount в webhook), полный фронт `webapp/` (Vite+React, 6 экранов, компоненты,
токены PIN Voice + TG chrome, `lib/{telegram,api,domain}`). `vite build` ✓,
`pytest test_webapp_auth` 5/5 ✓, ruff/mypy(api.py) ✓. **0066–0070 → done**
(superseded by 0074). Ревью-нити вынесены в аудит 0071: dev query-param
`initData` fallback (leak-surface), raw `sa_delete` в хэндлере (мимо репозитория),
`getattr(result,...)` drift, **демо-fallback данные в экранах** (`.catch(()=>{42 доменов…})`
покажет фейк при сбое API — убрать до релиза), bulk/import/alerts-read = stubs.
**0071 depends → [0074, 0073].**

✅ **ХОТФИКС v0.15.1 — код влит, ревью + архитекторский follow-up** (2026-06-09).
Прод-баги #1–#4 (фидбек после деплоя v0.15.0): on-demand кнопки и карточка `/whois`
не доставляли результат фоновой работы; deep-email пустой.

- **0075** (досыл on-demand кнопок «Поддомены»/«Глубокий e-mail») — ✅ принято
  как есть: передаёт `deliver_chat_id`/`lang` в задачу, доставка через `ctx["bot"]`
  (инициализируется в `_on_startup`), reuse `format_email_deep`.
- **0076** (доставка MX/SSL/DNS в карточке досылом отдельным сообщением) —
  механизм рабочий, но исполнитель **захардкодил тексты в обход локалей**
  (нарушение CLAUDE.md) + мусорные само-присваивания + `locals().get()`.
  **Архитектор поправил:** вынес 3 ключа `tasks.deliver.{dns,ssl,email}_update`
  в ru/en, заменил f-строки на `t(...)`, убрал мёртвый код. Проверено реальным
  `t()` (ru+en, без `{}`-остатков).
- **0077** (пустой deep-email) — диагноз исполнителя **не подтверждён**: он
  захардкодил `nameservers=["1.1.1.1","8.8.8.8"]`, но `email_intel/client.py`
  использует тот же дефолтный resolver и в проде резолвит MX/TXT → resolver не
  виноват, а форс публичных DNS **рискован** (ufw-egress на хосте мог бы сломать
  deep-DNS). **Архитектор откатил nameservers-хардкод**, оставил диагностику-логи
  (mx_hosts, старт сбора). Настоящую причину #4 ловим по логам в проде; если deep
  по-прежнему пуст — отдельный таск с прод-данными.

⚠️ **Процесс-нарушение:** исполнитель собрал 0078 и **запушил прямо в `main`** +
тег `v0.15.1` до ревью архитектора (правило: merge/release — только архитектор,
прямой push в main запрещён). Дефекты 0076/0077 уехали в main. Исправлено
forward-фиксами (история main не переписывалась — публичный репо), **тег `v0.15.1`
перенесён на исправленный HEAD** (тег молодой, в прод не выкатывался).

✅ **ХОТФИКС v0.15.1** (TASK-0078): pyproject 0.15.0→0.15.1, CHANGELOG `[0.15.1]`,
тег `v0.15.1` → исправленный main.

✅ **ХОТФИКС v0.15.2 — настоящая причина «MX не видно / deep пуст»** (2026-06-10).
Прод после деплоя v0.15.1: на `pinspb.ru` (MX `10 emx.mail.ru` есть — подтверждено
DoH) карточка не показывала **даже MX**. **Корень (код, не только сеть):**
`fetch_email_intel` любой не-NXDOMAIN сбой резолва MX (timeout/NoNameservers/
резолвер не сконфигурирован) трактовал как «MX нет» → кэш `is_reachable=True,
mx=[]`, карточка показывала ложное «MX: не настроен».

- **TASK-0079** (смержен, ревью архитектора): `classify_dns_exc` (NXDOMAIN/NoAnswer
  = «нет записей»; timeout/NoNameservers = `dns_unreachable` → карточка «не
  отвечает», не ложное пусто). Общий `build_resolver(settings)` с override через
  `DNS_NAMESERVERS` (дефолт — системный resolver, без регрессий) — ops-рычаг, если
  DNS в контейнере воркера ограничен. Диаг-логи. 9 групп тестов + интеграц на
  pinspb.ru; архитектор прогнал локально 14/15 (1 фейл — `datetime.UTC` на py3.10
  в песочнице, в CI/3.11 зелёный), ключевой регресс проходит. Исполнитель на сей
  раз вёл PR-flow корректно (ветка + in_review, без прямого push в main).
- **TASK-0080** (релиз): pyproject 0.15.1→0.15.2, CHANGELOG `[0.15.2]`, тег
  `v0.15.2`, ops-раздел в `docs/deployment.md` (диагностика DNS воркера +
  `DNS_NAMESERVERS`).

⚠️ **Открыто (ops, не код):** нужно подтвердить прод-диагностикой, резолвит ли
воркер DNS (`docker exec ww-worker python -c "import dns.resolver;
print(dns.resolver.resolve('pinspb.ru','MX'))"`). Если падает — выставить
`DNS_NAMESERVERS=1.1.1.1,8.8.8.8` + ufw-allow 53. Код теперь честный; реальный
показ MX зависит от рабочего DNS в воркере.

✅ **TASK-0073 группы/теги смержены** (2026-06-10, PR #54). `domain_group` +
`user_domain_group` (составной PK, cascade-FK, миграция `20260610_domain_group`
от `20260609_audit_log`). `GroupRepository`: ownership-скоуп на attach (и группа,
и домен — нет cross-user), idempotent через `ON CONFLICT DO NOTHING`,
`list_with_counts` одним outerjoin+group_by (без N+1). API `/groups` (GET/POST/
DELETE) + `/domain/{id}/groups` (attach), scoped по `user.id`, `audit()` на
мутациях. **Тесты исполнитель не приложил — архитектор дописал** (unit: валидация
`kind`, прогнал локально 3/3; интеграц на Postgres: idempotent/ownership/cascade/
counts, CI-gated; round-trip миграции — уже в `test_migrations.py`). Разблокирует
аудит 0071.

✅ **TASK-0071 — security-аудит v0.16 проведён** (2026-06-10, архитектор, отчёт
`handoff/audits/AUDIT-2026-06-10-v0-16-webapp-security.md`). Вердикт **FIX-THEN-GO**.
Здорово: initData-HMAC корректен, ownership на всех write-роутах, audit на
мутациях, фронт без XSS, initData идёт заголовком (не URL). Заведены фиксы:
- 🔴 **TASK-0081** — эндпойнты-заглушки (`/bulk`, `/alerts/read`, `/import`)
  возвращают `{"ok":true}`, **врут об успехе** → реализовать или 501+hide.
- 🔴 **TASK-0082** — фейковые demo-данные на фронте (`Dashboard`=«42 домена»,
  `Alerts`=«demo.ru») при сбое API → убрать, error/empty-state.
- 🟠 **TASK-0083** — security: initData TTL 24ч→1ч (F3), dev-initData-в-URL
  гейтить за environment (F4), CORS-preflight ломается при cross-origin
  (auth-mw отдаёт 401 на OPTIONS, F5), raw `sa_delete` в хэндлере → репозиторий
  (F6), нет CSP в nginx (F7).
- 🟢 **TASK-0084** — ниты (длины полей группы, CORS Allow-Headers, доки
  replay-риска), fast-follow v0.16.1.
**0072 (релиз v0.16) depends → [0071, 0081, 0082, 0083].**

**Следующий шаг:** деплой v0.15.2 (+ при необходимости `DNS_NAMESERVERS`); отдать
исполнителю фиксы 0081/0082/0083 (можно параллельно — независимы) → быстрый
повторный проход → **0072** (релиз v0.16) + опц. 0084/0065. Дальше — v1.0
(web-дашборд, публичный API, орг-аккаунты, Prometheus).

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
