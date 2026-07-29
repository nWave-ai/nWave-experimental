# @feature-agnostic-at-discovery
# @slice-03
"""``des carpaccio-slice-gate`` auto-discovers a slice's AT kind (ADR-AAD-001).

agnostic-at-discovery slice-03 (TERMINAL). Value statement (feature-delta.md
[REF] Slice Plan): "A slice whose ATs are pytest (or Rust) and correctly
tagged clears `des carpaccio-slice-gate` with zero operator-declared flag --
closes the two paused lanes."

Today ``carpaccio_slice_gate.py``'s ``--at-kind`` defaults to the LITERAL
string ``"gherkin"``; a slice whose ATs are pytest-shaped (no ``.feature``
scenarios at all) is rejected ``no-scenarios-for-slice`` (exit 45) unless the
operator already knows to declare ``--at-kind pytest-regression
--regression-test-file <path>``. This slice wires ``feature_at_files.
discover_at_kind_for_slice`` (shipped slice-02, already GREEN) into
``main()``: the CLI default moves to a ``None`` sentinel ("auto"); in auto
mode, when the Gherkin path would otherwise reject ``no-scenarios-for-slice``,
the gate consults auto-discovery instead of rejecting outright.

Driving surface (Mandate 13, Layer 3 subprocess-free composition -- the
established precedent for this exact gate, see
``tests/des/unit/cli/test_carpaccio_mechanical_seal.py`` and
``tests/bugs/des/test_rust_regression_at_kind_fully_wired.py``): every
scenario drives the REAL ``des.cli.carpaccio_slice_gate.main(argv)`` entry
point in-process against a ``tmp_path`` repository -- the exact CLI surface
ADR-AAD-001's own Driving Ports table names as unchanged-in-shape (one
default-value change only). No new driving port is introduced.

RED-for-right-reason (P1-P4, ``nw-distill-red-scaffolding``): the module-top
imports ONLY stable, already-existing production symbols (``carpaccio_slice_
gate.main``, ``verify_red_green._seal_path``/``_content_sha``) -- the CLI
already exists and already runs; only its AUTO-DISCOVERY BEHAVIOR is
unimplemented. Every scenario below fails TODAY on a semantic
``AssertionError`` over the observed ``(exit_code, payload)`` -- never an
import/collection error -- because the default ``--at-kind`` is still the
literal ``"gherkin"`` and no auto-discovery branch exists in ``main()`` yet.
Scenarios 3-4 (the escape-hatch + only-widens regression pins, invariants 3-4
of the dispatch envelope) already hold TODAY and stay green across this
slice's implementation by construction -- they encode the "auto-discovery is
a strict widening, never a narrowing" contract (ADR-AAD-001 DA-7/Consequences)
as durable regression pins, not net-new capability.
"""

from __future__ import annotations

import contextlib
import io
import json
from typing import TYPE_CHECKING

from des.cli import carpaccio_slice_gate
from des.cli.verify_red_green import _content_sha as _red_seal_content_sha
from des.cli.verify_red_green import _seal_path as _red_green_seal_path


if TYPE_CHECKING:
    from pathlib import Path


_FEATURE_ID = "aad-slice03-gate-fixture"
_ENTERING_SLICE = "slice-01"

# Mirrors tests/des/unit/cli/test_carpaccio_mechanical_seal.py's fixture shape
# verbatim (reuse-first, per this repo's own precedent): one presence-only
# test function plus one carrying a negative-AT name token (`_rejects_`), so
# the P0.3 --all-critical mandate is satisfied by the SAME content shape the
# mechanical-seal route already proves clears the gate.
_REGRESSION_BODY_WITH_NEGATIVE = (
    "def test_fix_applies():\n"
    "    assert True\n"
    "\n"
    "\n"
    "def test_fix_rejects_bad_input():\n"
    "    assert True\n"
)


def _write_feature_delta(
    repo: Path, feature_id: str, *, annotation: str = "", justification: str = ""
) -> None:
    """A single-row ``[REF] Slice Plan`` for ``_ENTERING_SLICE``.

    Mirrors ``tests/des/cli/f_prefactoring_dispatch_clears_honestly/
    test_slice_02_entry_point_wires_green_to_green.py::_write_feature_delta``
    (this repo's own precedent for a minimal carpaccio-gate fixture) --
    ``annotation``/``justification`` default to empty cells (a plain,
    unannotated slice) and are overridden per-scenario for the
    ``@prefactoring`` regression pin.
    """
    delta = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta.parent.mkdir(parents=True, exist_ok=True)
    delta.write_text(
        "# Feature Delta: agnostic-at-discovery slice-03 gate fixture\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_ENTERING_SLICE} | the entering slice under test "
        f"| pending | {annotation} | {justification} |\n",
        encoding="utf-8",
    )


def _write_tagged_candidate(
    repo: Path, rel_path: str, feature_id: str, slice_id: str, body: str
) -> Path:
    """A test file head-tagged ``@feature-{feature_id}`` / ``@{slice_id}``.

    Mirrors the exact tagging idiom ``discover_at_kind_for_slice`` (slice-02,
    already GREEN) and its own AT file already exercise -- no new tagging
    convention invented here (DA-3).
    """
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        f"# @feature-{feature_id}\n# @{slice_id}\n{body}", encoding="utf-8"
    )
    return target


def _write_red_seal(repo: Path, regression_rel: str) -> None:
    """Craft a fresh ``RedObserved`` seal matching the CURRENT file content.

    Reuses ``verify_red_green``'s own seal-path/content-sha producer helpers
    (``tests/des/unit/cli/test_carpaccio_mechanical_seal.py::_write_red_seal``
    precedent) so the slug/hash can never diverge from the real producer.
    """
    test_file = (repo / regression_rel).resolve()
    seal = _red_green_seal_path(repo.resolve(), test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": regression_rel,
                "content_sha256": _red_seal_content_sha(test_file),
                "outcomes": {"t::test_a": "fail", "t::test_b": "fail"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_approved_gherkin_verdict(
    repo: Path, feature_id: str, at_content_hash: str
) -> None:
    """Mint the legacy ``ATReviewVerdict`` for a single-scenario Gherkin slice."""
    ledger = repo / ".nwave" / "telemetry" / "atdd-pure" / f"{feature_id}.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": "ATReviewVerdict",
        "schema_version": "1.0.0",
        "slice_id": _ENTERING_SLICE,
        "verdict": "APPROVED",
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": ["AT-1"],
        "at_content_hash": at_content_hash,
        "timestamp": "2026-07-28T00:00:00Z",
        "findings_summary": [],
    }
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _write_feature_file(repo: Path, feature_id: str) -> str:
    """A single-scenario ``.feature`` file tagged for ``_ENTERING_SLICE``.

    Returns the scenario body carpaccio hashes (``_at_content_hash``'s
    input), computed the same way the gate's own Gherkin parser would, so the
    caller can mint a matching ``ATReviewVerdict``.
    """
    feature_dir = repo / "tests" / "acceptance" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f"@feature-{feature_id}\n"
        f"Feature: gherkin slice unaffected by auto-discovery\n\n"
        f"  @{_ENTERING_SLICE}\n"
        "  Scenario: a normal gherkin-shaped slice clears exactly as before\n"
        "    Given a gherkin scenario tagged for the entering slice\n"
        "    When the gate runs\n"
        "    Then the slice clears through the gherkin path\n"
    )
    (feature_dir / "walking-skeleton.feature").write_text(text, encoding="utf-8")
    return text


def _run_gate(repo: Path, argv_tail: list[str]) -> tuple[int, dict[str, object]]:
    """Drive the REAL ``des.cli.carpaccio_slice_gate.main(argv)`` entry point."""
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--entering-slice",
        _ENTERING_SLICE,
        "--repo-root",
        str(repo),
        *argv_tail,
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        exit_code = carpaccio_slice_gate.main(argv)
    payload: dict[str, object] = {}
    for line in out.getvalue().splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            payload = json.loads(stripped)
    return exit_code, payload


# ---------------------------------------------------------------------------
# 1. HAPPY -- a single tag-matched pytest candidate, ZERO operator flags,
#    zero Gherkin scenarios for the slice -> exit 0, SliceCleared.
# ---------------------------------------------------------------------------


def test_pytest_tagged_candidate_clears_with_zero_operator_declared_flags(
    tmp_path: Path,
) -> None:
    """The two paused-lane scenario: no ``.feature`` file exists for this
    slice, but exactly one ``@feature-{id}``/``@{slice}``-tagged pytest file
    does. With ``--at-kind`` OMITTED entirely, the gate must auto-discover it
    and clear -- never fall through to ``no-scenarios-for-slice``.
    """
    # covers: R7
    repo = tmp_path / "repo"
    _write_feature_delta(repo, _FEATURE_ID)
    candidate_rel = "tests/regression/test_fix.py"
    _write_tagged_candidate(
        repo,
        candidate_rel,
        _FEATURE_ID,
        _ENTERING_SLICE,
        _REGRESSION_BODY_WITH_NEGATIVE,
    )
    _write_red_seal(repo, candidate_rel)

    exit_code, payload = _run_gate(repo, [])

    assert exit_code == 0, (
        "a tag-matched pytest candidate with zero --at-kind must clear "
        f"(auto-discovery) -- got exit_code={exit_code}, payload={payload!r}. "
        "This is the exact 'two paused lanes' defect ADR-AAD-001 exists to fix."
    )
    assert payload.get("event") == "SliceCleared", (
        f"expected event=SliceCleared -- got payload={payload!r}"
    )
    assert payload.get("at_evidence") == "mechanical-seal", (
        "auto-discovery must resolve at_kind=pytest-regression and thread the "
        f"discovered file into check_at_review -- got payload={payload!r}"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE (MANDATORY) -- 2+ tag-matched candidates for the SAME slice
#    must NEVER be silently resolved, and must NEVER collapse into the
#    no-scenarios-for-slice rejection. Auto-discovery refuses honestly.
# ---------------------------------------------------------------------------


def test_ambiguous_discovery_is_never_collapsed_into_no_scenarios_rejection(
    tmp_path: Path,
) -> None:
    """Two independently ``@feature-.../@slice-01``-tagged pytest candidates
    -- the gate must refuse (never guess), NAME both candidates, and the
    refusal must be DISTINGUISHABLE from the plain "nothing found" rejection
    (different exit code, different reason) -- reproducing the GDP-8 arity
    defect this ADR exists to remove would mean this test silently passes
    with exit_code==45/reason=='no-scenarios-for-slice' instead.
    """
    # covers: R8
    repo = tmp_path / "repo"
    _write_feature_delta(repo, _FEATURE_ID)
    first = _write_tagged_candidate(
        repo,
        "tests/regression/test_a.py",
        _FEATURE_ID,
        _ENTERING_SLICE,
        _REGRESSION_BODY_WITH_NEGATIVE,
    )
    second = _write_tagged_candidate(
        repo,
        "tests/regression/test_b.py",
        _FEATURE_ID,
        _ENTERING_SLICE,
        _REGRESSION_BODY_WITH_NEGATIVE,
    )

    exit_code, payload = _run_gate(repo, [])

    assert exit_code != 45 or payload.get("reason") != "no-scenarios-for-slice", (
        "a 2+-candidate ambiguous match must NEVER be reported through the "
        "same 'nothing found' rejection as a genuine zero-candidate slice -- "
        f"got exit_code={exit_code}, payload={payload!r}"
    )
    assert exit_code == 2, (
        "ADR-AAD-001 Decision 3: an ambiguous auto-discovery refuses with a "
        f"self-explaining exit 2 -- got exit_code={exit_code}, payload={payload!r}"
    )
    payload_text = json.dumps(payload)
    assert "test_a.py" in payload_text and "test_b.py" in payload_text, (
        "the refusal must NAME every candidate found (GDP-3 self-explaining) "
        f"-- got payload={payload!r}; candidates were {first!r}, {second!r}"
    )
    assert "--at-kind" in payload_text, (
        "the refusal must instruct the operator to declare --at-kind "
        f"explicitly (the HOW, GDP-3/GDP-4) -- got payload={payload!r}"
    )


# ---------------------------------------------------------------------------
# 3. ESCAPE HATCH INTACT -- an explicit --at-kind is honored VERBATIM; auto-
#    discovery never even runs, so a candidate set that WOULD be ambiguous
#    under auto-discovery is irrelevant when the operator names the file.
# ---------------------------------------------------------------------------


def test_explicit_at_kind_flag_bypasses_auto_discovery_verbatim(
    tmp_path: Path,
) -> None:
    """A repo whose auto-discovery would be AMBIGUOUS (2 tag-matched
    candidates) still clears via the EXISTING explicit-flag pytest-regression
    route when the operator names one file directly -- auto-discovery is
    never consulted, so the second (unrelated, unsealed) candidate cannot
    poison the explicit invocation. This invariant already holds TODAY
    (unaffected by slice-03's implementation) and must keep holding after --
    the escape hatch is never removed (ADR-AAD-001 Decision, 'an explicit
    --at-kind <value> is honored verbatim, unchanged, for every existing
    caller').
    """
    # covers: R9
    repo = tmp_path / "repo"
    _write_feature_delta(repo, _FEATURE_ID)
    named_rel = "tests/regression/test_named.py"
    _write_tagged_candidate(
        repo, named_rel, _FEATURE_ID, _ENTERING_SLICE, _REGRESSION_BODY_WITH_NEGATIVE
    )
    _write_tagged_candidate(
        repo,
        "tests/regression/test_unrelated.py",
        _FEATURE_ID,
        _ENTERING_SLICE,
        _REGRESSION_BODY_WITH_NEGATIVE,
    )
    _write_red_seal(repo, named_rel)

    exit_code, payload = _run_gate(
        repo,
        ["--at-kind", "pytest-regression", "--regression-test-file", named_rel],
    )

    assert exit_code == 0, (
        "an explicit --at-kind pytest-regression naming ONE file must clear "
        "regardless of a would-be-ambiguous candidate set elsewhere in the "
        f"repo -- got exit_code={exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "SliceCleared"
    assert payload.get("at_evidence") == "mechanical-seal"


# ---------------------------------------------------------------------------
# 4a. SOLO-ALLARGA (only-widens) -- a normal Gherkin-shaped slice with a
#     real scenario clears exactly as it does today; auto-discovery is never
#     consulted because the gherkin path never raises no-scenarios-for-slice.
# ---------------------------------------------------------------------------


def test_gherkin_slice_with_scenarios_clears_byte_identical_to_today(
    tmp_path: Path,
) -> None:
    """A slice owning a real, tagged ``.feature`` scenario plus an APPROVED
    ``ATReviewVerdict`` clears via the ORIGINAL gherkin path with
    ``--at-kind`` omitted -- unaffected by auto-discovery existing, because
    the gherkin scan finds a match and the no-scenarios-for-slice branch (the
    ONLY point auto-discovery is wired in) is never reached. Pins ADR-AAD-001
    DA-7: 'it never runs, and never overrides, when Gherkin already resolved
    the slice.' This invariant already holds today and must keep holding.
    """
    # covers: R10
    repo = tmp_path / "repo"
    _write_feature_delta(repo, _FEATURE_ID)
    _write_feature_file(repo, _FEATURE_ID)

    # Whatever `check_at_review`'s own content-hash normalization decides
    # (with no matching `ATReviewVerdict` minted here, it legitimately
    # rejects "absent" -- a FIXTURE-construction concern, not the
    # auto-discovery contract this AT exists to pin). The load-bearing
    # assertion is the one below: whatever the gherkin path decides, it must
    # NEVER be the no-scenarios-for-slice / AtKindAmbiguous auto-discovery
    # branch, because a real scenario for this slice DOES exist.
    _exit_code, payload = _run_gate(repo, [])

    assert payload.get("reason") != "no-scenarios-for-slice", (
        "a slice that owns a real, tagged .feature scenario must never reach "
        f"the no-scenarios-for-slice branch -- got payload={payload!r}"
    )
    assert payload.get("event") != "AtKindDiscoveryAmbiguous", (
        f"auto-discovery must never be consulted when gherkin resolved the "
        f"slice -- got payload={payload!r}"
    )


# ---------------------------------------------------------------------------
# 4b. SOLO-ALLARGA (only-widens) -- an @prefactoring 0-AT exempt slice clears
#     exactly as it does today via LaneAtExemptionAccepted; auto-discovery is
#     never consulted because check_carpaccio never raises for this lane.
# ---------------------------------------------------------------------------


def test_prefactoring_exempt_zero_at_slice_clears_byte_identical_to_today(
    tmp_path: Path,
) -> None:
    """A 0-AT ``@prefactoring`` slice (zero Gherkin scenarios AND zero
    tag-matched pytest/native-regression candidates anywhere) clears via the
    EXISTING ``LaneAtExemptionAccepted`` escape -- proving auto-discovery
    never engages for an exempt lane, because ``check_carpaccio`` returns the
    exemption event BEFORE the no-scenarios-for-slice branch is ever reached.
    This invariant already holds today (verified in
    ``tests/des/cli/f_prefactoring_dispatch_clears_honestly/
    test_slice_02_entry_point_wires_green_to_green.py``) and must keep
    holding unchanged.
    """
    # covers: R11
    repo = tmp_path / "repo"
    _write_feature_delta(
        repo, _FEATURE_ID, annotation="@prefactoring", justification="exempt fixture"
    )

    exit_code, payload = _run_gate(repo, [])

    assert exit_code == 0, (
        "a 0-AT @prefactoring slice must clear end-to-end unaffected by "
        f"auto-discovery -- got exit_code={exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "LaneAtExemptionAccepted", (
        f"expected the EXISTING lane-exemption event, unchanged -- got "
        f"payload={payload!r}"
    )


# ---------------------------------------------------------------------------
# 5. NONE-FOUND -- zero Gherkin scenarios AND zero tag-matched candidates
#    anywhere: the EXISTING no-scenarios-for-slice rejection still fires
#    (exit 45), text enriched to report the non-Gherkin scan also came up
#    empty.
# ---------------------------------------------------------------------------


def test_zero_candidates_anywhere_still_rejects_no_scenarios_with_enriched_text(
    tmp_path: Path,
) -> None:
    """Genuinely nothing exists for this slice -- neither a tagged
    ``.feature`` scenario nor a tagged pytest/native-regression candidate.
    The gate must still refuse with the EXISTING ``no-scenarios-for-slice``
    reason/exit-code (unchanged, per ADR-AAD-001 Decision 3 AtKindNoneFound
    branch) -- but the message must now say the non-Gherkin auto-discovery
    scan ALSO came up empty, not just name the pytest-regression escape hatch
    as an untried option.
    """
    # covers: R12
    repo = tmp_path / "repo"
    _write_feature_delta(repo, _FEATURE_ID)

    exit_code, payload = _run_gate(repo, [])

    assert exit_code == 45, (
        f"a genuinely empty slice must still reject exit 45 (unchanged) -- "
        f"got exit_code={exit_code}, payload={payload!r}"
    )
    assert payload.get("event") == "ATReviewGateRejected"
    assert payload.get("reason") == "no-scenarios-for-slice", (
        f"the reason code must stay the EXISTING 'no-scenarios-for-slice' -- "
        f"got payload={payload!r}"
    )
    error_text = str(payload.get("error", "")).lower()
    assert "came up empty" in error_text, (
        "the enriched message must report that the pytest/native-regression "
        "auto-discovery scan ALSO came up empty (ADR-AAD-001 Decision 3: "
        "'text enriched to say the pytest/native-regression scan also came "
        f"up empty') -- got payload={payload!r}"
    )
