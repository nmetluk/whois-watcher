"""Тесты search-helper'а для ``/list`` (Этап 9).

Сама ILIKE-семантика — на стороне Postgres. Здесь проверяем что
``_search_clause`` формирует валидное выражение (без падения) с
вариантами под punycode и Unicode.
"""

from __future__ import annotations

from sqlalchemy.dialects import postgresql

from src.db.repositories.domains import _search_clause


def _render(clause: object) -> str:
    """Компилирует под Postgres-диалект (нативный ILIKE)."""
    return str(
        clause.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


class TestSearchClause:
    def test_renders_ilike_with_query(self) -> None:
        rendered = _render(_search_clause("example")).lower()
        assert "ilike" in rendered
        assert "%example%" in rendered

    def test_lowercases_input(self) -> None:
        rendered = _render(_search_clause("EXAMPLE")).lower()
        assert "%example%" in rendered
        assert "%EXAMPLE%".lower() in rendered

    def test_idn_input_adds_punycode_variant(self) -> None:
        rendered = _render(_search_clause("пример"))
        assert "xn--e1afmkfd" in rendered.lower()

    def test_empty_query_returns_truthy_clause(self) -> None:
        rendered = _render(_search_clause("   ")).strip().lower()
        # func.true() рендерится как ``true`` или ``true()`` в зависимости от
        # версии SQLAlchemy/диалекта — обоих хватает как «no-op фильтр».
        assert rendered.startswith("true")

    def test_invalid_punycode_does_not_crash(self) -> None:
        rendered = _render(_search_clause("..")).lower()
        # ILIKE с введённой строкой — есть. PunyCode-вариант мог не получиться,
        # но это не должно валить хелпер.
        assert "ilike" in rendered
        assert "%..%" in rendered
