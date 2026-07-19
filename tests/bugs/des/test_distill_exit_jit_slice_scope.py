"""Regression AT -- G-DISTILL-EXIT blocks the FIRST slice of every multi-slice
`atdd_pure` feature under per-slice JIT authoring (backlog #128, this bugfix's
own RCA, reproduced live twice on real features before this AT existed).

DEFECT: `_handle_distill_exit_gate` (`src/des/adapters/drivers/hooks/
subagent_stop_handler.py:1933`, decision table at :1949-1977) computes
``missing = planned - verdict_signed`` where ``planned`` is EVERY row
`_slice_plan_slice_ids` (:1377) parses out of the feature-delta `[REF] Slice
Plan` table -- ALL planned slices, at EVERY D_DISTILL return, never scoped to
the slice(s) actually authored in THIS dispatch. Per-slice JIT authoring
(atdd_pure canonical, `nw-distill` Mandate 4) deliberately leaves slice-02+
absent from disk until their turn -- they can never carry a signed
`ATReviewVerdict`, so ``missing`` always contains them and the gate blocks
`DistillExitVerdictIncomplete` on slice-01's own, correctly-reviewed return.
Verbatim block observed: ``{"event":"DistillExitVerdictIncomplete",
"missing":["slice-02"]}``.

THE FIX (crafter's job, NOT implemented here -- test-authoring only, zero
`src/` edits): `_handle_distill_exit_gate` must distinguish a planned slice
that is ABSENT FROM DISK (no `.feature` file anywhere carrying its
`@slice-NN` tag under the feature's `@feature-{id}` scope -- the JIT-not-yet-
reached case, safe to exclude from `missing`) from one that IS PRESENT ON
DISK but carries neither a verdict nor mechanical-seal evidence (a genuine
review omission, must stay in `missing`). The natural discovery primitive
already exists and is reused elsewhere in this exact call chain for the
identical purpose: `des.application.slice_at_completeness.feature_files_for_
slice(repo, slice_id, feature_id)` (empty list == absent-by-JIT). This AT
pins the OUTCOME (three-way split: verdict/seal-cleared, present-but-
unevidenced, absent-and-excluded) and the DURABLE audit-trail shape of the
exclusion, never the discovery mechanism.

Charter (the negative oracles below are its, not invented): `docs/product/
expectations/fix-distill-exit-blocks-jit-slices/operator-passes-distill-exit-
on-slice-one-without-later-slice-verdicts.md`.
  1. slice-01 authored+reviewed, slice-02+ absent from disk -> PASS, naming
     slice-01 specifically as what it validated (never a blanket "all ok").
  2. slice-01 itself unevidenced -> STILL REFUSE, even with slice-02 absent.
     A scaffold-only (`@skip`) `.feature` must read as "not reviewed", never
     a hollow pass.
  3. slice-02 EXISTS on disk (authored early) but unevidenced -> STILL
     CAUGHT -- "absent" must never widen to "anything past slice-01".
  4. An excluded (absent-by-JIT) slice must be NAMED, not silently dropped --
     a pass that looks identical whether the gate reasoned about scope or
     simply stopped looking is not a trustworthy pass.

Driving surface (Mandate 13 driving-port-only, Layer 3/4 wiring_e2e):
identical to the sibling `test_distill_exit_mechanical_seal_route.py` -- the
REAL `handle_subagent_stop` SubagentStop hook, invoked over its JSON stdin
protocol in-process via `tests.common.in_process_cli.run_hook_in_process`,
against a real git repo, a real feature-delta `[REF] Slice Plan`, real
`.feature` files, and the real `AtCompletionLedger` writer/reader.

CRITICAL -- this gate's success protocol is SILENCE: `_handle_distill_exit_
gate` prints nothing on the ALLOW path (`return 0` with no JSON, see the
SubagentStop protocol docstring at :1980-1982). Asserting on stdout therefore
CANNOT distinguish "armed and correctly scoped" from "never ran". Every
positive assertion below reads the SIDE EFFECT instead: the durable
`WorkflowPhaseCompletedDistill` ledger record. Because that record is
CURRENTLY written with no per-slice detail at all (`{"event": ...,
"slice_id": ""}`, `at_completion_ledger.py:601-604`), the fix must extend it
with two new fields this AT pins as the observable contract for oracle 1/4
(there is no other durable surface a silent-success gate could use):
  - ``validated_slices``: the slices this record actually certifies (verdict-
    signed or mechanical-seal-cleared) -- e.g. ``["slice-01"]``, never a
    blanket claim about the whole plan.
  - ``excluded_slices``: the JIT-absent slices this evaluation explicitly
    left out of scope -- e.g. ``["slice-02"]`` -- the durable "say so" the
    charter's oracle 4 demands; empty for an ordinary single-slice feature.

RED-for-right-reason: today `_handle_distill_exit_gate` computes
``missing = planned - verdict_signed`` (minus the pytest-regression-only
mechanical-seal route) with NO absent-from-disk carve-out at all, so the
POSITIVE case below still blocks `DistillExitVerdictIncomplete` naming
slice-02 -- a genuine semantic `AssertionError` on the `GateOutcome.ALLOWED`
assertion, never an import/collection error.

covers: fix-distill-exit-blocks-jit-slices
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


_FEATURE_ID = "fix-distill-exit-jit-scope-probe"
_SLICE_01 = "slice-01"
_SLICE_02 = "slice-02"


@dataclass
class _HookOutcome:
    """Observable result of one G-DISTILL-EXIT SubagentStop evaluation."""

    allowed: bool
    decision_event: str | None
    exit_code: int
    missing: tuple[str, ...] = ()
    # The durable WorkflowPhaseCompletedDistill record, or None when the gate
    # blocked (no success record is ever written on a block).
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


def _write_feature_file(
    repo: Path, *, slice_id: str, skip: bool = False, filename: str | None = None
) -> Path:
    """Author a real, DISCOVERABLE `.feature` file for ``slice_id``.

    File-level `@feature-{feature_id}` tag + scenario-level `@slice-NN` tag --
    the SAME discovery convention `feature_at_files.feature_tag_files` /
    `slice_at_completeness.feature_files_for_slice` already use elsewhere in
    this exact call chain (SSOT, per Example 5 of the acceptance-designer's
    own gate-form tagging convention). `skip=True` produces a scaffold-only
    body (`@skip`, no real steps) -- oracle 2's "must read as not reviewed"
    probe.
    """
    acceptance_dir = repo / "tests" / _FEATURE_ID / "acceptance"
    acceptance_dir.mkdir(parents=True, exist_ok=True)
    scenario_tags = f"@{slice_id}" + (" @skip" if skip else "")
    if skip:
        steps = (
            "    Given this scenario has not been authored yet\n"
            "    Then it stays pending\n"
        )
    else:
        steps = (
            f"    Given a multi-slice feature with {slice_id} authored and reviewed\n"
            "    When the DISTILL exit gate runs\n"
            f"    Then the operator proceeds to DELIVER for {slice_id}\n"
        )
    text = (
        f"@feature-{_FEATURE_ID}\n"
        f"Feature: distill exit JIT scope probe ({slice_id})\n\n"
        f"  {scenario_tags}\n"
        f"  Scenario: probe scenario for {slice_id}\n"
        f"{steps}"
    )
    path = acceptance_dir / (filename or f"{slice_id}.feature")
    path.write_text(text, encoding="utf-8")
    return path


_VERDICT_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)


def _seed_review_verdict(repo: Path, slice_id: str) -> None:
    """Seed one signed `ATReviewVerdict` record via the production writer.

    Mirrors `test_distill_exit_mechanical_seal_route.py::_seed_review_verdict`
    verbatim -- routed through the SAME `append_review_verdict` producer the
    gate's `ledger.review_verdict_slices()` read trusts, under the M7
    fail-closed integrity contract (seq + record_hash).
    """
    record: dict[str, object] = {
        "schema_version": "1.0.0",
        "slice_id": slice_id,
        "verdict": "APPROVED",
        "reviewer_agent_id": "nw-acceptance-designer-reviewer",
        "at_ids": [f"{slice_id}-AT-1"],
        "at_content_hash": hashlib.sha256(slice_id.encode()).hexdigest(),
        "timestamp": "2026-07-19T10:00:00Z",
    }
    signed = {field_name: record[field_name] for field_name in _VERDICT_SIGNED_FIELDS}
    canonical = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
    record["hmac_sha256"] = hmac.new(
        b"jit-scope-seed-key", canonical, hashlib.sha256
    ).hexdigest()
    record["findings_summary"] = "clean"
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
            "session_id": "jit-scope-session",
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
# 1. POSITIVE -- slice-01 authored + reviewed, slice-02 absent from disk
#    (JIT, not yet reached) -> PASS, naming slice-01 specifically.
# ---------------------------------------------------------------------------


def test_slice_one_verdict_signed_slice_two_absent_from_disk_clears_distill_exit(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01, _SLICE_02])
    _write_feature_file(repo, slice_id=_SLICE_01)
    _seed_review_verdict(repo, _SLICE_01)
    # slice-02: nothing written at all -- no .feature file anywhere, no
    # verdict -- the JIT-not-yet-authored case.

    outcome = _run_gate(repo)

    assert outcome.allowed, (
        f"a correctly-reviewed slice-01 with slice-02 deliberately absent "
        f"from disk (JIT authoring) must clear G-DISTILL-EXIT -- got blocked "
        f"with event={outcome.decision_event!r}, missing={outcome.missing!r} "
        f"(exit_code={outcome.exit_code}). The gate must not count a "
        "not-yet-authored later slice as a missing verdict."
    )
    assert outcome.exit_code == 0
    assert outcome.phase_record is not None, (
        "expected a WorkflowPhaseCompletedDistill ledger record on the "
        f"success path -- none was found (exit_code={outcome.exit_code})"
    )
    validated = set(outcome.phase_record.get("validated_slices", []))
    excluded = set(outcome.phase_record.get("excluded_slices", []))
    assert validated == {_SLICE_01}, (
        "oracle 1: the pass must name slice-01 SPECIFICALLY as the verdict "
        f"it validated -- not a blanket 'all slices ok'. Expected "
        f"validated_slices == {{'slice-01'}}, got {validated!r} "
        f"(record={outcome.phase_record!r})"
    )
    assert excluded == {_SLICE_02}, (
        "oracle 4: an excluded (JIT-absent) slice must be NAMED on the "
        "durable record, not silently dropped -- a pass that looks "
        "identical whether the gate reasoned about scope or simply stopped "
        f"looking is not a trustworthy pass. Expected excluded_slices == "
        f"{{'slice-02'}}, got {excluded!r} (record={outcome.phase_record!r})"
    )


# ---------------------------------------------------------------------------
# 2. NEGATIVE (`_rejects_`) -- slice-01 itself unevidenced must still block,
#    even though slice-02 is absent-by-JIT. A fix that stops checking
#    slice-01 too, to also stop checking the absent slices, trades a loud
#    false block for a silent hole -- worse than the defect it closes.
# ---------------------------------------------------------------------------


def test_slice_one_without_verdict_still_rejects_distill_exit_when_slice_two_absent(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01, _SLICE_02])
    # slice-01: no .feature file, no verdict -- genuinely unreviewed.
    # slice-02: absent from disk (JIT).

    outcome = _run_gate(repo)

    assert not outcome.allowed, (
        "slice-01 itself carries no signed verdict and no mechanical seal -- "
        f"the gate must still REFUSE even with slice-02 absent-by-JIT. Got "
        f"allowed (exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        f"expected DistillExitVerdictIncomplete -- got {outcome.decision_event!r}"
    )
    assert set(outcome.missing) == {_SLICE_01}, (
        "the block must name ONLY the genuinely unevidenced slice-01 -- "
        "slice-02 is absent-by-JIT and must never be reported missing "
        f"alongside it. Got missing={outcome.missing!r}"
    )
    assert outcome.phase_record is None, (
        "no WorkflowPhaseCompletedDistill record should be written on a block"
    )


# ---------------------------------------------------------------------------
# 3. NEGATIVE (`_never_`) -- slice-02 DOES exist on disk (authored early) but
#    carries no verdict -> still caught. "Absent" must never widen to "any
#    later slice, evidenced or not".
# ---------------------------------------------------------------------------


def test_slice_two_authored_but_unreviewed_is_never_silently_excluded_from_missing(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01, _SLICE_02])
    _write_feature_file(repo, slice_id=_SLICE_01)
    _seed_review_verdict(repo, _SLICE_01)
    # slice-02: authored EARLY (a real .feature file with real steps exists)
    # but never reviewed -- a genuine omission, not a JIT absence.
    _write_feature_file(repo, slice_id=_SLICE_02)

    outcome = _run_gate(repo)

    assert not outcome.allowed, (
        "slice-02 has a real .feature file on disk but no verdict -- the "
        "gate must catch this, never treat it as absent-by-JIT just because "
        f"it is not slice-01. Got allowed (exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        f"expected DistillExitVerdictIncomplete -- got {outcome.decision_event!r}"
    )
    assert set(outcome.missing) == {_SLICE_02}, (
        "expected the block to name the genuinely-authored-but-unreviewed "
        f"slice-02 -- got missing={outcome.missing!r}"
    )
    assert outcome.phase_record is None


# ---------------------------------------------------------------------------
# 4. NEGATIVE (`_not_`, guard) -- a scaffold-only (`@skip`, no real steps)
#    `.feature` file must read as "not reviewed", never a hollow pass. Stays
#    green both before AND after a correct fix -- proves "present on disk"
#    is never conflated with "reviewed".
# ---------------------------------------------------------------------------


def test_scaffold_only_feature_file_is_not_mistaken_for_a_reviewed_slice(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    _write_slice_plan(repo, [_SLICE_01, _SLICE_02])
    _write_feature_file(repo, slice_id=_SLICE_01, skip=True)
    # slice-01 carries NO signed verdict -- only a scaffold `.feature`.
    # slice-02: absent from disk (JIT).

    outcome = _run_gate(repo)

    assert not outcome.allowed, (
        "a scaffold-only (@skip, no real steps) .feature file for slice-01, "
        "with no signed verdict, must NOT clear DISTILL-exit -- a file's "
        "mere presence on disk is not a review. Got allowed "
        f"(exit_code={outcome.exit_code})"
    )
    assert outcome.decision_event == "DistillExitVerdictIncomplete", (
        f"expected DistillExitVerdictIncomplete -- got {outcome.decision_event!r}"
    )
    assert set(outcome.missing) == {_SLICE_01}
    assert outcome.phase_record is None
