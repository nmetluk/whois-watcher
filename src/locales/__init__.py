"""Локали бота (ADR 014).

Используем простой словарь ``LOCALES[lang][key]`` без gettext: для двух
языков gettext — избыточная инфраструктура.

Использование::

    from src.locales import t

    text = t("commands.add.success", lang="ru", domain="example.com", ...)

Поведение:

- если ключа нет в ``lang`` → fallback на ``ru``
- если и в ``ru`` нет → возвращается сам ключ, в лог пишется warning
- ``**kwargs`` подставляются через ``str.format`` — отсутствующий placeholder
  даст ``KeyError`` (намеренно: помогает быстро находить пропуски)
"""

from __future__ import annotations

import logging
from typing import Final

from src.locales.en import LOCALE as _EN
from src.locales.ru import LOCALE as _RU

logger = logging.getLogger(__name__)

# Регистр доступных локалей. Дефолт — русская (ADR 014).
DEFAULT_LANG: Final[str] = "ru"
LOCALES: Final[dict[str, dict[str, str]]] = {
    "ru": _RU,
    "en": _EN,
}

__all__ = ["DEFAULT_LANG", "LOCALES", "t"]


def t(key: str, lang: str = DEFAULT_LANG, /, **kwargs: object) -> str:
    """Возвращает локализованную строку.

    :param key: dot.case-путь к ключу, например ``"errors.invalid_domain"``
    :param lang: код языка (``"ru"`` или ``"en"``). Неизвестный код → fallback.
    :param kwargs: значения для ``str.format``
    """
    locale = LOCALES.get(lang, LOCALES[DEFAULT_LANG])
    template = locale.get(key)
    if template is None and lang != DEFAULT_LANG:
        template = LOCALES[DEFAULT_LANG].get(key)
    if template is None:
        logger.warning("Missing locale key", extra={"key": key, "lang": lang})
        return key
    if not kwargs:
        return template
    return template.format(**kwargs)
