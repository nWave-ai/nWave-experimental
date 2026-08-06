"""Composition root for the des-verify-integrity mode-aware acceptance slice.

ADR-028 D4.2 / slice-02 (Mandate-12, Pillar 3). Wires the PRODUCTION
des-verify-integrity CLI entry point (`des.cli.verify_deliver_integrity.main`)
against a tmp_path deliver project. Business logic lives here as the single
source of truth; step bodies delegate to `VerifyIntegrityComposition` methods
and never inline logic.

Layer 2 (component: driving port invoked in-process via main(argv) under
redirect_stdout, real FS on tmp_path). No PBT machinery (Mandate 9/11).

Mode resolution: slice-02 reads `workflow.mode` from
`{project_dir}/.nwave/config.yaml`, the SAME path slice-01's des-init-log uses
(`init_log._resolve_workflow_mode`). The composition writes that file so the
ATs exercise the production resolver, not a test re-implementation.

The suite deliberately provisions only ATDD-pure artifacts.
"""

from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from des.cli.verify_deliver_integrity import main as verify_integrity_main

from .domain_types import (
    FeatureId,
    IntegrityVerdict,
    LedgerState,
    WorkflowMode,
)


@dataclass
class VerifyIntegrityResult:
    """Observable outcome of one des-verify-integrity invocation."""

    exit_code: int
    output: str

    @property
    def verdict(self) -> IntegrityVerdict:
        """Map the CLI exit code onto the user-observable verdict."""
        return {
            0: IntegrityVerdict.VERIFIED,
            1: IntegrityVerdict.VIOLATION,
            2: IntegrityVerdict.USAGE_ERROR,
        }.get(self.exit_code, IntegrityVerdict.USAGE_ERROR)


@dataclass
class VerifyIntegrityComposition:
    """Production-wired composition root for the des-verify-integrity slice.

    `project_dir` is a real tmp_path directory acting as the deliver project.
    The `.nwave/config.yaml` workflow mode and the AT-completion ledger are
    provisioned through dedicated methods so each scenario builds only the
    ATDD-pure project state it needs.
    """

    project_dir: Path
    feature_id: FeatureId = field(default=FeatureId("unset"))

    @property
    def _nwave_dir(self) -> Path:
        return self.project_dir / ".nwave"

    @property
    def ledger_path(self) -> Path:
        """AT-completion ledger for this feature (ADR-028 D3).

        `.nwave/telemetry/atdd-pure/{feature_id}.jsonl` -- the atdd_pure audit
        artifact that replaces per-step execution-log.json.
        """
        return self._nwave_dir / "telemetry" / "atdd-pure" / f"{self.feature_id}.jsonl"

    def create_project(self, feature_id: FeatureId) -> None:
        """Create the deliver project directory for `feature_id`."""
        self.feature_id = feature_id
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._nwave_dir.mkdir(parents=True, exist_ok=True)

    def set_workflow_mode(self, mode: WorkflowMode) -> None:
        """Record the project workflow mode in .nwave/config.yaml.

        WorkflowMode.UNSET writes no `workflow.mode` key -- the default
        (config-without-mode) state des-verify-integrity must treat as atdd_pure.
        """
        if mode is WorkflowMode.UNSET:
            return
        config_path = self._nwave_dir / "config.yaml"
        config_path.write_text(
            yaml.safe_dump({"workflow": {"mode": mode.value}}, sort_keys=True),
            encoding="utf-8",
        )

    def provision_ledger(self, state: LedgerState) -> None:
        """Provision the AT-completion ledger in the requested state.

        PRESENT_ALL_SHIPPED -- write a genuine M7 integrity-checked ledger via
                               `AtCompletionLedger`: every slice carries a
                               terminal `SliceCommitVerified` record AND the
                               feature-end cycle recorded its `EBatchRefactor
                               Completed` + `FeatureEndReviewVerdict` records
                               (Finding 1: a "complete" ledger is one whose
                               feature-end cycle ran, not merely a present file).
        ABSENT              -- write nothing; the ledger file does not exist.
        """
        if state is LedgerState.ABSENT:
            return
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        ledger = AtCompletionLedger(self.feature_id, self.project_dir)
        ledger.append_gate_event(event="SliceCommitVerified", slice_id="slice-01")
        # The 6 U4-required feature-end records are seeded structurally via
        # the shared helper -- a single registry-driven seed keeps every
        # frozenset extension a one-line change (helper + production) instead
        # of a 6-fixture cascade.
        seed_required_feature_end_records(
            ledger,
            verdict_hash="verify-integrity-mode-aware-verdict-hash",
        )
        # The verified slice DEMANDS DDD-10 reconciliation. Make the deliver
        # project a real git work-tree carrying the matching `Slice-Id: slice-01`
        # commit so reconciliation reads `shipped == verified` and clears
        # git-present. gate-trailer-read-git-port-extract slice-01 flipped
        # `_shipped_slices` from a silent `return frozenset()` on git-absence to
        # a LOUD cannot-evaluate refusal (exit 4); a verified-but-non-git tmp
        # tree would now refuse before the verified verdict (intent here =
        # mode-resolution, NOT git-absence). Making the
        # fixture an honest git-present reconciling delivery preserves the
        # verified (exit 0) verdict these scenarios assert.
        self._make_git_present_with_slice("slice-01")

    def _make_git_present_with_slice(self, slice_id: str) -> None:
        """Real git work-tree whose history carries the matching Slice-Id trailer."""
        import subprocess

        run = lambda *a: subprocess.run(  # noqa: E731 -- terse local git driver
            ["git", *a],
            cwd=self.project_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        run("init", "-q")
        run("config", "user.email", "t@t.com")
        run("config", "user.name", "T")
        (self.project_dir / "README.md").write_text(
            f"reconciling delivery for {slice_id}\n", encoding="utf-8"
        )
        run("add", "-A")
        run("commit", "-q", "-m", f"ship {slice_id}\n\nSlice-Id: {slice_id}")

    def run_verify_integrity(self) -> VerifyIntegrityResult:
        """Invoke the production des-verify-integrity CLI via its argv entry point.

        The verifier carries exactly one ATDD-pure spine.
        """
        argv = [str(self.project_dir)]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = verify_integrity_main(argv)
        return VerifyIntegrityResult(exit_code=exit_code, output=buffer.getvalue())

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        des-verify-integrity has a pure-read contract: it MUST NOT mutate the
        deliver project. The universe is the project artifact whose
        existence the verifier could be tempted to touch -- the state-delta
        guard proves the verifier reads without writing.
        """
        return {
            "ledger.exists": self.ledger_path.exists(),
        }
