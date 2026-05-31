---
id: TASK-0047
title: MTA-STS hardening — anti-SSRF (отсечение приватных IP) + корректный TXT-матч
status: in_review
milestone: v0.13.0
adr: 040
area: code
depends_on: [TASK-0041]
branch: task/0047-mta-sts-ssrf-hardening
owner: claude-code
session: docs/sessions/2026-06-03_task-0047-mta-sts-ssrf-hardening.md
pr: ""
created: 2026-06-02
---

# ⚠️ СТАТУС РЕВЬЮ (2026-06-03, круг 3) — НЕ мержить, осталась 1 правка (тест)

> **Исполнителю: перечитай этот блок — здесь всё, что нужно.**
> Ветка `task/0047-mta-sts-ssrf-hardening`, тип-коммит `f90a530`.

## ✅ Что уже сделано правильно (НЕ переделывать)

- Строгий TXT-матч `txt.lower().startswith("v=stsv1")`.
- A/AAAA резолвятся **независимо**; собираются только безопасные публичные IP;
  нет безопасных → `reachable=False`, GET не выполняется.
- **DNS-rebinding закрыт:** HTTPS через
  `aiohttp.TCPConnector(resolver=_SafeMtaStsResolver(safe_ips))` — резолвер
  отдаёт только проверенные публичные IP. Правильный подход.
- **`_SafeMtaStsResolver.close()` добавлен** — `TypeError` инстанциации
  устранён. Security-код корректен. ✅

## 🔴 Что осталось (блокирует мерж) — ТОЛЬКО тест

**`test_fetch_mta_sts_happy_path_public_ip` — тавтология, переписать.**
Сейчас тест настраивает реальные dns+`ClientSession`-моки на публичный IP, а
потом **патчит саму функцию под тестом**:
`with patch("src.email_intel.deep_client._fetch_mta_sts") as mock_fetch:` и
ассертит хардкод `MtaStsResult(...)`. То есть **реальный `_fetch_mta_sts`
(с `_SafeMtaStsResolver` + `TCPConnector`) НЕ выполняется** — тест проверяет,
что мок вернул то, что в него положили. Если убрать `close()` снова — этот тест
останется зелёным. Ноль защиты от регресса именно того, что чиним.

**Как починить:**
- Убрать `with patch("...deep_client._fetch_mta_sts")` — пусть выполняется
  **реальный** `_fetch_mta_sts` с уже настроенными dns+`ClientSession`-моками
  (публичный IP `1.2.3.4`, ответ 200 + policy-тело — они уже написаны в тесте).
- Ассертить, что **`mock_session.get` был вызван** (т.е. реальный путь дошёл до
  GET через `_SafeMtaStsResolver`+`TCPConnector` на публичном IP) и результат
  `reachable=True`, `policy_mode="enforce"`, mx содержит `mail.example.com`.
- Убрать дублирующиеся ассерты и неиспользуемые моки.
- Этот же тест служит регресс-гардом на `close()` (без него — TypeError).

## Definition of Done (повтор — отметить перед сдачей)

- [ ] `test_fetch_mta_sts_happy_path_public_ip` гоняет **реальный**
  `_fetch_mta_sts` (без `patch(_fetch_mta_sts)`), ассертит `mock_session.get`
  вызван
- [ ] **Полный `pytest` зелёный локально** (не за счёт мока функции под тестом);
  `ruff`/`black --check`/`mypy src`
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

---

# TASK-0047 — MTA-STS anti-SSRF + TXT-матч (ADR 040)

> Тело самодостаточно. Перед стартом:
> `git checkout main && git pull --rebase origin main`, затем `claim`.
> 🟠 Блокер тега v0.13.0. Источник — `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`.

## Цель

Закрыть SSRF-поверхность MTA-STS-fetch'а и убрать ложные срабатывания
детектора TXT.

## Контекст / корень проблемы

`src/email_intel/deep_client.py::_fetch_mta_sts` делает
`GET https://mta-sts.<domain>/.well-known/mta-sts.txt`, где `<domain>` —
пользовательский (бот публичный, любой может запросить deep-email для любого
домена). Защита есть (https-only, `allow_redirects=False`, size 16KB, timeout,
тело не эхо-ится), **но нет отсечения приватных/зарезервированных IP**:
атакующий, контролирующий DNS своего домена, направляет `mta-sts.attacker.tld`
на `169.254.169.254` / `10.0.0.0/8` / `127.0.0.1` → прод-хост ходит во
внутреннюю сеть (слепой SSRF; reachable + тайминги — сигнал).

Дополнительно: детектор TXT `if "v=sts1" in txt.lower() or "sts" in txt.lower()`
— подстрока «sts» в любом TXT (`hosts`/`costs`/`tests`) ложно включает
HTTPS-fetch (лишний трафик + расширение SSRF-триггера).

## Изменения по файлам

- `src/email_intel/deep_client.py::_fetch_mta_sts`:
  - **Корректный TXT-матч:** считать MTA-STS присутствующим только если запись
    начинается с `v=STSv1` (case-insensitive, с учётом ведущих пробелов), а не
    по подстроке «sts».
  - **Anti-SSRF:** перед HTTPS GET резолвить хост `mta-sts.<domain>` (A/AAAA) и
    **отклонять**, если любой адрес — приватный/зарезервированный/loopback/
    link-local/ULA/multicast (`ipaddress.ip_address(...).is_private /
    is_loopback / is_link_local / is_reserved / is_multicast`). При попадании —
    `reachable=False`, без GET. Учесть, что aiohttp может ресолвить заново —
    либо пере-резолвить и передавать проверенный IP, либо использовать кастомный
    `TCPConnector`/`resolver`, который блокирует приватные адреса. Документировать
    выбранный подход в коде.
  - Таймаут/лимит размера/no-redirect — оставить.

## Миграции БД

Не требуется.

## Инварианты (защитить тестами)

- TXT `v=STSv1; id=...` → present; TXT `"random costs sts text"` → НЕ present
  (нет лишнего fetch).
- Хост, резолвящийся в приватный/loopback/link-local IP → `reachable=False`,
  HTTP GET **не** выполняется (мок резолвера + проверка, что session.get не
  вызван).
- Публичный IP → обычный путь (мок GET).
- Моки со `spec`/`autospec`; коллектор по-прежнему никогда не raise.

## Требования к тестам

- Unit на `_fetch_mta_sts`: TXT-матч (строгий), отказ на приватном IP (GET не
  зван), happy-path на публичном IP. Инъекция резолвера/HTTP.

## Definition of Done

- [ ] Код реализован; SSRF закрыт; TXT-матч строгий
- [ ] `pytest` зелёный; `ruff`/`black --check`/`mypy src` чисто
- [ ] Per-session отчёт; `handoff.py validate`; PR + зелёный CI

## Ссылки

- Аудит: `handoff/audits/AUDIT-2026-06-02-v0-13-deep-email.md`
- ADR 040; RFC 8461 (MTA-STS); `src/email_intel/deep_client.py`
