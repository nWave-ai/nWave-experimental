"""Regression AT: the automatic hand-back check and `des verify-integrity`
agree with each other -- correctly -- whether or not the optional coverage-map
tracking feature is switched on.

Charter (authoritative oracle -- this test is authored FROM this file only):
docs/product/expectations/fix-na-marker-reconcile-drift/
a-developer-with-tracking-off-sees-one-consistent-completion-verdict.md

Real surfaces under test (both located via the codebase, not assumed from any
prompt):

- The automatic hand-back check: ``_missing_feature_end_cycle_records`` in
  ``des.adapters.drivers.hooks.subagent_stop_handler`` -- the SubagentStop
  hook's U4 feature-end-cycle completion enforcer. Its observable is the
  missing-required-record ``frozenset`` (empty == the hand-back is permitted).
- The manual completion-status command: ``des verify-integrity`` (module
  ``des.cli.verify_deliver_integrity``), driven as a real subprocess
  (``python -m des verify-integrity <repo> --feature-id <id>``). Exit 0 +
  no ``FeatureEndCycleIncomplete``/``INTEGRITY VIOLATION`` in stdout == done.

The optional tracking feature the charter refers to is coverage-map adoption
(``coverage_map_adoption`` in ``.nwave/des-config.json``). Both real entry
points read only the AT-completion LEDGER (never the config file) to decide
completion, and reconcile the ``CoverageMapNotApplicableAt{Distill,Deliver}
Exit`` NA markers in place of the ``CoverageMapVerifiedAt{Distill,Deliver}
Exit`` heartbeats via the SAME shared source
(``nWave/flavors/atdd_pure.yaml`` ``feature_end_na_marker_reconciles`` /
``des.application.feature_end_na_marker_reconciliation``) -- so staging the
ledger directly (the established composition-root precedent in
``tests/des/acceptance/walking_skeleton_feature_end_wiring``) drives both real
entry points exactly as a live hand-back / CLI invocation would.

Divergence from the suspect draft (tests/bugs/test_bug_na_marker_reconcile_
drift_between_hook_and_cli.py, disqualified, NOT read while authoring this
file): this file additionally asserts (1) the full charter 2x2 matrix
(tracking off/on x work complete/incomplete) for BOTH checks in every cell,
not only the previously-drifting coverage-map cell; (2) the "genuinely
complete work must never be jointly blocked" oracle in both tracking
configurations; (3) the three-way could-not-check / checked-fine /
checked-not-fine distinction at the ledger-event level (Negative oracle 4 in
the charter) via the recorded NA-marker vs Verified-marker types, not merely
the missing-set boolean; (4) that the reported missing-record set genuinely
NAMES the real cause and differs across differently-broken projects (charter
bullet 3), rather than emitting one canned message. Anywhere this file's
assertions differ in SHAPE from the suspect draft, the charter above wins by
construction -- the suspect draft was never consulted to decide any assertion
here.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import (
    _missing_feature_end_cycle_records,
)
from tests.des._helpers.feature_end_seeding import seed_required_feature_end_records


# The two coverage-map heartbeats -- the ONLY dimension the optional tracking
# feature (coverage-map adoption) governs.
_COVERAGE_MAP_VERIFIED = (
    "CoverageMapVerifiedAtDistillExit",
    "CoverageMapVerifiedAtDeliverExit",
)
_COVERAGE_MAP_NOT_APPLICABLE = (
    "CoverageMapNotApplicableAtDistillExit",
    "CoverageMapNotApplicableAtDeliverExit",
)

# A required record with NO NotApplicable escape hatch (the shipped
# `nWave/flavors/atdd_pure.yaml` `feature_end_na_marker_reconciles` map names
# exactly three reconcilable records -- the two coverage-map heartbeats plus
# `FullSuiteLegRan`; this one is not among them). Standing in for "genuinely
# incomplete work" that no tracking toggle can ever mask.
_UNRELATED_REQUIRED_RECORD = "EBatchRefactorCompleted"


# --- composition root --------------------------------------------------------


def _seed_repo(*, tracking_on: bool, work_complete: bool) -> tuple[Path, str]:
    """Stage a real AT-completion ledger for one charter 2x2-matrix cell.

    ``tracking_on`` selects whether the optional coverage-map tracking
    dimension is ON (mints the real ``CoverageMapVerifiedAt*Exit``
    heartbeats -- coverage was actually checked) or OFF (mints the
    ``CoverageMapNotApplicableAt*Exit`` NA markers -- the honest "could not
    check, tracking is off" signal). ``work_complete`` selects whether the
    ONE required record with no NA escape hatch (``EBatchRefactorCompleted``)
    is present -- independent of the tracking axis, so a project can be
    complete or incomplete under EITHER tracking setting.
    """
    workspace = Path(tempfile.mkdtemp(prefix="na-marker-reconcile-drift-"))
    feature_id = f"fixture-feature-{uuid.uuid4().hex[:8]}"
    ledger = AtCompletionLedger(feature_id, workspace)

    exclude = list(_COVERAGE_MAP_VERIFIED)
    if not work_complete:
        exclude.append(_UNRELATED_REQUIRED_RECORD)
    seed_required_feature_end_records(ledger, exclude=exclude)

    if tracking_on:
        ledger.append_coverage_map_verified_at_distill_exit()
        ledger.append_coverage_map_verified_at_deliver_exit()
    else:
        ledger.append_coverage_map_not_applicable_at_distill_exit()
        ledger.append_coverage_map_not_applicable_at_deliver_exit()

    return workspace, feature_id


def _hook_missing(repo: Path, feature_id: str) -> frozenset[str]:
    """Run the REAL SubagentStop hook completion-check (the automatic check)."""
    return _missing_feature_end_cycle_records(repo, feature_id)


def _cli_verdict(repo: Path, feature_id: str) -> tuple[int, str]:
    """Run the REAL `des verify-integrity` CLI (the manual completion-status
    command) as a hermetic subprocess -- no PATH/entry-point dependency."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "des",
            "verify-integrity",
            str(repo),
            "--feature-id",
            feature_id,
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, proc.stdout


def _cli_reports_incomplete(stdout: str) -> bool:
    return (
        '"event": "FeatureEndCycleIncomplete"' in stdout
        or "INTEGRITY VIOLATION" in stdout
    )


def _hook_permits(missing: frozenset[str]) -> bool:
    return len(missing) == 0


def _cli_permits(exit_code: int, stdout: str) -> bool:
    return exit_code == 0 and not _cli_reports_incomplete(stdout)


# --- the charter's positive oracle: the full 2x2 matrix -----------------------


@pytest.mark.parametrize(
    "tracking_on,work_complete,both_should_permit",
    [
        pytest.param(False, True, True, id="tracking-off_work-complete"),
        pytest.param(False, False, False, id="tracking-off_work-incomplete"),
        pytest.param(True, True, True, id="tracking-on_work-complete"),
        pytest.param(True, False, False, id="tracking-on_work-incomplete"),
    ],
)
def test_hand_back_check_and_completion_status_agree_across_the_2x2_matrix(
    tracking_on: bool, work_complete: bool, both_should_permit: bool
) -> None:
    # covers: R1
    # covers: R2
    # covers: R3
    # covers: R4
    """One consistent verdict in every cell of tracking(off/on) x
    work(complete/incomplete) -- the charter's Expected observations 1, 2, 4."""
    repo, feature_id = _seed_repo(tracking_on=tracking_on, work_complete=work_complete)

    missing = _hook_missing(repo, feature_id)
    exit_code, stdout = _cli_verdict(repo, feature_id)

    hook_permits = _hook_permits(missing)
    cli_permits = _cli_permits(exit_code, stdout)

    assert hook_permits == cli_permits == both_should_permit, (
        "the automatic hand-back check and the manual completion-status "
        f"command disagree (or agree incorrectly) for tracking_on={tracking_on}, "
        f"work_complete={work_complete}: hook_permits={hook_permits} "
        f"(missing={sorted(missing)}), cli_permits={cli_permits} "
        f"(exit={exit_code}, stdout={stdout!r})"
    )


# --- negative oracle (a): must not rubber-stamp because tracking is off -------


def test_hand_back_check_does_not_pass_unconditionally_when_tracking_is_off() -> None:
    # covers: R5
    """Tracking off must not become a free pass: with real, unrelated work
    still missing, the automatic check keeps blocking and names the actual
    cause -- it never waves a hand-back through just because the optional
    tracking feature is off."""
    repo, feature_id = _seed_repo(tracking_on=False, work_complete=False)

    missing = _hook_missing(repo, feature_id)

    assert missing, (
        "the automatic hand-back check reported an empty missing-record set "
        "with tracking off and work genuinely incomplete -- it must keep "
        "actually checking completion, not rubber-stamp every hand-back as "
        "done just because tracking is switched off"
    )
    assert _UNRELATED_REQUIRED_RECORD in missing, (
        "the genuinely missing, non-reconcilable record must be named"
    )
    assert not (set(_COVERAGE_MAP_VERIFIED) & missing), (
        "the tracking-off dimension is correctly reconciled via its NA "
        "marker and must not itself appear as a missing cause"
    )


# --- negative oracle (b): never jointly declare broken work done --------------


@pytest.mark.parametrize(
    "tracking_on", [False, True], ids=["tracking-off", "tracking-on"]
)
def test_checks_never_jointly_declare_incomplete_work_done(tracking_on: bool) -> None:
    # covers: R6
    """Neither check, in any tracking configuration, may call genuinely
    unfinished work done -- agreement is not itself sufficient; both being
    wrong together is worse than the original disagreement."""
    repo, feature_id = _seed_repo(tracking_on=tracking_on, work_complete=False)

    missing = _hook_missing(repo, feature_id)
    exit_code, stdout = _cli_verdict(repo, feature_id)

    hook_says_done = _hook_permits(missing)
    cli_says_done = _cli_permits(exit_code, stdout)

    assert not hook_says_done, (
        f"hook wrongly declared incomplete work done (tracking_on={tracking_on})"
    )
    assert not cli_says_done, (
        f"CLI wrongly declared incomplete work done (tracking_on={tracking_on}, "
        f"exit={exit_code}, stdout={stdout!r})"
    )
    assert not (hook_says_done and cli_says_done)


# --- negative oracle (c): never jointly block genuinely complete work ---------


@pytest.mark.parametrize(
    "tracking_on", [False, True], ids=["tracking-off", "tracking-on"]
)
def test_checks_never_jointly_block_genuinely_complete_work(tracking_on: bool) -> None:
    # covers: R7
    """Neither check, in any tracking configuration, may block genuinely
    finished work -- a developer must not trade "stuck forever, tracking
    off" for "stuck forever" under some other legitimate setting."""
    repo, feature_id = _seed_repo(tracking_on=tracking_on, work_complete=True)

    missing = _hook_missing(repo, feature_id)
    exit_code, stdout = _cli_verdict(repo, feature_id)

    assert _hook_permits(missing), (
        f"hook blocked genuinely complete work (tracking_on={tracking_on}): "
        f"missing={sorted(missing)}"
    )
    assert _cli_permits(exit_code, stdout), (
        f"CLI blocked genuinely complete work (tracking_on={tracking_on}): "
        f"exit={exit_code}, stdout={stdout!r}"
    )


# --- negative oracle (d): could-not-check is a THIRD, visible outcome ---------


def test_could_not_check_is_never_collapsed_into_checked_fine_or_checked_not_fine() -> (
    None
):
    # covers: R8
    """With tracking off, the coverage-map dimension is "could not check" --
    a distinct claim from both "checked, it's fine" (would need the Verified
    marker, which must be ABSENT) and "checked, it's not fine" (would need
    the requirement to surface as missing/blocking, which must NOT happen).
    All three outcomes must stay visibly distinct at the ledger-event level,
    never silently collapsed into either extreme."""
    repo, feature_id = _seed_repo(tracking_on=False, work_complete=True)

    ledger = AtCompletionLedger(feature_id, repo)
    recorded = ledger.coverage_map_touchpoint_events()

    # Not silently promoted to "checked, it's fine": the Verified marker
    # (an actual, positive verification) must never appear -- nothing was
    # really verified.
    assert not (set(_COVERAGE_MAP_VERIFIED) & recorded), (
        "tracking is off -- coverage was never actually verified, so the "
        "ledger must not carry the Verified marker (that would mistake "
        "incapacity-to-check for a found success): "
        f"recorded={sorted(recorded)}"
    )
    # The honest, distinct "could not check" signal IS present.
    assert set(_COVERAGE_MAP_NOT_APPLICABLE) <= recorded, (
        f"the distinct could-not-check NA marker is missing: recorded={sorted(recorded)}"
    )
    # Not silently demoted to "checked, it's not fine" (blocking): the
    # automatic check must not treat the could-not-check dimension as a
    # found FAILURE.
    missing = _hook_missing(repo, feature_id)
    assert not (set(_COVERAGE_MAP_VERIFIED) & missing), (
        "tracking is off -- coverage could not be checked, so it must not "
        "be treated as a found FAILURE either (blocking on it would mistake "
        f"incapacity-to-check for a found problem): missing={sorted(missing)}"
    )


# --- charter bullet 3: names the real cause, never a canned repeat ------------


def test_hand_back_check_names_the_real_missing_record_not_a_canned_message() -> None:
    # covers: R9
    """If the automatic check still has a legitimate reason to block, it
    names what is missing -- two differently-broken projects must produce
    two differently-shaped missing-record reports, never one constant
    message regardless of the real cause."""
    repo_a, feature_a = _seed_repo(tracking_on=False, work_complete=False)

    repo_b = Path(tempfile.mkdtemp(prefix="na-marker-reconcile-drift-"))
    feature_b = f"fixture-feature-{uuid.uuid4().hex[:8]}"
    ledger_b = AtCompletionLedger(feature_b, repo_b)
    seed_required_feature_end_records(
        ledger_b, exclude=[*_COVERAGE_MAP_VERIFIED, "WalkingSkeletonGateRan"]
    )
    ledger_b.append_coverage_map_not_applicable_at_distill_exit()
    ledger_b.append_coverage_map_not_applicable_at_deliver_exit()

    missing_a = _hook_missing(repo_a, feature_a)
    missing_b = _hook_missing(repo_b, feature_b)

    assert missing_a != missing_b, (
        "two projects broken for different real reasons produced the "
        "identical missing-record report -- the check is not naming the "
        f"actual cause: missing_a={sorted(missing_a)}, missing_b={sorted(missing_b)}"
    )
    assert _UNRELATED_REQUIRED_RECORD in missing_a
    assert "WalkingSkeletonGateRan" not in missing_a
    assert "WalkingSkeletonGateRan" in missing_b
    assert _UNRELATED_REQUIRED_RECORD not in missing_b
