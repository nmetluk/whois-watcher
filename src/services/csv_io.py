"""Сервис экспорта и импорта CSV.

Используется ``/csv`` (экспорт списка пользователя) и ``/download`` (разбор
загруженного файла перед массовым импортом).

Принципы:

- Без сетевых вызовов и без записи в БД — здесь только генерация байтов и
  чистый парсинг текстовых файлов.
- Запись в БД, постановка фоновых задач — забота хэндлера ``/download``.
- Все домены внутри хранятся в punycode (ASCII). Конверсия в Unicode только
  на границе UI (экспорт CSV).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import idna

from src.bot.validators import is_valid_domain
from src.db.repositories import DomainRepository
from src.db.session import get_session
from src.utils.formatting import days_until
from src.utils.idn import from_punycode, normalize_domain

logger = logging.getLogger(__name__)

# UTF-8 BOM — открытие в Excel на Windows без перекодировки.
_BOM = "﻿"
# Заголовки CSV для экспорта.
_CSV_HEADER: tuple[str, ...] = (
    "domain",
    "expires_at",
    "days_left",
    "registrar",
    "status",
    "notifications",
    "added_at",
    "note",
)


@dataclass(slots=True)
class ParsedFileResult:
    """Результат разбора пользовательского файла для ``/download``.

    ``valid_domains`` — нормализованные в punycode и дедуплицированные.
    Уникальность проверяется внутри файла; проверка против БД (
    ``already_tracked``) — забота вызывающей стороны.
    """

    valid_domains: list[str] = field(default_factory=list)
    invalid_lines: list[str] = field(default_factory=list)
    truncated: bool = False
    total_lines: int = 0


# ---------------------------------------------------------------------------
# Экспорт
# ---------------------------------------------------------------------------


async def generate_user_csv(user_id: int) -> tuple[bytes, int]:
    """Сгенерировать CSV со всеми доменами пользователя.

    Возвращает пару ``(bytes, count)`` — содержимое файла (UTF-8 BOM,
    запятая, кавычки) и число строк (без заголовка).

    Колонки (``_CSV_HEADER``):

    - ``domain``         — Unicode (декодируем из punycode)
    - ``expires_at``     — ``YYYY-MM-DD`` или пусто
    - ``days_left``      — число или пусто
    - ``registrar``      — строка или пусто
    - ``status``         — через ``", "``
    - ``notifications``  — ``on``/``off`` (on если хотя бы один notify_* флаг)
    - ``added_at``       — ``YYYY-MM-DD HH:MM``
    - ``note``           — строка или пусто
    """
    async with get_session() as session:
        domain_repo = DomainRepository(session)
        rows = await domain_repo.iter_all_with_whois(user_id)

    buffer = io.StringIO()
    buffer.write(_BOM)
    writer = csv.writer(
        buffer,
        dialect="excel",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    writer.writerow(_CSV_HEADER)

    now = datetime.now(tz=UTC)
    count = 0
    for ud, cache in rows:
        writer.writerow(_row_for(ud, cache, now=now))
        count += 1

    return buffer.getvalue().encode("utf-8"), count


def _row_for(ud: object, cache: object | None, *, now: datetime) -> list[str]:
    """Сериализует одну пару (user_domain, whois_cache) в значения CSV-строки."""
    domain_punycode = getattr(ud, "domain", "")
    domain_unicode = from_punycode(domain_punycode) if domain_punycode else ""

    expires_at = getattr(cache, "expires_at", None) if cache is not None else None
    expires_str = expires_at.strftime("%Y-%m-%d") if expires_at is not None else ""

    days_left_str = str(days_until(expires_at, now=now)) if expires_at is not None else ""

    registrar = (getattr(cache, "registrar", None) if cache is not None else None) or ""

    status_list = getattr(cache, "status", None) if cache is not None else None
    status_str = ", ".join(status_list) if status_list else ""

    notifications_on = any(
        bool(getattr(ud, attr, False))
        for attr in (
            "notify_expiry",
            "notify_ns_change",
            "notify_registrar_change",
            "notify_status_change",
        )
    )

    added_at = getattr(ud, "added_at", None)
    added_str = added_at.strftime("%Y-%m-%d %H:%M") if added_at is not None else ""

    note = getattr(ud, "note", None) or ""

    return [
        domain_unicode,
        expires_str,
        days_left_str,
        registrar,
        status_str,
        "on" if notifications_on else "off",
        added_str,
        note,
    ]


# ---------------------------------------------------------------------------
# Импорт
# ---------------------------------------------------------------------------


def parse_domain_file(content: bytes, max_domains: int) -> ParsedFileResult:
    """Разобрать содержимое пользовательского файла со списком доменов.

    Поддерживаются:

    - TXT построчно (один домен на строку)
    - CSV: берётся первая колонка; первая строка-заголовок (``domain``) при
      наличии пропускается

    Что делает с каждой строкой:

    - пропускает пустые и комментарии (``#…``)
    - снимает схему ``http(s)://``, путь, пробелы — через ``normalize_domain``
    - валидирует через ``is_valid_domain``
    - нормализует в punycode
    - дедуплицирует в пределах файла
    - при превышении ``max_domains`` останавливает разбор и проставляет
      ``truncated=True`` (но всё валидное до лимита возвращает)

    Возвращает ``ParsedFileResult`` — словарь без побочных эффектов.
    """
    result = ParsedFileResult()
    if not content:
        return result
    text = _decode(content)
    if text is None:
        return result

    raw_lines = text.splitlines()
    result.total_lines = len(raw_lines)

    seen: set[str] = set()
    is_csv_like = _looks_like_csv(raw_lines)
    header_consumed = False

    for line in raw_lines:
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith("#"):
            continue

        token = _extract_first_token(raw) if is_csv_like else raw
        if not token:
            continue

        # Пропускаем заголовок CSV ровно один раз и только если он явно похож
        # на ``domain`` (а не на реальный домен с точкой).
        if (
            is_csv_like
            and not header_consumed
            and token.lower() in {"domain", "domains", "host", "hostname"}
        ):
            header_consumed = True
            continue
        header_consumed = True  # дальше уже не пропускаем

        try:
            normalized = normalize_domain(token)
        except (idna.IDNAError, ValueError, UnicodeError):
            result.invalid_lines.append(raw)
            continue
        if not is_valid_domain(normalized):
            result.invalid_lines.append(raw)
            continue

        if normalized in seen:
            continue
        seen.add(normalized)

        if len(result.valid_domains) >= max_domains:
            result.truncated = True
            break
        result.valid_domains.append(normalized)

    return result


def _decode(content: bytes) -> str | None:
    """Декодирует байты с попыткой UTF-8 (с BOM) → cp1251 → latin-1.

    Возвращает None, если ничего не получилось (очень странный бинарник).
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _looks_like_csv(lines: list[str]) -> bool:
    """Эвристика: считаем файл CSV, если в значимых строках встречаются разделители."""
    for line in lines[:20]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "," in stripped or ";" in stripped or "\t" in stripped:
            return True
    return False


def _extract_first_token(line: str) -> str:
    """Возвращает содержимое первой колонки CSV-подобной строки.

    Простой парсер: ``csv.reader`` для одной строки, чтобы корректно
    обработать значения в кавычках. На исключение возвращаем split по запятой.
    """
    try:
        reader = csv.reader([line])
        for row in reader:
            if row:
                return row[0].strip()
            return ""
    except csv.Error:
        pass
    for sep in (",", ";", "\t"):
        if sep in line:
            return line.split(sep, 1)[0].strip()
    return line.strip()


__all__ = ["ParsedFileResult", "generate_user_csv", "parse_domain_file"]
