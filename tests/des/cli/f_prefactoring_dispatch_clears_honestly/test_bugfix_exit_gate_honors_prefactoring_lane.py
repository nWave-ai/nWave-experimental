"""Regression AT -- the exit gate (`des verify-slice-commit` E2) must honor
the `@prefactoring` / EXEMPT lane the ENTRY gate already honors.

Feature `f-prefactoring-dispatch-clears-honestly` (epic
`non-slice-dispatch-exemption-model`). RCA (`/nw-bugfix` diagnosis, self-
explaining from the gate output): `LANE_PROFILES["prefactoring"]`
(`AtRequirement.EXEMPT`) is consulted at carpaccio ENTRY
(`check_carpaccio`/`check_at_review` via `_lane_profile_for_slice`,
`carpaccio_format.py:640-655`) but `des.cli.verify_slice_commit_completeness`
(the `des verify-slice-commit` exit gate, E1+E2+E3) consults NO lane profile
at all. Its E2 leg (`_run_contract_gate`) spawns
`des.cli.run_contract_gate --feature-id --entering-slice` as a real subprocess
-- `run_contract_gate._mode_feature_scoped` requires the union of `@slice-NN`
tags across the feature's `.feature` files to intersect the entering slice
(the M-8 non-vacuity floor). A `@prefactoring` slice authors ZERO scenarios
by definition, so that intersection is always empty -- the gate refuses
`FeatureScopeMalformed`/`empty-intersection`, `verify-slice-commit` surfaces
that as `SliceCommitRefused`/`refused_half: "E2"`, and `SliceCommitVerified`
is NEVER recorded. The slice clears entry, but can never clear exit -- which
blocks the SUCCESSOR slice's carpaccio ordering (no predecessor
`SliceCommitVerified` record). This is the defect this feature's own promise
("a prefactoring clears honestly, entry AND exit") requires closed.

Driving port (Mandate 16, no-direct-domain-testing): drives the REAL
`des.cli.verify_slice_commit_completeness.main` (the `des verify-slice-commit`
CLI edge) against a REAL git repository, with NO monkeypatch of
`_run_contract_gate` -- E2 spawns the genuine `run_contract_gate` subprocess,
so the refusal (today) / clearance (post-fix) is the true production
behaviour, not a stubbed approximation. Mirrors the established sibling
precedent `tests/des/integration/test_verify_slice_commit_examine_gate.py`
(same `_init_repo`/commit-with-`Slice-Id:`-trailer shape) and
`tests/des/acceptance/des_e2_contract_gate_degrade_loud/steps/composition.py`
(`drive_verify_slice_commit_with_interpreter`, the real-E2-subprocess
happy-path precedent this file's GREEN assertion mirrors).

RED-for-the-right-reason (confirmed at authorship, see report): the exit gate
currently emits `SliceCommitRefused` / `refused_half == "E2"` for a 0-AT
`@prefactoring` slice-commit -- a semantic `AssertionError` on the recorded
event, never an import/collection error. GREEN once the exit gate's E2 leg
reads the SAME `LANE_PROFILES` datum the entry gate already consults (via the
feature's `[REF] Slice Plan` Annotation cell) and short-circuits to an honest
`SliceCommitVerified` for an EXEMPT lane, mirroring `LaneAtExemptionAccepted`'s
entry-gate shape.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli import verify_slice_commit_completeness as vscc


_FEATURE_ID = "f-vscc-prefactoring-exit"
_PREDECESSOR = "slice-01"
_ENTERING = "slice-02"


# --- fixtures ----------------------------------------------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base: walking skeleton")


def _write_feature_delta(repo: Path, entering_annotation: str) -> None:
    """A minimal feature-delta carrying the `[REF] Slice Plan` table.

    `_PREDECESSOR` is an ordinary slice-with-AT row; the entering slice's
    Annotation cell is parametrized so the leak-guard companion test (below)
    can reuse this same builder with an EMPTY annotation.
    """
    delta_dir = repo / "docs" / "feature" / _FEATURE_ID
    delta_dir.mkdir(parents=True, exist_ok=True)
    (delta_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_PREDECESSOR} | the predecessor slice ships a real scenario | "
        "pending | | a real AT-bearing slice |\n"
        f"| {_ENTERING} | a behavior-preserving refactor introduces the seam | "
        f"pending | {entering_annotation} | "
        f"{'a green-to-green prefactoring' if entering_annotation else ''} |\n",
        encoding="utf-8",
    )


def _commit_predecessor_with_at(repo: Path) -> None:
    """Commit `_PREDECESSOR` with a real `@slice-01`-tagged `.feature` file.

    Makes the feature's `_feature_tag_files` resolution NON-EMPTY -- the
    precondition that turns the defect's failure mode into the exact
    `empty-intersection` reason the RCA names (as opposed to the unrelated
    `zero-collected` reason a feature with NO `.feature` files at all would
    hit).
    """
    feat_dir = repo / "tests" / "acceptance" / _FEATURE_ID.replace("-", "_")
    feat_dir.mkdir(parents=True, exist_ok=True)
    (feat_dir / f"{_PREDECESSOR}.feature").write_text(
        f"@feature-{_FEATURE_ID}\n"
        "Feature: the predecessor slice's behaviour\n\n"
        f"  @{_PREDECESSOR}\n"
        "  Scenario: the predecessor delivers its observable outcome\n"
        "    Given a precondition\n"
        "    When the action happens\n"
        "    Then the outcome holds\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat(slice): predecessor behaviour\n\nSlice-Id: {_PREDECESSOR}",
    )


def _commit_entering_zero_at(repo: Path) -> None:
    """Commit `_ENTERING` as a genuine 0-AT slice -- NO new `.feature` file.

    The behavior-preserving refactor touches only production code (never a
    test path), mirroring the real prefactoring shape: green-to-green, zero
    new scenarios.
    """
    prod_file = repo / "src" / "app" / "module.py"
    prod_file.parent.mkdir(parents=True, exist_ok=True)
    prod_file.write_text(
        "def helper() -> str:\n    return 'refactored, same behaviour'\n",
        encoding="utf-8",
    )
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"refactor(slice): behavior-preserving seam\n\nSlice-Id: {_ENTERING}",
    )


def _mark_predecessor_verified(repo: Path) -> None:
    AtCompletionLedger(_FEATURE_ID, repo).append_gate_event(
        event="SliceCommitVerified", slice_id=_PREDECESSOR
    )


def _last_json_event(combined_output: str) -> dict:
    json_lines = [
        ln for ln in combined_output.splitlines() if ln.strip().startswith("{")
    ]
    assert json_lines, (
        f"no JSON event line found in captured output: {combined_output!r}"
    )
    return json.loads(json_lines[-1])


def _run_verify_slice_commit(repo: Path, capsys) -> tuple[int, dict]:
    capsys.readouterr()  # drain any setup noise
    exit_code = vscc.main(
        ["--repo", str(repo), "--commit", "HEAD", "--feature-id", _FEATURE_ID]
    )
    combined = capsys.readouterr().out
    return exit_code, _last_json_event(combined)


# --- AT-1 (the diagnosed defect -- @prefactoring EXEMPT 0-AT slice must -----
# clear the exit gate, not be refused at E2) ----------------------------------


def test_prefactoring_exempt_zero_at_slice_clears_exit_gate(
    tmp_path: Path, capsys
) -> None:
    """A `@prefactoring`-annotated 0-AT slice-commit must record
    `SliceCommitVerified` through the REAL `des verify-slice-commit` exit gate
    -- not `SliceCommitRefused`/`refused_half: "E2"`.

    Drives the REAL E1 -> E2 (real `run_contract_gate` subprocess, NOT
    monkeypatched) -> E3 chain. E1 clears (a 0-AT slice's `.feature` candidate
    set is empty -> nothing missing). E3 is unarmed (no expectation charter
    exists for this synthetic feature/slice) -> clears trivially once E2
    clears. E2 is today's defect: `_run_contract_gate`'s subprocess has no
    lane-profile awareness, so `run_contract_gate._mode_feature_scoped`
    refuses `empty-intersection` for every EXEMPT 0-AT slice.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: RCA (this bugfix task) + feature-delta.md's own promise
    ("a prefactoring clears honestly, entry AND exit").
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta(repo, entering_annotation="@prefactoring")
    _commit_predecessor_with_at(repo)
    _mark_predecessor_verified(repo)
    _commit_entering_zero_at(repo)

    exit_code, event = _run_verify_slice_commit(repo, capsys)

    assert exit_code == 0 and event.get("event") == "SliceCommitVerified", (
        "a @prefactoring/EXEMPT 0-AT slice-commit must clear the REAL "
        "`des verify-slice-commit` exit gate with a SliceCommitVerified "
        "record (the entry gate's LaneAtExemptionAccepted honored "
        "symmetrically at exit) -- the exit gate's E2 leg does not yet "
        "consult LANE_PROFILES at all, so it refuses the vacuous "
        "@slice-NN-tag intersection every EXEMPT 0-AT slice trips. "
        f"observed exit_code={exit_code!r} event={event!r}"
    )


# --- AT-2 (leak-guard companion -- an UNANNOTATED 0-AT slice must still -----
# be refused at exit, exactly as today; the exemption must not leak) ---------


def test_unannotated_zero_at_slice_still_refused_at_exit_gate(
    tmp_path: Path, capsys
) -> None:
    """KPI-2 guardrail (exit-gate twin of the entry-gate leak-guard,
    `test_slice_03_carpaccio_lane_exemption_leak_guard.py`): an ordinary 0-AT
    slice-commit carrying NO `@prefactoring` annotation must STILL be
    refused at exit -- the fix must not leak the exemption into the
    slice-with-AT path at the exit gate either.

    This assertion holds BOTH before and after the fix -- it is the
    regression guard proving the fix is additive (reads the lane datum,
    branches only on EXEMPT), never a blanket relaxation of the non-vacuity
    floor.

    UPDATED 2026-07-27 (stale-assertion repair, not a behavior regression):
    at authorship (2026-07-06) the un-annotated zero-AT case was refused at
    `refused_half == "E2"` (`run_contract_gate`'s empty-`@slice-NN`-
    intersection check), which this guardrail pinned. Commit 26cbd849e
    (2026-07-21, "E1 vacuous-taxonomy refusal honors an armed examine-verdict
    PASS", the same E1-vacuous-taxonomy fix family as
    F-CARPACCIO-E1-VACUOUS-BLOCKS-PREDECESSOR-DISCRIMINATION) made E1's own
    `non_verifiable` check refuse a zero-recognized-AT-candidate slice
    BEFORE E2 is ever reached (`verify_slice_commit_completeness.py`
    ~L1353-1369, "a deficient slice refuses before E2 is reached"). The
    un-annotated slice here has NO EXEMPT lane and authors no `.feature`, so
    it now trips that earlier E1 refusal instead of falling through to E2 --
    still refused, still `SliceCommitRefused`, just caught one gate sooner
    (GDP-1, intercept earlier). Re-pinned to `refused_half == "E1"`.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: feature-delta.md (`[REF] Outcome KPIs`, KPI 2: "0 leaked
    exemptions across every non-lane slice dispatch").
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_feature_delta(repo, entering_annotation="")
    _commit_predecessor_with_at(repo)
    _mark_predecessor_verified(repo)
    _commit_entering_zero_at(repo)

    exit_code, event = _run_verify_slice_commit(repo, capsys)

    assert (
        exit_code != 0
        and event.get("event") == "SliceCommitRefused"
        and event.get("refused_half") == "E1"
    ), (
        "an UN-annotated 0-AT slice-commit must still be refused at exit -- "
        "the @prefactoring lane exemption must not leak to a plain slice "
        f"carrying no lane annotation. observed exit_code={exit_code!r} "
        f"event={event!r}"
    )
