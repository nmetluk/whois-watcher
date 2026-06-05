"""Фасад WHOIS-ядра: ``lookup_domain``.

Внешний код (хэндлеры на Этапе 4, таски воркеров) пользуется ИСКЛЮЧИТЕЛЬНО
этой функцией. Внутри она:

1. **Primary path (ADR 028, Этап 10):** HTTP-запрос к локальному
   WHOIS proxy gateway (``src.whois.proxy_client.lookup_via_proxy``).
   Прокси сам выбирает upstream и кэширует ответы.
2. **Fallback:** если прокси недоступен (``ProxyUnreachable``) —
   прямой RDAP + WHOIS:43 lookup (``lookup_direct``). Это сохранённый
   страховочный путь из Этапов 3 и 7a; всё что было раньше — здесь.

Никаких побочных эффектов кроме сетевого I/O. Сохранение в БД, отправка
уведомлений — слой выше.
"""

from __future__ import annotations

import asyncio
import logging

import idna

from src.config.limits import Limits, get_limits
from src.config.settings import get_settings
from src.utils.idn import normalize_domain
from src.whois.parser import looks_like_upstream_error, parse_rdap, parse_whois_text
from src.whois.proxy_client import ProxyUnreachable, lookup_via_proxy
from src.whois.rdap import query_rdap
from src.whois.types import WhoisData, WhoisError, WhoisResult
from src.whois.whois_protocol import WhoisProtocolError, query_whois

logger = logging.getLogger(__name__)


async def lookup_domain(domain: str, *, limits: Limits | None = None) -> WhoisResult:
    """Главный entry-point WHOIS-ядра — прокси сначала, direct как fallback.

    1. Если ``whois_proxy_enabled=True`` (дефолт) — пробуем прокси.
    2. ``ProxyUnreachable`` → переходим на ``lookup_direct``. В лог летит
       warning (Sentry увидит как event); если direct тоже сфейлится —
       вернётся обычная ``WhoisError``.
    3. Прокси отключён → сразу ``lookup_direct``.

    ``limits`` параметризован только для direct-пути — прокси читает свой
    таймаут из ``Settings.whois_proxy_timeout_seconds``.
    """
    settings = get_settings()

    result: WhoisResult | None = None
    if settings.whois_proxy_enabled:
        try:
            result = await lookup_via_proxy(domain)
        except ProxyUnreachable as exc:
            logger.warning(
                "WHOIS proxy unreachable, falling back to direct lookup: %s " "(domain=%s)",
                exc,
                domain,
            )
            # Здесь могла бы быть отправка alert в админ-канал, но мы её
            # делаем через отдельный cron-хелсчек (proxy_health.py): иначе
            # дедупликация AlertService отфильтрует первый алерт, и потом
            # любой direct-fallback подавится без записи.

    if result is None:
        result = await lookup_direct(domain, limits=limits)

    return await _verify_unregistered(result, limits=limits)


#: Источники, где «свободен» = отсутствие записи в WHOIS-тексте (negative
#: evidence). Для них перед утверждением «свободен» делаем RDAP-кросс-чек:
#: positive evidence (RDAP 200) бьёт negative. Инцидент TASK-0091:
#: relay/TCI отдавал «No entries found» для уже зарегистрированного домена
#: 2+ суток — бот уверенно показывал «свободен».
_TEXT_BASED_SOURCES = ("whois", "proxy_whois", "proxy_whois_ru", "proxy_none")


async def _verify_unregistered(result: WhoisResult, *, limits: Limits | None) -> WhoisResult:
    """RDAP-верификация ответа «домен свободен» (ADR 045, TASK-0092).

    Применяется только когда «свободен» пришёл из WHOIS-текста (см.
    ``_TEXT_BASED_SOURCES``) — RDAP-источники и так дают авторитетный 404.

    - RDAP «found» и parse говорит registered → возвращаем RDAP-данные
      (домен ЗАНЯТ; в raw_data — пометка о противоречии для алертов/отладки).
    - RDAP «not_found» → «свободен» подтверждён (``free_verified``).
    - RDAP unsupported/error → «свободен» НЕ подтверждён
      (``free_unverified=True``) — UX покажет осторожную формулировку.
    """
    if not isinstance(result, WhoisData) or result.is_registered:
        return result
    if result.source not in _TEXT_BASED_SOURCES:
        return result

    cfg = limits if limits is not None else get_limits()
    rdap_status, rdap_data = await query_rdap(
        result.domain, timeout=float(cfg.whois_timeout_seconds)
    )

    if rdap_status == "found" and rdap_data is not None:
        try:
            parsed = parse_rdap(rdap_data, result.domain)
        except Exception:
            logger.exception("parse_rdap crashed verifying %s", result.domain)
            result.raw_data["free_unverified"] = True
            return result
        if parsed.is_registered:
            logger.warning(
                "WHOIS said free but RDAP says REGISTERED for %s "
                "(whois source=%s) — using RDAP data",
                result.domain,
                result.source,
            )
            parsed.raw_data["free_contradicted_whois_source"] = result.source
            return parsed
        result.raw_data["free_verified"] = "rdap"
        return result

    if rdap_status == "not_found":
        result.raw_data["free_verified"] = "rdap"
        return result

    # unsupported / error — подтвердить не смогли
    result.raw_data["free_unverified"] = True
    return result


async def lookup_direct(domain: str, *, limits: Limits | None = None) -> WhoisResult:
    """Прямой WHOIS lookup без прокси — RDAP сначала, WHOIS:43 как fallback.

    Сохранённая старая логика из Этапов 3/7a, используется как страховка
    когда прокси недоступен. ``limits`` для тестов; в проде — синглтон.
    Возвращает либо ``WhoisData``, либо ``WhoisError`` — не бросает.
    """
    cfg = limits if limits is not None else get_limits()
    timeout = float(cfg.whois_timeout_seconds)

    # Нормализация имени: ``Example.COM``/``пример.рф``/``https://...`` →
    # punycode, lowercase, без trailing dot.
    try:
        normalized = normalize_domain(domain)
    except (idna.IDNAError, ValueError, UnicodeError) as exc:
        return WhoisError(
            domain=domain,
            error_type="parse_error",
            message=f"invalid domain syntax: {exc}",
        )

    # --- RDAP ---
    rdap_status, rdap_data = await query_rdap(normalized, timeout=timeout)
    if rdap_status == "found" and rdap_data is not None:
        try:
            return parse_rdap(rdap_data, normalized)
        except Exception:
            # Парсер обещает не падать — но защищаемся на случай регрессий.
            logger.exception("parse_rdap crashed on %s", normalized)
            return WhoisError(
                domain=normalized,
                error_type="parse_error",
                message="RDAP parser crashed (see logs)",
            )
    if rdap_status == "not_found":
        return WhoisData(
            domain=normalized,
            is_registered=False,
            source="rdap",
        )

    # --- WHOIS:43 fallback ---
    settings = get_settings()
    try:
        raw_text = await query_whois(
            normalized,
            timeout=timeout,
            follow_referral=settings.whois_referral_following,
        )
    except TimeoutError:
        return WhoisError(domain=normalized, error_type="timeout", message="WHOIS:43 timeout")
    except WhoisProtocolError as exc:
        # Нет известного WHOIS-сервера для TLD — это уже ``unsupported_tld``.
        # Сетевые/таймауты — ``network_error``.
        msg = str(exc)
        if msg.startswith("No WHOIS server"):
            return WhoisError(domain=normalized, error_type="unsupported_tld", message=msg)
        return WhoisError(domain=normalized, error_type="network_error", message=msg)

    # TASK-0092: текст ошибки/рейтлимита/HTML — это сбой, а не «свободен».
    if looks_like_upstream_error(raw_text):
        return WhoisError(
            domain=normalized,
            error_type="unavailable",
            message=f"WHOIS:43 returned error-like text: {raw_text[:120]!r}",
            raw_response=raw_text[:5000] if raw_text else None,
        )

    try:
        return parse_whois_text(raw_text, normalized)
    except Exception:
        logger.exception("parse_whois_text crashed on %s", normalized)
        return WhoisError(
            domain=normalized,
            error_type="parse_error",
            message="WHOIS parser crashed (see logs)",
            raw_response=raw_text[:5000] if raw_text else None,
        )


async def lookup_with_semaphore(
    domain: str,
    semaphore: asyncio.Semaphore,
    *,
    limits: Limits | None = None,
) -> WhoisResult:
    """``lookup_domain`` под глобальным ``Semaphore``.

    Используется в воркерах (Этап 4), чтобы не превысить
    ``MAX_CONCURRENT_WHOIS`` и не получить бан от RDAP-серверов.
    """
    async with semaphore:
        return await lookup_domain(domain, limits=limits)


__all__ = [
    "WhoisData",
    "WhoisError",
    "WhoisResult",
    "lookup_direct",
    "lookup_domain",
    "lookup_with_semaphore",
]
