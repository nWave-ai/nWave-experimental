# @feature-agnostic-at-discovery
# @slice-02
"""``discover_at_kind_for_slice`` auto-resolves a slice's AT kind (ADR-AAD-001).

agnostic-at-discovery slice-02. Value statement (feature-delta.md [REF] Slice
Plan): "``discover_at_kind_for_slice`` can auto-resolve a slice's AT kind from
tag-matched files on disk, honestly reporting resolved/none-found/ambiguous."

Today no such function exists in ``des.application.feature_at_files`` -- this
slice adds ONE new pure function, composed entirely from the two sibling
resolvers this same module already ships (``feature_tagged_test_files`` for
the ``@feature-{id}`` head-tag candidate scan, ``resolve_test_file_attribution``
for the ``@slice-NN`` sub-tag filter) plus the ``AT_KIND_SUFFIX_MAP`` SSOT
slice-01 promoted into ``des.ports.test_runner_port``.

Contract-shape: pure-function (read-only; zero writes, zero raises -- every
outcome is a typed return value, never an exception -- per feature-delta.md
[REF] Architecture & Contract Tests, Contract-Tests row 1). The result has
arity 3 (``AtKindResolved`` / ``AtKindNoneFound`` / ``AtKindAmbiguous``,
DA-2) and ``AtKindAmbiguous`` must NEVER collapse into ``AtKindNoneFound`` --
"found something, cannot pick" is a different fact from "found nothing"
(GDP-8 arity corollary). The negative AT below
(``test_two_tag_matched_candidates_are_never_reported_as_none_found``) pins
exactly this non-collapse.

Driving surface (Mandate 13, Layer 3 composition-root default): every
scenario drives the REAL, STABLE, EXISTING production module
``des.application.feature_at_files`` directly -- the exact application-layer
composition root this feature's own DESIGN names (Driven Ports + Adapters:
"``des.application.feature_at_files`` ... gains
``discover_at_kind_for_slice``"). No new CLI driving port exists at this
granularity (slice-03 wires the CLI); this repo's own precedent already
tests an application-layer function directly this same way (see
``test_slice_01_suffix_map_ssot.py``, this feature's own slice-01 AT file).

RED-for-right-reason (P1-P4, ``nw-distill-red-scaffolding``): the module-top
import is ONLY the stable, already-existing ``feature_at_files`` module --
never the not-yet-defined ``discover_at_kind_for_slice`` name or the 3
not-yet-defined result dataclasses. Each scenario resolves those absent
names via ``getattr(module, name, None)`` and asserts on the guard FIRST,
converting the otherwise-raw ``AttributeError``/``TypeError`` into a
semantic, message-carrying ``AssertionError`` at RUNTIME inside the test
body -- collection never fails, every test fails for the same honest reason:
the production symbol does not exist yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.application import feature_at_files


_FEATURE_ID = "agnostic-at-discovery"
_SLICE_ID = "slice-02"
_OTHER_SLICE_ID = "slice-01"


def _write_candidate(
    repo: Path, rel_path: str, slice_id: str, comment: str = "#"
) -> Path:
    """A test file head-tagged ``@feature-{_FEATURE_ID}`` / ``@{slice_id}``.

    Mirrors the fixture-building idiom already established for this exact
    tag convention (``tests/des/unit/application/
    test_feature_files_for_slice_pytest_discovery.py:_write_tagged_pytest_at``,
    ``tests/des/acceptance/carpaccio_pytest_at_comment_tag_binding/steps/``)
    -- per DA-3, no new tagging convention is invented here. The scan is
    comment-syntax-agnostic (plain substring match over the head window), so
    the ``comment`` marker is cosmetic realism, not a functional requirement.
    """
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"{comment} @feature-{_FEATURE_ID}\n{comment} @{slice_id}\n"
        "def test_delivers_the_slice():\n    assert True\n"
    )
    return target


def _resolve_symbol(name: str):
    symbol = getattr(feature_at_files, name, None)
    assert symbol is not None, (
        f"des.application.feature_at_files must expose {name} "
        "(ADR-AAD-001 slice-02) -- not yet implemented."
    )
    return symbol


# ---------------------------------------------------------------------------
# 1. exactly-one tag-matched candidate, recognized suffix -> AtKindResolved
#    (parametrized over both currently-recognized suffixes, DA-4's mapping).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rel_path", "expected_at_kind"),
    [
        ("tests/regression/test_balance.py", "pytest-regression"),
        ("tests/regression/balance_invariants.rs", "native-regression"),
    ],
)
def test_single_recognized_suffix_candidate_resolves_at_kind(
    tmp_path: Path, rel_path: str, expected_at_kind: str
) -> None:
    """A single ``@feature-.../@slice-02``-tagged candidate whose OWN suffix
    is in ``AT_KIND_SUFFIX_MAP`` must resolve to ``AtKindResolved`` naming
    the DA-4 CLI-vocabulary ``at_kind`` value (``.py`` -> pytest-regression,
    ``.rs`` -> native-regression) and the exact candidate file.
    """
    # covers: R1
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    resolved_cls = _resolve_symbol("AtKindResolved")

    candidate = _write_candidate(tmp_path, rel_path, _SLICE_ID)

    result = discover_at_kind_for_slice(tmp_path, _FEATURE_ID, _SLICE_ID)

    assert isinstance(result, resolved_cls), (
        f"expected AtKindResolved for exactly one recognized-suffix "
        f"candidate -- got {result!r}"
    )
    assert result.at_kind == expected_at_kind, (
        f"expected at_kind={expected_at_kind!r} (DA-4 runner->at_kind "
        f"mapping) -- got {result.at_kind!r}"
    )
    assert result.regression_test_file == candidate, (
        f"expected regression_test_file={candidate!r} -- got "
        f"{result.regression_test_file!r}"
    )


# ---------------------------------------------------------------------------
# 2. zero tag-matched candidates -> AtKindNoneFound.
# ---------------------------------------------------------------------------


def test_zero_tag_matched_candidates_report_none_found(tmp_path: Path) -> None:
    """No file anywhere below ``repo`` carries the
    ``@feature-agnostic-at-discovery`` / ``@slice-02`` tag pair -> the
    honest zero-candidate outcome is ``AtKindNoneFound``, never a raise.
    """
    # covers: R2
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    none_found_cls = _resolve_symbol("AtKindNoneFound")

    # An unrelated, untagged file must not be mistaken for a candidate.
    unrelated = tmp_path / "tests" / "unrelated" / "test_noise.py"
    unrelated.parent.mkdir(parents=True, exist_ok=True)
    unrelated.write_text("def test_noise():\n    assert True\n")

    result = discover_at_kind_for_slice(tmp_path, _FEATURE_ID, _SLICE_ID)

    assert isinstance(result, none_found_cls), (
        f"expected AtKindNoneFound for zero tag-matched candidates -- got {result!r}"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE AT -- 2+ tag-matched candidates must NEVER collapse into
#    AtKindNoneFound. This is the whole point of the slice (DA-2, GDP-8
#    arity corollary): "found something, cannot pick" != "found nothing".
# ---------------------------------------------------------------------------


def test_two_tag_matched_candidates_are_never_reported_as_none_found(
    tmp_path: Path,
) -> None:
    """Two independently ``@feature-.../@slice-02``-tagged candidate files
    (both recognized-suffix) must resolve to ``AtKindAmbiguous`` naming both
    candidates -- collapsing this into ``AtKindNoneFound`` would reproduce
    the exact defect class this feature exists to remove (a rejection that
    claims "nothing found" when something WAS found, just not resolvable).
    """
    # covers: R3
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    none_found_cls = _resolve_symbol("AtKindNoneFound")
    ambiguous_cls = _resolve_symbol("AtKindAmbiguous")

    first = _write_candidate(tmp_path, "tests/regression/test_a.py", _SLICE_ID)
    second = _write_candidate(tmp_path, "tests/regression/test_b.py", _SLICE_ID)

    result = discover_at_kind_for_slice(tmp_path, _FEATURE_ID, _SLICE_ID)

    assert not isinstance(result, none_found_cls), (
        "a 2+-candidate match must NEVER be reported as AtKindNoneFound "
        f"(DA-2 non-collapse) -- got {result!r}"
    )
    assert isinstance(result, ambiguous_cls), (
        f"expected AtKindAmbiguous for 2+ tag-matched candidates -- got {result!r}"
    )
    assert set(result.candidates) == {first, second}, (
        f"expected candidates={{first, second}}={{{first!r}, {second!r}}} -- "
        f"got {result.candidates!r}"
    )


# ---------------------------------------------------------------------------
# 4. exactly-one tag-matched candidate, UNRECOGNIZED suffix -> AtKindAmbiguous
#    (never AtKindNoneFound, never a guessed AtKindResolved -- DA-2/DA-4).
# ---------------------------------------------------------------------------


def test_single_candidate_with_unrecognized_suffix_reports_ambiguous(
    tmp_path: Path,
) -> None:
    """A single tag-matched candidate whose suffix is NOT in
    ``AT_KIND_SUFFIX_MAP`` (e.g. ``.go``, not yet a registered language) must
    resolve to ``AtKindAmbiguous`` -- auto-discovery refuses to guess a
    runner for a structurally unclassifiable candidate, per DA-2/DA-4.
    """
    # covers: R4
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    ambiguous_cls = _resolve_symbol("AtKindAmbiguous")

    candidate = _write_candidate(
        tmp_path, "tests/regression/balance_test.go", _SLICE_ID
    )

    result = discover_at_kind_for_slice(tmp_path, _FEATURE_ID, _SLICE_ID)

    assert isinstance(result, ambiguous_cls), (
        f"expected AtKindAmbiguous for a matched-but-unrecognized-suffix "
        f"candidate -- got {result!r}"
    )
    assert candidate in result.candidates, (
        f"expected {candidate!r} among result.candidates -- got {result.candidates!r}"
    )


# ---------------------------------------------------------------------------
# 5. Slice-binding filter -- a candidate tagged for a DIFFERENT slice of the
#    SAME feature must not leak into slice-02's candidate set.
# ---------------------------------------------------------------------------


def test_candidate_files_tagged_for_other_slices_do_not_leak_into_resolution(
    tmp_path: Path,
) -> None:
    """A file head-tagged ``@feature-agnostic-at-discovery`` but ``@slice-01``
    (another slice of the SAME feature) must not count as a slice-02
    candidate -- resolving slice-02 must see only the genuinely slice-02
    -tagged file and return AtKindResolved for it alone, not AtKindAmbiguous.
    """
    # covers: R5
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    resolved_cls = _resolve_symbol("AtKindResolved")

    other_slice_file = _write_candidate(
        tmp_path, "tests/regression/other_slice.py", _OTHER_SLICE_ID
    )
    this_slice_file = _write_candidate(
        tmp_path, "tests/regression/this_slice.py", _SLICE_ID
    )

    result = discover_at_kind_for_slice(tmp_path, _FEATURE_ID, _SLICE_ID)

    assert isinstance(result, resolved_cls), (
        "a slice-01-tagged file must not leak into slice-02's candidate "
        f"set -- expected AtKindResolved for the single slice-02 file, got "
        f"{result!r}"
    )
    assert result.regression_test_file == this_slice_file, (
        f"expected regression_test_file={this_slice_file!r} (the ONLY "
        f"slice-02-tagged file) -- got {result.regression_test_file!r}; "
        f"other_slice_file={other_slice_file!r} must have been excluded"
    )


# ---------------------------------------------------------------------------
# 6. Purity -- a missing repo directory must degrade to a typed outcome,
#    never raise (Contract-Tests row 1: "zero writes, zero raises").
# ---------------------------------------------------------------------------


def test_discover_at_kind_for_slice_never_raises_on_a_missing_repo_directory(
    tmp_path: Path,
) -> None:
    """A non-existent ``repo`` path must not raise -- the sibling resolvers
    this function composes (``feature_tagged_test_files``) already degrade a
    missing directory to zero candidates, so the honest outcome here is
    ``AtKindNoneFound``, never an exception.
    """
    # covers: R6
    discover_at_kind_for_slice = _resolve_symbol("discover_at_kind_for_slice")
    none_found_cls = _resolve_symbol("AtKindNoneFound")

    missing_repo = tmp_path / "does-not-exist"

    result = discover_at_kind_for_slice(missing_repo, _FEATURE_ID, _SLICE_ID)

    assert isinstance(result, none_found_cls), (
        f"a missing repo directory must degrade to AtKindNoneFound (zero "
        f"raises, Contract-Tests row 1) -- got {result!r}"
    )
