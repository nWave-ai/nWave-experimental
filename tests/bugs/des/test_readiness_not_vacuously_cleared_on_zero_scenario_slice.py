"""Regression: `des verify-readiness-pre-dispatch` VACUOUSLY clears a slice
that owns ZERO matching `@slice-NN` scenarios, while `des carpaccio-slice-gate`
correctly REJECTS the very same slice -- the two gates contradict.

Charter: docs/product/expectations/fix-readiness-not-vacuously-cleared/
two-gates-agree-on-a-zero-scenario-slice.md
RCA: bug #73 (Rex).

Root cause (single locus, confirmed by code read): `_check_scenario_slice_tags`
(`src/des/cli/verify_readiness_pre_dispatch.py:292`) checks a FEATURE-WIDE
predicate -- "every scenario in the feature's .feature files carries SOME
`@slice-NN` tag" -- and never even receives the entering `slice_id` as an
argument. Contrast carpaccio's `check_carpaccio` (`carpaccio_format.py:949`,
via `_slice_scenarios(scenarios, entering_slice)`): a PER-SLICE predicate --
"the ENTERING slice owns >=1 matching scenario" -- that raises
`no-scenarios-for-slice` (`GateError` exit 45 / `ATReviewGateRejected`) when
the entering slice owns none. A feature whose only scenario is tagged
`@slice-01` (never `@slice-02`) makes readiness for `slice-02` see "no
UNTAGGED scenarios" (vacuously satisfied -- the bug) while carpaccio for the
SAME `slice-02` sees "zero scenarios OWNED by slice-02" (correctly rejected).
Twin of bug #27 (fix-readiness-gate-clears-on-empty, the sibling
`slice_plan_section` cross-reference gap this same file already closed).

Driving port (Mandate 16, no-direct-domain-testing; mirrors
`test_readiness_gate_refuses_nonexistent_slice.py`'s established idiom): every
AT below drives `des.cli.verify_readiness_pre_dispatch.main(argv)` AND
`des.cli.carpaccio_slice_gate.main(argv)` -- the SAME composition roots
`des verify-readiness-pre-dispatch` / `des carpaccio-slice-gate` dispatch --
capturing the emitted stdout JSON verdict line. The ledger fixture for the
positive-clear guard (AT-2) is authored via the THIRD production composition
root, `des.cli.at_review_verdict.main(argv)` (`des record-at-review-verdict`),
so the AT-set/content-hash the ledger record carries is derived by the SAME
producer carpaccio's `check_at_review` consults -- never a hand-rolled hash.
No subprocess fork needed (in-process CLI-JSON-shape bug); hermetic, box-light.

RED-for-right-reason: `test_readiness_must_agree_with_carpaccio_on_zero_scenario_slice`
below FAILS today with a genuine semantic `AssertionError` -- readiness reports
`scenario_slice_tags` `satisfied: True` / `verdict: "cleared"` for `slice-02`
while carpaccio, run against the SAME fixture, REJECTS `slice-02` with
`no-scenarios-for-slice` -- never an import/collection error.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from des.cli import at_review_verdict, carpaccio_slice_gate
from des.cli import verify_readiness_pre_dispatch as readiness_gate


_FEATURE_ID = "synthetic-readiness-vacuous-slice-feature"
_SLICE_WITH_SCENARIO = "slice-01"
_SLICE_WITHOUT_SCENARIO = "slice-02"
_INV_SCENARIO_TAGS = "scenario_slice_tags"

_ZERO_FEATURE_FILES_FEATURE_ID = "synthetic-readiness-no-feature-files-yet"


def _author_feature_delta_two_slices(repo_root: Path, feature_id: str) -> None:
    """A hermetic feature-delta with TWO Slice-Plan rows (`slice-01`,
    `slice-02`), neither carrying `@coupled`/`@prefactoring`/`@walking_skeleton`
    -- plain rows, mirrors `_author_feature_delta_with_one_real_slice`
    (`test_readiness_gate_refuses_nonexistent_slice.py`) extended to two rows
    plus the sustainability leg both gates' aggregate consults."""
    workspace = repo_root / "docs" / "feature" / feature_id
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_SLICE_WITH_SCENARIO} | owns the only authored scenario |\n"
        f"| {_SLICE_WITHOUT_SCENARIO} | owns zero authored scenarios |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _author_single_scenario_tagged_slice_01(repo_root: Path, feature_id: str) -> None:
    """ONE `.feature` file, self-identifying via `@feature-{feature_id}`
    (carpaccio's tag-based resolver, `feature_at_files.feature_tag_files`) AND
    living under `tests/` with `feature_id` in its path (readiness's own
    path-based resolver, `_check_scenario_slice_tags`'s `feature_id in
    p.parts` filter) -- discoverable by BOTH gates. Its ONE Scenario carries
    `@slice-01` only -- `slice-02` owns zero matching scenarios."""
    acceptance_dir = repo_root / "tests" / "bugs" / "des" / "acceptance" / feature_id
    acceptance_dir.mkdir(parents=True)
    (acceptance_dir / "only_slice_01.feature").write_text(
        f"@feature-{feature_id}\n"
        "Feature: Only slice-01 owns an authored scenario\n\n"
        f"  @{_SLICE_WITH_SCENARIO}\n"
        "  Scenario: A scenario belonging exclusively to slice-01\n"
        "    Given a precondition slice-01 sets up\n"
        "    When the slice-01 behavior runs\n"
        "    Then the slice-01 outcome is observed\n"
    )


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> Path:
    """A hermetic repo_root: a bare `.git` marker (no real `git init` -- both
    gates are git-free, target-machine agnosticism) plus a two-slice feature-
    delta and ONE `.feature` file whose only scenario is tagged `@slice-01`."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    _author_feature_delta_two_slices(repo_root, _FEATURE_ID)
    _author_single_scenario_tagged_slice_01(repo_root, _FEATURE_ID)
    return repo_root


def _run_readiness(repo_root: Path, feature_id: str, slice_id: str) -> tuple[int, dict]:
    """Invoke `des verify-readiness-pre-dispatch`'s `main(argv)` in-process
    and capture the emitted stdout JSON verdict line -- mirrors `_run` in
    `test_readiness_gate_refuses_nonexistent_slice.py` verbatim."""
    argv = [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--repo-root",
        str(repo_root),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = readiness_gate.main(argv)
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _run_carpaccio(
    repo_root: Path, feature_id: str, entering_slice: str
) -> tuple[int, dict]:
    """Invoke `des carpaccio-slice-gate`'s `main(argv)` in-process and capture
    the emitted stdout JSON verdict line. `main()` never raises/`sys.exit`s --
    it catches its own `GateError` and returns the exit code -- so no
    `pytest.raises`/`SystemExit` wrapper is needed (confirmed by code read,
    `carpaccio_slice_gate.py:930-932`)."""
    argv = [
        "--feature-id",
        feature_id,
        "--entering-slice",
        entering_slice,
        "--repo-root",
        str(repo_root),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = carpaccio_slice_gate.main(argv)
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _record_approved_at_review_verdict(
    repo_root: Path, feature_id: str, slice_id: str
) -> None:
    """Author an APPROVED `ATReviewVerdict` ledger record via the production
    composition root `des record-at-review-verdict` (`at_review_verdict.main`)
    -- the SAME producer `check_at_review` consults, so `at_ids` /
    `at_content_hash` are derived identically to what carpaccio itself
    recomputes at entry. Never a hand-rolled hash (would silently drift from
    the producer's own derivation)."""
    argv = [
        "--feature-id",
        feature_id,
        "--slice-id",
        slice_id,
        "--verdict",
        "APPROVED",
        "--reviewer-agent-id",
        "test-harness-reviewer",
        "--repo-root",
        str(repo_root),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = at_review_verdict.main(argv)
    assert code == 0, (
        f"fixture setup failed: recording an APPROVED AT-review verdict for "
        f"{feature_id}/{slice_id} must succeed. stdout={out.getvalue()!r}"
    )


def _invariant(report: dict, invariant_id: str) -> dict:
    for inv in report.get("invariants", []):
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(
        f"invariant {invariant_id!r} missing from report entirely -- the "
        f"gate must always emit every invariant it evaluates. observed "
        f"report={report}"
    )


# --- AT-1 (core -- RED today, the diagnosed defect) --------------------------


@pytest.mark.negative_at
def test_readiness_must_agree_with_carpaccio_on_zero_scenario_slice(
    hermetic_repo: Path,
) -> None:
    """`slice-02` owns ZERO scenarios tagged `@slice-02` (the fixture's only
    scenario is tagged `@slice-01`). `des carpaccio-slice-gate` correctly
    REJECTS `slice-02` (`no-scenarios-for-slice`, exit 45). `des
    verify-readiness-pre-dispatch` for the SAME `(feature, slice-02)` must
    ALSO refuse -- not vacuously CLEAR it.

    RED today (bug #73): `_check_scenario_slice_tags` checks a FEATURE-WIDE
    "every scenario has SOME @slice-NN tag" predicate that never receives
    `slice_id` at all -- it cannot distinguish "slice-02 owns scenarios" from
    "slice-02 owns none but slice-01's scenario happens to be tagged". Today
    it reports `scenario_slice_tags` `satisfied: True` and the overall
    readiness `verdict: "cleared"` for `slice-02`, directly contradicting
    carpaccio's rejection of the identical slice.

    CONTRACT_SHAPE: bounded-change
    """
    carpaccio_code, carpaccio_report = _run_carpaccio(
        hermetic_repo, _FEATURE_ID, _SLICE_WITHOUT_SCENARIO
    )
    # Control assertion: carpaccio's own per-slice predicate already rejects
    # slice-02 correctly -- this is the STRICTER, correct gate; if this ever
    # fails the fixture itself is malformed, not the bug under test.
    assert carpaccio_code == 45 and carpaccio_report.get("reason") == (
        "no-scenarios-for-slice"
    ), (
        "fixture control check failed: carpaccio must reject slice-02 with "
        f"no-scenarios-for-slice. observed code={carpaccio_code}, "
        f"report={carpaccio_report}"
    )

    readiness_code, readiness_report = _run_readiness(
        hermetic_repo, _FEATURE_ID, _SLICE_WITHOUT_SCENARIO
    )

    # THE BUG: readiness must NOT clear a slice carpaccio just rejected for
    # owning zero matching scenarios -- the two gates must agree, and
    # agreement must land on the STRICTER (refuse) side.
    assert readiness_report.get("verdict") != "cleared" and readiness_code != 0, (
        "readiness must NOT vacuously clear slice-02 while carpaccio rejects "
        "the identical slice for owning zero matching scenarios. THE BUG: "
        "_check_scenario_slice_tags (verify_readiness_pre_dispatch.py:292) "
        "checks a feature-wide 'every scenario has SOME @slice-NN tag' "
        "predicate and never receives slice_id, so it cannot see that "
        "slice-02 itself owns no scenarios. observed readiness "
        f"verdict={readiness_report.get('verdict')!r}, code={readiness_code}, "
        f"invariants={readiness_report.get('invariants')} -- contrast "
        f"carpaccio's rejection of the SAME slice: {carpaccio_report}"
    )

    scenario_tags_inv = _invariant(readiness_report, _INV_SCENARIO_TAGS)
    assert scenario_tags_inv["satisfied"] is False, (
        "the scenario_slice_tags invariant must report satisfied: false for "
        "slice-02 (it owns zero matching scenarios), mirroring carpaccio's "
        f"own per-slice verdict. observed={scenario_tags_inv}"
    )

    # Loud, not a silent flip: the refusal must carry a remediation naming
    # the offending slice (every-failure-explains-what-why-how, STANDING).
    remediation = scenario_tags_inv.get("remediation") or ""
    assert remediation, (
        "the scenario_slice_tags refusal must carry a what/why/how "
        f"remediation, not a bare failure. observed={scenario_tags_inv}"
    )
    assert _SLICE_WITHOUT_SCENARIO in remediation, (
        "the remediation must NAME the offending slice id so the operator "
        f"knows exactly what to fix. observed remediation={remediation!r}"
    )


# --- AT-2 (negative -- over-correction guard: a real slice still clears) ----


def test_readiness_and_carpaccio_both_still_clear_a_slice_that_owns_a_scenario(
    hermetic_repo: Path,
) -> None:
    """`slice-01` DOES own a matching scenario (the fixture's only scenario is
    tagged `@slice-01`). Both gates must STILL clear it -- the fix for AT-1
    must not now over-refuse a legitimately satisfied slice.

    CONTRACT_SHAPE: bounded-change
    """
    _record_approved_at_review_verdict(hermetic_repo, _FEATURE_ID, _SLICE_WITH_SCENARIO)

    carpaccio_code, carpaccio_report = _run_carpaccio(
        hermetic_repo, _FEATURE_ID, _SLICE_WITH_SCENARIO
    )
    assert carpaccio_code == 0 and carpaccio_report.get("event") == "SliceCleared", (
        "carpaccio must clear slice-01 -- it owns the one authored scenario. "
        f"observed code={carpaccio_code}, report={carpaccio_report}"
    )

    readiness_code, readiness_report = _run_readiness(
        hermetic_repo, _FEATURE_ID, _SLICE_WITH_SCENARIO
    )
    assert readiness_report.get("verdict") == "cleared" and readiness_code == 0, (
        "readiness must still clear slice-01 -- the AT-1 fix must not "
        f"over-refuse a legitimately satisfied slice. observed verdict="
        f"{readiness_report.get('verdict')!r}, code={readiness_code}, "
        f"invariants={readiness_report.get('invariants')}"
    )
    scenario_tags_inv = _invariant(readiness_report, _INV_SCENARIO_TAGS)
    assert scenario_tags_inv["satisfied"] is True, (
        "the scenario_slice_tags invariant must stay satisfied: true for "
        f"slice-01 (it owns a matching scenario). observed={scenario_tags_inv}"
    )


# --- AT-3 (negative -- the legitimate vacuous case must survive the fix) ----


def test_readiness_still_clears_when_the_feature_owns_no_feature_files_at_all(
    tmp_path: Path,
) -> None:
    """A feature with ZERO `.feature` files anywhere (first dispatch, before
    DISTILL has authored any scenario) must STILL clear on
    `scenario_slice_tags` -- that vacuous-truth branch (`_check_scenario_
    slice_tags`'s `if not feature_files: return satisfied=True`) is
    INTENTIONAL and distinct from AT-1's bug (a slice with SOME scenarios
    authored, none of which match the entering slice). The fix must not
    blanket-reject every absence of a matching scenario -- only the case
    where the entering slice specifically owns none while OTHER scenarios for
    the feature exist.

    CONTRACT_SHAPE: bounded-change
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    workspace = repo_root / "docs" / "feature" / _ZERO_FEATURE_FILES_FEATURE_ID
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(
        f"# Feature Delta: {_ZERO_FEATURE_FILES_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_SLICE_WITH_SCENARIO} | not yet distilled |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )
    # Deliberately NO tests/ directory, NO .feature file anywhere.

    readiness_code, readiness_report = _run_readiness(
        repo_root, _ZERO_FEATURE_FILES_FEATURE_ID, _SLICE_WITH_SCENARIO
    )

    assert readiness_report.get("verdict") == "cleared" and readiness_code == 0, (
        "a feature with literally zero .feature files anywhere (pre-DISTILL "
        "first dispatch) must still clear scenario_slice_tags -- that "
        "vacuous-truth branch is intentional and the fix for AT-1 must "
        f"preserve it. observed verdict={readiness_report.get('verdict')!r}, "
        f"code={readiness_code}, invariants={readiness_report.get('invariants')}"
    )
    scenario_tags_inv = _invariant(readiness_report, _INV_SCENARIO_TAGS)
    assert scenario_tags_inv["satisfied"] is True, (
        "scenario_slice_tags must stay satisfied: true when the feature owns "
        f"no .feature files at all. observed={scenario_tags_inv}"
    )
