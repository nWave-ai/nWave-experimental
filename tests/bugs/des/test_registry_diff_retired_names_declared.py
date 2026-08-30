"""RED oracle: `des.cli.registry_diff.retired_names_declared` -- the reader
the new pre-commit gate (`scripts/hooks/check_retired_subcommand_declared.py`)
needs to know which names a `_RETIRED` mapping already covers, via static
AST parse only (never imports the file it reads -- same discipline as
`registry_names_from_source`).

Follow-up to F-INSTALL-REMOVAL-TRANSPARENCY (Ale): "the fix reproduces one
level up the same defect it repairs" -- `_RETIRED` is a hand-maintained
map; nothing stopped a future silent removal from skipping it. This reader
is what the new gate diffs against.
"""

from __future__ import annotations

from pathlib import Path


def test_extracts_keys_from_a_plain_dict_literal(tmp_path: Path) -> None:
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "main.py"
    path.write_text(
        '_RETIRED = {\n    "foo": object(),\n    "bar": object(),\n}\n',
        encoding="utf-8",
    )

    assert retired_names_declared(path) == frozenset({"foo", "bar"})


def test_extracts_keys_from_an_annotated_dict_literal(tmp_path: Path) -> None:
    """The exact shape `src/des/cli/__main__.py` uses: an annotated
    assignment, not a bare `Assign` node."""
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "main.py"
    path.write_text(
        '_RETIRED: dict = {\n    "foo": object(),\n}\n',
        encoding="utf-8",
    )

    assert retired_names_declared(path) == frozenset({"foo"})


def test_extracts_names_from_the_identity_dict_comprehension_shape(
    tmp_path: Path,
) -> None:
    """The shape `src/des/cli/__main__.py` actually uses today: one shared
    reason applied to every name in a fixed tuple."""
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "main.py"
    path.write_text(
        "_RETIRED: dict = {\n"
        "    name: object()\n"
        '    for name in ("alpha", "beta", "gamma")\n'
        "}\n",
        encoding="utf-8",
    )

    assert retired_names_declared(path) == frozenset({"alpha", "beta", "gamma"})


def test_none_for_missing_file(tmp_path: Path) -> None:
    from des.cli.registry_diff import retired_names_declared

    assert retired_names_declared(tmp_path / "absent.py") is None


def test_none_for_unparseable_file(tmp_path: Path) -> None:
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "broken.py"
    path.write_text("def(((( not python", encoding="utf-8")

    assert retired_names_declared(path) is None


def test_none_when_no_retired_assignment_present(tmp_path: Path) -> None:
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "main.py"
    path.write_text("x = 1\n", encoding="utf-8")

    assert retired_names_declared(path) is None


def test_none_for_an_unrecognised_comprehension_shape(tmp_path: Path) -> None:
    """A filtered or computed-key comprehension is unsupported -- fail-open,
    never guessed at (the gate must not silently trust an empty set)."""
    from des.cli.registry_diff import retired_names_declared

    path = tmp_path / "main.py"
    path.write_text(
        "_RETIRED: dict = {\n"
        "    name: object()\n"
        '    for name in ("alpha", "beta")\n'
        '    if name != "beta"\n'
        "}\n",
        encoding="utf-8",
    )

    assert retired_names_declared(path) is None


def test_the_real_registry_file_declares_all_18_retired_names() -> None:
    """Non-regression against the actual file this gate protects."""
    from des.cli.registry_diff import retired_names_declared

    real_path = (
        Path(__file__).resolve().parents[3] / "src" / "des" / "cli" / "__main__.py"
    )

    names = retired_names_declared(real_path)

    assert names is not None
    assert len(names) == 18
    assert "commit-slice" in names
    assert "revise-contract-round" in names
