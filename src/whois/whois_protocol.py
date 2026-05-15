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


async def _resolve_via_iana(domain: str, *, timeout: float) -> str | None:
    """Спрашивает у IANA, на каком сервере искать WHOIS этого TLD.

    IANA на запрос ``<tld>\\r\\n`` отдаёт текст с полем ``refer: <hostname>``.
    Если поля нет — возвращаем None.
    """
    tld = _tld_of(domain)
    try:
        text = await _query(host=IANA_WHOIS_SERVER, query=tld, timeout=timeout)
    except WhoisProtocolError as exc:
        logger.debug("IANA whois discovery failed for .%s: %s", tld, exc)
        return None
    m = re.search(r"^refer:\s*(\S+)", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


async def query_whois(
    domain: str,
    *,
    server: str | None = None,
    timeout: float,
) -> str:
    """Делает WHOIS-запрос на 43 порт и возвращает декодированный текст.

    Если ``server`` не задан — ищет по ``WHOIS_SERVERS``, при отсутствии —
    спрашивает у IANA. ``WhoisProtocolError`` — если ни один путь не дал
    сервер или соединение не удалось.
    """
    target = server or WHOIS_SERVERS.get(_tld_of(domain))
    if target is None:
        target = await _resolve_via_iana(domain, timeout=timeout)
    if target is None:
        raise WhoisProtocolError(f"No WHOIS server known for .{_tld_of(domain)}")
    return await _query(host=target, query=domain, timeout=timeout)


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
