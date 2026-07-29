"""Regression AT -- D04a follow-up (declared-facts-reachable-recorded
slice-01's own DD-1 fix, commit 0303ecea5): the G-DISTILL-EXIT gate's
completeness numerator conflates "reviewed" with "APPROVED".

DEFECT: DD-1 (`fix(at-review-verdict): record NEEDS_REVISION verdicts, not
only approvals`, commit 0303ecea5) made `record_review_outcome` append an
`ATReviewVerdict` ledger record for BOTH APPROVED and NEEDS_REVISION -- before
that fix, only APPROVED ever wrote a record. `AtCompletionLedger.
review_verdict_slices()` (`src/des/adapters/driven/logging/
at_completion_ledger.py:1954-1973`, introduced 2026-05-29, commit 052591b3f,
well BEFORE DD-1) returns "the set of slice ids carrying an `ATReviewVerdict`
record" -- filtered on `event == "ATReviewVerdict"` ONLY, never on the
record's `verdict` field. `_handle_distill_exit_gate`
(`src/des/adapters/drivers/hooks/subagent_stop_handler.py:2434`) assigns this
set to a variable literally named `verdict_signed` and uses it as the
numerator of the G-DISTILL-EXIT completeness check: `missing = planned -
verdict_signed`. Before DD-1 this was safe (presence implied APPROVED, the
only verdict that ever wrote). After DD-1, a slice reviewed and REJECTED
(`NEEDS_REVISION`) also appears in `review_verdict_slices()` -- so
`_handle_distill_exit_gate` now treats a REJECTED slice as satisfied and
ALLOWS the DISTILL->DELIVER transition, silently contradicting ADR-029 D5's
UNCHANGED control-flow clause (NEEDS_REVISION loops back to the
acceptance-designer, it must never proceed to DELIVER).

This is the exact failure mode the declared-facts-reachable-recorded
feature-delta's own Prefactoring Assessment (F3 row) warned against checking
for and then under-scoped: it verified only `carpaccio_slice_gate.py`'s
`_check_verdict_record` ("the ONE existing consumer") discriminates on
`record.get("verdict") != "APPROVED"`, not on presence -- true for that
consumer, but `review_verdict_slices()` is a SECOND consumer of the same
`ATReviewVerdict` record shape, and it does NOT discriminate on verdict at
all. A control that changes meaning without changing shape, silent by
construction (feedback_gate_how_routes_to_producing_system... /
mikado audit "a lying rejection is worse than a bare traceback" applies
here in its ALLOW-shaped mirror: a lying ALLOW).

Non-bug (verified, not assumed): `review_verdict_slices()`'s OTHER caller,
`verify_deliver_integrity.py::_foreign_owned_slices`, unions it with
`verified_slices()` to answer "was this slice-id ever TOUCHED by this other
feature's ledger" (cross-feature ownership disambiguation) -- a REJECTED
review is still legitimate positive evidence of ownership there, so THAT
caller's use of "any verdict" is correct and stays unchanged. Only the
completeness/approval gate needed a narrower predicate.

THE FIX (implemented alongside this test, not a "crafter's job" deferral --
XS scope, single seam): `AtCompletionLedger` gains a new method
`approved_review_verdict_slices()` (verdict-filtered sibling of
`review_verdict_slices()`, same M7 fail-closed read contract).
`_handle_distill_exit_gate`'s `verdict_signed` assignment switches to it.
`review_verdict_slices()` itself is untouched (backward-compatible for its
one other, verdict-agnostic caller).

RED-for-right-reason: before the fix, the ONLY-planned-slice-is-REJECTED
scenario below `outcome.allowed` is `True` -- a genuine semantic
`AssertionError` on the block-expectation, never an import/collection error
(confirmed interactively before authoring this test).

Driving surface (Mandate 13 driving-port-only, Layer 3/4 wiring_e2e):
the REAL `handle_subagent_stop` SubagentStop hook, invoked over its JSON
stdin protocol in-process via `tests.common.in_process_cli.
run_hook_in_process`, against a real git repo, a real feature-delta `[REF]
Slice Plan`, and the real `AtCompletionLedger` writer/reader -- mirrors
`test_distill_exit_jit_slice_scope.py`'s own driving-surface discipline.

covers: declared-facts-reachable-recorded slice-01 (DD-1 follow-up), D04a
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process


_FEATURE_ID = "distill-exit-rejected-slice-probe"
_SLICE_01 = "slice-01"

_VERDICT_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)


@dataclass
class _HookOutcome:
    """Observable result of one G-DISTILL-EXIT SubagentStop evaluation."""

    allowed: bool
    decision_event: str | None
    exit_code: int
    missing: tuple[str, ...] = ()
    phase_record: dict[str, Any] | None = None


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


def _write_slice_plan(repo: Path, slice_ids: list[str]) -> None:
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f"| {slice_id} | probe row for {slice_id} | pending | | |"
        for slice_id in slice_ids
    )
    text = (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"{rows}\n"
    )
    (feature_dir / "feature-delta.md").write_text(text, encoding="utf-8")


def _write_feature_file(repo: Path, *, slice_id: str) -> Path:
    """A real, discoverable `.feature` file for `slice_id` (so the JIT
    absent-from-disk carve-out never masks this scenario -- the slice must be
    evaluated on its verdict, not excluded as not-yet-reached)."""
    acceptance_dir = repo / "tests" / _FEATURE_ID / "acceptance"
    acceptance_dir.mkdir(parents=True, exist_ok=True)
    text = (
        f"@feature-{_FEATURE_ID}\n"
        f"Feature: distill exit rejected-slice probe ({slice_id})\n\n"
        f"  @{slice_id}\n"
        f"  Scenario: probe scenario for {slice_id}\n"
        f"    Given a slice reviewed and REJECTED\n"
        "    When the DISTILL exit gate runs\n"
        "    Then it must NOT proceed to DELIVER\n"
    )
    path = acceptance_dir / f"{slice_id}.feature"
    path.write_text(text, encoding="utf-8")
    return path


def _seed_review_verdict(repo: Path, slice_id: str, *, verdict: str) -> None:
    """Seed one `ATReviewVerdict` record via the production writer.

    Mirrors `test_distill_exit_jit_slice_scope.py::_seed_review_verdict`
    verbatim except for the parametrized `verdict` -- routed through the SAME
    `append_review_verdict` producer the gate's ledger read trusts, under the
    M7 fail-closed integrity contract (seq + record_hash).
    """
    record: dict[str, object] = {
        "schema_version": "1.0.0",
        "slice_id": slice_id,
        "verdict": verdict,
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": [f"{slice_id}-AT-1"],
        "at_content_hash": hashlib.sha256(slice_id.encode()).hexdigest(),
        "timestamp": "2026-07-19T10:00:00Z",
    }
    signed = {field_name: record[field_name] for field_name in _VERDICT_SIGNED_FIELDS}
    canonical = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    record["hmac_sha256"] = hmac.new(
        b"rejected-slice-seed-key", canonical, hashlib.sha256
    ).hexdigest()
    record["findings_summary"] = (
        "rejected in review" if verdict != "APPROVED" else "clean"
    )
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    ledger.append_review_verdict(slice_id=slice_id, verdict_fields=record)


def _marker_block(*, repo: Path) -> str:
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : D_DISTILL -->\n"
        "<!-- DES-SLICE : feature-end -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
        f"<!-- DES-PROJECT-ROOT : {repo} -->\n"
    )


def _write_distill_return_transcript(repo: Path) -> Path:
    transcript_path = repo / "agent.jsonl"
    line = json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": _marker_block(repo=repo)},
            "uuid": "distill-return",
            "timestamp": "2026-07-19T10:30:00Z",
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")
    return transcript_path


def _phase_completed_record(repo: Path) -> dict[str, Any] | None:
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    try:
        records = ledger.read_records(event_type="WorkflowPhaseCompletedDistill")
    except Exception:
        return None
    return records[-1] if records else None


def _run_gate(repo: Path) -> _HookOutcome:
    """Invoke the REAL `handle_subagent_stop` hook over its JSON stdin protocol."""
    transcript = _write_distill_return_transcript(repo)
    hook_input = json.dumps(
        {
            "session_id": "rejected-slice-session",
            "hook_event_name": "SubagentStop",
            "agent_id": "acceptance-designer-1",
            "agent_type": "acceptance-designer",
            "agent_transcript_path": str(transcript),
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
    allowed = True
    missing: tuple[str, ...] = ()
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
            raw_missing = payload.get("missing")
            if isinstance(raw_missing, list):
                missing = tuple(raw_missing)
    return _HookOutcome(
        allowed=allowed,
        decision_event=decision_event,
        exit_code=exit_code,
        missing=missing,
        phase_record=_phase_completed_record(repo),
    )


# ---------------------------------------------------------------------------
# 1. NEGATIVE -- the ONLY planned slice was reviewed and REJECTED
#    (NEEDS_REVISION). The gate must NOT treat "a record exists" as
#    "approved" -- DISTILL-exit must stay BLOCKED, never silently ALLOWED.
# ---------------------------------------------------------------------------


def test_needs_revision_only_slice_never_clears_distill_exit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01])
    _write_feature_file(repo, slice_id=_SLICE_01)
    _seed_review_verdict(repo, _SLICE_01, verdict="NEEDS_REVISION")

    outcome = _run_gate(repo)

    assert not outcome.allowed, (
        "a slice whose ONLY ATReviewVerdict record is NEEDS_REVISION must "
        "NOT clear the G-DISTILL-EXIT gate -- ADR-029 D5's control-flow "
        "clause routes a rejection back to the acceptance-designer, it must "
        f"never reach DELIVER. Got allowed=True (exit_code={outcome.exit_code}). "
        "review_verdict_slices() counts ANY verdict as 'signed'; the gate's "
        "numerator must use an APPROVED-only predicate instead."
    )
    assert _SLICE_01 in outcome.missing, (
        f"expected {_SLICE_01!r} to be named in the block's 'missing' list "
        f"-- got missing={outcome.missing!r} (event={outcome.decision_event!r})"
    )
    assert outcome.phase_record is None, (
        "no WorkflowPhaseCompletedDistill record may be written when the "
        f"only planned slice was rejected -- got {outcome.phase_record!r}"
    )


# ---------------------------------------------------------------------------
# 2. POSITIVE (regression pin) -- an APPROVED-only slice still clears
#    DISTILL-exit exactly as before this fix; the narrowed predicate must not
#    regress the ordinary approval path.
# ---------------------------------------------------------------------------


def test_approved_only_slice_still_clears_distill_exit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01])
    _write_feature_file(repo, slice_id=_SLICE_01)
    _seed_review_verdict(repo, _SLICE_01, verdict="APPROVED")

    outcome = _run_gate(repo)

    assert outcome.allowed, (
        f"an APPROVED-only planned slice must still clear DISTILL-exit -- "
        f"got blocked with event={outcome.decision_event!r}, "
        f"missing={outcome.missing!r} (exit_code={outcome.exit_code})"
    )
    assert outcome.phase_record is not None, (
        "expected a WorkflowPhaseCompletedDistill record once the APPROVED "
        "slice clears DISTILL-exit"
    )
