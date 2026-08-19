"""Unit tests for the acceptance-oracle locator CONVENTION
(`des compile-contract`'s oracle-locator decision, never ATD's or root's)."""

from __future__ import annotations

from pathlib import Path

from des.domain.oracle_locator_resolver import (
    oracle_slug,
    resolve_oracle_locator,
    resolve_oracle_test_dir,
)


def test_slug_converts_kebab_delivery_id_to_snake_case() -> None:
    assert oracle_slug("k4-maintenance-windows") == "k4_maintenance_windows"


def test_prefers_sibling_tests_dir_next_to_primary_target(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") == "hc/api/tests"


def test_falls_back_to_repository_root_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "pkg/widget.py") == "tests"


def test_sibling_dir_wins_over_repository_root_when_both_exist(
    tmp_path: Path,
) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") == "hc/api/tests"


def test_returns_none_when_no_test_dir_convention_exists(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api").mkdir(parents=True)
    assert resolve_oracle_test_dir(tmp_path, "hc/api/models.py") is None


def test_root_level_target_resolves_a_bare_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    assert resolve_oracle_test_dir(tmp_path, "widget.py") == "tests"


def test_resolve_oracle_locator_composes_dir_and_slug(tmp_path: Path) -> None:
    (tmp_path / "hc" / "api" / "tests").mkdir(parents=True)
    assert (
        resolve_oracle_locator(tmp_path, "hc/api/models.py", "k4-maintenance-windows")
        == "hc/api/tests/test_k4_maintenance_windows.py"
    )


def test_resolve_oracle_locator_none_when_undiscoverable(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    assert resolve_oracle_locator(tmp_path, "pkg/widget.py", "widget-color") is None
