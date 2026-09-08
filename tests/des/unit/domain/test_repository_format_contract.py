"""What the repository DECLARES about the form of its files, and nothing more."""

from __future__ import annotations

import pytest

from des.domain.repository_format_contract import declared_format_contract


@pytest.mark.parametrize(
    "table",
    ["[tool.ruff]", "[tool.ruff.format]", "  [tool.ruff.lint.isort]  "],
    ids=["bare", "format", "nested-indented"],
)
def test_a_ruff_table_in_pyproject_declares_the_repositorys_formatter(
    table: str,
) -> None:
    contract = declared_format_contract(f"[project]\nname = 'x'\n{table}\n", None)

    assert contract is not None
    assert contract.tool == "ruff"
    assert contract.declaration == "pyproject.toml [tool.ruff]"


def test_a_dedicated_ruff_config_file_declares_it_by_existing() -> None:
    contract = declared_format_contract(None, "line-length = 88\n")

    assert contract is not None
    assert contract.declaration == "ruff.toml"


@pytest.mark.parametrize(
    "pyproject",
    [
        "",
        "[project]\nname = 'x'\n",
        "[tool.ruffian]\n",
        '[tool.other]\nnote = "see [tool.ruff] in the sibling repo"\n',
    ],
    ids=["empty", "no-ruff", "prefix-collision", "mentioned-in-a-string"],
)
def test_a_repository_that_declares_no_formatter_has_no_contract(
    pyproject: str,
) -> None:
    # Nothing to honour is a legitimate answer, not a degraded one: the runner
    # enforces the repository's declaration, never its own taste.
    assert declared_format_contract(pyproject, None) is None


def test_the_contract_reaches_only_the_files_its_tool_decides_the_form_of() -> None:
    contract = declared_format_contract("[tool.ruff]\n", None)
    assert contract is not None

    paths = (
        "src/a.py",
        "src/b.pyi",
        "docs/c.md",
        "notes.txt",
        "Makefile",
        "analysis.ipynb",
    )

    assert contract.reaches(paths) == ("src/a.py", "src/b.pyi")


def test_a_malformed_declaration_degrades_to_no_contract_rather_than_raising() -> None:
    # A candidate refused by a config parser would be a worse failure than an
    # unnormalized line, so detection never raises on text it cannot read.
    assert declared_format_contract("[[[ not toml at all", None) is None


def repairs(pyproject: str) -> tuple[tuple[str, ...], ...]:
    contract = declared_format_contract(pyproject, None)
    assert contract is not None
    return contract.repairs


def test_the_declared_repair_is_the_ordered_pair_the_quality_job_runs() -> None:
    # `scripts/local_ci.py --python-quality`, the entry of both the local hook
    # and the CI job, runs the auto-fixing check BEFORE the formatter. A repair
    # that ran only the formatter would integrate a candidate that job rejects.
    declared = repairs('[tool.ruff.lint]\nselect = ["E", "F", "I"]\n')

    assert [repair[0] for repair in declared] == ["check", "format"]
    assert "--fix-only" in declared[0]
    assert declared[0][-2:] == ("--select", "I")


@pytest.mark.parametrize(
    "selection",
    [
        '[tool.ruff.lint]\nselect = ["E", "F", "I"]\n',
        '[tool.ruff.lint]\nselect = [\n    "E",  # errors\n    "I",  # isort\n]\n',
        '[tool.ruff.lint]\nextend-select = ["I001"]\n',
        '[tool.ruff.lint]\nselect = ["ALL"]\n',
    ],
    ids=["inline", "multiline-commented", "extend-select-code", "all"],
)
def test_import_order_is_repaired_where_the_repository_selected_isort(
    selection: str,
) -> None:
    assert len(repairs(selection)) == 2


@pytest.mark.parametrize(
    "selection",
    [
        "[tool.ruff]\nline-length = 88\n",
        '[tool.ruff.lint]\nselect = ["E", "F"]\n',
        '[tool.ruff.lint]\nselect = ["ISC"]\n',
    ],
    ids=["no-selection", "isort-not-selected", "initial-collision"],
)
def test_import_order_is_left_alone_where_the_repository_did_not_select_it(
    selection: str,
) -> None:
    # A repository that never selected isort has not declared unsorted imports a
    # violation; reordering them would be the runner imposing its own taste.
    # `ISC` shares the initial and is a different family.
    assert repairs(selection) == (("format", "--force-exclude", "--no-cache"),)


def test_every_repair_overrules_neither_the_repositorys_exclude_nor_its_disk() -> None:
    # `--force-exclude`: ruff ignores its own exclude for an explicitly passed
    # path, so without the flag the runner would rewrite a file the repository
    # put out of scope. `--no-cache`: a `.ruff_cache/` directory appearing
    # mid-run reads as unattributed drift in a repository that does not ignore
    # it.
    for repair in repairs('[tool.ruff.lint]\nselect = ["I"]\n'):
        assert "--force-exclude" in repair
        assert "--no-cache" in repair


def test_an_empty_ruff_config_file_declares_the_formatter_by_existing() -> None:
    # The file has no other purpose, so its emptiness is not an absence.
    contract = declared_format_contract(None, "")

    assert contract is not None
    assert contract.declaration == "ruff.toml"
