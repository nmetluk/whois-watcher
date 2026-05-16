"""WHOIS-клиент на 43-м порту (RFC 3912).

Минимальная реализация:

1. Если ``server`` не задан — определяем по TLD через ``WHOIS_SERVERS`` или
   через IANA whois (``whois.iana.org``) с парсингом строки ``refer:``.
2. Открываем TCP-соединение через ``asyncio.open_connection``.
3. Шлём ``<domain>\\r\\n``, читаем до EOF.
4. Декодируем: utf-8 → cp1251 → latin-1 (последний всегда успешен).

Возвращает текст. Парсинг — в ``parser.parse_whois_text``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re

logger = logging.getLogger(__name__)

# Дефолтный whois-сервер IANA — используется как «корень» для обнаружения
# WHOIS-сервера для незнакомого TLD.
IANA_WHOIS_SERVER = "whois.iana.org"
WHOIS_PORT = 43

# Известные WHOIS-сервера для популярных TLD. Не покрывает всё — для остальных
# используем discover через IANA. Источник — https://www.iana.org/domains/root/db
# и личный опыт сообщества: «.com → verisign» и так далее.
WHOIS_SERVERS: dict[str, str] = {
    "com": "whois.verisign-grs.com",
    "net": "whois.verisign-grs.com",
    "org": "whois.pir.org",
    "info": "whois.afilias.net",
    "biz": "whois.nic.biz",
    "io": "whois.nic.io",
    "co": "whois.nic.co",
    "me": "whois.nic.me",
    "ai": "whois.nic.ai",
    "dev": "whois.nic.google",
    "app": "whois.nic.google",
    "ru": "whois.tcinet.ru",
    "su": "whois.tcinet.ru",
    "xn--p1ai": "whois.tcinet.ru",  # .рф в punycode
    "ua": "whois.ua",
    "by": "whois.cctld.by",
    "kz": "whois.nic.kz",
    "uk": "whois.nic.uk",
    "de": "whois.denic.de",
    "fr": "whois.nic.fr",
    "it": "whois.nic.it",
    "es": "whois.nic.es",
    "nl": "whois.domain-registry.nl",
    "pl": "whois.dns.pl",
    "ch": "whois.nic.ch",
    "se": "whois.iis.se",
    "fi": "whois.fi",
    "no": "whois.norid.no",
    "cz": "whois.nic.cz",
    "jp": "whois.jprs.jp",
    "cn": "whois.cnnic.cn",
    "kr": "whois.kr",
    "au": "whois.auda.org.au",
    "ca": "whois.cira.ca",
    "br": "whois.registro.br",
    "tv": "whois.nic.tv",
    "cc": "whois.nic.cc",
    "xyz": "whois.nic.xyz",
    "online": "whois.nic.online",
    "site": "whois.nic.site",
    "store": "whois.nic.store",
    "shop": "whois.nic.shop",
}


class WhoisProtocolError(Exception):
    """Ошибка низкоуровневого WHOIS-запроса (сеть/таймаут/неизвестный TLD)."""


def _tld_of(domain: str) -> str:
    """Возвращает последний label домена (без точки)."""
    return domain.rsplit(".", 1)[-1].lower() if "." in domain else domain.lower()


_IANA_DISCOVERY_TIMEOUT_SECONDS = 5.0

# IANA отдаёт WHOIS-сервер TLD под разными ключами в зависимости от записи:
# - ``refer:`` — самый распространённый (gTLD: .com, .info, .org)
# - ``whois:`` — встречается у ccTLD (.us, .me и ряд других)
# Регэксп берёт первое попавшееся; если в одном ответе оба ключа, мы
# приоритизируем ``refer:`` отдельным проходом (см. ниже).
_IANA_REFER_RE = re.compile(r"^refer:\s*(\S+)", re.MULTILINE | re.IGNORECASE)
_IANA_WHOIS_RE = re.compile(r"^whois:\s*(\S+)", re.MULTILINE | re.IGNORECASE)


async def _resolve_via_iana(domain: str, *, timeout: float) -> str | None:
    """Спрашивает у IANA, на каком сервере искать WHOIS этого TLD.

    IANA на запрос ``<tld>\\r\\n`` отдаёт текст с полем ``refer: <hostname>``
    (gTLD) или ``whois: <hostname>`` (ccTLD типа .us/.me). Проверяем оба,
    ``refer:`` приоритетнее.

    Таймаут на эту операцию ограничен 5 секундами независимо от глобального
    ``timeout`` — IANA отвечает быстро, и долго ждать смысла нет.
    """
    tld = _tld_of(domain)
    iana_timeout = min(timeout, _IANA_DISCOVERY_TIMEOUT_SECONDS)
    try:
        text = await _query(host=IANA_WHOIS_SERVER, query=tld, timeout=iana_timeout)
    except WhoisProtocolError as exc:
        logger.debug("IANA whois discovery failed for .%s: %s", tld, exc)
        return None
    m = _IANA_REFER_RE.search(text) or _IANA_WHOIS_RE.search(text)
    if m is None:
        logger.debug("IANA whois discovery for .%s: no refer:/whois: line", tld)
        return None
    return m.group(1).strip()


_REFERRAL_RE = re.compile(r"^\s*Registrar WHOIS Server:\s*(\S+)", re.MULTILINE | re.IGNORECASE)


async def query_whois(
    domain: str,
    *,
    server: str | None = None,
    server_overrides: dict[str, str] | None = None,
    timeout: float,
    follow_referral: bool = False,
) -> str:
    """Делает WHOIS-запрос на 43 порт и возвращает декодированный текст.

    Приоритет выбора сервера:

    1. Явный ``server`` (программное намерение, в т.ч. тесты).
    2. ``server_overrides[tld]`` (конфиг через env — обход недоступных серверов).
    3. ``WHOIS_SERVERS[tld]`` (встроенный mapping).
    4. IANA discovery.

    ``follow_referral=True`` (для thin-WHOIS реестров типа Verisign .com/.net):
    если в первом ответе есть ``Registrar WHOIS Server:`` и он отличается от
    сервера, к которому мы уже ходили — делаем второй запрос туда и
    возвращаем ответ регистратора (он содержит полные данные регистрации).

    ``WhoisProtocolError`` — если ни один путь не дал сервер или соединение
    не удалось. Ключи в ``server_overrides`` должны быть в lowercase
    (валидатор Settings уже это гарантирует).
    """
    tld = _tld_of(domain)
    target = server
    if target is None and server_overrides is not None:
        target = server_overrides.get(tld)
    if target is None:
        target = WHOIS_SERVERS.get(tld)
    if target is None:
        target = await _resolve_via_iana(domain, timeout=timeout)
    if target is None:
        raise WhoisProtocolError(f"No WHOIS server known for .{tld}")

    response = await _query(host=target, query=domain, timeout=timeout)
    if not follow_referral:
        return response

    referral = _extract_referral(response)
    if referral is None or referral.lower() == target.lower():
        return response

    # Второй раунд: ходим в WHOIS-сервер регистратора. Сетевые ошибки тут
    # не валим — лучше отдать thin-ответ, чем ничего: парсер из него
    # извлечёт хотя бы базовые поля.
    try:
        return await _query(host=referral, query=domain, timeout=timeout)
    except WhoisProtocolError as exc:
        logger.debug(
            "Referral WHOIS query failed (%s → %s): %s; returning thin response",
            target,
            referral,
            exc,
        )
        return response


def _extract_referral(response: str) -> str | None:
    """Возвращает ``Registrar WHOIS Server`` из thin-ответа или None."""
    m = _REFERRAL_RE.search(response)
    if m is None:
        return None
    candidate = m.group(1).strip().rstrip(".")
    return candidate or None


async def _query(*, host: str, query: str, timeout: float) -> str:
    """Низкоуровневый запрос: TCP-connect, write, read-all, decode.

    Соединение закрывается в ``finally`` — даже на исключении/cancel.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host=host, port=WHOIS_PORT),
            timeout=timeout,
        )
    except (TimeoutError, OSError) as exc:
        raise WhoisProtocolError(f"connect to {host}: {exc}") from exc

    try:
        writer.write(f"{query}\r\n".encode("ascii", errors="replace"))
        await writer.drain()
        raw = await asyncio.wait_for(reader.read(), timeout=timeout)
    except (TimeoutError, OSError) as exc:
        raise WhoisProtocolError(f"read from {host}: {exc}") from exc
    finally:
        writer.close()
        # ``wait_closed`` может бросать на грязно закрытом сокете — это
        # уже не наша забота, дренируем тихо.
        with contextlib.suppress(OSError):
            await writer.wait_closed()

    return _decode(raw)


def _decode(raw: bytes) -> str:
    """Декодирует ответ: utf-8 → cp1251 → latin-1 (последний всегда успешен).

    cp1251 нужен для .ru/.рф whois-серверов, которые временами отдают
    кириллицу в Windows-кодировке.
    """
    for encoding in ("utf-8", "cp1251"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")
