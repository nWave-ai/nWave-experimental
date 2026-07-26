"""The shipped flavor parc is declared in three places; they must agree.

Which flavors this build ships is stated independently by:

1. the FILES in `nWave/flavors/` (what a document reader can find),
2. `ACTIVE_MODES` (what the identity guard will admit),
3. the Gherkin Examples table of AT-7 in
   `slice-02-iterator-contract.feature` (what the non-regression suite walks).

Three sites deciding the same thing separately is connascence at long locality:
nothing makes them move together, so they drift, and the drift surfaces as a
misleading verdict rather than as a missing declaration. It already happened --
the Examples table kept a `classic` row after both the flavor file and the
registry entry were removed, and the row then failed as though a shipped
composition had REGRESSED. Nothing had regressed; the table was simply naming a
flavor that no longer existed. A reader chasing that red would have gone looking
for a broken iterator.

This file is the one place that fails when they disagree, and it names WHICH of
the three is out of step -- so the next person to add or retire a flavor is told
exactly what they still have to update, instead of discovering it as a puzzling
regression somewhere downstream.
"""

from __future__ import annotations

import re
from pathlib import Path

from des.application.flavor_dispatcher import ACTIVE_MODES


_REPO_ROOT = Path(__file__).resolve().parents[3]
_FLAVORS_DIR = _REPO_ROOT / "nWave" / "flavors"
_FEATURE = (
    _REPO_ROOT
    / "tests"
    / "des"
    / "acceptance"
    / "declarative_gate_composition"
    / "slice-02-iterator-contract.feature"
)


def _shipped_flavor_files() -> set[str]:
    """Flavor ids that have a document. `_schema.yaml` is the schema, not a flavor."""
    return {
        path.stem
        for path in _FLAVORS_DIR.glob("*.yaml")
        if not path.stem.startswith("_")
    }


def _at7_example_rows() -> set[str]:
    """The flavor ids listed in AT-7's Examples table.

    Parsed rather than imported because Gherkin Examples cannot be computed --
    that inability is exactly why the table drifts, and why it needs an external
    check instead of a comment asking people to remember.
    """
    text = _FEATURE.read_text()
    marker = "Scenario Outline: The shipped <flavor> flavor event compositions"
    tail = text.split(marker, 1)[1]
    examples = tail.split("Examples:", 1)[1]
    rows: set[str] = set()
    for line in examples.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if rows:
                break
            continue
        cell = line.strip("|").strip()
        if cell and cell != "flavor":
            rows.add(cell)
    return rows


def test_every_shipped_flavor_file_is_an_executable_identity() -> None:
    """A flavor with a document but no registry entry can never be dispatched."""
    orphan_documents = _shipped_flavor_files() - set(ACTIVE_MODES)

    assert not orphan_documents, (
        f"WHAT: {sorted(orphan_documents)} have a flavor document in "
        f"{_FLAVORS_DIR} but no entry in ACTIVE_MODES. "
        "WHY: the identity guard refuses them before the document is ever read, "
        "so the file ships as dead weight and anyone reading the directory is "
        "told this build supports a mode it will refuse. "
        "HOW: add the id to ACTIVE_MODES if the mode is meant to be executable, "
        "or delete the document if the mode was retired."
    )


def test_every_executable_identity_has_a_shipped_document() -> None:
    """A registry entry with no document fails at dispatch, not at declaration."""
    missing_documents = set(ACTIVE_MODES) - _shipped_flavor_files()

    assert not missing_documents, (
        f"WHAT: {sorted(missing_documents)} are in ACTIVE_MODES but have no "
        f"document in {_FLAVORS_DIR}. "
        "WHY: the identity guard admits them, so the failure lands later, at "
        "composition time, on whoever happened to dispatch that mode -- far "
        "from the declaration that is actually wrong. "
        "HOW: ship the flavor document, or remove the id from ACTIVE_MODES."
    )


def test_at7_examples_table_lists_exactly_the_shipped_parc() -> None:
    """The hand-written table matches the parc it claims to walk.

    Asserted as set EQUALITY, not containment: a missing row silently narrows
    the non-regression sweep (a new flavor never gets checked), and a surplus
    row fails as a fake regression. Both are drift, and only equality catches
    both directions.
    """
    assert _at7_example_rows() == set(ACTIVE_MODES), (
        f"WHAT: AT-7's Examples table lists {sorted(_at7_example_rows())} but "
        f"this build ships {sorted(ACTIVE_MODES)}. "
        "WHY: a surplus row fails as a REGRESSION when nothing regressed (it is "
        "how `classic` lingered), and a missing row means a shipped flavor's "
        "compositions are never non-regression-checked at all. "
        f"HOW: edit the Examples table in {_FEATURE.name} to list exactly the "
        "ACTIVE_MODES ids."
    )


def test_the_regex_free_parser_actually_found_rows() -> None:
    """The parser is not exempt from the class it checks.

    If `_at7_example_rows()` silently returned an empty set -- a renamed
    scenario, a reformatted table -- the equality test above would still pass
    whenever ACTIVE_MODES was also empty, and would otherwise fail with a
    confusing message blaming the table rather than the parser. Pinning
    non-emptiness on a second axis keeps a broken reader from masquerading as a
    finding about what it read.
    """
    rows = _at7_example_rows()

    assert rows, (
        f"the AT-7 Examples parser found no rows in {_FEATURE}; the scenario "
        "title or table shape changed, so this file is no longer reading what "
        "it claims to read -- fix the parser before trusting its verdict"
    )
    assert all(re.fullmatch(r"[a-z0-9_]+", row) for row in rows), (
        f"parsed rows {sorted(rows)} do not look like flavor ids; the table "
        "shape changed under the parser"
    )
