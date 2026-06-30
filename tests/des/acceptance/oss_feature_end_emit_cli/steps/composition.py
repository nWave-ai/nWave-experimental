"""Composition root for slice-01 -- the `des emit-feature-end` CLI.

slice-01 of oss-feature-end-emit-cli (the R2 walking-skeleton).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION single entry point -- the real `des emit-feature-end` subcommand
invoked end-to-end over the `des.cli.__main__` dispatcher as a subprocess
(Layer 3 subprocess, the same driving surface as `des verify-slice-commit`).
The composition NEVER imports the CLI's `main` and calls it at the step
boundary (no `from des.cli.emit_feature_end import main`); the only entry is
the real subprocess through the dispatcher, exactly as an operator invokes it.

The production `AtCompletionLedger` reader is used ONLY to read back the
observable -- the feature-end records the CLI appends and the `verdict_hash`
they carry. This is the audit SUBSTRATE the done-gate (`des verify-integrity`)
consumes, NOT the SUT (the same seed/read-back pattern the shipped
oss-hook-side-phase-injection slice-01 composition uses).

There are no test doubles: the git working tree and the AT-completion ledger
JSONL are real I/O -- a layer-3 `@real-io` surface (Mandate 9/11: example only,
no PBT machinery).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import (
    EmitOutcome,
    FeatureEndRecord,
    FeatureId,
    VerdictHash,
)


_FEATURE_ID = FeatureId("oss-feature-end-demo")

# A signed reviewer verdict hash -- the same lowercase-hex HMAC shape the
# per-slice ATReviewVerdict carries. The CLI binds this VALUE into the
# FeatureEndReviewVerdict record (hashed into record_hash); the test reads it
# back to assert the hash was bound (tamper-evident).
_SIGNED_VERDICT_HASH = VerdictHash("a" * 64)


@dataclass
class EmitResult:
    """The observable result of one `des emit-feature-end` invocation.

    Universe entries are port-exposed only (Mandate 8): the command outcome
    (success / refused, derived from the exit code) and the feature-end record
    set read back from the completion ledger -- never an internal CLI struct.
    """

    outcome: EmitOutcome
    exit_code: int


class EmitFeatureEndComposition:
    """Production-wired composition root for the `des emit-feature-end` slice.

    The driving port is the real `des emit-feature-end` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the feature-end records (with their `verdict_hash`) the CLI
    appends to the AT-completion ledger.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        # Env-parity (F21/RCA-#68): the `des emit-feature-end` subprocess runs
        # with cwd=project_root (the per-test tmp workspace). Mark it as a
        # developer checkout so the runtime-freshness gate AUTOSKIPS
        # (`des.runtime.freshness.autoskipped`, dev-checkout) instead of the
        # customer-install REFUSAL (exit 78) on the manifest-less tmp tree.
        # The gate stays ACTIVE -- a test fixture IS a synthetic dev workspace;
        # this is the honest fix shipped in 131a4e292, NOT a NWAVE_FRESHNESS=skip
        # mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._project_root)

    # --- driving-port invocation --------------------------------------------

    def emit_record(
        self,
        record: FeatureEndRecord,
        *,
        verdict_hash: VerdictHash | None = None,
    ) -> EmitResult:
        """Invoke the REAL `des emit-feature-end` subcommand over the dispatcher.

        Mirrors `des verify-slice-commit`'s `--repo`/`--feature-id` shape. One
        record per invocation; `--verdict-hash` is supplied only for the
        deep-review verdict, and its ABSENCE on a deep-review verdict is the
        anti-theater refusal path the CLI must reject.
        """
        argv = [
            "emit-feature-end",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(self._feature_id),
            "--record",
            record.value,
        ]
        if verdict_hash is not None:
            argv += ["--verdict-hash", str(verdict_hash)]
        return self._run_des(argv)

    def _run_des(self, argv: list[str]) -> EmitResult:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point."""
        exit_code, _stdout, _stderr = run_cli_in_process(argv, cwd=self._project_root)
        outcome = EmitOutcome.SUCCEEDED if exit_code == 0 else EmitOutcome.REFUSED
        return EmitResult(outcome=outcome, exit_code=exit_code)

    # --- observable read-back (ledger SUBSTRATE, NOT the SUT) ---------------

    def ledger_has_record(self, record: FeatureEndRecord) -> bool:
        """Whether the completion ledger carries a record of this feature-end kind.

        Read back through the production `AtCompletionLedger` reader under the
        M7 fail-closed integrity contract -- the done-gate's
        `feature_end_events()` reads the same set. A corrupt ledger raises here
        (never a silent miss); an absent ledger means no record was emitted.
        """
        return record.value in self._feature_end_events()

    def recorded_verdict_hash(self, record: FeatureEndRecord) -> str | None:
        """The signed `verdict_hash` bound into a recorded feature-end record.

        Returns the bound hash value when a record of this kind carries one, or
        None when no such record exists / it carries no hash. The
        FeatureEndReviewVerdict record MUST carry the signed hash (tamper-
        evident); the EBatchRefactorCompleted record carries none.
        """
        for entry in self._read_feature_end_records():
            if entry.get("event") == record.value and "verdict_hash" in entry:
                return str(entry["verdict_hash"])
        return None

    def _feature_end_events(self) -> frozenset[str]:
        return AtCompletionLedger(
            self._feature_id, self._project_root
        ).feature_end_events()

    def _read_feature_end_records(self) -> list[dict[str, object]]:
        ledger = AtCompletionLedger(self._feature_id, self._project_root)
        return [
            record
            for record in ledger.read_records()
            if record.get("event")
            in {
                FeatureEndRecord.BATCH_REFACTOR_COMPLETED.value,
                FeatureEndRecord.DEEP_REVIEW_VERDICT.value,
            }
        ]

    @property
    def signed_verdict_hash(self) -> VerdictHash:
        """The signed reviewer verdict hash the deep-review record binds."""
        return _SIGNED_VERDICT_HASH


__all__ = [
    "EmitFeatureEndComposition",
    "EmitResult",
]
