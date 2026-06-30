"""Composition root for f-finalize-verify-single-spine slice-01.

Single source of truth for the business logic the step bodies invoke. Steps
delegate here -- no inline logic in the .feature bindings (Mandate-12).

Driving surface (Mandate-13, Pillar 3): the PRODUCTION des verify-integrity
entry point. Two facets of the SAME CLI surface:

  * `run_on_installed_spine` -- the walking-skeleton terminal-wiring proof: a
    REAL subprocess against the shipped `des verify-integrity <dir>`
    console-script and a real git work-tree (the surviving single spine, end
    to end). The single shipped dispatcher entry is resolved hermetically from
    the running interpreter's environment.
  * `run_for_feature` / `run_with_no_target` -- the in-process facet
    (`main(argv)` under redirect_stdout, real FS on tmp_path) -- the inverted-
    Driving default.

Classic fixtures are built by writing roadmap.json + execution-log.json
DIRECTLY as plain JSON files -- no roadmap authoring CLI dependency. Feature-3
of this epic removes that authoring CLI, so the direct file writes let this
acceptance test survive the removal. The atdd_pure completion ledger is seeded
via the shared `seed_required_feature_end_records` helper + a real
`SliceCommitVerified` record reconciled by a matching `Slice-Id:` git commit.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from des.cli.verify_deliver_integrity import main as verify_integrity_main

from .domain_types import (
    ClassicProjectShape,
    FeatureId,
    IntegrityVerdict,
    WorkflowMode,
)


# The single synthetic feature id every fixture uses. The completion ledger,
# the `--feature-id` flag, and the seeded `{id}.jsonl` all key off it so the
# missing-ledger diagnostic names a deterministic feature.
DEMO_FEATURE_ID = FeatureId("finalize-spine-demo")

# TDD phases the default rigor profile records per step. A COMPLETE classic
# project logs all three for the step, which the classic cross-reference
# verifies as a complete DES trace (exit 0) -- the verdict the REDUCE removes.
_CLASSIC_TDD_PHASES = ("RED", "GREEN", "COMMIT")


@dataclass
class VerifyResult:
    """Observable outcome of one des verify-integrity invocation."""

    exit_code: int
    output: str

    @property
    def verdict(self) -> IntegrityVerdict:
        return {
            0: IntegrityVerdict.VERIFIED,
            1: IntegrityVerdict.VIOLATION,
            2: IntegrityVerdict.USAGE_ERROR,
            4: IntegrityVerdict.CANNOT_EVALUATE,
        }.get(self.exit_code, IntegrityVerdict.USAGE_ERROR)


@dataclass
class FinalizeSpineComposition:
    """Production-wired composition root over a tmp_path finalize directory."""

    project_dir: Path
    feature_id: FeatureId = DEMO_FEATURE_ID

    # --- paths ---------------------------------------------------------------

    @property
    def _nwave_dir(self) -> Path:
        return self.project_dir / ".nwave"

    @property
    def roadmap_path(self) -> Path:
        return self.project_dir / "roadmap.json"

    @property
    def execution_log_path(self) -> Path:
        return self.project_dir / "execution-log.json"

    @property
    def ledger_path(self) -> Path:
        return self._nwave_dir / "telemetry" / "atdd-pure" / f"{self.feature_id}.jsonl"

    # --- Given builders ------------------------------------------------------

    def create_project(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._nwave_dir.mkdir(parents=True, exist_ok=True)

    def set_workflow_mode(self, mode: WorkflowMode) -> None:
        """Record the finalize mode in .nwave/config.yaml.

        WorkflowMode.UNSET writes no key -- the absent-config state that
        `resolve_workflow_mode` already resolves to atdd_pure (DDD-7).
        """
        if mode is WorkflowMode.UNSET:
            return
        (self._nwave_dir / "config.yaml").write_text(
            yaml.safe_dump({"workflow": {"mode": mode.value}}, sort_keys=True),
            encoding="utf-8",
        )

    def provision_full_atdd_pure_feature(self) -> None:
        """Seed a completion ledger whose feature-end cycle fully ran + reconcile.

        The verifier's exit-0 contract demands: every required feature-end
        record present, a terminal `SliceCommitVerified` slice, and -- because
        a verified slice DEMANDS DDD-10 reconciliation -- a real git work-tree
        carrying the matching `Slice-Id:` commit (else `_shipped_slices`
        refuses LOUD with exit 4). This builds an honest reconciling delivery.
        """
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        self.set_workflow_mode(WorkflowMode.ATDD_PURE)
        ledger = AtCompletionLedger(self.feature_id, self.project_dir)
        ledger.append_gate_event(event="SliceCommitVerified", slice_id="slice-01")
        seed_required_feature_end_records(
            ledger, verdict_hash="finalize-single-spine-verdict-hash"
        )
        self._make_git_present_with_slice("slice-01")

    def provision_zero_shipped_atdd_pure_feature(self) -> None:
        """Seed a VALID completion ledger whose feature-end cycle ran but which
        ships NO slice -- the C3 cardinality-0 success path (ADR-027).

        Unlike `provision_full_atdd_pure_feature`, this seeds ONLY the required
        feature-end records: NO `SliceCommitVerified` slice and NO git work-tree
        with a `Slice-Id:` commit. So `verified_slices()` is empty and the
        done-gate's `shipped` set is `frozenset()` (the reconciliation demand is
        nothing, so git-absence is harmless and falls through). The verifier
        clears the feature-end cycle and emits the plain-text complete-trace
        verdict (exit 0) -- NOT the `FeatureReconciled` JSON of the non-empty
        path. This is the only fixture that drives the `shipped = frozenset()`
        leg through a fully VALID ledger.
        """
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        self.set_workflow_mode(WorkflowMode.ATDD_PURE)
        ledger = AtCompletionLedger(self.feature_id, self.project_dir)
        seed_required_feature_end_records(
            ledger, verdict_hash="finalize-single-spine-zero-shipped-verdict-hash"
        )

    def provision_classic_project(self, shape: ClassicProjectShape) -> None:
        """Build a classic (roadmap + execution-log) deliver project.

        COMPLETE_TRACES -- roadmap.json + an execution-log.json recording every
        TDD phase for the step. TODAY the classic cross-reference verifies this
        as a complete DES trace (exit 0); the REDUCE removes that branch.
        """
        step_id = self._write_valid_roadmap()
        phases = (
            _CLASSIC_TDD_PHASES
            if shape is ClassicProjectShape.COMPLETE_TRACES
            else _CLASSIC_TDD_PHASES[:-1]
        )
        log = {
            "schema_version": "3.0",
            "feature_id": str(self.feature_id),
            "events": [
                {"sid": step_id, "p": phase, "s": "EXECUTED", "d": "PASS"}
                for phase in phases
            ],
        }
        self.execution_log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    def _write_valid_roadmap(self) -> str:
        """Write a schema-valid roadmap.json directly as plain JSON.

        No roadmap authoring CLI dependency: feature-3 of this epic removes
        that CLI, so the fixture writes the roadmap document itself. The shape
        mirrors the roadmap skeleton schema (one phase, one step); the returned
        step id is the key the execution-log events reference.
        """
        step_id = "01-01"
        roadmap = {
            "roadmap": {
                "project_id": str(self.feature_id),
                "created_at": "2026-01-01T00:00:00Z",
                "total_steps": 1,
            },
            "phases": [
                {
                    "id": "01",
                    "name": "finalize-single-spine acceptance fixture",
                    "steps": [
                        {
                            "id": step_id,
                            "name": "finalize-single-spine acceptance fixture",
                            "criteria": [],
                            "test_file": "",
                            "scenario_name": "",
                        }
                    ],
                }
            ],
            "implementation_scope": {
                "source_directories": ["src/TODO/"],
                "test_directories": ["tests/TODO/"],
                "excluded_patterns": ["__init__.py", "__pycache__/**"],
            },
            "validation": {
                "status": "pending",
                "reviewer": "TODO",
                "approved_at": "TODO",
            },
        }
        self.roadmap_path.write_text(json.dumps(roadmap, indent=2), encoding="utf-8")
        return step_id

    def _make_git_present_with_slice(self, slice_id: str) -> None:
        """Real git work-tree whose history carries the matching Slice-Id trailer."""

        def run(*args: str) -> None:
            subprocess.run(
                ["git", *args],
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

    # --- When drivers --------------------------------------------------------

    def run_on_installed_spine(self) -> VerifyResult:
        """Walking skeleton: REAL `des verify-integrity` console-script.

        Resolves the single shipped `des` dispatcher entry point hermetically
        (see `_resolve_des_console_script`) and drives it as a real subprocess
        (cwd = the finalize directory) against a real git work-tree. Proves the
        surviving single spine runs end-to-end through the one shipped console
        entry point -- the terminal-wiring proof.
        """
        des_console_script = self._resolve_des_console_script()
        completed = subprocess.run(
            [
                des_console_script,
                "verify-integrity",
                str(self.project_dir),
                "--feature-id",
                str(self.feature_id),
            ],
            cwd=str(self.project_dir),
            capture_output=True,
            text=True,
            check=False,
        )
        return VerifyResult(
            exit_code=completed.returncode,
            output=completed.stdout + completed.stderr,
        )

    @staticmethod
    def _resolve_des_console_script() -> str:
        """Locate the production `des` dispatcher console-script hermetically.

        Prefer the entry installed alongside the running interpreter (the venv
        bin next to `sys.executable`), then a PATH lookup. This is the single
        shipped dispatcher entry point the slice-03 migration target names; the
        console-script resolves the package from its own environment, so no
        ad-hoc interpreter-path wiring is needed. Raises LOUD when the entry is
        unresolvable rather than silently falling back to a weaker driving
        surface.
        """
        venv_bin = Path(sys.executable).parent / "des"
        if venv_bin.exists():
            return str(venv_bin)
        on_path = shutil.which("des")
        if on_path is not None:
            return on_path
        raise RuntimeError(
            "the production `des` console-script is not resolvable in this "
            "environment; install the package (`uv sync`) so the single "
            "shipped dispatcher entry point is on the venv bin / PATH."
        )

    def run_for_feature(self) -> VerifyResult:
        """In-process: `main([project_dir, --feature-id <id>])` under capture."""
        return self._run_in_process(
            [str(self.project_dir), "--feature-id", str(self.feature_id)]
        )

    def run_with_no_target(self) -> VerifyResult:
        """In-process: `main([])` -- the structural usage error (exit 2)."""
        return self._run_in_process([])

    def _run_in_process(self, argv: list[str]) -> VerifyResult:
        buffer = io.StringIO()
        try:
            with (
                contextlib.redirect_stdout(buffer),
                contextlib.redirect_stderr(buffer),
            ):
                exit_code = verify_integrity_main(argv)
        except SystemExit as exc:  # argparse usage error -> exit 2
            code = exc.code
            exit_code = code if isinstance(code, int) else 2
        return VerifyResult(exit_code=exit_code, output=buffer.getvalue())

    # --- pure-read state-delta universe (Mandate 8) --------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot: des verify-integrity is pure-read.

        The verifier reads roadmap.json / execution-log.json / the ledger; it
        must create or delete none of them. The state-delta guard proves the
        gate reads without writing.
        """
        return {
            "roadmap.json.exists": self.roadmap_path.exists(),
            "execution_log.json.exists": self.execution_log_path.exists(),
            "ledger.exists": self.ledger_path.exists(),
        }
