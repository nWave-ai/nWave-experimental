"""Composition root for slice-01 -- the G-DISTILL-EXIT SubagentStop gate.

slice-01 of oss-hook-side-phase-injection (the DISTILL-wave hook keystone, D1).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION composition root -- the real ``handle_subagent_stop`` hook invoked
end-to-end over its JSON stdin protocol as a subprocess (Layer 3/4 wiring_e2e,
the direct mirror of the shipped U2 ``g-commit-exit-gate`` /  U4
``feature-end`` SubagentStop ATs). The hook reads stdin, resolves the
``D_DISTILL`` atdd_pure return, runs the G-DISTILL-EXIT gate, and writes a
``{"decision": "block"}`` body (or allows) + emits a ledger record.

The composition NEVER imports the hook's gate logic and calls it at the step
boundary (no ``from des.adapters.drivers.hooks.subagent_stop_handler import
_handle_distill_exit_gate``); the only entry is the real hook subprocess. The
production ``AtCompletionLedger`` writer is used ONLY to (a) seed the
precondition substrate (signed ``ATReviewVerdict`` records the gate will read)
and (b) read back the observable phase-completed terminal the gate emits --
this is the audit SUBSTRATE the hook consumes, not the SUT. This mirrors the
shipped U4 ``slice04_composition.py`` pattern verbatim (it seeds
``SliceCommitVerified`` records through the same writer for the same
``_slice_plan_slice_ids`` denominator).

The only test doubles are the absent ones: there are none. The git repo, the
feature-delta ``[REF] Slice Plan``, the ledger JSONL, the transcript JSONL, and
the hook subprocess are all real I/O -- a layer-3/4 ``@real-io`` /
``@wiring_e2e`` surface (Mandate 9/11: example only, no PBT machinery).

HARD INVARIANT (hook-can't-spawn-agent): the observable surface is the block
decision, the exit code, and the ledger record. No assertion claims the hook
dispatched the reviewer -- it cannot, and the gate's job is to BLOCK/EMIT only.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .domain_types import (
    FeatureId,
    GateOutcome,
    SlicePlanShape,
    VerdictSetShape,
)


_FEATURE_ID = FeatureId("atdd-pure-demo")
_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The planned slice ids for the synthetic feature-delta slice plan -- the
# DENOMINATOR the gate resolves via ``_slice_plan_slice_ids`` (MAJOR-2).
_PLANNED_SLICES: tuple[str, ...] = ("slice-00", "slice-01")

# The success terminal the gate emits on a complete verdict set (MAJOR-1):
# ``WorkflowPhaseCompletedDistill`` with ``slice_id=""`` (feature-scoped).
_PHASE_COMPLETED_DISTILL = "WorkflowPhaseCompletedDistill"

# The seven HMAC-signed fields of an ``ATReviewVerdict`` (ADR-029 D5 B1), pinned
# locally so the seeded precondition records carry the same signed shape the
# production producer writes -- the gate reads them back as the verdict set.
_VERDICT_SIGNED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)
_VERDICT_SCHEMA_VERSION = "1.0.0"
# A fixed seeding key for the precondition records. The gate's verdict-set
# completeness check keys on the PRESENCE of an ``ATReviewVerdict`` record per
# planned slice, read under the M7 integrity contract -- the HMAC value itself
# is the producer's concern (slice-03), not this gate's. The seeded signature
# is a deterministic local HMAC so the record is well-formed.
_SEED_SIGNING_KEY = b"slice-01-seed-key"


@dataclass
class DistillExitOutcome:
    """The observable result of a G-DISTILL-EXIT SubagentStop gate evaluation.

    Universe entries are port-exposed only (Mandate 8): the block decision +
    its event name, the hook exit code, and the phase-completed terminal read
    back from the ledger -- never an internal handler struct field.
    """

    outcome: GateOutcome
    decision_event: str | None
    exit_code: int
    phase_completed_emitted: bool


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


class DistillExitGateComposition:
    """Production-wired composition root for the G-DISTILL-EXIT gate slice.

    The driving port is the real ``handle_subagent_stop`` hook invoked over its
    JSON stdin protocol; the observable surface is the hook's stdout decision
    body, its exit code, and the ``WorkflowPhaseCompletedDistill`` ledger record
    the gate emits on a complete verdict set.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._transcript_path = repo / "agent.jsonl"

    # --- repository + feature-delta provisioning ----------------------------

    def init_repo(self) -> None:
        """Initialise a real git repo carrying a feature-delta slice plan."""
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "README.md")
        _git(self._repo, "commit", "-m", "chore: seed")

    def write_slice_plan(self, shape: SlicePlanShape) -> None:
        """Write a feature-delta with (or without) a real ``[REF] Slice Plan``.

        PRESENT     -- a well-formed table whose slice rows are the
                       denominator the gate resolves.
        UNPARSEABLE -- a feature-delta with no parseable slice-plan table, so
                       the gate's denominator read raises and it fail-closed
                       blocks ``SlicePlanParseUnresolved`` (never a vacuous
                       pass).
        """
        feature_dir = self._repo / "docs" / "feature" / self._feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        if shape is SlicePlanShape.UNPARSEABLE:
            text = (
                "# Feature Delta: atdd-pure-demo\n\n"
                "## Wave: DISCUSS\n\n"
                "No slice plan table here -- the denominator is unresolvable.\n"
            )
        else:
            rows = "\n".join(
                f"| {sid} | deliver {sid} | shipped | | justified |"
                for sid in _PLANNED_SLICES
            )
            text = (
                "# Feature Delta: atdd-pure-demo\n\n"
                "## Wave: DISCUSS / [REF] Slice Plan\n\n"
                "| Slice | Value statement | Status | Annotation | Justification |\n"
                "|-------|-----------------|--------|------------|---------------|\n"
                f"{rows}\n"
            )
        (feature_dir / "feature-delta.md").write_text(text, encoding="utf-8")

    # --- ledger provisioning (precondition substrate, NOT the SUT) ----------

    def seed_verdict_set(self, shape: VerdictSetShape) -> None:
        """Seed signed ``ATReviewVerdict`` records for the planned slices.

        COMPLETE    -- one signed verdict per planned slice; the gate's
                       completeness check (planned ⊆ verdict-signed) holds.
        MISSING_ONE -- a verdict for every planned slice EXCEPT the last; the
                       gate blocks ``DistillExitVerdictIncomplete``. This pins
                       the denominator = ``_slice_plan_slice_ids`` (MAJOR-2):
                       the omitted slice is one the plan declares, so its
                       absence from the verdict set is what the gate catches.

        Each record is routed through the production ``append_review_verdict``
        so it carries the same ``seq`` + ``record_hash`` the producer writes --
        the gate reads it back under the M7 fail-closed integrity contract.
        """
        signed_slices = (
            _PLANNED_SLICES
            if shape is VerdictSetShape.COMPLETE
            else _PLANNED_SLICES[:-1]
        )
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        for sid in signed_slices:
            ledger.append_review_verdict(
                slice_id=sid, verdict_fields=self._signed_verdict_fields(sid)
            )

    def _signed_verdict_fields(self, slice_id: str) -> dict[str, object]:
        """A well-formed signed ``ATReviewVerdict`` field set for ``slice_id``."""
        record: dict[str, object] = {
            "schema_version": _VERDICT_SCHEMA_VERSION,
            "slice_id": slice_id,
            "verdict": "APPROVED",
            "reviewer_agent_id": "nw-acceptance-designer-reviewer",
            "at_ids": [f"{slice_id}-AT-1"],
            "at_content_hash": hashlib.sha256(slice_id.encode()).hexdigest(),
            "timestamp": "2026-05-29T10:00:00Z",
        }
        signed = {field: record[field] for field in _VERDICT_SIGNED_FIELDS}
        canonical = json.dumps(signed, sort_keys=True, separators=(",", ":")).encode()
        record["hmac_sha256"] = hmac.new(
            _SEED_SIGNING_KEY, canonical, hashlib.sha256
        ).hexdigest()
        record["findings_summary"] = "clean"
        return record

    # --- acceptance-designer transcript -------------------------------------

    def write_distill_return_transcript(self) -> None:
        """Write a transcript whose LAST atdd_pure block is a ``D_DISTILL`` return.

        The ``D_DISTILL`` dispatch is per-feature, so its only coherent slice
        scope is the ``feature-end`` literal (MAJOR-2 / the closed-world XOR).
        """
        block = self._marker_block(phase="D_DISTILL", slice_id="feature-end")
        line = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "distill-return",
                "timestamp": "2026-05-29T10:30:00Z",
            }
        )
        self._transcript_path.write_text(line + "\n", encoding="utf-8")

    def _marker_block(self, *, phase: str, slice_id: str) -> str:
        return (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {phase} -->\n"
            f"<!-- DES-SLICE : {slice_id} -->\n"
            f"<!-- DES-PROJECT-ID : {self._feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )

    # --- driving-port invocation --------------------------------------------

    def run_subagent_stop_hook(self) -> DistillExitOutcome:
        """Invoke the REAL ``handle_subagent_stop`` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": "slice-01-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "acceptance-designer-1",
                "agent_type": "acceptance-designer",
                "agent_transcript_path": str(self._transcript_path),
                "stop_hook_active": False,
                "cwd": str(self._repo),
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )
        runner = (
            "import sys; "
            f"sys.path.insert(0, {str(Path('src').resolve())!r}); "
            f"from {_HANDLER_MODULE} import handle_subagent_stop; "
            "sys.exit(handle_subagent_stop())"
        )
        completed = subprocess.run(
            [sys.executable, "-c", runner],
            input=hook_input,
            capture_output=True,
            text=True,
            cwd=str(Path.cwd()),
            env=_subprocess_env(),
        )
        return self._interpret(completed)

    def _interpret(self, completed: subprocess.CompletedProcess) -> DistillExitOutcome:
        decision_event: str | None = None
        outcome = GateOutcome.ALLOWED
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                outcome = GateOutcome.BLOCKED
                decision_event = payload.get("event")
        return DistillExitOutcome(
            outcome=outcome,
            decision_event=decision_event,
            exit_code=completed.returncode,
            phase_completed_emitted=self._phase_completed_emitted(),
        )

    def _phase_completed_emitted(self) -> bool:
        """Whether the gate persisted a ``WorkflowPhaseCompletedDistill`` record.

        The symmetric SUCCESS terminal (SF ADR-016): read back through the
        production ledger reader under the M7 integrity contract. A corrupt
        ledger raises here; the block path means no terminal was written.
        """
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        try:
            records = ledger.read_records(event_type=_PHASE_COMPLETED_DISTILL)
        except Exception:
            return False
        return len(records) >= 1


def _subprocess_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path("src").resolve())
    return env


__all__ = [
    "DistillExitGateComposition",
    "DistillExitOutcome",
]
