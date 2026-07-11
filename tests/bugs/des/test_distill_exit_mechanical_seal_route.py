"""Regression (wiring gap #94, ATD finding 2026-07-11): the G-DISTILL-EXIT
gate has NO mechanical-seal route for a pytest-regression bugfix slice.

DEFECT: `_handle_distill_exit_gate` (`src/des/adapters/drivers/hooks/
subagent_stop_handler.py:1751`) computes `missing = planned - verdict_signed`
and blocks `DistillExitVerdictIncomplete` whenever ANY planned slice lacks a
signed `ATReviewVerdict` -- unconditionally, for every `at_kind`. But per
ADR-029 / the nw-bugfix P1.1 evolution, a pytest-regression bugfix slice is
ALREADY eligible to clear the DELIVER-entry carpaccio gate (`des
carpaccio-slice-gate`, `check_at_review` in `src/des/cli/carpaccio_slice_gate.
py:420-506`) via the MECHANICAL-SEAL route: a fresh `RedObserved` seal
(`des verify-red-green --record-red`, content-bound to the regression file)
PLUS a satisfied negative-AT mandate (`des verify-negative-at --all-critical`)
clears assertion 5 as `at_evidence: "mechanical-seal"`, with zero
`ATReviewVerdict` involved. `_handle_distill_exit_gate` has no analogous
route: it demands a reviewer verdict for EVERY planned slice, including one
that already carries valid, fresh mechanical evidence -- so a bugfix slice
that is legitimately DELIVER-ready per the entry gate still cannot close
DISTILL.

The fix (crafter's job, NOT implemented by this AT -- test-authoring only,
zero `src/` edits): for each planned slice in `missing` (not verdict-signed),
`_handle_distill_exit_gate` must additionally check whether that slice is
mechanical-seal-eligible and, if so, treat it as satisfied. This AT assumes
the DISCOVERY of "which regression file backs this slice" is read from the
SAME `[REF] Slice Plan` table `_slice_plan_slice_ids` already parses (via the
shared `carpaccio_format.parse_slice_plan_rows`, C10): a NEW,
already-safe-to-parse `Annotation`-cell token, `@regression-test-file:<repo-
relative-path>` (the `Annotation` column is free text today, per
`_build_slice_rows` -- no vocabulary restriction, so this token round-trips
without touching the parser). When a planned-but-unverdicted slice's row
carries this token, the fix is expected to reuse (never duplicate --
SSOT) `carpaccio_slice_gate._mechanical_seal_satisfied(repo,
regression_test_file)` -- the EXACT predicate the DELIVER-entry gate already
trusts -- to decide whether that slice clears. This AT pins the OUTCOME (a
fresh, content-bound seal + a satisfied negative-AT mandate clears DISTILL-exit
without a verdict; an absent/stale seal does not), never the mechanism; a
different discovery convention is an acceptable fix as long as the three
outcomes below hold.

Driving surface (Mandate 13 driving-port-only, Layer 3/4 wiring_e2e): the REAL
`handle_subagent_stop` SubagentStop hook, invoked over its JSON stdin protocol
in-process via `tests.common.in_process_cli.run_hook_in_process` (the
faithful in-process analogue of the subprocess fork), against a real git
repo, a real feature-delta `[REF] Slice Plan`, a real regression test file,
and the real `AtCompletionLedger` writer/reader -- mirrors
`tests/des/acceptance/oss-hook-side-phase-injection/steps/composition.py`'s
`DistillExitGateComposition` verbatim (same hook, same transcript-marker
shape, same ledger substrate); the RedObserved seal is crafted directly in
`verify_red_green`'s own record shape via its `_seal_path`/`_content_sha`
helpers, mirroring `tests/des/unit/cli/test_carpaccio_mechanical_seal.py`'s
`_write_red_seal` so the slug/hash can never diverge from the producer.

RED-for-right-reason (red-scaffolding discipline): today
`_handle_distill_exit_gate` reads ONLY `_slice_plan_slice_ids` (slice_id +
status) and `ledger.review_verdict_slices()` -- it never looks at the
Annotation cell, never calls `_mechanical_seal_satisfied`, and never reads a
RedObserved seal file. So the POSITIVE case below (seal present, no verdict)
still computes `missing = {"slice-01"}` and BLOCKS
`DistillExitVerdictIncomplete` -- a genuine semantic `AssertionError` on the
`GateOutcome.ALLOWED` assertion, never an import/collection error (module-top
imports name only the stable hook entry + ledger reader + seal-shape helpers,
all of which exist today; per the in-process active-RED pattern P1-P4, the
absent behaviour is reached inside the hook's own runtime dispatch, not at
collection).
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


_FEATURE_ID = "bug-94-distill-exit-mechanical-seal"
_SLICE_ID = "slice-01"
_REGRESSION_REL = "tests/regression/bug_94/test_fix.py"

# Two module-level test_* functions; one carries the negative-AT name token
# (`_rejects_`) so the P0.3 --all-critical check is satisfied (mirrors
# `test_carpaccio_mechanical_seal.py`'s fixture exactly).
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


def _write_slice_plan(repo: Path, *, annotate_regression_file: bool) -> None:
    """Write a single-slice `[REF] Slice Plan`.

    `annotate_regression_file=True` adds the `@regression-test-file:<path>`
    token to the Annotation cell -- the discovery convention this AT assumes
    (see module docstring). `False` pins the GUARD case, where the gate has no
    route to any regression file at all.
    """
    feature_dir = repo / "docs" / "feature" / _FEATURE_ID
    feature_dir.mkdir(parents=True, exist_ok=True)
    annotation = (
        f"@regression-test-file:{_REGRESSION_REL}" if annotate_regression_file else ""
    )
    text = (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|-------|-----------------|--------|------------|---------------|\n"
        f"| {_SLICE_ID} | fix wiring gap #94 | pending | {annotation} | |\n"
    )
    (feature_dir / "feature-delta.md").write_text(text, encoding="utf-8")


def _write_regression_file(repo: Path) -> Path:
    regression = repo / _REGRESSION_REL
    regression.parent.mkdir(parents=True, exist_ok=True)
    regression.write_text(_REGRESSION_SRC_WITH_NEGATIVE, encoding="utf-8")
    return regression


def _write_red_seal(repo: Path, *, content_sha: str | None = None) -> Path:
    """Craft the RedObserved seal in the P0.2 producer's exact record shape.

    Mirrors `test_carpaccio_mechanical_seal.py::_write_red_seal` verbatim --
    reuses `verify_red_green`'s own `_seal_path`/`_content_sha` helpers so the
    slug and hash can never diverge from the real producer
    (`des verify-red-green --record-red`).
    """
    test_file = (repo / _REGRESSION_REL).resolve()
    seal = _red_green_seal_path(repo.resolve(), test_file)
    seal.parent.mkdir(parents=True, exist_ok=True)
    seal.write_text(
        json.dumps(
            {
                "test_file": _REGRESSION_REL,
                "content_sha256": (
                    content_sha
                    if content_sha is not None
                    else _red_seal_content_sha(test_file)
                ),
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
            "timestamp": "2026-07-11T10:30:00Z",
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")
    return transcript_path


def _run_gate(repo: Path, transcript_path: Path) -> _HookOutcome:
    """Invoke the REAL `handle_subagent_stop` hook over its JSON stdin protocol."""
    hook_input = json.dumps(
        {
            "session_id": "bug-94-session",
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
    return _HookOutcome(
        allowed=allowed,
        decision_event=decision_event,
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


def test_fresh_mechanical_seal_clears_distill_exit_without_reviewer_verdict(
    tmp_path: Path,
) -> None:
    """POSITIVE (the bug, active-RED today): a planned slice with NO
    `ATReviewVerdict` but a valid, fresh `RedObserved` seal + satisfied
    negative-AT mandate in its declared regression file must clear the
    G-DISTILL-EXIT gate -- today it blocks
    `DistillExitVerdictIncomplete` because the gate has no mechanical-seal
    route at all.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, annotate_regression_file=True)
    _write_regression_file(repo)
    _write_red_seal(repo)
    transcript = _write_distill_return_transcript(repo)

    outcome = _run_gate(repo, transcript)

    assert outcome.allowed, (
        "expected the G-DISTILL-EXIT gate to ALLOW the transition for a "
        "planned slice carrying a fresh RedObserved seal + satisfied "
        "negative-AT mandate (the mechanical-seal route), even with zero "
        f"ATReviewVerdict records -- got blocked with "
        f"event={outcome.decision_event!r} (exit_code={outcome.exit_code}). "
        "The gate has no mechanical-seal route today (it only checks "
        "`ledger.review_verdict_slices()`); see this module's docstring for "
        "the fix direction."
    )
    assert outcome.phase_completed_emitted, (
        "expected a `WorkflowPhaseCompletedDistill` ledger record once the "
        "mechanical-seal route clears every planned slice -- none was found "
        f"(exit_code={outcome.exit_code}, event={outcome.decision_event!r})"
    )
    assert outcome.exit_code == 0


def test_no_verdict_no_seal_still_blocks_distill_exit(tmp_path: Path) -> None:
    """GUARD (stays green today and after the fix): a planned slice with
    NEITHER a signed `ATReviewVerdict` NOR any mechanical-seal evidence (no
    `@regression-test-file` annotation, no seal file) must keep blocking
    `DistillExitVerdictIncomplete` -- the mechanical-seal route must never
    become a blanket bypass for an un-evidenced slice.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, annotate_regression_file=False)
    transcript = _write_distill_return_transcript(repo)

    outcome = _run_gate(repo, transcript)

    assert not outcome.allowed, (
        "expected the G-DISTILL-EXIT gate to BLOCK when the planned slice "
        "carries neither a signed ATReviewVerdict nor any mechanical-seal "
        f"evidence -- got allowed (exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        "expected the self-explaining `DistillExitVerdictIncomplete` block "
        f"event -- got {outcome.decision_event!r}"
    )
    assert not outcome.phase_completed_emitted, (
        "no `WorkflowPhaseCompletedDistill` record should be written when "
        "the gate blocks"
    )
    assert outcome.exit_code == 0


def test_stale_red_seal_does_not_clear_distill_exit_not_bypassed_by_edit(
    tmp_path: Path,
) -> None:
    """NEGATIVE (`_not_`): a `RedObserved` seal whose `content_sha256` no
    longer matches the regression file's CURRENT content (the file was
    edited after the seal was recorded) must NOT clear DISTILL-exit -- the
    mechanical route must honor the same content-binding / tamper semantics
    `_mechanical_seal_satisfied` already enforces at the DELIVER-entry gate.
    A stale seal is evidentially equivalent to no seal at all: the gate keeps
    blocking `DistillExitVerdictIncomplete`.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, annotate_regression_file=True)
    regression = _write_regression_file(repo)
    _write_red_seal(repo)
    # Edit AFTER the seal was recorded -- content_sha256 in the seal now
    # disagrees with the file's current hash (tamper / post-RED edit).
    regression.write_text(
        regression.read_text(encoding="utf-8") + "\n# tampered after RED\n",
        encoding="utf-8",
    )
    transcript = _write_distill_return_transcript(repo)

    outcome = _run_gate(repo, transcript)

    assert not outcome.allowed, (
        "expected the G-DISTILL-EXIT gate to BLOCK when the RedObserved "
        "seal's content_sha256 no longer matches the regression file's "
        f"CURRENT content (stale/tampered seal) -- got allowed "
        f"(exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        "expected the same `DistillExitVerdictIncomplete` block event a "
        f"missing-seal slice gets -- got {outcome.decision_event!r}. A "
        "stale seal must be treated as evidentially absent, never as a "
        "partial pass."
    )
    assert not outcome.phase_completed_emitted
