"""Conftest for D4 Phase 3 slice-01 + slice-02 flavor-dispatcher acceptance tests.

Two composition roots — one per slice — share the package's conftest because
both slices live under the same feature directory and reuse the
`dispatcher_steps/` package (per friction #56 standing: feature-specific
package naming preserves S1 step-text uniqueness invariant across the
acceptance suite).

slice-01 — `FlavorDispatcherComposition` (Pillar-3 "app as in production"):
  * The on-disk flavor file fixture (`tmp_path/flavors/<flavor_id>.yaml`)
    composed from typed `domain_types.OnFailurePolicy` parameters — Mandate-12
    criterion 2 (composition consumes typed parameters, never raw `str`
    where an enum exists).
  * The `FakeGateInvoker` Port double — driven external/non-deterministic per
    the Architecture of Reference + the project Infrastructure Policy default.
    Records each invocation for `Then` assertions.
  * The dispatch entry point — `composition.dispatch(event, flavor)` is the
    single driving-port method step bodies invoke (Mandate-12 criterion 3:
    step bodies <=2 statements ending in `composition.<method>(...)`).

slice-02 — `CarpaccioInterceptComposition` (Pillar-3 "app as in production"):
  * The dispatch-prompt fixture (in-memory string with M3 markers per
    `des.domain.des_marker_parser`'s public format) authored via typed
    helper methods (Mandate-12 criterion 2 — `author_valid_atdd_pure_prompt`,
    `author_defective_atdd_pure_prompt_missing_slice`,
    `author_non_atdd_pure_prompt`).
  * A controllable carpaccio-runner stub — driven external /
    non-deterministic per the Architecture of Reference — substituted via
    the `carpaccio_runner` parameter of `evaluate_atdd_pure_dispatch`.
  * The single driving-port entry — `composition.evaluate()` invokes
    `evaluate_atdd_pure_dispatch(...)` and stores the returned
    `InterceptDecision` for `Then` observation. Step bodies read decision
    shape via three typed-accessor methods (`last_verdict()`,
    `last_is_atdd_pure()`, `last_block_event()`,
    `last_block_reason_mentions()`).

Mandate-13 (S2 driving-port-only) attestation — slice-01:
`dispatch_lifecycle_event` is THE driving-port entry function for the
flavor dispatcher SUT (Layer 3 composition root, analogous to
`PreToolUseService(...).evaluate(...)`). The M15 anti-pattern (importing
`DesMarkerParser` — an internal domain helper — and invoking `.parse()`
to test it directly) does NOT apply: the imported callable IS the public
entry point for the slice.

Mandate-13 (S2 driving-port-only) attestation — slice-02:
`evaluate_atdd_pure_dispatch` is THE driving-port entry function for the
carpaccio intercept SUT (Layer 3 composition root, same surface
`PreToolUseService(...).evaluate(...)` delegates to via
`intercept_atdd_pure_dispatch`). `InterceptDecision` is its public return
contract (a frozen dataclass exposed via `__all__`); reading the four
public attributes (`is_block`, `is_atdd_pure`, `event`, `reason`) is
inspection of the public contract, NOT direct-domain function-boundary
invocation. The slice-02 composition does NOT import `DesMarkerParser` /
`AtCompletionLedger` / any internal helper — prompt authoring builds the
M3-marker text via the public `DES-MODE:atdd_pure` / `DES-PHASE:...` /
`Slice-Id: slice-NN` format documented in
`docs/feature/single-entry-point/distill/des-marker-format.md`.

Step modules (`dispatcher_steps/steps_*.py`) invoke ONLY each composition's
methods — they never import from `des.domain.*` / `des.application.*` /
`des.adapters.*` themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml

from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    evaluate_atdd_pure_dispatch,
)
from des.application.flavor_dispatcher import (
    CompositionResult,
    compose_lifecycle_event,
)
from tests.env_parity import seed_dev_checkout_marker

from .dispatcher_steps.domain_types import (
    FlavorId,
    GateId,
    GateOutcome,
    InterceptVerdict,
    LifecycleEventName,
    OnFailurePolicy,
)


# --- slice-01 composition --------------------------------------------------


@dataclass
class FakeGateInvoker:
    """Driven-external Port fake — captures gate invocations in-process.

    The dispatcher injects this via the `gate_invoker` parameter, replacing the
    real `python -m des.cli.<gate_id>` subprocess invocation (slice-02 wires
    the real one). Per Architecture of Reference: driven external /
    non-deterministic ports get a fake by default; the project Infrastructure
    Policy specializes the mechanism (here: a callable dataclass capturing
    invocations to a list).
    """

    invocations: list[tuple[str, dict]] = field(default_factory=list)
    outcomes: dict[str, GateOutcome] = field(default_factory=dict)

    def record_outcome(self, gate_id: GateId, outcome: GateOutcome) -> None:
        self.outcomes[gate_id] = outcome

    def __call__(self, gate_id: str, args: dict) -> tuple[int, str]:
        self.invocations.append((gate_id, args))
        outcome = self.outcomes.get(gate_id, GateOutcome.SUCCESS)
        exit_code = 0 if outcome is GateOutcome.SUCCESS else 1
        return exit_code, ""


@dataclass
class FlavorDispatcherComposition:
    """Production composition root for the slice-01 ATs.

    Owns the flavor file fixture, the FakeGateInvoker Port, and the dispatch
    entry call. Each step body calls one method on this composition — the
    business logic lives here, never in step bodies (Mandate-12 criterion 3).
    """

    flavors_dir: Path
    invoker: FakeGateInvoker
    last_result: CompositionResult | None = None

    def author_flavor(
        self,
        flavor_id: FlavorId,
        event: LifecycleEventName,
        gates: list[tuple[GateId, OnFailurePolicy]],
    ) -> None:
        """Write a flavor YAML file with the given lifecycle-event composition."""
        composition = [
            {"gate_id": gate_id, "on_failure": policy.value}
            for gate_id, policy in gates
        ]
        flavor_doc = {
            "flavor_id": flavor_id,
            "description": f"slice-01 test flavor for {event} composition",
            "lifecycle_events": {event: composition},
        }
        (self.flavors_dir / f"{flavor_id}.yaml").write_text(yaml.safe_dump(flavor_doc))

    def record_gate_outcome(self, gate_id: GateId, outcome: GateOutcome) -> None:
        """Pre-program the FakeGateInvoker's outcome for a gate_id."""
        self.invoker.record_outcome(gate_id, outcome)

    def dispatch(
        self,
        event: LifecycleEventName,
        flavor_id: FlavorId,
    ) -> CompositionResult:
        """Compose a lifecycle event from a flavor DOCUMENT. Stores the result.

        These scenarios exercise SYNTHETIC flavor documents (`demo_single`,
        `demo_block`, `demo_warn`) that name no shipped mode, so they drive the
        document entry rather than the identity entry -- which is precisely the
        separation under test: composition reads a file and is blind to the mode
        registry.

        This driver therefore no longer witnesses the identity->document leg
        (`resolve_executable_flavor_path`). That leg is NOT left unattested: it
        has its own witness in
        `tests/des/unit/test_flavor_identity_resolution.py`. Dropping a leg's
        only witness while moving a test is how a refactor silently narrows what
        the suite proves -- the replacement is named here so a reader can check
        the claim instead of taking it.
        """
        self.last_result = compose_lifecycle_event(
            self.flavors_dir / f"{flavor_id}.yaml",
            event_id=event,
            flavor_id=flavor_id,
            context={},
            gate_invoker=self.invoker,
        )
        return self.last_result


@pytest.fixture
def composition(tmp_path: Path) -> FlavorDispatcherComposition:
    """Composition-root fixture wiring real tmp_path flavors_dir + FakeGateInvoker."""
    flavors_dir = tmp_path / "flavors"
    flavors_dir.mkdir()
    return FlavorDispatcherComposition(
        flavors_dir=flavors_dir,
        invoker=FakeGateInvoker(),
    )


# --- slice-02 composition --------------------------------------------------


@dataclass
class CarpaccioInterceptComposition:
    """Production composition root for the slice-02 ATs.

    Owns the dispatch-prompt fixture, the controllable carpaccio-runner Port
    double, and the single driving-port `evaluate()` entry call. Each step
    body calls one method on this composition — the prompt-authoring logic
    and InterceptDecision-shape readers live here, never in step bodies
    (Mandate-12 criterion 3).

    The composition exposes typed accessors that translate the public
    `InterceptDecision` dataclass attributes into the `InterceptVerdict`
    enum the slice-02 step bodies assert against — the enum mapping keeps
    step bodies trivially `composition.last_verdict() is InterceptVerdict.X`.
    """

    project_root: Path
    feature_id: str = "f-x"
    _prompt: str | None = None
    _carpaccio_exit_code: int = 0
    _carpaccio_stdout: str = ""
    _last_decision: InterceptDecision | None = None

    # --- prompt authoring (slice-02 driving-port input) -------------------

    def author_valid_atdd_pure_prompt(
        self, feature_id: str, slice_id: str, phase: str
    ) -> None:
        """Author a dispatch prompt carrying the full M3 marker set.

        Public marker format per `des.domain.des_marker_parser` docstring +
        ADR-030 D8:
            <!-- DES-MODE : atdd_pure -->
            <!-- DES-PHASE : <phase> -->
            <!-- DES-SLICE : <slice-NN> -->
        """
        self.feature_id = feature_id
        self._prompt = (
            f"<!-- DES-MODE : atdd_pure -->\n"
            f"<!-- DES-PHASE : {phase} -->\n"
            f"<!-- DES-SLICE : {slice_id} -->\n"
        )

    def author_defective_atdd_pure_prompt_missing_slice(self) -> None:
        """Author a defective atdd_pure prompt — mode + phase present, slice marker missing.

        Triggers the M3 `defective` classification + the
        `AtddPureMarkerSetIncomplete` block (carpaccio_intercept line 263-272).
        """
        self._prompt = (
            "<!-- DES-MODE : atdd_pure -->\n<!-- DES-PHASE : A_GREEN_ATS -->\n"
        )

    def author_non_atdd_pure_prompt(self) -> None:
        """Author a prompt carrying NO DES markers — classic dispatch path.

        Triggers the M3 `absent` classification + the
        `InterceptDecision.passthrough()` return (line 262).
        """
        self._prompt = "regular orchestrator prompt with no markers\n"

    # --- carpaccio runner programming -------------------------------------

    def program_carpaccio_gate_to_clear(self) -> None:
        """Programme the injected carpaccio-runner stub to return exit 0."""
        self._carpaccio_exit_code = 0
        self._carpaccio_stdout = ""

    # --- driving-port entry -----------------------------------------------

    def evaluate(self) -> InterceptDecision:
        """Invoke `evaluate_atdd_pure_dispatch` and store the verdict.

        slice-05 multi-gate dispatch.pre wire (commit shipping with slice-05):
        the production `atdd_pure.yaml` now wires `verify-readiness-pre-dispatch`
        AHEAD of `carpaccio-slice-gate`. The slice-02 ATs do not exercise
        readiness behaviour; the composition passes a clearing `readiness_runner`
        so the multi-gate YAML reads as "readiness clears then carpaccio runs"
        and the slice-02 carpaccio-only contract observes the carpaccio verdict
        unchanged. Without this clearing runner the slice-02 ATs would observe
        an UnknownGateOnDispatchPre block from the missing readiness registry
        entry -- a wiring artefact of the multi-gate prod YAML, NOT a slice-02
        contract change. The .feature semantics are unchanged.
        """
        assert self._prompt is not None, "prompt must be authored before evaluate()"
        self._last_decision = evaluate_atdd_pure_dispatch(
            prompt=self._prompt,
            feature_id=self.feature_id,
            project_root=self.project_root,
            carpaccio_runner=lambda _fid, _sid: (
                self._carpaccio_exit_code,
                self._carpaccio_stdout,
            ),
            readiness_runner=lambda _fid, _sid: (0, ""),
        )
        return self._last_decision

    # --- public InterceptDecision-shape accessors -------------------------

    def last_verdict(self) -> InterceptVerdict:
        """Translate the public InterceptDecision attributes to the verdict enum."""
        assert self._last_decision is not None, "evaluate() must run first"
        return _verdict_of(self._last_decision)

    def last_is_atdd_pure(self) -> bool:
        assert self._last_decision is not None, "evaluate() must run first"
        return self._last_decision.is_atdd_pure

    def last_block_event(self) -> str | None:
        assert self._last_decision is not None, "evaluate() must run first"
        return self._last_decision.event

    def last_block_reason_mentions(self, token: str) -> bool:
        assert self._last_decision is not None, "evaluate() must run first"
        return token in (self._last_decision.reason or "")


def _verdict_of(decision: InterceptDecision) -> InterceptVerdict:
    """Map the three-way InterceptDecision shape to the InterceptVerdict enum.

    Lives at module-scope (NOT inside a step body) so step bodies stay at
    <=2 statements per Mandate-12 criterion 3. This is the verdict
    decision-table translation between the production contract
    (`InterceptDecision.is_block` + `.is_atdd_pure`) and the slice-02
    test-domain enum.
    """
    if decision.is_block:
        return InterceptVerdict.BLOCK
    if decision.is_atdd_pure:
        return InterceptVerdict.ALLOW
    return InterceptVerdict.PASSTHROUGH


@pytest.fixture
def intercept_composition(tmp_path: Path) -> CarpaccioInterceptComposition:
    """Composition-root fixture for slice-02 — tmp_path project_root, no ledger writes."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".nwave").mkdir()
    return CarpaccioInterceptComposition(project_root=project_root)


# --- slice-03 composition (D1 readiness pre-dispatch gate) ----------------

import hashlib
import subprocess
import sys

from .dispatcher_steps.domain_types import (
    FirstDispatchInvariantId,
    InvariantStatus,
    ReadinessVerdict,
)


def _snapshot_workspace_tree(root: Path) -> dict[str, str]:
    """Deterministic byte-level snapshot of the workspace universe under ``root``.

    Closed-world (Mandate-14 ``contract-shape:unbounded-preservation``): the
    universe is the bounded ``repo_root`` tree the readiness gate operates on,
    NOT the whole filesystem. Returns a sorted mapping of each relative path to
    a content fingerprint:
      * regular file  -> ``"f:" + sha256(bytes)``
      * directory     -> ``"d:"`` (presence/absence is itself observable)
      * symlink       -> ``"l:" + target`` (target change is a mutation)
      * other         -> ``"?:" + str(stat.st_mode)``

    Two equal snapshots prove the gate's ``verify()`` invocation was read-only:
    any created/deleted/renamed path, or any byte changed in any file under the
    workspace, yields a different mapping -> the equality assertion flips RED.
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
    """Public report shape the readiness gate emits to its operator.

    The five invariants entries mirror the closed FirstDispatchInvariantId
    enum -- one row per invariant catalogued in friction #57. Each entry
    carries the invariant's status + an actionable remediation string when
    status is FAILED.

    The composition translates the gate's subprocess output (exit code +
    JSON-line stdout) into this typed report so step bodies stay <=2
    statements per Mandate-12 criterion 3.
    """

    verdict: ReadinessVerdict
    invariant_statuses: dict[FirstDispatchInvariantId, InvariantStatus]
    remediations: dict[FirstDispatchInvariantId, str]


@dataclass
class ReadinessGateComposition:
    """Production composition root for the slice-03 ATs.

    Owns the feature workspace fixture (real tmp_path filesystem), the
    workspace-authoring helpers (typed parameters per Mandate-12 criterion 2),
    and the single driving-port entry `verify()` invoking the gate via
    subprocess (`python -m des verify-readiness-pre-dispatch`).

    The composition exposes typed accessors translating the public gate
    contract (exit code 0/1 + per-invariant JSON-line diagnostic) into the
    `ReadinessReport` dataclass step bodies assert against.

    Per Mandate-13 (S2 driving-port-only): the driving port is the
    `des verify-readiness-pre-dispatch` CLI subcommand (Layer 3 subprocess).
    The composition NEVER imports `des.cli.verify_readiness_pre_dispatch`
    directly -- it invokes the subprocess and reads the public stdout/exit
    contract.
    """

    repo_root: Path
    feature_id: str = "f-readiness"
    slice_id: str = "slice-01"
    _workspace_path: Path | None = None
    _last_report: ReadinessReport | None = None
    _pre_verify_snapshot: dict[str, str] | None = None
    _post_verify_snapshot: dict[str, str] | None = None

    # --- workspace authoring (slice-03 driving-port input) ----------------

    def workspace_without_feature_delta(self) -> None:
        """Create a feature workspace with no feature-delta.md authored.

        Triggers the slice-plan invariant failure (no feature-delta to
        inspect -> no slice plan section to find).
        """
        workspace = self.repo_root / "docs" / "feature" / self.feature_id
        workspace.mkdir(parents=True)
        self._workspace_path = workspace

    def workspace_missing_slice_plan_heading(self) -> None:
        """Create a feature workspace whose feature-delta omits the slice plan heading.

        Triggers the slice-plan invariant failure (feature-delta present
        but `## Wave: DISCUSS / [REF] Slice Plan` heading absent).
        """
        workspace = self.repo_root / "docs" / "feature" / self.feature_id
        workspace.mkdir(parents=True)
        delta_path = workspace / "feature-delta.md"
        delta_path.write_text(
            "# Feature Delta: f-readiness\n\n"
            "## Wave: DISCUSS\n\n"
            "Some content but no slice plan heading.\n"
        )
        self._workspace_path = workspace

    def workspace_satisfying_every_invariant(self) -> None:
        """Create a feature workspace satisfying every first-dispatch invariant.

        Authors feature-delta.md with slice plan heading, a Gherkin feature
        with @slice-NN tags, an AT-review verdict ledger record, a valid
        CWD layout for carpaccio CLI output, and a pre-commit-scope
        satisfiable test layout (RED scaffolds marked @skip).

        Per the DELIVER crafter slice-03 A_GREEN_ATS attachment, every
        first-dispatch invariant fixture is authored mechanically:
          1. SLICE_PLAN_SECTION -- feature-delta.md with the heading.
          2. SCENARIO_SLICE_TAGS -- a `.feature` file in tests/ tagged
             with `@slice-01`. (Vacuously satisfied when no feature files
             exist, so the structural author is optional; we author one
             to exercise the positive path explicitly.)
          3. GATE_OUTPUT_PRODUCEABLE -- `.nwave/` directory presence in
             the repo_root (already created by the fixture).
          4. PRE_COMMIT_SCOPE -- structurally satisfied when no untagged
             RED scaffolds exist (vacuously true under tmp_path).
          5. REUSE_FIRST_OR_DESIGN_SKIP -- a `## Reuse Analysis` section
             carrying a no-overlap exemption marker (reuse leg present).

        NOTE (fix-readiness-carpaccio-disagree): the gate USED to also carry
        an `AT_REVIEW_VERDICT` invariant (satisfied here by writing an
        APPROVED `ATReviewVerdict` ledger record below); that invariant was
        DELETED from the gate as a rigor-gated duplicate of carpaccio's own
        fail-closed AT-review block. The ledger write below is now inert
        w.r.t. this gate -- left in place as harmless setup, not asserted on.
        """
        import json

        workspace = self.repo_root / "docs" / "feature" / self.feature_id
        workspace.mkdir(parents=True)
        (workspace / "feature-delta.md").write_text(
            "# Feature Delta: f-readiness\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | ATs |\n|---|---|\n| slice-01 | 1 |\n\n"
            # 6th invariant (reuse_first_or_design_skip, added by
            # fix-readiness-gate-reuse-first-invariant): the canonical
            # "satisfying every invariant" workspace must now ALSO carry a
            # valid reuse-first leg. A no-overlap exemption marker is the
            # lightest accepted form (VERDICT_NO_OVERLAP_DECLARED).
            "## Reuse Analysis\n\n"
            "Reuse-Analysis: no-overlap\n\n"
            # 7th invariant (sustainability, added by sustainable-test-suite
            # slice-06 wiring invariant 7 into the readiness aggregate): the
            # canonical "satisfying every invariant" workspace must now ALSO
            # carry a well-formed Test Reuse & Consolidation Analysis section.
            # A `methodology-exempt` marker is the lightest accepted verdict
            # (_SUSTAINABILITY_ACCEPTED_VERDICTS).
            "## Test Reuse & Consolidation Analysis\n\n"
            "Test-Reuse-Analysis: methodology-exempt\n"
        )
        # Author a tagged Gherkin feature so SCENARIO_SLICE_TAGS holds
        # positively (rather than vacuously) when feature files exist.
        feature_dir = self.repo_root / "tests" / "acceptance" / self.feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "happy.feature").write_text(
            "Feature: readiness happy path\n\n"
            f"  @{self.slice_id}\n"
            "  Scenario: every invariant clears\n"
            "    Given a satisfied workspace\n"
            "    Then dispatch clears\n"
        )
        # Author the AT-review ledger record for the entering slice.
        ledger_dir = self.repo_root / ".nwave" / "telemetry" / "atdd-pure"
        ledger_dir.mkdir(parents=True)
        ledger = ledger_dir / f"{self.feature_id}.jsonl"
        ledger.write_text(
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

        Captures exit code + stdout JSON line. Translates into typed
        ReadinessReport. Per Mandate-13 driving-port-only: the SUT is the
        CLI subcommand surface, not the in-process Python module.
        """
        # Closed-world filesystem oracle (Mandate-14 unbounded-preservation):
        # snapshot the bounded repo_root workspace immediately around the gate's
        # subprocess invocation. A read-only gate leaves both snapshots equal;
        # any write under the workspace during verify() flips them, which
        # `verify_was_filesystem_preserving()` surfaces RED.
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
    ) -> InvariantStatus:
        assert self._last_report is not None, "verify() must run first"
        return self._last_report.invariant_statuses[invariant]

    def last_remediation_mentions(
        self, invariant: FirstDispatchInvariantId, token: str
    ) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return token in self._last_report.remediations.get(invariant, "")

    def every_invariant_satisfied(self) -> bool:
        assert self._last_report is not None, "verify() must run first"
        return all(
            status is InvariantStatus.SATISFIED
            for status in self._last_report.invariant_statuses.values()
        )

    def verify_was_filesystem_preserving(self) -> bool:
        """True iff the workspace tree is byte-identical before vs after verify().

        Compares the closed-world repo_root snapshots captured around the gate
        subprocess. Falsifiable: a write/create/delete/rename under the
        workspace during verify() makes the snapshots differ -> returns False.
        """
        assert self._post_verify_snapshot is not None, "verify() must run first"
        return self._pre_verify_snapshot == self._post_verify_snapshot


def _parse_readiness_report(exit_code: int, stdout: str) -> ReadinessReport:
    """Translate the gate's exit-code + stdout JSON line into ReadinessReport.

    Lives at module-scope (NOT inside a step body) per Mandate-12 criterion 3.
    The expected stdout shape (per gate-contract YAML) is one JSON line:
        {"verdict": "cleared|refused",
         "invariants": [{"id": "<id>", "status": "satisfied|failed", "remediation": "<text>"}, ...]}

    Returns: typed ReadinessReport. Stub-tolerant on empty stdout (the
    scaffold raises before producing stdout) -- step bodies assert the
    refused/cleared verdict from exit_code alone for the walking skeleton.
    """
    import json

    verdict = ReadinessVerdict.CLEARED if exit_code == 0 else ReadinessVerdict.REFUSED
    statuses: dict[FirstDispatchInvariantId, InvariantStatus] = {}
    remediations: dict[FirstDispatchInvariantId, str] = {}
    if stdout.strip():
        try:
            doc = json.loads(stdout.strip().splitlines()[0])
            for entry in doc.get("invariants", []):
                inv_id = FirstDispatchInvariantId(entry["id"])
                statuses[inv_id] = InvariantStatus(entry["status"])
                if entry.get("remediation"):
                    remediations[inv_id] = entry["remediation"]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    return ReadinessReport(
        verdict=verdict,
        invariant_statuses=statuses,
        remediations=remediations,
    )


@pytest.fixture
def readiness_composition(tmp_path: Path) -> ReadinessGateComposition:
    """Composition-root fixture for slice-03 -- tmp_path repo_root with empty .nwave/."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".nwave").mkdir()
    # Env-parity (F21/RCA-#68): `des verify-readiness-pre-dispatch` runs as a
    # subprocess with cwd=repo_root. Mark the synthetic workspace as a developer
    # checkout so the runtime-freshness gate autoskips instead of fail-closed
    # exit 78 on the manifest-less tmp tree. See tests/env_parity.py.
    seed_dev_checkout_marker(repo_root)
    return ReadinessGateComposition(repo_root=repo_root)


# --- slice-04 composition (LogPersistencePort + adapters) -----------------


import io
from datetime import datetime, timezone

from des.adapters.driven.log_persistence import (
    JsonlLogAdapter,
    SilentLogAdapter,
)
from des.application.log_persistence import (
    GateLogEvent,
    LogPersistencePort,
)

from .dispatcher_steps.domain_types import GateEventId, LogAdapterKind


@dataclass
class LogPersistenceComposition:
    """Production composition root for the slice-04 ATs.

    Owns:
      * The repo_root tmp_path filesystem (real I/O fixture for the
        jsonl adapter's per-feature + common-log destinations).
      * The active adapter instance (JsonlLogAdapter / StdoutLogAdapter /
        SilentLogAdapter) wired with typed parameters per Mandate-12
        criterion 2 -- no raw `str` where the LogAdapterKind enum exists.
      * The captured stderr buffer (for fail-OPEN diagnostic assertions in
        AT-2 -- the JsonlLogAdapter writes a one-line diagnostic to stderr
        when fail_open=True and the destination is not writeable).
      * A list of authored GateLogEvent instances (slice-04 step bodies
        author events one at a time, then emit each in a single `When`).

    Each step body calls one method on this composition -- the
    business logic (path resolution, JSON-line serialisation, fanout
    iteration, stderr diagnostic shape) lives in the adapter, never in
    step bodies (Mandate-12 criterion 3).

    Per Mandate-13 (S2 driving-port-only): the driving port is
    `LogPersistencePort.emit(event)` -- the public Protocol method on the
    adapter instance. The composition NEVER inspects adapter internals
    (no _captured list reach-in, no path-template reach-in); it reads only
    public state via:
      * Filesystem reads of the per-feature + common-log paths (the
        public adapter contract is "writes appear on disk per config").
      * Captured stderr buffer (the public fail-OPEN contract is "stderr
        diagnostic on sink failure").
      * `SilentLogAdapter.captured_events()` (the public introspection
        method documented in the silent adapter's docstring).
    """

    repo_root: Path
    _adapter_kind: LogAdapterKind | None = None
    _adapter: LogPersistencePort | None = None
    _stderr_buf: io.StringIO = field(default_factory=io.StringIO)
    _authored_events: list[GateLogEvent] = field(default_factory=list)
    _per_feature_destination_unwriteable: bool = False
    _active_feature_id: str | None = None

    # --- adapter configuration (slice-04 driving-port input) --------------

    def configure_jsonl_adapter_with_fanout(self, feature_id: str) -> None:
        """Wire a JsonlLogAdapter with fanout=True under the repo_root.

        Per `nWave/data/log-persistence-defaults.yaml` defaults:
          per_feature_path: ".nwave/telemetry/atdd-pure/{feature_id}.jsonl"
          common_log_path:  ".nwave/audit/atdd-pure-events.jsonl"
          fanout:           true
          fail_open:        true
        """
        self._adapter_kind = LogAdapterKind.JSONL
        self._active_feature_id = feature_id
        self._adapter = JsonlLogAdapter(
            per_feature_template=".nwave/telemetry/atdd-pure/{feature_id}.jsonl",
            common_log_path=".nwave/audit/atdd-pure-events.jsonl",
            fanout=True,
            fail_open=True,
            repo_root=self.repo_root,
        )

    def configure_silent_adapter_with_capture(self) -> None:
        """Wire a SilentLogAdapter with capture_in_memory=True."""
        self._adapter_kind = LogAdapterKind.SILENT
        self._adapter = SilentLogAdapter(capture_in_memory=True)

    def make_per_feature_destination_unwriteable(self) -> None:
        """Pre-create the per-feature ledger path as a read-only directory.

        The DELIVER crafter's JsonlLogAdapter.emit() attempts to open the
        per-feature path for append; opening a directory as a file raises
        IsADirectoryError (a subclass of OSError). With fail_open=True the
        adapter must swallow the OSError + write a one-line diagnostic to
        the stderr stream wired into this composition. This is the fail-
        OPEN contract pin per INV-3.
        """
        assert self._active_feature_id is not None, (
            "configure jsonl adapter with feature_id before making destination unwriteable"
        )
        per_feature_path = (
            self.repo_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{self._active_feature_id}.jsonl"
        )
        per_feature_path.parent.mkdir(parents=True, exist_ok=True)
        # Create the path AS A DIRECTORY so the adapter's append-open raises
        # IsADirectoryError (an OSError subclass). The fail_open=True
        # contract requires the adapter to swallow + diagnose, NOT raise.
        per_feature_path.mkdir()
        self._per_feature_destination_unwriteable = True

    # --- event authoring (slice-04 driving-port input) --------------------

    def author_event(self, event_id: GateEventId, payload_summary: str) -> None:
        """Author a single GateLogEvent and stage it for emit.

        payload_summary is the Gherkin-readable summary string; the
        composition translates it into the dict payload field per the
        slice-04 contract (the exact payload shape is a gate-internal
        concern; the ATs pin event_id presence + count + order, NOT the
        per-gate payload schema).
        """
        event = GateLogEvent(
            event_id=event_id,
            gate_id=event_id.split(".")[1] if "." in event_id else "unknown",
            feature_id=self._active_feature_id,
            slice_id=None,
            payload={"summary": payload_summary},
            timestamp=datetime.now(timezone.utc),
            host="cli",
        )
        self._authored_events.append(event)

    # --- driving-port entry: LogPersistencePort.emit ---------------------

    def emit_first_authored_event(self) -> None:
        """Invoke the driving port `LogPersistencePort.emit(event)` once.

        Per Mandate-13 driving-port-only: emit() is the public Protocol
        method on the LogPersistencePort. The composition routes stderr
        through self._stderr_buf for AT-2's fail-OPEN diagnostic assertion.
        """
        assert self._adapter is not None, "adapter must be configured before emit"
        assert self._authored_events, "at least one event must be authored before emit"
        self._emit_with_stderr_capture(self._authored_events[0])

    def emit_each_authored_event(self) -> None:
        """Invoke `LogPersistencePort.emit(event)` for every authored event in order."""
        assert self._adapter is not None
        assert self._authored_events
        for event in self._authored_events:
            self._emit_with_stderr_capture(event)

    def _emit_with_stderr_capture(self, event: GateLogEvent) -> None:
        """Invoke emit while capturing stderr writes into self._stderr_buf.

        Module-scope helper per Mandate-12 criterion 3 (no control flow in
        step bodies; this helper lives in the composition class but is
        invoked from step bodies as a single composition method call).
        """
        import contextlib

        with contextlib.redirect_stderr(self._stderr_buf):
            self._adapter.emit(event)  # type: ignore[union-attr]

    # --- public observable accessors --------------------------------------

    def per_feature_event_count(self, feature_id: str, event_id: GateEventId) -> int:
        """Count events with the given event_id in the per-feature ledger.

        Reads the per-feature path on disk + counts lines whose JSON
        decodes to a dict carrying event_id == event_id. Adapter-internal
        details (line buffering, encoding) are hidden behind the public
        on-disk contract.
        """
        return _count_events_in_jsonl(
            self.repo_root
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{feature_id}.jsonl",
            event_id,
        )

    def common_log_event_count(self, event_id: GateEventId) -> int:
        """Count events with the given event_id in the singleton common log."""
        return _count_events_in_jsonl(
            self.repo_root / ".nwave" / "audit" / "atdd-pure-events.jsonl",
            event_id,
        )

    def emit_raised(self) -> bool:
        """Whether the most recent emit() invocation raised an exception.

        Always False under the slice-04 fail-OPEN contract -- the adapter
        swallows OSError when fail_open=True. AT-2 asserts this is False
        even when the per-feature destination is not writeable.
        """
        # The composition's _emit_with_stderr_capture call propagates any
        # exception; since fail_open=True swallows, we never see one here.
        # The pin is "we got this far without raising".
        return False

    def stderr_diagnostic_mentions(self, token: str) -> bool:
        """Whether the captured stderr buffer contains the given token."""
        return token in self._stderr_buf.getvalue()

    def silent_adapter_captured_count(self) -> int:
        """Public introspection method on the silent adapter."""
        assert isinstance(self._adapter, SilentLogAdapter)
        return len(self._adapter.captured_events())

    def silent_adapter_captured_event_id(self, index: int) -> str:
        """Read the event_id of the index-th captured event in the silent adapter."""
        assert isinstance(self._adapter, SilentLogAdapter)
        return self._adapter.captured_events()[index].event_id


def _count_events_in_jsonl(path: Path, event_id: GateEventId) -> int:
    """Count JSON lines in `path` whose `event_id` field equals `event_id`.

    Lives at module-scope (NOT inside a step body) per Mandate-12
    criterion 3. Returns 0 when the file does not exist (a missing common
    log is a count-of-0 observation, not an error).
    """
    import json

    if not path.exists():
        return 0
    count = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            doc = json.loads(line)
        except json.JSONDecodeError:
            continue
        if doc.get("event_id") == event_id:
            count += 1
    return count


@pytest.fixture
def log_persistence_composition(tmp_path: Path) -> LogPersistenceComposition:
    """Composition-root fixture for slice-04 -- tmp_path repo_root with empty .nwave/."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".nwave").mkdir()
    return LogPersistenceComposition(repo_root=repo_root)


# --- slice-05 composition (multi-gate dispatch.pre wire) ------------------
#
# slice-05 refactors `_gate_invoker_for` inside `carpaccio_intercept.py` so
# the helper dispatches on each gate id in the `atdd_pure.yaml dispatch.pre`
# YAML composition (rather than fail-closing with `UnknownGateOnDispatchPre`
# on any non-carpaccio gate id) AND activates the previously-deferred
# `verify-readiness-pre-dispatch` wire in the flavor file.
#
# The composition exercises the public driving-port surface
# `evaluate_atdd_pure_dispatch(prompt, feature_id, project_root,
# carpaccio_runner=..., readiness_runner=...)`. The slice-05 DELIVER crafter
# extends the slice-02 frozen signature with an ADDITIVE
# `readiness_runner: ReadinessRunner | None = None` parameter (default
# preserves backward-compat with slice-02 callers -- the AT-3 regression-pin
# scenario verifies that calling the function WITHOUT readiness_runner
# yields the same InterceptDecision behaviour as slice-02 today).
#
# Per Mandate-13 driving-port-only: step modules import ONLY the slice-05
# composition + `domain_types` enums. The conftest imports
# `evaluate_atdd_pure_dispatch` + `InterceptDecision` (already inherited
# from slice-02 conftest above) -- the public driving-port surface, NOT
# internal helpers (`_gate_invoker_for`, `_decision_from_composition`).
#
# Composition design (revised post Sentinel M86-R BLOCKER 1):
#
#   * The composition explicitly wires TWO programmable runner adapters --
#     `_readiness_runner_adapter` and `_carpaccio_runner_adapter` -- each
#     of which is responsible for recording its own gate id in the
#     `_invocation_log` and returning the programmed exit code. The two
#     adapters are passed as DISTINCT parameters to
#     `evaluate_atdd_pure_dispatch` (the slice-05 crafter extends the
#     signature with the additive `readiness_runner=` parameter); the
#     post-refactor `_gate_invoker_for` builds the per-gate registry from
#     BOTH parameters internally. Pre-refactor (slice-02 signature) the
#     ATs are RED because the additive parameter is not yet accepted AND
#     because `_gate_invoker_for` fail-closes on any non-carpaccio gate id
#     with `UnknownGateOnDispatchPre` -- both production causes, not
#     fixture/stub artefacts.


from .dispatcher_steps.domain_types import (
    BlockEventName,
    GateIdOnDispatchPre,
)


@dataclass
class MultiGateWireComposition:
    """Production composition root for the slice-05 ATs.

    Owns:
      * The tmp_path flavors_dir + a tmp_path atdd_pure.yaml fixture
        wiring `verify-readiness-pre-dispatch` ahead of `carpaccio-slice-gate`
        on `dispatch.pre` (this is the post-DELIVER target shape; the
        in-flight production atdd_pure.yaml still carries the deferral
        comment).
      * A per-gate runner registry -- two in-memory runners keyed by
        `GateIdOnDispatchPre` (`VERIFY_READINESS_PRE_DISPATCH`,
        `CARPACCIO_SLICE_GATE`); each runner is programmable via
        `program_*` helper methods to clear or block deterministically.
        Each runner adapter records its own gate id in `_invocation_log`.
      * The dispatch prompt fixture (valid M3 marker set for the fresh
        slice path -- AT-1 / AT-2 / AT-3 all use the same valid prompt;
        only the per-gate outcome programming varies).
      * The captured `InterceptDecision` from the last `evaluate()` call +
        the captured per-gate invocation log (ordered list of
        `GateIdOnDispatchPre` the intercept invoked through the registry --
        observable proof of multi-gate dispatch ordering).

    The composition uses `monkeypatch.setattr` to swap the intercept
    module's `_FLAVORS_DIR` constant during `evaluate()` -- this lets the
    composition control the YAML the intercept reads without touching the
    production atdd_pure.yaml file. The monkeypatch fixture is wired via
    the fixture closure (see `multi_gate_composition` pytest fixture below).
    """

    project_root: Path
    flavors_dir: Path
    monkeypatch: pytest.MonkeyPatch
    feature_id: str = "f-multi"
    _prompt: str | None = None
    _readiness_clears: bool = True
    _carpaccio_clears: bool = True
    _invocation_log: list[GateIdOnDispatchPre] = field(default_factory=list)
    _last_decision: InterceptDecision | None = None

    # --- flavor YAML authoring (slice-05 driving-port input) --------------

    def author_multi_gate_atdd_pure_flavor(self) -> None:
        """Write a tmp_path atdd_pure.yaml wiring two gates on dispatch.pre.

        verify-readiness-pre-dispatch precedes carpaccio-slice-gate; both
        carry `on_failure: block`. The intercept's `_FLAVORS_DIR` constant
        is monkey-patched to this tmp_path inside `evaluate()` so the
        production atdd_pure.yaml is not touched.
        """
        flavor_doc = {
            "flavor_id": "atdd_pure",
            "description": "slice-05 multi-gate test flavor",
            "lifecycle_events": {
                "dispatch.pre": [
                    {
                        "gate_id": GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH.value,
                        "on_failure": "block",
                    },
                    {
                        "gate_id": GateIdOnDispatchPre.CARPACCIO_SLICE_GATE.value,
                        "on_failure": "block",
                    },
                ]
            },
        }
        (self.flavors_dir / "atdd_pure.yaml").write_text(yaml.safe_dump(flavor_doc))

    # --- per-gate runner programming --------------------------------------

    def program_readiness_runner_to_clear(self) -> None:
        """Programme the readiness gate runner to return exit_code=0."""
        self._readiness_clears = True

    def program_readiness_runner_to_block(self) -> None:
        """Programme the readiness gate runner to return exit_code=1."""
        self._readiness_clears = False

    def program_carpaccio_runner_to_clear(self) -> None:
        """Programme the carpaccio gate runner to return exit_code=0."""
        self._carpaccio_clears = True

    def program_carpaccio_runner_to_block(self) -> None:
        """Programme the carpaccio gate runner to return exit_code=1."""
        self._carpaccio_clears = False

    # --- dispatch prompt authoring (valid M3 marker set) -----------------

    def author_fresh_slice_prompt(self) -> None:
        """Author a valid atdd_pure dispatch prompt for a fresh A_GREEN_ATS slice."""
        self._prompt = (
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : A_GREEN_ATS -->\n"
            "<!-- DES-SLICE : slice-01 -->\n"
        )

    # --- driving-port entry -----------------------------------------------

    def bind_flavors_dir_monkeypatch(self) -> None:
        """Apply the `_FLAVORS_DIR` monkey-patch.

        Bound from Background step so AT-1..AT-3 and AT-4 share the
        precondition wiring (the production atdd_pure.yaml is never
        touched at test time). AT-4 (slice-02 single-gate call shape)
        authors a slice-02-shape carpaccio-only flavor on the same
        tmp_path flavors_dir before invoking the slice-02 call shape.
        """
        self.monkeypatch.setattr(
            "des.adapters.drivers.hooks.carpaccio_intercept._FLAVORS_DIR",
            self.flavors_dir,
        )

    def author_slice_02_single_gate_flavor(self) -> None:
        """Write a tmp_path atdd_pure.yaml in the slice-02 single-gate shape.

        Carpaccio-slice-gate alone on dispatch.pre -- mirrors the
        production atdd_pure.yaml SHIPPED today by slice-02. Used by AT-4
        (slice-02 backward-compat regression-pin) to verify that calling
        `evaluate_atdd_pure_dispatch` WITHOUT `readiness_runner=` against
        a single-gate flavor still yields the same InterceptDecision
        behaviour as slice-02 today.
        """
        flavor_doc = {
            "flavor_id": "atdd_pure",
            "description": "slice-02 single-gate shape (backward-compat regression-pin)",
            "lifecycle_events": {
                "dispatch.pre": [
                    {
                        "gate_id": GateIdOnDispatchPre.CARPACCIO_SLICE_GATE.value,
                        "on_failure": "block",
                    },
                ]
            },
        }
        (self.flavors_dir / "atdd_pure.yaml").write_text(yaml.safe_dump(flavor_doc))

    def evaluate(self) -> InterceptDecision:
        """Invoke `evaluate_atdd_pure_dispatch` with TWO runners explicitly.

        Wires BOTH runner adapters via DISTINCT keyword parameters --
        the slice-05 crafter extends the slice-02 frozen public signature
        with an ADDITIVE `readiness_runner: ReadinessRunner | None = None`
        parameter (backward-compat preserved -- AT-4 regression-pin
        verifies that the slice-02 single-runner call shape still yields
        the same InterceptDecision behaviour as today).

        Each adapter records ITS OWN gate id in `_invocation_log` -- the
        readiness adapter records VERIFY_READINESS_PRE_DISPATCH, the
        carpaccio adapter records CARPACCIO_SLICE_GATE. The post-refactor
        `_gate_invoker_for` looks up the runner per gate id in the
        2-entry registry built from the two parameters.

        Pre-refactor (current production), `evaluate_atdd_pure_dispatch`
        does NOT accept `readiness_runner`; the call below RAISES
        TypeError -- a PRODUCTION-CAUSE RED (the public signature lacks
        the additive parameter), NOT a fixture/stub artefact.
        """
        assert self._prompt is not None, "prompt must be authored before evaluate()"
        self._last_decision = evaluate_atdd_pure_dispatch(
            prompt=self._prompt,
            feature_id=self.feature_id,
            project_root=self.project_root,
            carpaccio_runner=self._carpaccio_runner_adapter,
            readiness_runner=self._readiness_runner_adapter,
        )
        return self._last_decision

    def evaluate_slice_02_call_shape(self) -> InterceptDecision:
        """Invoke `evaluate_atdd_pure_dispatch` WITHOUT `readiness_runner=`.

        Pins the slice-02 backward-compat contract -- calling the
        function with the slice-02 single-runner kwarg set (carpaccio
        only, no readiness) MUST yield the same InterceptDecision
        behaviour as today. The composition wires ONLY the carpaccio
        runner adapter; the readiness adapter is not passed. Combined
        with `author_slice_02_single_gate_flavor()` this exercises the
        full slice-02 dispatch path on the post-refactor function.

        Pre-refactor this call shape is the production today (slice-02
        ships exactly this signature); post-refactor the additive
        `readiness_runner=None` default preserves behaviour.
        """
        assert self._prompt is not None, "prompt must be authored before evaluate()"
        self._last_decision = evaluate_atdd_pure_dispatch(
            prompt=self._prompt,
            feature_id=self.feature_id,
            project_root=self.project_root,
            carpaccio_runner=self._carpaccio_runner_adapter,
        )
        return self._last_decision

    def _readiness_runner_adapter(
        self, feature_id: str, slice_id: str
    ) -> tuple[int, str]:
        """Programmable adapter for the verify-readiness-pre-dispatch gate.

        Records VERIFY_READINESS_PRE_DISPATCH in the invocation log; returns
        the programmed exit code. Instance method (not module-scope helper)
        because it needs access to `self._invocation_log` +
        `self._readiness_clears`. The closed-world observable contract is
        the same shape the production runner emits (exit_code + stdout).
        """
        self._invocation_log.append(GateIdOnDispatchPre.VERIFY_READINESS_PRE_DISPATCH)
        return (0 if self._readiness_clears else 1), ""

    def _carpaccio_runner_adapter(
        self, feature_id: str, slice_id: str
    ) -> tuple[int, str]:
        """Programmable adapter for the carpaccio-slice-gate gate.

        Records CARPACCIO_SLICE_GATE in the invocation log; returns the
        programmed exit code. Same shape as the slice-02 carpaccio runner
        stub (the slice-02 frozen signature is preserved verbatim --
        carpaccio_runner=Callable[[str, str], tuple[int, str]]).
        """
        self._invocation_log.append(GateIdOnDispatchPre.CARPACCIO_SLICE_GATE)
        return (0 if self._carpaccio_clears else 1), ""

    # --- public observable accessors --------------------------------------

    def last_verdict(self) -> InterceptVerdict:
        """Read the verdict shape from the last InterceptDecision."""
        assert self._last_decision is not None, "evaluate() must run first"
        return _verdict_of(self._last_decision)

    def last_block_event(self) -> BlockEventName | None:
        """Read the block event name from the last InterceptDecision.

        Returns a typed `BlockEventName` enum (Mandate-12 criterion 2 --
        the composition exposes typed observables, raw `str` only when
        the production contract attribute itself is `str | None`).
        Returns None when the verdict is not BLOCK (allow / passthrough).
        """
        assert self._last_decision is not None, "evaluate() must run first"
        raw = self._last_decision.event
        return BlockEventName(raw) if raw is not None else None

    def last_invocation_log(self) -> list[GateIdOnDispatchPre]:
        """Read the per-gate invocation log captured by the runner adapters."""
        return list(self._invocation_log)


@pytest.fixture
def multi_gate_composition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> MultiGateWireComposition:
    """Composition-root fixture for slice-05 -- tmp_path project_root + flavors dir + monkeypatch."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".nwave").mkdir()
    flavors_dir = tmp_path / "flavors"
    flavors_dir.mkdir()
    return MultiGateWireComposition(
        project_root=project_root,
        flavors_dir=flavors_dir,
        monkeypatch=monkeypatch,
    )
