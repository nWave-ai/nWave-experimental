"""Composition root + fixtures for the fix-readiness-gate-reuse-first-invariant ATs.

Driving port (Mandate-13, S2 driving-port-only): the public
`des verify-readiness-pre-dispatch` CLI subcommand (Layer 3 subprocess). The
composition NEVER imports `des.cli.verify_readiness_pre_dispatch` nor
`des.cli.validate_feature_delta` directly -- it invokes the real subprocess and
reads the public stdout-JSON + exit-code contract. The SUT is the CLI surface,
not the in-process Python module.

The composition arms a real tmp_path `repo_root` workspace whose feature-delta
SATISFIES the four pre-existing first-dispatch invariants (slice-plan heading,
@slice-NN scenario tags, gate-output-produceable `.nwave/`, pre-commit scope --
the AT-review ledger record invariant that used to sit here was DELETED,
fix-readiness-carpaccio-disagree: it duplicated carpaccio's own fail-closed
block). This isolates the NEW invariant (`reuse_first_or_design_skip`) as the
only variable: any refusal of an otherwise-complete workspace is attributable
to the reuse-first/design-skip dimension alone, and the AT cross-checks that
the four pre-existing verdicts are unchanged (additive aggregate, friction #57
single-invocation preserved).

Active-RED today: the gate ships five invariants only. A workspace with all five
satisfied + no Reuse Analysis + no witness currently CLEARS (exit 0); the
refuse-path ATs assert REFUSED + the 6th invariant FAILED -> they fail for the
right reason (the 6th invariant does not yet exist). DELIVER adds the invariant
and turns them GREEN.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.env_parity import seed_dev_checkout_marker

from .readiness_reuse_invariant_steps.domain_types import (
    DesignSkipWitness,
    FirstDispatchInvariantId,
    InvariantStatus,
    ReadinessVerdict,
    ReuseAnalysisShape,
)


# --- workspace-authoring building blocks (module-scope, NOT step bodies) -----

_DESIGN_SKIP_HEADING = "## Wave: DESIGN / [REF] Design Skipped"


def _five_invariant_satisfying_delta_prefix(feature_id: str) -> str:
    """The feature-delta body that satisfies the slice-plan invariant (inv 1).

    Carries the canonical `## Wave: DISCUSS / [REF] Slice Plan` heading + a
    table. The other four pre-existing invariants are satisfied by the
    surrounding workspace (feature file tags, ledger record, `.nwave/`,
    pre-commit scope) authored in `_arm_workspace`.
    """
    return (
        f"# Feature Delta: {feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        "| slice-01 | refuse path | pending | @walking-skeleton | thin |\n"
    )


def _reuse_analysis_block(shape: ReuseAnalysisShape) -> str:
    """Render the Reuse Analysis fragment for the requested shape.

    Each fragment drives a specific `validate_reuse_analysis_content` verdict
    (the SHIPPED parser the 6th invariant reuses), per the DESIGN verdict ->
    present/absent mapping table.
    """
    if shape is ReuseAnalysisShape.ABSENT:
        return ""
    if shape is ReuseAnalysisShape.METHODOLOGY_EXEMPT:
        return "## Reuse Analysis\n\nReuse-Analysis: methodology-exempt\n"
    if shape is ReuseAnalysisShape.NO_OVERLAP_DECLARED:
        # The exact DDD-9 marker `_REUSE_MARKER_NO_OVERLAP_RE` recognizes:
        # `^Reuse-Analysis:\s*no-overlap\s*$` -> verdict no-overlap-declared.
        return "## Reuse Analysis\n\nReuse-Analysis: no-overlap\n"
    if shape is ReuseAnalysisShape.VALID:
        return (
            "## Reuse Analysis\n\n"
            "| Existing Component | File | Overlap | Decision | Justification |\n"
            "|---|---|---|---|---|\n"
            "| Readiness gate | src/des/cli/verify_readiness_pre_dispatch.py | "
            "same aggregate | EXTEND | add one _check_* mirroring the five existing |\n"
        )
    if shape is ReuseAnalysisShape.MALFORMED:
        # Wrong column header -> validator verdict malformed-reuse-analysis.
        return (
            "## Reuse Analysis\n\n"
            "| Thing | Place | Decision | Why |\n"
            "|---|---|---|---|\n"
            "| Readiness gate | gate.py | EXTEND | reasons |\n"
        )
    # UNJUSTIFIED_CREATE_NEW: a CREATE_NEW row with an empty Justification.
    return (
        "## Reuse Analysis\n\n"
        "| Existing Component | File | Overlap | Decision | Justification |\n"
        "|---|---|---|---|---|\n"
        "| New thing | new.py | none | CREATE_NEW |  |\n"
    )


def _witness_block(witness: DesignSkipWitness) -> str:
    """Render the `## Wave: DESIGN / [REF] Design Skipped` witness fragment."""
    if witness is DesignSkipWitness.ABSENT:
        return ""
    if witness is DesignSkipWitness.EMPTY_RATIONALE:
        # Bare heading, no rationale body -> witness ABSENT (degrade-LOUD).
        return f"{_DESIGN_SKIP_HEADING}\n\n## Wave: DELIVER\n"
    # WITH_RATIONALE: heading + non-empty rationale body.
    return (
        f"{_DESIGN_SKIP_HEADING}\n\n"
        "DESIGN was deliberately skipped: this is a one-line config tweak with no "
        "architecture surface and no reuse overlap.\n"
    )


def _snapshot_workspace_tree(root: Path) -> dict[str, str]:
    """Deterministic byte-level snapshot of the bounded repo_root universe.

    Closed-world (Mandate-14 `contract-shape:unbounded-preservation`): the
    universe is the bounded `repo_root` tree the readiness gate operates on, NOT
    the whole filesystem. Two equal snapshots prove `verify()` was read-only.
    """
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=str):
        rel = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[rel] = "l:" + str(path.readlink())
        elif path.is_dir():
            snapshot[rel] = "d:"
        elif path.is_file():
            snapshot[rel] = "f:" + hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            snapshot[rel] = "?:" + str(path.stat().st_mode)
    return snapshot


@dataclass
class ReadinessReport:
    """Typed projection of the gate's exit-code + stdout-JSON contract."""

    verdict: ReadinessVerdict
    invariant_statuses: dict[FirstDispatchInvariantId, InvariantStatus]
    remediations: dict[FirstDispatchInvariantId, str]
    raw_stdout: str


def _parse_readiness_report(exit_code: int, stdout: str) -> ReadinessReport:
    """Translate the gate's exit-code + stdout JSON line into ReadinessReport.

    Module-scope (NOT a step body) per Mandate-12 criterion 3. Tolerant of an
    unrecognised 6th-invariant id (active-RED: the gate may not yet emit it) and
    of empty stdout (scaffold raises before stdout) -- the verdict still derives
    from exit_code, and an absent `reuse_first_or_design_skip` entry simply
    leaves the dict without that key, which the refuse-path AT asserts RED
    against.
    """
    verdict = ReadinessVerdict.CLEARED if exit_code == 0 else ReadinessVerdict.REFUSED
    statuses: dict[FirstDispatchInvariantId, InvariantStatus] = {}
    remediations: dict[FirstDispatchInvariantId, str] = {}
    line = next((ln for ln in stdout.splitlines() if ln.strip().startswith("{")), "")
    if line.strip():
        try:
            doc = json.loads(line.strip())
            for entry in doc.get("invariants", []):
                try:
                    inv_id = FirstDispatchInvariantId(entry["id"])
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
class ReadinessReuseComposition:
    """Production composition root for the reuse-first-invariant ATs.

    Owns the real tmp_path `repo_root` workspace, the workspace-authoring
    helpers (typed parameters per Mandate-12 criterion 2), and the single
    driving-port entry `verify()` invoking the gate via subprocess.
    """

    repo_root: Path
    feature_id: str = "f-reuse-probe"
    slice_id: str = "slice-01"
    _workspace_path: Path | None = None
    _last_report: ReadinessReport | None = None
    _pre_verify_snapshot: dict[str, str] | None = None
    _post_verify_snapshot: dict[str, str] | None = None

    # --- workspace authoring (driving-port input) -------------------------

    def _arm_workspace(self, delta_body: str) -> None:
        """Author a workspace satisfying the five pre-existing invariants.

        Writes `feature-delta.md` (caller supplies the body so the reuse/witness
        fragments vary), a `@slice-NN`-tagged feature file, the APPROVED
        AT-review ledger record, and relies on the fixture's `.nwave/` for
        gate-output-produceable + pre-commit scope. Isolates the 6th invariant
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

    def arm_feature_delta(
        self, reuse: ReuseAnalysisShape, witness: DesignSkipWitness
    ) -> None:
        """Arm a complete (five-invariant-satisfying) workspace whose reuse-first
        dimension is set by `reuse` + `witness`.

        The 6th invariant is the only variable; the body is the slice-plan
        prefix + the requested Reuse Analysis fragment + the requested witness
        fragment.
        """
        body = (
            _five_invariant_satisfying_delta_prefix(self.feature_id)
            + "\n"
            + _reuse_analysis_block(reuse)
            + "\n"
            + _witness_block(witness)
        )
        self._arm_workspace(body)

    def arm_unreadable_feature_delta(self) -> None:
        """Arm a workspace whose feature-delta is undecodable as UTF-8 text.

        Exercises the degrade-LOUD INDETERMINATE path: the 6th invariant must
        catch the read error and refuse with a diagnostic naming the unreadable
        source -- never silent-pass, never an unhandled crash.
        """
        workspace = self.repo_root / "docs" / "feature" / self.feature_id
        workspace.mkdir(parents=True)
        # Invalid UTF-8 bytes -> read_text(encoding="utf-8") raises.
        (workspace / "feature-delta.md").write_bytes(b"\xff\xfe\x00\x80 not utf8")
        feature_dir = self.repo_root / "tests" / "acceptance" / self.feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "happy.feature").write_text(
            f"Feature: probe\n\n  @{self.slice_id}\n  Scenario: x\n    Given y\n"
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

    # --- driving-port entry -----------------------------------------------

    def verify(self) -> ReadinessReport:
        """Invoke `des verify-readiness-pre-dispatch` via subprocess (Layer 3).

        Snapshots the bounded repo_root around the invocation (closed-world
        read-only oracle). Translates exit-code + stdout-JSON into the typed
        ReadinessReport. The SUT is the CLI subcommand surface.
        """
        self._pre_verify_snapshot = _snapshot_workspace_tree(self.repo_root)
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
        self._post_verify_snapshot = _snapshot_workspace_tree(self.repo_root)
        self._last_report = _parse_readiness_report(proc.returncode, proc.stdout)
        return self._last_report

    # --- public ReadinessReport-shape accessors ---------------------------

    def last_verdict(self) -> ReadinessVerdict:
        assert self._last_report is not None, "verify() must run first"
        return self._last_report.verdict

    def last_invariant_status(
        self, invariant: FirstDispatchInvariantId
    ) -> InvariantStatus | None:
        assert self._last_report is not None, "verify() must run first"
        return self._last_report.invariant_statuses.get(invariant)

    def pre_existing_invariants_unchanged(
        self, expected: dict[FirstDispatchInvariantId, InvariantStatus]
    ) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return all(
            self._last_report.invariant_statuses.get(inv) is status
            for inv, status in expected.items()
        )

    def last_remediation_contains(
        self, invariant: FirstDispatchInvariantId, token: str
    ) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return token in self._last_report.remediations.get(invariant, "")

    def stdout_mentions(self, token: str) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return token in self._last_report.raw_stdout

    def verify_was_filesystem_preserving(self) -> bool:
        assert self._post_verify_snapshot is not None, "verify() must run first"
        return self._pre_verify_snapshot == self._post_verify_snapshot


@pytest.fixture
def readiness_reuse_composition(tmp_path: Path) -> ReadinessReuseComposition:
    """Composition-root fixture -- tmp_path repo_root with `.nwave/` + dev marker.

    Marks the synthetic workspace as a developer checkout so the runtime
    freshness gate autoskips (env-parity, F21/RCA-#68) instead of fail-closed
    exit 78 on the manifest-less tmp tree.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".nwave").mkdir()
    seed_dev_checkout_marker(repo_root)
    return ReadinessReuseComposition(repo_root=repo_root)
