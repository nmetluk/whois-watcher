"""Работа с Public Suffix List и разбор доменов.

Модуль предоставляет чистые функции для определения registrable-домена
(eTLD+1) и классификации поддоменов/публичных суффиксов через PSL.

Никаких сетевых вызовов — используется bundled snapshot из tldextract.
Все функции работают на punycode-форме (после idn.normalize_domain).
"""

from __future__ import annotations

import dataclasses

import tldextract

from src.utils.idn import normalize_domain


@dataclasses.dataclass(frozen=True, slots=True)
class DomainParts:
    """Компоненты домена после разбора через PSL."""

    subdomain: str  # Всё левее registrable (может быть пустым)
    registrable: str  # eTLD+1 — домен, который можно регистрировать
    suffix: str  # Публичный суффикс (TLD или ccTLD+TLD типа co.uk)


# Инициализация tldextract с оффлайн-снапшотом и БЕЗ сетевого автофетча.
# suffix_list_urls=() отключает загрузку из сети.
# cache_dir=None отключает дисковый кэш (по умолчанию tldextract использует
# ~/.cache/python-tldextract/, что ломается в read-only контейнерах).
# include_psl_private_domains=False — только публичные суффиксы.
_TLD_EXTRACTOR = tldextract.TLDExtract(
    suffix_list_urls=(),  # Без сетевого автофетча
    include_psl_private_domains=False,
    cache_dir=None,  # Отключаем дисковый кэш для read-only сред
)


def split_domain(domain: str) -> DomainParts:
    """Разбивает домен на subdomain, registrable и suffix через PSL.

    Args:
        domain: Доменное имя (может быть в любом регистре/форме).

    Returns:
        DomainParts с тремя компонентами.

    Raises:
        idna.IDNAError: Если домен невалиден.

    Примеры::

        split_domain("a.pinbetting.ru")
        # DomainParts(subdomain="a", registrable="pinbetting.ru", suffix="ru")

        split_domain("pinbetting.ru")
        # DomainParts(subdomain="", registrable="pinbetting.ru", suffix="ru")

        split_domain("a.b.foo.co.uk")
        # DomainParts(subdomain="a.b", registrable="foo.co.uk", suffix="co.uk")
    """
    normalized = normalize_domain(domain)
    parts = _TLD_EXTRACTOR(normalized)
    return DomainParts(
        subdomain=parts.subdomain,
        registrable=f"{parts.domain}.{parts.suffix}" if parts.domain else "",
        suffix=parts.suffix,
    )


def registrable_domain(domain: str) -> str:
    """Возвращает registrable-домен (eTLD+1) для данного домена.

    Для поддомена возвращает домен второго уровня.
    Для уже registrable-домена возвращает его самого.

    Args:
        domain: Доменное имя.

    Returns:
        Registrable-домен (пустая строка если домен — это публичный суффикс).

    Примеры::

        registrable_domain("a.pinbetting.ru")  # -> "pinbetting.ru"
        registrable_domain("pinbetting.ru")     # -> "pinbetting.ru"
        registrable_domain("a.b.foo.co.uk")     # -> "foo.co.uk"
        registrable_domain("foo.org.uk")        # -> "foo.org.uk"
        registrable_domain("co.uk")             # -> ""
    """
    return split_domain(domain).registrable


def is_subdomain(domain: str) -> bool:
    """Проверяет, является ли домен поддоменом относительно registrable.

    True если есть непустая subdomain-часть относительно registrable-домена.

    Args:
        domain: Доменное имя.

    Returns:
        True если это поддомен, False если registrable-домен или публичный суффикс.

    Примеры::

        is_subdomain("www.foo.org.uk")  # -> True
        is_subdomain("foo.org.uk")      # -> False
        is_subdomain("a.pinbetting.ru") # -> True
        is_subdomain("pinbetting.ru")   # -> False
    """
    parts = split_domain(domain)
    # Публичный суффикс не считается поддоменом (у него нет registrable части)
    return bool(parts.subdomain) and bool(parts.registrable)


def is_public_suffix_only(domain: str) -> bool:
    """Проверяет, является ли ввод чистым публичным суффиксом.

    Args:
        domain: Доменное имя.

    Returns:
        True если это публичный суффикс (без registrable части).

    Примеры::

        is_public_suffix_only("co.uk")        # -> True
        is_public_suffix_only("org.uk")       # -> True
        is_public_suffix_only("ru")           # -> True
        is_public_suffix_only("pinbetting.ru") # -> False
    """
    parts = split_domain(domain)
    return bool(parts.suffix) and not bool(parts.registrable)
