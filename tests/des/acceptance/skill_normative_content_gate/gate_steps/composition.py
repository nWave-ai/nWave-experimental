"""Composition root for skill-normative-content-gate ATs (the SSOT-via-Types mandate).

Single source of truth for ALL step-method business logic across slices 01-04
(Mandate-12 c2/c3: step bodies delegate here, ≤2 statements, no inline control
flow). Domain concepts arrive as typed `domain_types` enums, never raw strings.

Pillar 3 (App as in production): the SUT is driven through PRODUCTION driving
ports only —
  • CLI port (slices 01/02/03/04): a real subprocess through the real `des`
    dispatcher: `python -m des.cli.__main__ skill-normative-gate ...`. Driving
    through the dispatcher (NOT `python -m des.cli.skill_normative_gate`) is what
    forces the `_SubcommandRow` registration to exist (M-1, DESIGN §9 — the
    dormant-seam guard). Until DELIVER registers it, the dispatcher exits
    non-zero with an argparse "invalid choice" error — still RED, still through
    the real seam.
  • hook port (slice-03): a real subprocess of the real
    `des.adapters.drivers.hooks.pre_write_handler:handle_pre_write` with a real
    JSON hook payload on stdin (`tool_input.file_path` under `nWave/skills/**`),
    asserting the `{decision:block}` body + exit code.

Driving-Port-Only Boundary (the Driving-Port-Only Boundary mandate, SSOT
`nw-test-design-mandates`; S2 gate): NO step imports a production domain /
application module and invokes it at the function boundary. The only production
symbols imported here are exit-code/error CONTRACTS (`Verdict`/`EXIT_BY_VERDICT`
live in test domain_types; the reader's typed errors are referenced only by name
in fault-injection fixtures, never invoked as the SUT). Every behavioural
assertion observes a subprocess artifact (exit code, stdout, decision body).

Dormant-Seam Reconciliation (D11 / S3): the net-new DESIGN-declared seams are
(a) the `des skill-normative-gate` subcommand row and (b) the `pre_write`
skill-edit intercept. Each is named here verbatim, driven through its REAL entry
point (the dispatcher / the hook handler subprocess), and asserts an observable
effect (exit code + stdout / decision block). The slice-01 CLI AT witnesses (a);
the slice-03 hook AT witnesses (b).

Mandate 9 v2 (mock-status OR-reduction): every driven surface here is REAL I/O
(real subprocess, real filesystem, real shipped skill files) → @real-io →
example-based; PBT machinery is intentionally NOT imported (Mandate 11: layer-3
sad paths are explicit named examples).

Mandate 8: the gate is a READ that emits a verdict; the only observable
mutations are the subprocess outcome fields (exit_code, verdict, stdout). Those
form the port-exposed universe asserted via `assert_state_delta` in the step
modules — never Popen handles, never internal service fields.

DISTILL active-RED (ADR-025 / ADR-GV-001 D6): the production modules are
scaffolds that import cleanly and raise a semantic AssertionError on call
(Mandate 7 RED-not-BROKEN). Every scenario RUNS and FAILS today (non-zero exit
with the scaffold message); none is @skip. DELIVER makes them GREEN — it does
NOT unskip.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process

from des.adapters.drivers.hooks.pre_write_handler import handle_pre_write

from .domain_types import (
    EXIT_BY_VERDICT,
    MARKER_BY_CLAUSE,
    SKILL_BY_CLAUSE,
    AssetFault,
    ClauseId,
    MarkerShape,
    ProtectedSkill,
    Verdict,
)


# tests/des/acceptance/skill_normative_content_gate/gate_steps/composition.py
#   parents[0]=gate_steps [1]=skill_normative_content_gate [2]=acceptance
#   [3]=des [4]=tests [5]=nWave-dev
REPO_ROOT = Path(__file__).resolve().parents[5]
SHIPPED_SKILLS_DIR = REPO_ROOT / "nWave" / "skills"
REAL_MANIFEST_PATH = REPO_ROOT / "nWave" / "data" / "skill-normative-clauses.json"

# The fault-injection env var the pre_write hook honours (AC-07); set in-process
# around the hook call (mirrors the subprocess `env=` the migration replaced).
_SKILL_GATE_FAULT_ENV = "NWAVE_SKILL_GATE_INJECT_FAULT"


def _skill_asset(skill: ProtectedSkill) -> Path:
    """Resolve a protected skill to its real shipped SKILL.md path."""
    return SHIPPED_SKILLS_DIR / skill.value / "SKILL.md"


@dataclass(frozen=True)
class GateOutcome:
    """Port-exposed observation of one gate subprocess invocation (Mandate 8 universe)."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class HookOutcome:
    """Port-exposed observation of one pre_write hook subprocess invocation."""

    exit_code: int
    decision: str | None
    reason: str
    stdout: str


class SkillNormativeGateComposition:
    """SSOT for every slice's step business logic; drives only production ports."""

    def __init__(self, tmp_path: Path) -> None:
        self._tmp = tmp_path
        self._manifest_path: Path = REAL_MANIFEST_PATH
        self._mutated_skill_dir = tmp_path / "skills"
        self._outcome: GateOutcome | None = None
        self._hook: HookOutcome | None = None

    # --- Real-surface preconditions (AC-08) ------------------------------

    def require_real_skill_present(self, clause: ClauseId) -> None:
        """Pin: the real shipped skill file for this clause exists with the marker."""
        asset = _skill_asset(SKILL_BY_CLAUSE[clause])
        text = asset.read_text(encoding="utf-8")
        assert MARKER_BY_CLAUSE[clause] in " ".join(text.split()), (
            f"real-surface precondition broken: marker for {clause.value} "
            f"absent from shipped {asset} — AC-08 binds to the real file"
        )

    def require_real_manifest_present(self) -> None:
        """Pin: the real shipped manifest exists (the gate's real SSOT input)."""
        assert REAL_MANIFEST_PATH.is_file(), (
            f"real manifest missing at {REAL_MANIFEST_PATH} — DELIVER must ship "
            "it; the slice-01 walking skeleton binds to the real manifest"
        )

    # --- Manifest authoring (tmp_path-scoped fixtures, real JSON) ---------

    def author_single_clause_manifest(self, clause: ClauseId) -> None:
        """Author a one-clause manifest pointing at the REAL shipped skill file."""
        self._manifest_path = self._write_manifest([self._clause_entry(clause)])

    def author_manifest_with_deleted_clause(self, clause: ClauseId) -> None:
        """Author a manifest whose marker is ABSENT from a real-text copy on disk."""
        self._manifest_path = self._write_manifest(
            [self._clause_entry(clause, root=self._mutated_skill_dir)]
        )
        self._copy_skill_without_marker(clause)

    def author_zero_clause_manifest(self) -> None:
        """AC-03 ZERO: a manifest registering NO clauses — the explicit empty case."""
        self._manifest_path = self._write_manifest([])

    def author_one_and_many_clause_manifest(self) -> None:
        """AC-03 one+N: one clause for nw-distill, many for at-completeness-check.

        nw-at-completeness-check carries two real markers below (zero-obligation
        plus protocol-driver re-anchored on its own real surface would not hold);
        we register the one real clause it owns AND the protocol-driver clause on
        its own skill, giving a genuine one-skill + many-corpus check.
        """
        entries = [
            self._clause_entry(ClauseId.WALKING_SKELETON),  # one (nw-distill)
            self._clause_entry(ClauseId.ZERO_OBLIGATION),  # many corpus
            self._clause_entry(ClauseId.PROTOCOL_DRIVER),  # many corpus
        ]
        self._manifest_path = self._write_manifest(entries)

    def author_marker_shape_manifest(self, shape: MarkerShape) -> None:
        """Author a one-clause manifest whose marker is a discrimination edge case.

        For the BARE_COMMON_TOKEN shape the marker is rejected at load (before any
        asset read), so it points at the real Mandate-13 skill harmlessly. For the
        SHORT_MULTI_WORD shape (AC-09) the marker is authored into a tmp skill file
        that genuinely contains it, so "loads without a discrimination error AND is
        enforceable" is observable as a PASS — the discrimination boundary, not a
        clause-absent FAIL.
        """
        if shape is MarkerShape.SHORT_MULTI_WORD:
            asset = self._authored_skill_with_text(
                "nw-probe", f"A canonical rule: {shape.value} in practice.\n"
            )
            entry = {
                "skill": "nw-probe",
                "clause_id": "discrimination:short-phrase",
                "marker": shape.value,
                "asset": str(asset),
            }
        else:
            entry = {
                "skill": ProtectedSkill.TEST_DESIGN_MANDATES.value,
                "clause_id": "discrimination:probe",
                "marker": shape.value,
            }
        self._manifest_path = self._write_manifest([entry])

    def _authored_skill_with_text(self, skill: str, body: str) -> Path:
        dest = self._mutated_skill_dir / skill / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(body, encoding="utf-8")
        return dest

    def author_manifest_with_faulted_asset(self, fault: AssetFault) -> None:
        """Author a manifest referencing an absent / undecodable asset (AC-06/AC-10)."""
        asset_rel = self._faulted_asset(fault)
        self._manifest_path = self._write_manifest(
            [
                {
                    "skill": "nw-faulted",
                    "clause_id": "asset-fault:probe",
                    "marker": MARKER_BY_CLAUSE[ClauseId.WALKING_SKELETON],
                    "asset": asset_rel,
                }
            ]
        )

    # --- When: drive the production ports (real subprocess) --------------

    def run_gate_via_dispatcher(self) -> None:
        """Drive `des skill-normative-gate` THROUGH the real dispatcher (M-1)."""
        self._outcome = self._spawn_dispatcher(self._manifest_path)

    def edit_skill_via_pre_write_hook(self, clause: ClauseId) -> None:
        """Drive the real pre_write hook on a Write to a `nWave/skills/**` path."""
        self._hook = self._spawn_pre_write(_skill_asset(SKILL_BY_CLAUSE[clause]))

    def inject_intercept_fault_via_pre_write_hook(self, clause: ClauseId) -> None:
        """Drive pre_write with the gate-subprocess spawn forced to raise (H-1)."""
        self._hook = self._spawn_pre_write(
            _skill_asset(SKILL_BY_CLAUSE[clause]), inject_fault=True
        )

    # --- Then: observe port-exposed effects ------------------------------

    @property
    def outcome(self) -> GateOutcome:
        assert self._outcome is not None, "no gate invocation was driven"
        return self._outcome

    @property
    def hook(self) -> HookOutcome:
        assert self._hook is not None, "no pre_write hook invocation was driven"
        return self._hook

    def expected_exit(self, verdict: Verdict) -> int:
        return EXIT_BY_VERDICT[verdict]

    def expected_exit_pass(self) -> int:
        return EXIT_BY_VERDICT[Verdict.PASS]

    # --- Internal: production-port drivers (the only I/O) ----------------

    def _spawn_dispatcher(self, manifest: Path) -> GateOutcome:
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "skill-normative-gate",
                "--manifest",
                str(manifest),
                "--root",
                str(REPO_ROOT),
            ],
            cwd=REPO_ROOT,
        )
        return GateOutcome(exit_code=exit_code, stdout=stdout, stderr=stderr)

    def _spawn_pre_write(
        self, file_path: Path, inject_fault: bool = False
    ) -> HookOutcome:
        payload = json.dumps(
            {"tool_name": "Write", "tool_input": {"file_path": str(file_path)}}
        )
        env_marker = "1" if inject_fault else "0"
        # Set the fault-injection env the subprocess passed via `env=` in-process,
        # save/restore in finally so the shared test process is never left mutated.
        prior = os.environ.get(_SKILL_GATE_FAULT_ENV)
        os.environ[_SKILL_GATE_FAULT_ENV] = env_marker
        try:
            exit_code, stdout, _stderr = run_hook_in_process(
                handle_pre_write,
                stdin_text=payload,
                cwd=REPO_ROOT,
            )
        finally:
            if prior is None:
                os.environ.pop(_SKILL_GATE_FAULT_ENV, None)
            else:
                os.environ[_SKILL_GATE_FAULT_ENV] = prior
        return HookOutcome(
            exit_code=exit_code,
            decision=self._decision_of(stdout),
            reason=self._reason_of(stdout),
            stdout=stdout,
        )

    # --- Internal helpers (pure / fixture authoring) ---------------------

    def _clause_entry(self, clause: ClauseId, root: Path | None = None) -> dict:
        entry = {
            "skill": SKILL_BY_CLAUSE[clause].value,
            "clause_id": clause.value,
            "marker": MARKER_BY_CLAUSE[clause],
        }
        if root is not None:
            entry["asset"] = str(root / SKILL_BY_CLAUSE[clause].value / "SKILL.md")
        return entry

    def _write_manifest(self, clauses: list[dict]) -> Path:
        path = self._tmp / "skill-normative-clauses.json"
        path.write_text(
            json.dumps({"schema_version": 1, "clauses": clauses}, indent=2),
            encoding="utf-8",
        )
        return path

    def _copy_skill_without_marker(self, clause: ClauseId) -> None:
        src = _skill_asset(SKILL_BY_CLAUSE[clause])
        text = src.read_text(encoding="utf-8")
        stripped = text.replace(MARKER_BY_CLAUSE[clause], "[[clause removed]]")
        dest = self._mutated_skill_dir / SKILL_BY_CLAUSE[clause].value / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(stripped, encoding="utf-8")

    def _faulted_asset(self, fault: AssetFault) -> str:
        if fault is AssetFault.ABSENT:
            return str(self._tmp / "nw-faulted" / "SKILL.md")
        dest = self._tmp / "nw-faulted" / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
        return str(dest)

    @staticmethod
    def _decision_of(stdout: str) -> str | None:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line).get("decision")
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _reason_of(stdout: str) -> str:
        for line in stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return str(json.loads(line).get("reason", ""))
                except json.JSONDecodeError:
                    continue
        return ""
