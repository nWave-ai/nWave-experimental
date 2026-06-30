"""Composition root + fixtures for the readiness SUSTAINABILITY-invariant ATs.

Driving port (Mandate-13, S2 driving-port-only): the public
`des verify-readiness-pre-dispatch` CLI subcommand (Layer 3 subprocess). The
composition NEVER imports `des.cli.verify_readiness_pre_dispatch` nor
`des.cli.validate_feature_delta` directly -- it invokes the real subprocess and
reads the public stdout-JSON + exit-code contract. The SUT is the CLI surface,
not the in-process Python module.

The composition arms a real tmp_path `repo_root` workspace whose feature-delta
SATISFIES the SIX pre-existing readiness invariants (slice-plan heading,
@slice-NN scenario tags, AT-review ledger record, gate-output-produceable
`.nwave/`, pre-commit scope, AND a valid Reuse Analysis for invariant 6). This
isolates the NEW 7th invariant (`sustainability`) as the only variable: any
refusal of an otherwise-complete workspace is attributable to the sustainability
dimension alone.

Active-RED today: the gate ships SIX invariants only. A workspace with all six
satisfied + a DECLARED-BUT-MISSING/malformed sustainability section currently
CLEARS (exit 0) -- the readiness gate does NOT yet check sustainability. The
must-block AT asserts REFUSED + the 7th invariant FAILED -> it fails for the
right reason (the 7th invariant does not yet exist). DELIVER adds the invariant
(calling `validate_sustainability_content`) and turns it GREEN.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.env_parity import seed_dev_checkout_marker

from .readiness_sustainability_invariant_steps.domain_types import (
    InvariantStatus,
    ReadinessInvariantId,
    ReadinessVerdict,
    SustainabilitySectionShape,
)


# --- workspace-authoring building blocks (module-scope, NOT step bodies) -----


def _six_invariant_satisfying_delta_prefix(feature_id: str) -> str:
    """The feature-delta body that satisfies invariants 1 (slice-plan) and 6
    (reuse-first).

    Carries the canonical `## Wave: DISCUSS / [REF] Slice Plan` heading + table
    (invariant 1) and a well-formed `## Reuse Analysis` table (invariant 6). The
    other four pre-existing invariants are satisfied by the surrounding workspace
    (feature file tags, ledger record, `.nwave/`, pre-commit scope) authored in
    `_arm_workspace`. The ONLY variable left is the sustainability section.
    """
    return (
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | wire the sustainability invariant | pending |"
        " @walking-skeleton | thin |\n\n"
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| Readiness gate | src/des/cli/verify_readiness_pre_dispatch.py | "
        "same aggregate | EXTEND | add one _check_* mirroring the six existing |\n"
    )


def _sustainability_block(shape: SustainabilitySectionShape) -> str:
    """Render the `## Test Reuse & Consolidation Analysis` fragment for `shape`.

    Each fragment drives a specific `validate_sustainability_content` verdict
    (the slice-03 pure-core function the 7th invariant reuses), per the
    verdict -> satisfied/failed mapping the wiring mirrors from invariant 6.
    """
    if shape is SustainabilitySectionShape.ABSENT:
        return ""
    if shape is SustainabilitySectionShape.METHODOLOGY_EXEMPT:
        return (
            "## Test Reuse & Consolidation Analysis\n\n"
            "Test-Reuse-Analysis: methodology-exempt\n"
        )
    if shape is SustainabilitySectionShape.WELL_FORMED:
        return (
            "## Test Reuse & Consolidation Analysis\n\n"
            "| Existing Test/DSL-Step | File | Overlap | Decision | Justification |\n"
            "|---|---|---|---|---|\n"
            "| readiness invariant ATs | tests/des/acceptance/"
            "readiness_sustainability_invariant/ | mirror of reuse package | "
            "REUSE | the sustainability ATs reuse the reuse-invariant shape |\n"
        )
    # MALFORMED: wrong column header -> validator malformed-sustainability-section.
    return (
        "## Test Reuse & Consolidation Analysis\n\n"
        "| Thing | Place | Decision | Why |\n"
        "|---|---|---|---|\n"
        "| readiness ATs | gate.py | REUSE | reasons |\n"
    )


@dataclass
class ReadinessReport:
    """Typed projection of the gate's exit-code + stdout-JSON contract."""

    verdict: ReadinessVerdict
    invariant_statuses: dict[ReadinessInvariantId, InvariantStatus]
    remediations: dict[ReadinessInvariantId, str]
    raw_stdout: str


def _parse_readiness_report(exit_code: int, stdout: str) -> ReadinessReport:
    """Translate the gate's exit-code + stdout JSON line into ReadinessReport.

    Module-scope (NOT a step body) per Mandate-12 criterion 3. Tolerant of an
    unrecognised 7th-invariant id (active-RED: the gate does not yet emit
    `sustainability`) and of empty stdout -- the verdict still derives from
    exit_code, and an absent `sustainability` entry simply leaves the dict
    without that key, which the must-block AT asserts RED against.
    """
    verdict = ReadinessVerdict.CLEARED if exit_code == 0 else ReadinessVerdict.REFUSED
    statuses: dict[ReadinessInvariantId, InvariantStatus] = {}
    remediations: dict[ReadinessInvariantId, str] = {}
    line = next((ln for ln in stdout.splitlines() if ln.strip().startswith("{")), "")
    if line.strip():
        try:
            doc = json.loads(line.strip())
            for entry in doc.get("invariants", []):
                try:
                    inv_id = ReadinessInvariantId(entry["id"])
                except ValueError:
                    continue
                statuses[inv_id] = InvariantStatus(entry["status"])
                if entry.get("remediation"):
                    remediations[inv_id] = entry["remediation"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return ReadinessReport(
        verdict=verdict,
        invariant_statuses=statuses,
        remediations=remediations,
        raw_stdout=stdout,
    )


@dataclass
class ReadinessSustainabilityComposition:
    """Production composition root for the sustainability-invariant ATs.

    Owns the real tmp_path `repo_root` workspace, the workspace-authoring helpers
    (typed parameters per Mandate-12 criterion 2), and the single driving-port
    entry `verify()` invoking the readiness gate via subprocess.
    """

    repo_root: Path
    feature_id: str = "f-sustain-probe"
    slice_id: str = "slice-01"
    _workspace_path: Path | None = None
    _last_report: ReadinessReport | None = None

    # --- workspace authoring (driving-port input) -------------------------

    def _arm_workspace(self, delta_body: str) -> None:
        """Author a workspace satisfying the six pre-existing invariants.

        Writes `feature-delta.md` (caller supplies the body so the sustainability
        fragment varies), a `@slice-NN`-tagged feature file, the APPROVED
        AT-review ledger record, and relies on the fixture's `.nwave/` for
        gate-output-produceable + pre-commit scope. Isolates the 7th invariant
        as the only variable.
        """
        workspace = self.repo_root / "docs" / "feature" / self.feature_id
        workspace.mkdir(parents=True)
        (workspace / "feature-delta.md").write_text(delta_body)
        feature_dir = self.repo_root / "tests" / "acceptance" / self.feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "happy.feature").write_text(
            "Feature: probe\n\n"
            f"  @{self.slice_id}\n"
            "  Scenario: every pre-existing invariant clears\n"
            "    Given a satisfied workspace\n"
            "    Then dispatch clears\n"
        )
        ledger_dir = self.repo_root / ".nwave" / "telemetry" / "atdd-pure"
        ledger_dir.mkdir(parents=True)
        (ledger_dir / f"{self.feature_id}.jsonl").write_text(
            json.dumps(
                {
                    "event": "ATReviewVerdict",
                    "feature_id": self.feature_id,
                    "slice_id": self.slice_id,
                    "verdict": "APPROVED",
                    "schema_version": "1.0.0",
                }
            )
            + "\n"
        )
        self._workspace_path = workspace

    def arm_feature_delta(self, sustainability: SustainabilitySectionShape) -> None:
        """Arm a complete (six-invariant-satisfying) workspace whose
        sustainability dimension is set by `sustainability`.

        The 7th invariant is the only variable; the body is the six-satisfying
        prefix (slice-plan + reuse analysis) + the requested sustainability
        fragment.
        """
        body = (
            _six_invariant_satisfying_delta_prefix(self.feature_id)
            + "\n"
            + _sustainability_block(sustainability)
        )
        self._arm_workspace(body)

    # --- driving-port entry -----------------------------------------------

    def verify(self) -> ReadinessReport:
        """Invoke `des verify-readiness-pre-dispatch` via subprocess (Layer 3).

        Translates exit-code + stdout-JSON into the typed ReadinessReport. The
        SUT is the CLI subcommand surface.
        """
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "des",
                "verify-readiness-pre-dispatch",
                "--feature-id",
                self.feature_id,
                "--slice-id",
                self.slice_id,
                "--repo-root",
                str(self.repo_root),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.repo_root),
        )
        self._last_report = _parse_readiness_report(proc.returncode, proc.stdout)
        return self._last_report

    # --- public ReadinessReport-shape accessors ---------------------------

    def last_verdict(self) -> ReadinessVerdict:
        assert self._last_report is not None, "verify() must run first"
        return self._last_report.verdict

    def last_invariant_status(
        self, invariant: ReadinessInvariantId
    ) -> InvariantStatus | None:
        assert self._last_report is not None, "verify() must run first"
        return self._last_report.invariant_statuses.get(invariant)

    def sustainability_invariant_among_failures(self) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return (
            self._last_report.invariant_statuses.get(
                ReadinessInvariantId.SUSTAINABILITY
            )
            is InvariantStatus.FAILED
        )

    def last_remediation_contains(
        self, invariant: ReadinessInvariantId, token: str
    ) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return token in self._last_report.remediations.get(invariant, "")


@pytest.fixture
def readiness_sustainability_composition(
    tmp_path: Path,
) -> ReadinessSustainabilityComposition:
    """Composition-root fixture -- tmp_path repo_root with `.nwave/` + dev marker.

    Marks the synthetic workspace as a developer checkout so the runtime
    freshness gate autoskips (env-parity, F21/RCA-#68) instead of fail-closed
    exit 78 on the manifest-less tmp tree.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".nwave").mkdir()
    seed_dev_checkout_marker(repo_root)
    return ReadinessSustainabilityComposition(repo_root=repo_root)
