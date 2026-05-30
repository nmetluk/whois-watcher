"""Тесты для compute_subdomain_diff (TASK-0028, ADR 038)."""

from __future__ import annotations

from src.subdomains.diff import compute_subdomain_diff


class TestComputeSubdomainDiff:
    """Тесты функции сравнения списков поддоменов."""

    def test_baseline_old_none_returns_empty_diff(self) -> None:
        """old=None → пустой diff (baseline, первая проверка)."""
        result = compute_subdomain_diff(old=None, new=["www.example.com", "api.example.com"])
        assert result.has_any_changes is False
        assert result.new == []
        assert result.removed == []

    def test_new_subdomains_detected(self) -> None:
        """Находит новые поддомены."""
        result = compute_subdomain_diff(
            old=["www.example.com"],
            new=["www.example.com", "api.example.com", "mail.example.com"],
        )
        assert result.has_any_changes is True
        assert set(result.new) == {"api.example.com", "mail.example.com"}
        assert result.removed == []

    def test_removed_subdomains_detected(self) -> None:
        """Находит исчезнувшие поддомены."""
        result = compute_subdomain_diff(
            old=["www.example.com", "api.example.com", "mail.example.com"],
            new=["www.example.com"],
        )
        assert result.has_any_changes is True
        assert result.new == []
        assert set(result.removed) == {"api.example.com", "mail.example.com"}

    def test_both_new_and_removed(self) -> None:
        """Находит и новые, и исчезнувшие поддомены."""
        result = compute_subdomain_diff(
            old=["www.example.com", "old.example.com"],
            new=["www.example.com", "new.example.com"],
        )
        assert result.has_any_changes is True
        assert result.new == ["new.example.com"]
        assert result.removed == ["old.example.com"]

    def test_order_does_not_matter(self) -> None:
        """Порядок не влияет на результат."""
        old_list = ["a.example.com", "b.example.com", "c.example.com"]
        new_list = ["c.example.com", "b.example.com", "a.example.com"]  # другой порядок
        result = compute_subdomain_diff(old=old_list, new=new_list)
        assert result.has_any_changes is False

    def test_duplicates_ignored(self) -> None:
        """Дубликаты не влияют на результат."""
        result = compute_subdomain_diff(
            old=["www.example.com", "www.example.com"],  # дубликат
            new=["www.example.com"],
        )
        assert result.has_any_changes is False

    def test_empty_old_empty_new(self) -> None:
        """Оба пустых — пустой diff."""
        result = compute_subdomain_diff(old=[], new=[])
        assert result.has_any_changes is False

    def test_empty_old_with_new(self) -> None:
        """Старый пустой, новый непустой — все считаются new."""
        result = compute_subdomain_diff(old=[], new=["a.example.com", "b.example.com"])
        assert result.has_any_changes is True
        assert set(result.new) == {"a.example.com", "b.example.com"}

    def test_with_old_empty_new(self) -> None:
        """Старый непустой, новый пустой — все считаются removed."""
        result = compute_subdomain_diff(old=["a.example.com", "b.example.com"], new=[])
        assert result.has_any_changes is True
        assert set(result.removed) == {"a.example.com", "b.example.com"}
