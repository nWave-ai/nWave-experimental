"""Composition root for slice-04 -- the U4 feature-end intercept + D6 skew.

slice-04 of F-DES-ATDD-PURE-HOOK-GATES (U4 + D6 / Mikado T-H).

Drives the PRODUCTION SubagentStop hook end-to-end through its real JSON hook
protocol (`handle_subagent_stop` reading stdin, writing a `{"decision":"block"}`
body to stdout). The composition root builds a real git repository carrying a
real feature-delta `[REF] Slice Plan` and a real U3 AT-completion ledger,
invokes the hook as a subprocess (`@wiring_e2e`), and reads back the decision.

The skew-classifier surface is exercised directly against the production
`_classify_hook_version_skew` -- a layer 1-2 pure-domain function (Mandate 9
PBT-eligible; the slice exercises it example-pinned over the 5-row M13 table).

The only test doubles are the absent ones: there are none. The git repo, the
feature-delta, the ledger JSONL, the transcript JSONL, and the hook subprocess
are all real I/O.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from tests.des._helpers.feature_end_seeding import (
    seed_required_feature_end_records,
)

from .slice04_domain_types import FeatureEndOutcome, FeatureId


_FEATURE_ID = FeatureId("atdd-pure-demo")
_HANDLER_MODULE = "des.adapters.drivers.hooks.subagent_stop_handler"

# The planned slice ids for the synthetic feature-delta slice plan.
_PLANNED_SLICES = ("slice-00", "slice-01")


@dataclass
class FeatureEndOutcomeResult:
    """The observable result of a U4 feature-end SubagentStop intercept."""

    outcome: FeatureEndOutcome
    decision_event: str | None
    exit_code: int


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout


class FeatureEndInterceptComposition:
    """Production-wired composition root for the U4 feature-end intercept.

    The driving port is the real `handle_subagent_stop` hook invoked over its
    JSON stdin protocol; the observable surface is the hook's stdout decision
    body and its exit code.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._transcript_path = repo / "agent.jsonl"
        self._fault_injected = False

    # --- repository + feature-delta provisioning ----------------------------

    def init_repo(self) -> None:
        """Initialise a real git repo carrying a feature-delta slice plan."""
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        self._write_feature_delta()
        self._write_atdd_pure_config()

    def _write_atdd_pure_config(self) -> None:
        """Write `.nwave/config.yaml` declaring `workflow.mode: atdd_pure`.

        `verify_deliver_integrity` resolves the spine shape from this file --
        without it the integrity gate takes the classic roadmap-shaped path.
        """
        nwave_dir = self._repo / ".nwave"
        nwave_dir.mkdir(parents=True, exist_ok=True)
        (nwave_dir / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )

    def _write_feature_delta(self) -> None:
        """Write a feature-delta carrying a real `[REF] Slice Plan` table."""
        feature_dir = self._repo / "docs" / "feature" / self._feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
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

    # --- ledger provisioning ------------------------------------------------

    def seed_all_slices_verified(self) -> None:
        """Append a `SliceCommitVerified` record for every planned slice."""
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        for sid in _PLANNED_SLICES:
            ledger.append_gate_event(event="SliceCommitVerified", slice_id=sid)

    def seed_feature_end_cycle_complete(self) -> None:
        """Record the feature-end cycle: refactor done + review verdict (F1).

        slice-05 revision (Finding 1): feature-end passes only when the cycle
        wrote BOTH machine records. The happy path seeds both.

        fix-oss-environmental-e2e-gate slice-02: the env-e2e heartbeat record
        is also required at feature-end (presence-of-proof done-gate); the
        happy path seeds it alongside the refactor + review records.

        fix-walking-skeleton-feature-end-wiring slice-01: the walking-skeleton
        heartbeat is also required at feature-end (5th sibling of the env-e2e
        pre-7af95a3d2 defect class); the happy path seeds it alongside the
        refactor + review + env-e2e records.

        fix-distill-signoff-feature-end-wiring slice-01: the two coverage-map
        touchpoint heartbeats are also required at feature-end (closes the
        F-SLICE-06-U4-CONSUMER-MISSING residue from Gate D slice-06); the
        happy path seeds both alongside the prior heartbeats.
        """
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        seed_required_feature_end_records(ledger, verdict_hash="slice-05-verdict-hash")

    def seed_feature_end_cycle_missing(self, missing_record: str) -> None:
        """Record every feature-end cycle record EXCEPT ``missing_record`` (F1).

        Exercises the `FeatureEndCycleIncomplete` fail-closed block: a feature
        with all slices shipped but a missing refactor or review record must be
        refused at feature-end.
        """
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        seed_required_feature_end_records(
            ledger,
            verdict_hash="partial-hash",
            exclude=(missing_record,),
        )

    def corrupt_the_ledger(self) -> None:
        """Seed a full ledger then hand-edit a record so `record_hash` mismatches.

        A tampered record breaks the M7 integrity contract; U4 must block with
        `LedgerIntegrityViolation`, NEVER degrade to the markdown fallback.
        """
        self.seed_all_slices_verified()
        ledger = AtCompletionLedger(self._feature_id, self._repo)
        path = ledger.ledger_path()
        lines = path.read_text(encoding="utf-8").splitlines()
        first = json.loads(lines[0])
        first["slice_id"] = "slice-tampered"  # hashed field -- breaks the digest
        lines[0] = json.dumps(first, separators=(",", ":"), sort_keys=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def inject_handler_fault(self) -> None:
        """Mark the run so the U4 branch raises -- exercises the M1 try/except.

        The fault path still needs a usable ledger so the run reaches the
        injected fault rather than a precondition block.
        """
        self.seed_all_slices_verified()
        self._fault_injected = True

    # --- crafter transcript -------------------------------------------------

    def write_f_final_review_transcript(self) -> None:
        """Write a transcript whose last atdd_pure block is a F_FINAL_REVIEW return."""
        block = (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : F_FINAL_REVIEW -->\n"
            "<!-- DES-SLICE : slice-01 -->\n"
            f"<!-- DES-PROJECT-ID : {self._feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self._repo} -->\n"
        )
        entry = json.dumps(
            {
                "type": "user",
                "message": {"role": "user", "content": block},
                "uuid": "feature-end-block",
                "timestamp": "2026-05-20T11:00:00Z",
            }
        )
        self._transcript_path.write_text(entry + "\n", encoding="utf-8")

    # --- driving-port invocation -------------------------------------------

    def run_subagent_stop_hook(self) -> FeatureEndOutcomeResult:
        """Invoke the REAL `handle_subagent_stop` hook over its JSON protocol."""
        hook_input = json.dumps(
            {
                "session_id": "slice-04-session",
                "hook_event_name": "SubagentStop",
                "agent_id": "reviewer-1",
                "agent_type": "software-crafter-reviewer",
                "agent_transcript_path": str(self._transcript_path),
                "stop_hook_active": False,
                "cwd": str(self._repo),
                "transcript_path": "/tmp/session.jsonl",
                "permission_mode": "default",
            }
        )
        env_fault = "1" if self._fault_injected else "0"
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
            env={
                **_subprocess_env(),
                "NWAVE_U4_FORCE_HANDLER_FAULT": env_fault,
            },
        )
        return self._interpret(completed)

    def _interpret(
        self, completed: subprocess.CompletedProcess
    ) -> FeatureEndOutcomeResult:
        decision_event: str | None = None
        outcome = FeatureEndOutcome.ALLOWED
        for line in completed.stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("decision") == "block":
                outcome = FeatureEndOutcome.BLOCKED
                decision_event = payload.get("event")
        return FeatureEndOutcomeResult(
            outcome=outcome,
            decision_event=decision_event,
            exit_code=completed.returncode,
        )


def classify_skew(installed: str | None, checkout: str) -> str:
    """Classify hook-version skew via the production D6/M5 classifier.

    Returns the skew case string -- `"none"` when the classifier returns None
    (no skew), else one of `"behind"` / `"ahead"` / `"stamp-absent"`.
    """
    from des.adapters.drivers.hooks.session_start_handler import (
        _classify_hook_version_skew,
    )

    case = _classify_hook_version_skew(installed, checkout)
    return case if case is not None else "none"


def _subprocess_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path("src").resolve())
    return env
