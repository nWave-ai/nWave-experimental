"""RED oracle: F-INSTALL-REMOVAL-TRANSPARENCY deliverable (2) -- a summary
line reporting the subcommand-count delta between an old installed `des`
tree and the new one about to replace it, emitted ONLY when the set of
names actually changed.

RCA (docs/product/backlog.md:1327, nw-troubleshooter, already approved):
no point of the installer ever diffs `_REGISTRY`'s name set between an old
install and a new one -- `sweep_retired_assets` deletes FILES one-per-line,
which does not apply here because `_REGISTRY` is Python source rows inside
ONE file that travels whole via `shutil.copytree`.

Design decision this oracle pins (crafter must not reinterpret):

* New module ``des.cli.registry_diff`` (does not exist yet -- this file's
  own collection failure IS today's RED).
* ``registry_names_from_source(path: Path) -> frozenset[str] | None`` reads
  ``path`` (a ``__main__.py``-shaped file) with a **static AST parse only**
  -- it must NEVER import, exec, or otherwise execute the file it reads,
  because the old tree may belong to a different, unknown-compatible
  Python/des version. Returns ``None`` when the file is unreadable or does
  not parse (fail-open: no summary line rather than a fabricated diff).
  It extracts the first string-literal positional argument of every
  ``_SubcommandRow(...)`` call appearing in the module.
* ``RegistryDiff`` (frozen dataclass): ``old_count: int``, ``new_count:
  int``, ``removed: frozenset[str]``, ``added: frozenset[str]``.
* ``diff_registry_names(old_path: Path, new_path: Path) -> RegistryDiff |
  None`` -- ``None`` when either side's ``registry_names_from_source``
  returns ``None``.
* ``format_removal_summary(diff: RegistryDiff) -> str | None`` -- exactly
  ``f"des subcommands: {old} -> {new} ({removed} removed, {added} added)"``
  when ``diff.removed`` or ``diff.added`` is nonempty; ``None`` when the
  name set is identical (no noise on an unchanged registry).
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _write_toy_main(path: Path, names: list[str]) -> None:
    rows = "\n".join(
        f'    _SubcommandRow("{name}", "des.cli.{name.replace("-", "_")}", "main"),'
        for name in names
    )
    path.write_text(
        "from dataclasses import dataclass\n\n\n"
        "@dataclass(frozen=True)\n"
        "class _SubcommandRow:\n"
        "    name: str\n"
        "    module_path: str\n"
        "    function_name: str\n\n\n"
        "_REGISTRY = (\n" + rows + "\n)\n",
        encoding="utf-8",
    )


@pytest.fixture
def toy_trees(tmp_path: Path) -> tuple[Path, Path]:
    old_path = tmp_path / "old_main.py"
    new_path = tmp_path / "new_main.py"
    _write_toy_main(old_path, ["a", "b", "c", "d", "e"])  # 5 names
    _write_toy_main(new_path, ["a", "b", "f"])  # 3 names: c,d,e removed; f added
    return old_path, new_path


def test_registry_names_from_source_parses_names_via_ast(tmp_path: Path) -> None:
    from des.cli.registry_diff import registry_names_from_source

    path = tmp_path / "main.py"
    _write_toy_main(path, ["health-check", "commit"])

    names = registry_names_from_source(path)

    assert names == frozenset({"health-check", "commit"})


def test_registry_names_from_source_never_imports_or_execs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Portability/safety constraint from the dispatch brief: never execute
    code from a potentially different-version installed tree."""
    from des.cli.registry_diff import registry_names_from_source

    path = tmp_path / "main.py"
    _write_toy_main(path, ["x"])

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("registry_names_from_source must not import")

    monkeypatch.setattr(importlib, "import_module", _boom)

    names = registry_names_from_source(path)

    assert names == frozenset({"x"})


def test_registry_names_from_source_returns_none_for_unparseable_file(
    tmp_path: Path,
) -> None:
    from des.cli.registry_diff import registry_names_from_source

    path = tmp_path / "broken.py"
    path.write_text("def(((( not python", encoding="utf-8")

    assert registry_names_from_source(path) is None


def test_registry_names_from_source_returns_none_for_missing_file(
    tmp_path: Path,
) -> None:
    from des.cli.registry_diff import registry_names_from_source

    assert registry_names_from_source(tmp_path / "does_not_exist.py") is None


def test_diff_registry_names_reports_counts_removed_and_added(
    toy_trees: tuple[Path, Path],
) -> None:
    from des.cli.registry_diff import diff_registry_names

    old_path, new_path = toy_trees

    diff = diff_registry_names(old_path, new_path)

    assert diff is not None
    assert diff.old_count == 5
    assert diff.new_count == 3
    assert diff.removed == frozenset({"c", "d", "e"})
    assert diff.added == frozenset({"f"})


def test_diff_registry_names_none_when_either_side_unparseable(
    tmp_path: Path,
) -> None:
    from des.cli.registry_diff import diff_registry_names

    good = tmp_path / "good.py"
    _write_toy_main(good, ["a"])
    broken = tmp_path / "broken.py"
    broken.write_text("not python (((", encoding="utf-8")

    assert diff_registry_names(broken, good) is None
    assert diff_registry_names(good, broken) is None


def test_format_removal_summary_matches_exact_user_facing_format(
    toy_trees: tuple[Path, Path],
) -> None:
    from des.cli.registry_diff import diff_registry_names, format_removal_summary

    old_path, new_path = toy_trees
    diff = diff_registry_names(old_path, new_path)
    assert diff is not None

    summary = format_removal_summary(diff)

    assert summary == "des subcommands: 5 -> 3 (3 removed, 1 added)"


def test_format_removal_summary_is_none_when_name_set_is_unchanged(
    tmp_path: Path,
) -> None:
    from des.cli.registry_diff import diff_registry_names, format_removal_summary

    old_path = tmp_path / "old.py"
    new_path = tmp_path / "new.py"
    _write_toy_main(old_path, ["a", "b"])
    _write_toy_main(new_path, ["a", "b"])

    diff = diff_registry_names(old_path, new_path)
    assert diff is not None
    assert diff.removed == frozenset()
    assert diff.added == frozenset()

    assert format_removal_summary(diff) is None
