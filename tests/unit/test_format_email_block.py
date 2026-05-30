"""Тесты ``format_email_block`` (TASK-0018, ADR 036).

Используем dataclass-фейк вместо ORM-объекта — ``format_email_block``
принимает структурный объект (EmailIntelCache | None). Никакой БД и
SQLAlchemy в этих тестах.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from src.services.formatters import format_email_block


@dataclass
class FakeEmailIntelCache:
    """Мок ``EmailIntelCache`` для тестов формата.

    Поля совпадают с реальной моделью (``src.db.models.EmailIntelCache``) —
    ``format_email_block`` обращается к ним через atomic attribute access.
    """

    domain: str = "example.com"
    fetched_at: datetime | None = field(default_factory=lambda: datetime.now(tz=UTC))
    last_successful_check_at: datetime | None = field(default_factory=lambda: datetime.now(tz=UTC))
    is_reachable: bool | None = True
    mx_records: list[dict[str, object]] | None = None
    spf_record: str | None = None
    spf_mode: str | None = None
    dmarc_policy: str | None = None
    dmarc_subpolicy: str | None = None
    dmarc_pct: int | None = None
    dkim_selectors: list[str] | None = None


def test_returns_none_for_unchecked_cache() -> None:
    cache = FakeEmailIntelCache(last_successful_check_at=None)
    assert format_email_block(cache, lang="ru") is None  # type: ignore[arg-type]


def test_returns_none_for_cache_with_no_data() -> None:
    # last_successful_check_at есть, но все записи пусты — покажем
    # минимальный блок ( MX не настроен, SPF/DMARC не настроены ).
    cache = FakeEmailIntelCache()
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "MX" in result
    assert "SPF" in result
    assert "DMARC" in result


def test_unreachable_returns_compact_line() -> None:
    cache = FakeEmailIntelCache(is_reachable=False)
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "не отвечает" in result.lower()
    # Compact-формат — никакого tree.
    assert "├" not in result and "└" not in result


def test_mx_records_displayed_with_truncation() -> None:
    cache = FakeEmailIntelCache(
        mx_records=[
            {"priority": 10, "host": "mail1.example.com"},
            {"priority": 20, "host": "mail2.example.com"},
            {"priority": 30, "host": "mail3.example.com"},
            {"priority": 40, "host": "mail4.example.com"},
        ]
    )
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    # Первые 3 MX показываются + индикатор остальных.
    assert "mail1.example.com" in result
    assert "mail2.example.com" in result
    assert "mail3.example.com" in result
    assert "(+1)" in result
    # 4-й MX не показывается.
    assert "mail4.example.com" not in result


def test_mx_sorted_by_priority() -> None:
    cache = FakeEmailIntelCache(
        mx_records=[
            {"priority": 30, "host": "mail3.example.com"},
            {"priority": 10, "host": "mail1.example.com"},
            {"priority": 20, "host": "mail2.example.com"},
        ]
    )
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    lines = result.splitlines()
    # MX-строка имеет формат "├ MX: ..."
    mx_line = next(line for line in lines if "MX:" in line)
    # Проверяем порядок: mail1, mail2, mail3
    assert mx_line.index("mail1") < mx_line.index("mail2") < mx_line.index("mail3")


def test_no_mx_shows_not_configured() -> None:
    cache = FakeEmailIntelCache(mx_records=None)
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "не настроен" in result


def test_spf_mode_displayed() -> None:
    cache = FakeEmailIntelCache(spf_record="v=spf1 -all", spf_mode="fail")
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "строгий" in result
    assert "-all" not in result  # только режим, не сырая запись


def test_spf_softfail_displayed() -> None:
    cache = FakeEmailIntelCache(spf_record="v=spf1 ~all", spf_mode="softfail")
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "мягкий" in result


def test_no_spf_shows_not_configured() -> None:
    cache = FakeEmailIntelCache(spf_record=None)
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "SPF:" in result
    assert "не настроен" in result


def test_dmarc_policy_displayed() -> None:
    cache = FakeEmailIntelCache(dmarc_policy="reject")
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "отклонять" in result


def test_dmarc_with_subpolicy_and_pct() -> None:
    cache = FakeEmailIntelCache(
        dmarc_policy="quarantine",
        dmarc_subpolicy="reject",
        dmarc_pct=50,
    )
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "карантин" in result
    assert "sp=отклонять" in result
    assert "50%" in result


def test_no_dmarc_shows_not_configured() -> None:
    cache = FakeEmailIntelCache(dmarc_policy=None)
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "DMARC:" in result
    assert "не настроен" in result


def test_dkim_selectors_displayed() -> None:
    cache = FakeEmailIntelCache(dkim_selectors=["google", "k1"])
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    assert "google" in result
    assert "k1" in result


def test_no_dkim_closes_tree_without_dkim_label() -> None:
    # Когда DKIM нет, последняя строка (DMARC) должна быть с └
    cache = FakeEmailIntelCache(dkim_selectors=None, dmarc_policy="reject")
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    lines = result.splitlines()
    # DMARC-строка теперь закрывающая (└), т.к. DKIM нет
    dmarc_line = next(line for line in lines if "DMARC:" in line)
    assert dmarc_line.startswith("└ ")


def test_english_locale_for_translatable_strings() -> None:
    cache = FakeEmailIntelCache(
        mx_records=[{"priority": 10, "host": "mail.example.com"}],
        spf_record="v=spf1 -all",
        spf_mode="fail",
        dmarc_policy="reject",
    )
    ru = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    en = format_email_block(cache, lang="en")  # type: ignore[arg-type]
    assert ru is not None and en is not None
    assert ru != en
    # RU: "строгий", EN: "strict"
    assert "строгий" in ru
    assert "strict" in en
    # RU: "отклонять", EN: "reject"
    assert "отклонять" in ru
    assert "reject" in en


def test_full_block_tree_format() -> None:
    cache = FakeEmailIntelCache(
        mx_records=[{"priority": 10, "host": "mail.example.com"}],
        spf_record="v=spf1 -all",
        spf_mode="fail",
        dmarc_policy="reject",
        dkim_selectors=["google"],
    )
    result = format_email_block(cache, lang="ru")  # type: ignore[arg-type]
    assert result is not None
    lines = result.splitlines()
    # Заголовок + 4 строки с данными
    assert len(lines) >= 5
    # Первая строка — заголовок
    assert lines[0].startswith("📧")
    # Tree-формат: ├ для всех, кроме последней
    assert lines[1].startswith("├ ")
    assert lines[2].startswith("├ ")
    assert lines[3].startswith("├ ")
    # Последняя (DKIM) с └
    assert lines[-1].startswith("└ ")
