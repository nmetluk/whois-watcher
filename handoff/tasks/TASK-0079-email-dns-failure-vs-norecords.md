---
id: TASK-0079
title: 🔴 Email-слой — DNS-сбой молча трактуется как «нет записей» (MX/deep пусты)
status: done
milestone: v0.15.2
adr: 040
area: code
depends_on: []
branch: task/0079-email-dns-failure-vs-norecords
owner: ""
session: docs/sessions/2026-06-10_task-0079-email-dns-failure-vs-norecords.md
pr: ""
created: 2026-06-09
---

# TASK-0079 — DNS-сбой ≠ «нет записей» в email-слое (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🔴 Прод: на `pinspb.ru` (есть `MX 10 emx.mail.ru`) карточка `/whois` **не
> показывает MX**, deep-email пуст. Подтверждено: записи существуют (DoH), но
> воркер их не отдаёт.

## Корень проблемы (подтверждён по коду)

`src/email_intel/client.py::fetch_email_intel`: при ошибке резолва MX
(`_resolve_mx` ловит `dns.exception.DNSException` и **возвращает** исключение):

```python
if isinstance(mx_answers, Exception):
    if _is_nxdomain_like(mx_answers):
        return EmailIntelError(... "nxdomain" ...)
    # Нет MX — валидно, просто пустой список   ← БАГ
else:
    mx_records = parse_mx_records(...)
```

То есть **любой не-NXDOMAIN сбой** (Timeout / NoNameservers / резолвер не
сконфигурирован / сеть) попадает в ветку «нет MX» → возвращается
`EmailIntelResult(is_reachable=True, mx_records=[])`. Кэш пишется как
«доступно, MX нет», карточка показывает «MX: не настроен»/пусто для домена,
у которого MX **есть**. То же в `deep_client.py::_resolve_txt_for_spf` и др.
ветках deep — `except Exception: return None` глотает сбой резолва как «нет
записи», поэтому deep-email тоже пуст.

Почему всплыло сейчас: вероятно в контейнере воркера резолв реально падает
(Docker DNS / ufw-egress на 53 / таймаут). Но **даже если так — код обязан
отличать сбой от отсутствия записи**, иначе мы показываем ложь и не видим
проблему. Это и есть настоящая причина #4 (и «MX не видно»).

## Цель

1. **Отличать сбой резолва от «записи нет».** Только `NXDOMAIN` и `NoAnswer`
   (имя есть, записей типа нет) = легитимное «нет записей» (`is_reachable=True`).
   `Timeout`/`LifetimeTimeout`/`NoNameservers`/`NoResolverConfiguration`/прочий
   сетевой сбой = **недоступность** → `EmailIntelError(error_type="dns_unreachable")`
   (карточка покажет «⚠️ не отвечает» или pending, а кэш НЕ зафиксирует ложное
   «MX нет»). Аналогично в deep — сбой не должен молча давать пустой раздел.
2. **Конфигурируемый resolver через settings** (без хардкода публичных DNS):
   общая фабрика, читает `settings.dns_nameservers` (список; пусто = системный
   resolver, как сейчас). Это даёт ops-рычаг: если в контейнере системный DNS
   не работает, оператор выставит `DNS_NAMESERVERS=1.1.1.1,8.8.8.8` env
   (+ ufw allow на 53 к ним) без правки кода. Дефолт — пусто (поведение как
   раньше, никаких регрессий).
3. **Диагностика-логи**: при сбое резолва — `logger.warning` с типом исключения
   и доменом (видно в проде, что именно падает).

## Изменения по файлам

- `src/config/settings.py` — `dns_nameservers: list[str] = Field(default_factory=list,
  description="Кастомные DNS для email/deep-резолва; пусто = системный resolver.")`.
  Парсинг как у `no_expiry_tlds`/`admin_user_ids` (см. их декодер). `.env.example` —
  закомментированный пример.
- `src/email_intel/resolver.py` (новый) — `build_resolver(settings) ->
  dns.asyncresolver.Resolver` (timeout/lifetime + `nameservers` если задан список)
  и `classify_dns_exc(exc) -> Literal["no_records","unreachable"]` (NXDOMAIN/
  NoAnswer → `no_records`; Timeout/LifetimeTimeout/NoNameservers/
  NoResolverConfiguration/прочее → `unreachable`).
- `src/email_intel/client.py` — использовать `build_resolver`; в ветке MX-ошибки:
  NXDOMAIN → как сейчас (nxdomain); `no_records` → пустой MX (reachable);
  **`unreachable` → `EmailIntelError(error_type="dns_unreachable")`** (не
  reachable-пусто). Прокинуть settings в `fetch_email_intel` (или через ctx в
  таске `check_email_intel`). Лог-warning на сбое.
- `src/email_intel/deep_client.py` — `build_resolver`; в `_resolve_txt_for_spf`
  и прочих: отличать `no_records` (None/пусто) от `unreachable` (логировать
  warning; SPF-обёртка может оставить пустой раздел, но залогировать сбой —
  чтобы в проде было видно). Откат хардкода nameservers уже сделан в v0.15.1.
- `src/tasks/check_email_intel.py` / `check_email_deep.py` — передать `settings`
  (есть в `ctx["settings"]`) в коллекторы.

## Инварианты и ТЕСТЫ (обязательно, со `spec`/`autospec`)

Юнит-тесты `tests/unit/test_email_intel_dns_classify.py` и расширение
`test_email_intel_client.py` — мокать `resolver.resolve` (через
`AsyncMock`/`create_autospec`), **без реальной сети**:

1. **MX резолвится** → `EmailIntelResult(is_reachable=True, mx_records=[...])`
   (хотя бы 1 запись распарсилась).
2. **MX raises `dns.resolver.NXDOMAIN`** → `EmailIntelError(error_type="nxdomain")`.
3. **MX raises `dns.resolver.NoAnswer`** (имя есть, MX нет) →
   `EmailIntelResult(is_reachable=True, mx_records=[])` — легитимное «нет MX».
4. **MX raises `dns.resolver.LifetimeTimeout`** → `EmailIntelError(
   error_type="dns_unreachable")` — НЕ reachable-пусто (это ключевой регресс-тест
   на баг).
5. **MX raises `dns.resolver.NoNameservers`** → `dns_unreachable`.
6. `classify_dns_exc`: таблица — NXDOMAIN/NoAnswer→`no_records`;
   LifetimeTimeout/Timeout/NoNameservers/NoResolverConfiguration→`unreachable`.
7. `build_resolver`: пустой `dns_nameservers` → resolver без переопределения
   `nameservers`; непустой → `resolver.nameservers == [...]`; timeout/lifetime
   проставлены.
8. **Карточка-флоу (регресс):** при `dns_unreachable` `format_email_block`
   рендерит «⚠️ не отвечает» (через настоящий `t()`, не мок — правило CLAUDE.md),
   а НЕ «MX: не настроен».
9. deep: `_resolve_txt_for_spf` при `unreachable`-исключении логирует warning
   (проверить через `caplog`) и не падает.

Плюс **opt-in интеграц-тест** `@pytest.mark.integration` на `pinspb.ru`:
ждём непустой MX (реальный DNS; гоняется только с маркером).

## Definition of Done

- [ ] DNS-сбой → `dns_unreachable` (не ложное «нет записей»); конфиг-резолвер;
      диаг-логи
- [ ] Все 9 групп тестов + интеграц-тест зелёные; **полный `pytest`**;
      `ruff`/`black`/`mypy`
- [ ] Реальная проверка в Telegram на `pinspb.ru` (после деплоя/ops-настройки
      DNS) — MX виден; в session-отчёте
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ops-заметка (для деплоя, не код)

Если прод-диагностика покажет, что системный resolver в контейнере воркера не
резолвит (`docker exec ww-worker python -c "import dns.resolver;
print(dns.resolver.resolve('pinspb.ru','MX'))"` падает) — выставить
`DNS_NAMESERVERS=1.1.1.1,8.8.8.8` в `.env` **и** добавить ufw-allow egress на
53 к ним из подсети `172.28.0.0/16` (ADR 028). Зафиксировать в
`docs/deployment.md`.

## Ссылки

- ADR 040; `src/email_intel/{client,deep_client}.py`,
  `src/services/formatters.py::format_email_block`, `src/config/settings.py`.
- Связанные: TASK-0077 (диагностика deep), 0075/0076 (доставка).
