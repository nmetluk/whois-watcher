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

# ⚠️ СТАТУС РЕВЬЮ (2026-06-03, круг 4) — НЕ мержить, осталась 1 правка (мок-механика теста)

> **Исполнителю: перечитай этот блок — здесь точная причина и готовый сниппет.**
> Security-код корректен. Затык — чисто в моке aiohttp. Ниже разбор.

## ✅ Что уже сделано правильно (НЕ переделывать)

- Строгий TXT-матч, независимые A/AAAA, сбор только публичных IP.
- DNS-rebinding закрыт через `TCPConnector(resolver=_SafeMtaStsResolver)`.
- `_SafeMtaStsResolver.close()` добавлен. Security-код готов. ✅

## 🔴 Корень затыка с `test_fetch_mta_sts_happy_path_public_ip`

Код делает **двойной `async with`**:
```python
async with (
    aiohttp.ClientSession(...) as session,
    session.get(url, allow_redirects=False) as resp,
):
```
`session.get(...)` — **НЕ корутина**: он синхронно возвращает объект
(`_RequestContextManager`), который сам async-context-manager. Его не `await`-ят.

В тесте было `mock_session.get = AsyncMock()`. `AsyncMock` при вызове возвращает
**корутину** → `async with <корутина>` → ошибка
*"'coroutine' object does not support the asynchronous context manager protocol"*.
Отсюда же уход в `except` и `reachable=False`.

**Правило:** `session.get` мокается **синхронным `MagicMock`**, возвращающим
объект с `__aenter__`/`__aexit__` как `AsyncMock`. И НЕ патчить
`_SafeMtaStsResolver`/`TCPConnector` — пусть инстанцируются реально (это и есть
регресс-гард на `close()`).

## ✅ Готовый рабочий тест (заменить целиком)

```python
@pytest.mark.asyncio
async def test_fetch_mta_sts_happy_path_public_ip():
    """Публичный IP — реальный _fetch_mta_sts доходит до GET (регресс-гард на close())."""
    with (
        patch("src.email_intel.deep_client.dns.asyncresolver.Resolver") as mock_res_cls,
        patch("src.email_intel.deep_client.aiohttp.ClientSession") as mock_session_cls,
    ):
        mock_res = MagicMock()

        async def fake_resolve(name, rdtype, **kw):
            if rdtype == "TXT":
                return [MagicMock(to_unicode=lambda: "v=STSv1; id=xyz")]
            if rdtype in ("A", "AAAA"):
                return [MagicMock(to_text=lambda: "1.2.3.4")]  # публичный
            return []

        mock_res.resolve = AsyncMock(side_effect=fake_resolve)
        mock_res_cls.return_value = mock_res

        # Ответ, который отдаёт async-CM от session.get(...)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.content.read = AsyncMock(
            return_value=b"version: STSv1\nmode: enforce\nmx: mail.example.com\nmax-age: 86400"
        )
        resp_cm = MagicMock()
        resp_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        resp_cm.__aexit__ = AsyncMock(return_value=False)

        # session — async-CM от ClientSession(...); .get — СИНХРОННЫЙ MagicMock!
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=resp_cm)   # ← ключевой фикс
        session_cm = MagicMock()
        session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        session_cm.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = session_cm

        # НЕ патчим _SafeMtaStsResolver/TCPConnector — реальная инстанциация = гард на close()
        result = await _fetch_mta_sts("good.example.com", resolver=mock_res)

        assert result.reachable is True
        assert result.policy_mode == "enforce"
        assert "mail.example.com" in result.mx
        mock_session.get.assert_called_once()   # реальный путь дошёл до GET
```

Почему работает: `session.get(...)` (синхронный мок) → `resp_cm` → `async with
resp_cm` корректно зовёт `__aenter__` (AsyncMock) → `mock_resp`. Корутина больше
нигде не подсовывается в `async with`.

## Definition of Done

- [ ] `test_fetch_mta_sts_happy_path_public_ip` заменён на сниппет выше
  (реальный `_fetch_mta_sts`, `session.get` — синхронный MagicMock, без патча
  `_SafeMtaStsResolver`)
- [ ] **Полный `pytest` зелёный локально** (включая этот тест);
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
