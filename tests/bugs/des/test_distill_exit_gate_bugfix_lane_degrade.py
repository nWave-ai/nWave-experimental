"""Regression AT -- sixth SSOT-divergence locus, discovered LIVE while
authoring `fix-dispatch-validity-ssot` (this ATD's own D_DISTILL return
hit exactly the defect diagnosed here; see backlog entry, commit bad80c7b5,
measure 47/167).

DEFECT: `_slice_plan_slice_ids` (`src/des/adapters/drivers/hooks/
subagent_stop_handler.py:1377`), used as the "planned" denominator at
`_handle_distill_exit_gate:1956`, propagates an UNCAUGHT `FileNotFoundError`
when a feature has no `feature-delta.md` -- which resolves at
`_handle_distill_exit_gate:1994-1999` into a `SlicePlanParseUnresolved`
block. `_mechanical_seal_cleared_slices` (:1430-1434), the function
`_handle_distill_exit_gate` calls a few lines LOWER to check the
mechanical-seal alternative, ALREADY catches the identical
`FileNotFoundError` on the SAME read and degrades to `frozenset()` --
because a bugfix-lane feature carries NO `feature-delta.md` BY DESIGN
(ADR-025 SLIM-crafter discipline; empirically confirmed 47/167 `fix-*`
features in this repo have none). The crash fires BEFORE the mechanical-seal
branch -- already written and ready for exactly this case -- is ever reached.

Same structural class the sibling test file (`test_dispatch_validity_single_
source.py`, this feature's slice-01 AT) pins: N loci deciding "is this
dispatch well-formed" without consulting the SAME source. Here the two loci
are `_slice_plan_slice_ids` (crashes) and `_mechanical_seal_cleared_slices`
(degrades) -- one function two lines away already does the right thing; the
other does not.

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): `_handle_distill_exit_gate` must not let `_slice_plan_slice_
ids`'s `FileNotFoundError` propagate when the returning agent is mechanical-
seal-eligible (`resolved.at_kind == "pytest-regression"` AND a
`DES-REGRESSION-TEST-FILE` marker is present on the transcript) -- that
combination must reach and be evaluated by the mechanical-seal route instead
of crashing into `SlicePlanParseUnresolved`. This AT pins the OUTCOME
(mechanical-seal-eligible + no feature-delta.md clears; anything else stays
fail-closed), never the mechanism -- mirrors `test_distill_exit_mechanical_
seal_route.py`'s own stated discipline.

GROUNDING NOTE (verified empirically, not invented): `DES-REGRESSION-TEST-
FILE` is NOT parsed from the RETURNING agent's transcript by ANY existing
code path today -- `extract_des_context_from_transcript` /
`_AtddPureResolvedContext` carry no such field (grep-confirmed against
`subagent_stop_handler.py`; the ONLY existing consumer of this exact marker
NAME is `dispatch.py:536-538`, which EMITS it into the DISPATCH prompt, and
`carpaccio_intercept.py`, which reads it at the DELIVER-entry PreToolUse
hook -- a different hook, a different payload). This test places the marker
on the RETURNING transcript regardless -- mirroring `test_distill_exit_
mechanical_seal_route.py::test_gherkin_at_kind_marker_never_bypasses_seal_
route`'s own precedent (placing `DES-AT-KIND` where a fix would need to read
it, proving today's gate ignores it) -- because that is where a correct fix
MUST read it from: there is no feature-delta.md to carry a slice-plan
Annotation cell for this lane, so the transcript marker is the only place
left for the discovery to live.

Driving surface (Mandate 13 driving-port-only, Layer 3/4 wiring_e2e):
identical to `test_distill_exit_mechanical_seal_route.py` -- the REAL
`handle_subagent_stop` SubagentStop hook, invoked over its JSON stdin
protocol in-process via `tests.common.in_process_cli.run_hook_in_process`,
against a real git repo, a real regression test file, and the real
`AtCompletionLedger`; the RedObserved seal is crafted directly in
`verify_red_green`'s own record shape via its `_seal_path`/`_content_sha`
helpers so the slug/hash can never diverge from the producer.

RED-for-right-reason: today `_slice_plan_slice_ids` reads `_feature_delta_
path(repo, feature_id).read_text(...)` unconditionally and lets
`FileNotFoundError` propagate -- so the POSITIVE case below (mechanical-seal
evidence present, no feature-delta.md) still crashes into
`SlicePlanParseUnresolved`, a genuine semantic `AssertionError` on the
`GateOutcome.ALLOWED` assertion, never an import/collection error.

covers: fix-dispatch-validity-ssot (sixth locus)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from des.cli.verify_red_green import _content_sha as _red_seal_content_sha
from des.cli.verify_red_green import _seal_path as _red_green_seal_path
from tests.common.in_process_cli import run_hook_in_process


_FEATURE_ID = "bugfix-lane-degrade-probe"
_SLICE_ID = "slice-01"
_REGRESSION_REL = "tests/regression/bugfix_lane_degrade/test_fix.py"

_REGRESSION_SRC_WITH_NEGATIVE = (
    "def test_fix_applies():\n"
    "    assert True\n"
    "\n"
    "\n"
    "def test_fix_rejects_bad_input():\n"
    "    assert True\n"
)


@dataclass
class _HookOutcome:
    """Observable result of one G-DISTILL-EXIT SubagentStop evaluation."""

    allowed: bool
    decision_event: str | None
    reason: str | None
    exit_code: int
    phase_completed_emitted: bool


def _git(repo: Path, *args: str) -> None:
    import subprocess

    subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)


def _init_repo(repo: Path) -> None:
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "chore: seed")


def _write_regression_file(repo: Path) -> Path:
    regression = repo / _REGRESSION_REL
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(_REGRESSION_SRC_WITH_NEGATIVE, encoding="utf-8")
    return regression


def _write_red_seal(repo: Path) -> Path:
    """Craft the RedObserved seal in the P0.2 producer's exact record shape --
    mirrors `test_distill_exit_mechanical_seal_route.py::_write_red_seal`
    verbatim (same producer helpers, so the slug/hash can never diverge)."""
    test_file = (repo / _REGRESSION_REL).resolve()
    seal = _red_green_seal_path(repo.resolve(), test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": _REGRESSION_REL,
                "content_sha256": _red_seal_content_sha(test_file),
                "outcomes": {
                    "t::test_fix_applies": "fail",
                    "t::test_fix_rejects_bad_input": "fail",
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return seal


def _write_feature_delta_with_unevidenced_slice(repo: Path) -> None:
    """A REAL `feature-delta.md` with one planned slice carrying NEITHER a
    verdict NOR a mechanical-seal annotation -- the fixture for the NEGATIVE
    control proving a mechanical-seal-eligible `at_kind` does not vacuously
    bypass evaluation against a plan that genuinely EXISTS."""
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_SLICE_ID} | real planned slice, no evidence | pending | | |\n"
    )
    (feature_dir / "feature-delta.md").write_text(text, encoding="utf-8")


def _marker_block(
    *,
    repo: Path,
    at_kind: str | None = None,
    regression_test_file: str | None = None,
) -> str:
    lines = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-MODE : atdd_pure -->",
        "<!-- DES-PHASE : D_DISTILL -->",
        "<!-- DES-SLICE : feature-end -->",
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->",
        f"<!-- DES-PROJECT-ROOT : {repo} -->",
    ]
    if at_kind is not None:
        lines.append(f"<!-- DES-AT-KIND : {at_kind} -->")
    if regression_test_file is not None:
        lines.append(f"<!-- DES-REGRESSION-TEST-FILE : {regression_test_file} -->")
    return "\n".join(lines) + "\n"


def _write_distill_return_transcript(repo: Path, *, marker_text: str) -> Path:
    transcript_path = repo / "agent.jsonl"
    line = json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": marker_text},
            "uuid": "distill-return",
            "timestamp": "2026-07-19T10:30:00Z",
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")
    return transcript_path


def _run_gate(repo: Path, transcript_path: Path) -> _HookOutcome:
    """Invoke the REAL `handle_subagent_stop` hook over its JSON stdin protocol."""
    hook_input = json.dumps(
        {
            "session_id": "bugfix-lane-degrade-session",
            "hook_event_name": "SubagentStop",
            "agent_id": "acceptance-designer-1",
            "agent_type": "acceptance-designer",
            "agent_transcript_path": str(transcript_path),
            "stop_hook_active": False,
            "cwd": str(repo),
            "transcript_path": "/tmp/session.jsonl",
            "permission_mode": "default",
        }
    )
    exit_code, stdout, _stderr = run_hook_in_process(
        handle_subagent_stop,
        stdin_text=hook_input,
        cwd=str(Path.cwd()),
    )
    decision_event: str | None = None
    reason: str | None = None
    allowed = True
    for raw_line in stdout.splitlines():
        raw_line = raw_line.strip()
        if not raw_line.startswith("{"):
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if payload.get("decision") == "block":
            allowed = False
            decision_event = payload.get("event")
            reason = payload.get("reason")
    return _HookOutcome(
        allowed=allowed,
        decision_event=decision_event,
        reason=reason,
        exit_code=exit_code,
        phase_completed_emitted=_phase_completed_emitted(repo),
    )


def _phase_completed_emitted(repo: Path) -> bool:
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    try:
        records = ledger.read_records(event_type="WorkflowPhaseCompletedDistill")
    except Exception:
        return False
    return len(records) >= 1


# ---------------------------------------------------------------------------
# 1. POSITIVE -- mechanical-seal-eligible + no feature-delta.md must clear
#    DISTILL-exit, never crash into SlicePlanParseUnresolved.
# ---------------------------------------------------------------------------


def test_mechanical_seal_eligible_return_without_feature_delta_clears_distill_exit(
    tmp_path: Path,
) -> None:
    """The EXACT live scenario this ATD hit: a `pytest-regression` bugfix
    D_DISTILL return, valid fresh seal + satisfied negative-AT mandate, on a
    feature with NO `feature-delta.md` (bugfix lane, ADR-025) -- must clear
    G-DISTILL-EXIT rather than crash into `SlicePlanParseUnresolved`.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_regression_file(repo)
    _write_red_seal(repo)
    transcript = _write_distill_return_transcript(
        repo,
        marker_text=_marker_block(
            repo=repo,
            at_kind="pytest-regression",
            regression_test_file=_REGRESSION_REL,
        ),
    )

    outcome = _run_gate(repo, transcript)

    assert outcome.decision_event != "SlicePlanParseUnresolved", (
        "a mechanical-seal-eligible D_DISTILL return with NO feature-delta.md "
        "must never crash into SlicePlanParseUnresolved -- _slice_plan_slice_"
        "ids propagates FileNotFoundError uncaught while the sibling "
        "_mechanical_seal_cleared_slices two lines below already degrades "
        f"gracefully on the SAME missing file. got event={outcome.decision_event!r}, "
        f"reason={outcome.reason!r} (exit_code={outcome.exit_code})"
    )
    assert outcome.allowed, (
        "expected the G-DISTILL-EXIT gate to ALLOW a mechanical-seal-eligible "
        "return with valid fresh evidence even with NO feature-delta.md to "
        f"parse -- got blocked with event={outcome.decision_event!r}, "
        f"reason={outcome.reason!r} (exit_code={outcome.exit_code})"
    )
    assert outcome.phase_completed_emitted, (
        "expected a WorkflowPhaseCompletedDistill ledger record once the "
        "mechanical-seal route clears the bugfix-lane return with no "
        f"feature-delta.md -- none was found (exit_code={outcome.exit_code})"
    )
    assert outcome.exit_code == 0


# ---------------------------------------------------------------------------
# 2. NEGATIVE (`_rejects_`) -- fail-closed: NO mechanical-seal-eligibility
#    signal + no feature-delta.md must STILL block. The degrade is for the
#    lane that by construction has no file, never a blanket "no file -> pass".
# ---------------------------------------------------------------------------


def test_plain_return_without_feature_delta_still_rejects_distill_exit(
    tmp_path: Path,
) -> None:
    """A D_DISTILL return carrying NO `DES-AT-KIND` marker at all (today's
    ordinary case, pre-mechanical-seal) on a feature with no feature-delta.md
    must keep blocking -- the fix must not turn EVERY absent feature-delta.md
    into a silent pass regardless of evidence.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    transcript = _write_distill_return_transcript(
        repo, marker_text=_marker_block(repo=repo)
    )

    outcome = _run_gate(repo, transcript)

    assert not outcome.allowed, (
        "a D_DISTILL return with NO at_kind marker and no feature-delta.md "
        f"must stay BLOCKED (fail-closed) -- got allowed (exit_code="
        f"{outcome.exit_code})"
    )
    assert outcome.reason is not None and "feature-delta" in outcome.reason.lower(), (
        "the block reason must keep naming WHAT is missing (the feature-delta) "
        f"-- got reason={outcome.reason!r}"
    )
    assert not outcome.phase_completed_emitted


def test_gherkin_at_kind_without_feature_delta_never_bypasses_the_gate(
    tmp_path: Path,
) -> None:
    """A D_DISTILL return explicitly declaring `DES-AT-KIND: gherkin` (an
    EXPLICIT non-mechanical-seal-eligible kind) with no feature-delta.md must
    also stay blocked -- mirrors the sibling D1 negative
    (`test_gherkin_at_kind_marker_never_bypasses_seal_route`): the
    mechanical-seal route (and any degrade riding on its eligibility check)
    is pytest-regression-ONLY, never triggered by the mere ABSENCE of a
    feature-delta.md.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    transcript = _write_distill_return_transcript(
        repo, marker_text=_marker_block(repo=repo, at_kind="gherkin")
    )

    outcome = _run_gate(repo, transcript)

    assert not outcome.allowed, (
        "a D_DISTILL return explicitly declaring DES-AT-KIND: gherkin with no "
        f"feature-delta.md must stay BLOCKED -- got allowed (exit_code="
        f"{outcome.exit_code})"
    )
    assert not outcome.phase_completed_emitted


# ---------------------------------------------------------------------------
# 3. NEGATIVE (`_never_`) -- a REAL feature-delta.md with a genuinely
#    unevidenced planned slice must still be evaluated against it, even when
#    the return carries a mechanical-seal-eligible at_kind. Proves the
#    degrade fires ONLY for the "file literally absent" case, never as a
#    universal "trust at_kind" bypass for a feature that DOES have a plan.
# ---------------------------------------------------------------------------


def test_mechanical_seal_eligible_at_kind_never_bypasses_a_real_unevidenced_plan(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_feature_delta_with_unevidenced_slice(repo)
    _write_regression_file(repo)
    _write_red_seal(repo)
    transcript = _write_distill_return_transcript(
        repo,
        marker_text=_marker_block(
            repo=repo,
            at_kind="pytest-regression",
            regression_test_file=_REGRESSION_REL,
        ),
    )

    outcome = _run_gate(repo, transcript)

    assert not outcome.allowed, (
        "a mechanical-seal-eligible at_kind must NEVER bypass evaluation "
        "against a REAL, existing feature-delta.md whose planned slice "
        f"carries no seal annotation and no verdict -- got allowed "
        f"(exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        "expected the ordinary DistillExitVerdictIncomplete block for a "
        f"genuinely unevidenced planned slice -- got {outcome.decision_event!r}"
    )
    assert not outcome.phase_completed_emitted
