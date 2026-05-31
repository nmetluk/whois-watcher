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

# ⚠️ СТАТУС РЕВЬЮ (2026-06-03, круг 2) — НЕ мержить, осталась 1 правка

> **Исполнителю: перечитай этот блок — здесь всё, что нужно.**
> Ветка `task/0047-mta-sts-ssrf-hardening`, тип-коммит `089f7e8`.

## ✅ Что уже сделано правильно (НЕ переделывать)

- Строгий TXT-матч: `txt.lower().startswith("v=stsv1")` (подстрока «sts» больше
  не ловит «hosts/costs»).
- A и AAAA резолвятся **независимо** (отдельные try/except) — ок.
- Собираются только безопасные публичные IP; нет безопасных → `reachable=False`,
  GET не выполняется.
- **DNS-rebinding закрыт по дизайну:** HTTPS идёт через
  `aiohttp.TCPConnector(resolver=_SafeMtaStsResolver(safe_ips))` — кастомный
  резолвер отдаёт только проверенные публичные IP, aiohttp не может пере-
  резолвить в приватный. Это правильный подход.

## 🔴 Что осталось (блокирует мерж)

1. **`_SafeMtaStsResolver` не реализует `close()` → `TypeError` при создании.**
   В aiohttp 3.13.5 (наш пин `>=3.9,<4.0`) `AbstractResolver` объявляет
   абстрактными **оба** метода: `resolve` **и** `close`. Класс реализует только
   `resolve()`, поэтому `_SafeMtaStsResolver(safe_ips)` падает
   `TypeError: Can't instantiate abstract class ... abstract method 'close'`.
   Строка выполняется на каждом нормальном MTA-STS (валидный TXT + публичный IP)
   → fetch ломается всегда.
   **Фикс — добавить метод в класс:**
   ```python
   async def close(self) -> None:
       return None
   ```

2. **Полный `pytest` НЕ прогнан (DoD «CI зелёный» не выполнен).**
   `test_fetch_mta_sts_happy_path_public_ip` мокает `aiohttp.ClientSession`, но
   **не** мокает `_SafeMtaStsResolver`/`aiohttp.TCPConnector` — значит реальная
   инстанциация резолвера всё равно происходит, и этот тест сейчас **падает**
   TypeError'ом (см. п.1). После фикса — **прогнать весь `pytest` локально**,
   убедиться, что happy-path реально зелёный, а не «по идее».

## Definition of Done (повтор — отметить перед сдачей)

- [ ] Добавлен `_SafeMtaStsResolver.close()`; `_fetch_mta_sts` не падает на
  публичном IP
- [ ] **Полный `pytest` зелёный локально** (особенно
  `test_fetch_mta_sts_happy_path_public_ip`); `ruff`/`black --check`/`mypy src`
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
