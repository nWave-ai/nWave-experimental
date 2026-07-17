"""Regression (fix-des-next-blind-to-sealed-red): ``des next`` never learns
about a genuinely-sealed mechanical RED for a pytest-regression bugfix
slice.

DEFECT: ``_project_pending_slice`` (``src/des/application/
deliver_loop_projection.py``, ~L175-192) gates precondition-1 on
``_has_event_for_slice(records, "RedObserved", slice_id)`` -- an
``AtCompletionLedger`` read. But no production path EVER writes a
``RedObserved`` LEDGER record for the atdd_pure pytest-regression mechanical-
seal path: ``des verify-red-green --record-red`` (``src/des/cli/
verify_red_green.py::_record_red``) writes ONLY a filesystem seal at
``.nwave/telemetry/red-green/<slug>.json`` (keyed by test-file path, via
``_seal_path``) and PRINTS the ``RedObserved`` event to stdout -- it never
touches the ledger. So for a bugfix slice whose ATs already exist, are
already RED-for-the-right-reason, and were sealed for real, precondition-1
is ALWAYS False -- ``des next`` prescribes ``/nw-distill --slice X``,
telling the developer to RE-AUTHOR acceptance tests that already exist
(destructive if followed).

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
``src/`` edits): when the ledger ``RedObserved`` event is absent,
``_project_pending_slice`` must additionally consult the pending Slice-Plan
row's Annotation cell for a ``@regression-test-file:<path>`` token and call
``carpaccio_slice_gate._mechanical_seal_satisfied(repo_root, repo_root /
path)`` -- the EXACT predicate the DELIVER-entry carpaccio gate
(``check_at_review``) and the G-DISTILL-EXIT hook
(``_mechanical_seal_cleared_slices``, bug #94's fix) already trust. Only
when BOTH the ledger event AND the mechanical seal are absent/unsatisfied
should precondition-1 route to ``/nw-distill``.

CRITICAL -- do NOT repeat the shipping AT's fatal mistake (``tests/des/
acceptance/test_des_next_loop_projection.py``, which seeds a FAKE
``RedObserved`` LEDGER event directly via ``append_gate_event`` -- exactly
why that AT could not catch this defect): every scenario below drives the
REAL seal-writing production path. The ``RedObserved`` seal is produced by
invoking ``des verify-red-green --record-red`` for real (``des.cli.
verify_red_green.main`` -- a genuine ``python -m pytest`` subprocess run
against a REAL, on-disk regression test file that REALLY fails) -- never by
hand-writing the seal JSON and never by seeding a ledger event. The
``AtCompletionLedger`` is left GENUINELY EMPTY/silent throughout (no
bootstrap record, no ``RedObserved``/``ATReviewVerdict`` ledger append of
any kind) -- the whole point of the defect is that the ledger has nothing to
say and ``des next`` must learn from the seal instead.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``des.cli.next_step`` CLI driver
(``main(argv)``), captured via ``capsys`` -- no subprocess fork for the
system under test itself (the nested ``python -m pytest`` subprocess run by
``des verify-red-green --record-red`` is a REAL dependency of the fixture,
not the SUT).

Scenario 5 (COMPLETENESS/RCA finding, tracked via ``xfail(strict=True)``):
precondition-2 (``ATReviewVerdict``) is ALSO never appended for a
mechanical-seal-cleared pytest-regression slice -- the fix above only
teaches precondition-1 the mechanical-seal route. Once precondition-1 stops
prescribing ``/nw-distill``, ``des next`` falls straight through to
precondition-2's ledger-only check (still nothing there) and gets stuck
prescribing "ATs are authored but not yet GREEN" / ``/nw-deliver`` forever --
a DIFFERENT wrong-direction advisory than the one this feature fixes, but
wrong all the same. This is OUT OF SCOPE for the fix above; tracked here so
it is never silently dropped.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.next_step import main as next_step_main
from des.cli.verify_red_green import main as verify_red_green_main


_FEATURE_ID = "mech-seal-next-fixture"
_SLICE_ID = "slice-01"
_REGRESSION_REL = "tests/regression/mech_seal_fixture/test_widget_pricing.py"
_OTHER_REGRESSION_REL = "tests/regression/mech_seal_fixture/test_other_slice_widget.py"

# A real, on-disk pytest-regression file: it genuinely FAILS when run (the
# ``assert False`` below), and its function name carries the ``_rejects_``
# negative-AT name token (P0.3 convention:
# ``des.cli.verify_negative_at``'s ``_not_``/``_never_``/``_rejects_``/
# ``_refuses_``/``_fails_`` scan) so ``_mechanical_seal_satisfied``'s
# negative-AT leg is satisfied honestly, not by coincidence.
_REGRESSION_SRC = (
    "def test_widget_rejects_a_negative_price():\n"
    "    assert False, "
    "'MISSING_FUNCTIONALITY: price validation not implemented yet'\n"
)


def _feature_delta_text(feature_id: str, slice_id: str, annotation: str) -> str:
    """Same doctor-clean 5-column Slice Plan shape the shipping AT
    (``test_des_next_loop_projection.py::_feature_delta_text``) uses --
    only the Annotation cell varies per scenario."""
    return (
        "## Wave: DESIGN / [REF] Architecture & Contract Tests\n"
        "\n"
        "Some architecture prose.\n"
        "\n"
        "## Wave: DESIGN / [REF] ADR Refs\n"
        "\n"
        "- ADR-001\n"
        "\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n"
        "\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"| {slice_id} | thinnest end-to-end read across the 4 SSOTs | "
        f"pending | {annotation} | mechanical-seal fixture |\n"
        "\n"
        "## Reuse Analysis\n"
        "\n"
        "Reuse-Analysis: no-overlap\n"
        "\n"
        "## Test Reuse & Consolidation Analysis\n"
        "\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _write_feature_delta(
    repo: Path, feature_id: str, slice_id: str, annotation: str
) -> None:
    delta_path = repo / "docs" / "feature" / feature_id / "feature-delta.md"
    delta_path.parent.mkdir(parents=True, exist_ok=True)
    delta_path.write_text(
        _feature_delta_text(feature_id, slice_id, annotation), encoding="utf-8"
    )


def _write_regression_file(repo: Path, rel: str = _REGRESSION_REL) -> Path:
    regression = repo / rel
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(_REGRESSION_SRC, encoding="utf-8")
    return regression


def _record_red_for_real(
    capsys: pytest.CaptureFixture[str], repo: Path, test_file_rel: str
) -> int:
    """Invoke the REAL ``des verify-red-green --record-red`` production CLI
    entry point -- never craft the seal JSON by hand, never seed a ledger
    event. Runs a genuine ``python -m pytest`` subprocess against the
    on-disk regression file, so the seal at ``.nwave/telemetry/red-green/
    <slug>.json`` (content_sha256 + real per-test outcomes) is produced by
    its actual producer.

    Drains ``capsys`` afterward so this fixture step's own stdout (the
    ``RedObserved`` JSON line + the human-readable confirmation) never
    bleeds into the SUT call's captured output.
    """
    exit_code = verify_red_green_main(
        ["--repo", str(repo), "--test-file", test_file_rel, "--record-red"]
    )
    capsys.readouterr()
    return exit_code


def _run_next(
    capsys: pytest.CaptureFixture[str], repo: Path, feature_id: str
) -> tuple[int, dict]:
    exit_code = next_step_main(
        ["--feature-id", feature_id, "--repo", str(repo), "--format", "json"]
    )
    captured = capsys.readouterr()
    verdict = json.loads(captured.out)
    return exit_code, verdict


# ---------------------------------------------------------------------------
# Scenario 1 -- POSITIVE (the bug, active-RED today): a genuinely-sealed RED
# must be credited and `des next` must point FORWARD, never back to
# `/nw-distill`.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


def test_des_next_credits_a_fresh_mechanical_seal_and_points_forward(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: EXP-fix-des-next-blind-to-sealed-red-1 (Expected
    observations, row 1).

    Given a pending slice whose Slice-Plan Annotation names a real
    regression file, and that file's RED was ACTUALLY observed via the real
    ``des verify-red-green --record-red`` (the AtCompletionLedger stays
    completely silent -- no RedObserved record, no bootstrap), `des next`
    must NOT claim the acceptance tests are unauthored and must NOT
    prescribe `/nw-distill` -- it must acknowledge the sealed RED and point
    forward toward GREEN/implementation.
    """
    _write_feature_delta(
        tmp_path, _FEATURE_ID, _SLICE_ID, f"@regression-test-file:{_REGRESSION_REL}"
    )
    _write_regression_file(tmp_path)
    record_red_exit = _record_red_for_real(capsys, tmp_path, _REGRESSION_REL)
    assert record_red_exit == 0, (
        f"fixture setup: the real `des verify-red-green --record-red` must "
        f"observe RED (exit 0) for the fixture to be meaningful, got exit "
        f"{record_red_exit}"
    )

    exit_code, verdict = _run_next(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, f"expected exit 0 (a step was projected): {verdict!r}"
    assert verdict.get("slice_id") == _SLICE_ID, verdict
    assert verdict.get("phase") != "D_DISTILL", (
        f"WRONG outcome produced: a genuinely-sealed RED (real "
        f"`verify-red-green --record-red` run, mechanical seal satisfied) "
        f"must not be reported as 'acceptance tests are not yet authored' -- "
        f"got phase={verdict.get('phase')!r}, how={verdict.get('how')!r}"
    )
    how = verdict.get("how", "")
    assert "/nw-distill" not in how, (
        f"WRONG outcome produced: `des next` must never send a developer "
        f"back to re-author acceptance tests that already exist and are "
        f"already sealed RED: {verdict!r}"
    )
    assert how.startswith("/nw-deliver"), (
        f"expected `des next` to point FORWARD (toward GREEN/implementation "
        f"via /nw-deliver), not backward: {verdict!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 -- NEGATIVE (false-positive floor): a test file merely EXISTING
# on disk, with NO seal ever recorded, must still prescribe `/nw-distill`.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_des_next_does_not_fabricate_a_seal_from_a_bare_test_file_on_disk(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: EXP-fix-des-next-blind-to-sealed-red-1 (Expected
    observations, negative row 2).

    A regression test file merely EXISTING at the annotated path -- with
    `des verify-red-green --record-red` NEVER run against it -- must NOT be
    credited as a sealed RED. "A test file with this name exists" and "a RED
    was actually witnessed for this file" must not produce the same
    advisory outcome.
    """
    _write_feature_delta(
        tmp_path, _FEATURE_ID, _SLICE_ID, f"@regression-test-file:{_REGRESSION_REL}"
    )
    _write_regression_file(tmp_path)  # on disk, but record-red is NEVER run

    exit_code, verdict = _run_next(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, verdict
    assert verdict.get("phase") == "D_DISTILL", (
        f"WRONG outcome produced: with no seal ever recorded, `des next` "
        f"must still prescribe AT authoring -- got: {verdict!r}"
    )
    assert (
        verdict.get("how")
        == f"/nw-distill --feature-id {_FEATURE_ID} --slice {_SLICE_ID}"
    ), (
        f"expected the unchanged D_DISTILL prescription for a genuinely "
        f"unsealed slice: {verdict!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 -- NEGATIVE (no cross-slice bleed): a seal recorded for a
# DIFFERENT regression file must not be credited to this slice, whether this
# slice's annotation points elsewhere or carries no regression-test-file
# token at all.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "annotation",
    [
        f"@regression-test-file:{_REGRESSION_REL}",
        "@walking_skeleton",
    ],
    ids=["points-elsewhere", "annotation-absent"],
)
def test_des_next_does_not_credit_a_seal_recorded_for_a_different_regression_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], annotation: str
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: EXP-fix-des-next-blind-to-sealed-red-1 (Expected
    observations, negative row 3).

    A fresh, real seal exists for `_OTHER_REGRESSION_REL` -- but THIS
    slice's own Annotation cell either names a DIFFERENT (never-sealed)
    regression file, or carries no `@regression-test-file:` token at all.
    Either way, `des next` must not "borrow" the neighboring seal; it must
    still prescribe `/nw-distill` for this slice.
    """
    _write_feature_delta(tmp_path, _FEATURE_ID, _SLICE_ID, annotation)
    _write_regression_file(tmp_path, _OTHER_REGRESSION_REL)
    record_red_exit = _record_red_for_real(capsys, tmp_path, _OTHER_REGRESSION_REL)
    assert record_red_exit == 0, (
        f"fixture setup: the real record-red for the OTHER file must "
        f"observe RED, got exit {record_red_exit}"
    )

    exit_code, verdict = _run_next(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, verdict
    assert verdict.get("phase") == "D_DISTILL", (
        f"WRONG outcome produced: a seal recorded for a DIFFERENT "
        f"regression file ({_OTHER_REGRESSION_REL!r}) must never be "
        f"credited to slice {_SLICE_ID!r} (annotation={annotation!r}) -- "
        f"got: {verdict!r}"
    )
    assert "/nw-distill" in verdict.get("how", ""), verdict


# ---------------------------------------------------------------------------
# Scenario 4 -- NEGATIVE (staleness): editing the regression file AFTER the
# seal was recorded must void the seal -- `des next` must ask for a fresh
# `record-red`, never wave the old seal through.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_des_next_does_not_trust_a_stale_seal_after_the_regression_file_is_edited(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: EXP-fix-des-next-blind-to-sealed-red-1 (Expected
    observations, negative row 4).

    A real seal was recorded, then the regression file was edited
    (content_sha256 no longer matches) -- even a whitespace/comment-only
    edit. The prior RED evidence is stale; `des next` must NOT treat it as
    still sealed.
    """
    _write_feature_delta(
        tmp_path, _FEATURE_ID, _SLICE_ID, f"@regression-test-file:{_REGRESSION_REL}"
    )
    regression = _write_regression_file(tmp_path)
    record_red_exit = _record_red_for_real(capsys, tmp_path, _REGRESSION_REL)
    assert record_red_exit == 0, (
        f"fixture setup: the real record-red must observe RED, got exit "
        f"{record_red_exit}"
    )
    # Edit AFTER the seal was recorded -- content_sha256 in the seal now
    # disagrees with the file's current hash (tamper / post-RED edit).
    regression.write_text(
        regression.read_text(encoding="utf-8") + "\n# tampered after RED\n",
        encoding="utf-8",
    )

    exit_code, verdict = _run_next(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, verdict
    assert verdict.get("phase") == "D_DISTILL", (
        f"WRONG outcome produced: the regression file was edited AFTER its "
        f"RED was sealed (content_sha256 mismatch) -- the stale seal must "
        f"be treated as evidentially absent, never as a partial pass: "
        f"{verdict!r}"
    )
    assert "/nw-distill" in verdict.get("how", ""), verdict


# ---------------------------------------------------------------------------
# Scenario 5 -- COMPLETENESS / RCA finding 5, TRACKED via xfail(strict=True):
# precondition-2 (ATReviewVerdict) is ALSO blind to the mechanical seal --
# out of THIS feature's scope (Option A only teaches precondition-1), so a
# mechanical-seal-cleared slice falls straight through to a DIFFERENT wrong-
# direction advisory ("not yet GREEN"/`/nw-deliver`) instead of `/nw-distill`.
# Expected to keep failing (for THIS reason) even after the fix above lands
# -- un-xfail this once precondition-2 is taught the same
# `_mechanical_seal_satisfied` route as a follow-on fix.
# CONTRACT_SHAPE: pure-function
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TRACKED (RCA finding 5, fix-des-next-blind-to-sealed-red): "
        "precondition-2 (_AT_REVIEW_VERDICT_EVENT) is ALSO never written "
        "for a pytest-regression mechanical-seal-cleared slice -- this "
        "feature's fix (Option A) only teaches precondition-1 the "
        "mechanical-seal route. Once precondition-1 stops prescribing "
        "/nw-distill, `des next` falls straight through to "
        "precondition-2's ledger-only check (still nothing there) and "
        "gets stuck prescribing 'ATs authored but not yet GREEN' / "
        "/nw-deliver forever -- a DIFFERENT wrong-direction advisory. "
        "Un-xfail once precondition-2 is taught the same "
        "_mechanical_seal_satisfied route as a follow-on fix."
    ),
)
def test_des_next_does_not_get_stuck_forever_after_the_mechanical_seal_clears_precondition_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """CONTRACT_SHAPE: pure-function

    Outcome anchor: RCA finding 5 (dispatch instruction item 5) --
    completeness check on the SECOND ledger-blind precondition
    (`ATReviewVerdict`) a mechanical-seal-cleared slice never satisfies
    either. Ideal behavior: once a slice's mechanical seal is fresh and
    satisfied, `des next` must neither prescribe `/nw-distill` (fixed by
    this feature) NOR get stuck reporting "not yet GREEN" / `A_GREEN`
    forever (the SAME mechanical evidence should also relieve
    precondition-2) -- it should report the slice ready to move past
    AT-authoring-and-green-verification entirely. NOT expected to pass
    within this feature's scope; tracked via xfail so the gap is never
    silently dropped.
    """
    _write_feature_delta(
        tmp_path, _FEATURE_ID, _SLICE_ID, f"@regression-test-file:{_REGRESSION_REL}"
    )
    _write_regression_file(tmp_path)
    record_red_exit = _record_red_for_real(capsys, tmp_path, _REGRESSION_REL)
    assert record_red_exit == 0, (
        f"fixture setup: the real record-red must observe RED, got exit "
        f"{record_red_exit}"
    )

    exit_code, verdict = _run_next(capsys, tmp_path, _FEATURE_ID)

    assert exit_code == 0, verdict
    assert verdict.get("phase") not in {"D_DISTILL", "A_GREEN"}, (
        f"a mechanical-seal-cleared slice must be credited for BOTH "
        f"precondition-1 (AT authoring/RED) AND precondition-2 (AT "
        f"review/GREEN) by the SAME mechanical evidence -- it must never "
        f"be reported as 'acceptance tests are not yet authored' NOR as "
        f"'ATs are authored but not yet GREEN': {verdict!r}"
    )
