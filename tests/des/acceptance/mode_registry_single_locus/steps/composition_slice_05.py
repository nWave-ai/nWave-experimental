"""Composition root for mode-registry-single-locus slice-05 (the SSOT-via-Types-Services-DSL mandate).

Pillar 3 (App as in production): the SUTs are the THREE real guardrail gates,
each driven through its real entry point:

  * Layer A — `des mode-locus-gate --root <working-copy>` (NEW DES gate),
    driven as a Layer-3 subprocess through the REAL `des` dispatcher
    (`python -m des.cli <subcommand>`), so the AT also witnesses the
    `__main__.py:_REGISTRY` dispatch row — the gate is reachable as a
    subcommand, not a dormant CLI.
  * Layer B — `des mode-registry-completeness --root <working-copy>` (NEW DES
    gate), same real dispatcher entry, same wiring witness.
  * Layer C — `python scripts/docgen.py --check --root <working-copy>` (the
    ALREADY-shipped slices-02/03 entry, ELEVATED here to assert resolver↔registry
    agreement AND registry↔runtime phase-shape parity).

Driving-Port-Only Boundary attestation (S2 gate): there is ZERO direct
production import in this module. Every gate is driven by subprocess through
its real entry; the catalog is read as a plain text/data artifact (the
wiring-witness oracle, like the slice-04 watcher-ledger live-tree read — the
legitimate structural-gate driving surface). No `des.domain.*` /
`des.application.*` / `des.adapters.*` import anywhere.

Dormant-Seam Reconciliation (D11 / S3): the DESIGN-declared net-new seams for
this slice are the two new gate CLIs + the elevated docgen agreement check.
Each is witnessed THROUGH its real entry with an observable effect:
  (i)   Layer A: a hand-planted naked literal → `des mode-locus-gate` REFUSES
        naming file+line; the clean copy → ACCEPTS. PLUS the wiring witness:
        the gate is dispatchable via `des <gate-id>` AND declared in the
        gate catalog (1:1 mirror).
  (ii)  Layer B: a half-declared registry → `des mode-registry-completeness`
        REFUSES naming the defect; the shipped registry → ACCEPTS. PLUS the
        same wiring witness.
  (iii) Layer C: resolver-default ≠ flavor-default OR deliver_phase_shape ≠
        runtime canonical phases → `docgen --check` REFUSES; the shipped state
        → ACCEPTS.
The witness counts INDIRECT wiring (dispatcher-registry membership), per S3.

DISTILL-authored ACTIVE-RED (ADR-025 / ADR-GV-001 D6): Layer A/B gate CLIs do
NOT yet exist — a Mandate-7 RED scaffold ships additively for each
(`src/des/cli/mode_locus_gate.py`, `src/des/cli/mode_registry_completeness.py`,
both `__SCAFFOLD__ = True`, `main` raising `AssertionError`). The dispatcher
does not yet route them, so the real-entry invocation surfaces the missing
capability as a semantic refusal recorded in When and asserted in Then —
active-RED via `AssertionError`, never an import/setup error masking the RED.
Layer C's entry exists but does not yet assert the two agreement legs, so its
clean-state-accepts / drift-refuses teeth fail in Then.

Mandate 8 (layer-3 FS acceptance): every mutating step asserts via
`assert_state_delta(before, after, universe, expected)` over port-exposed
observables only (registry file texts, the working-copy asset text, gate
exit/output). The accept-clean and refuse-on-defect legs assert the
empty-expected preservation contract — the gates rewrite nothing (pure reads).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from nwave_ai.state_delta import assert_state_delta

from scripts import docgen
from tests.common.in_process_cli import run_cli_in_process

from .domain_types_slice_05 import (
    ALLOW_MARKER,
    BENIGN_CLASSIC_SAMPLES,
    CATALOG_REL,
    FLAVORS_REL,
    NAKED_LITERAL_SENTINEL,
    GateUnderTest,
    RegistryCompletenessDefect,
    WorkflowFlavor,
)


REPO_ROOT = Path(__file__).resolve().parents[5]

# The framework catalog the docgen scan (Layer C) requires.
FRAMEWORK_CATALOG_REL = Path("nWave") / "framework-catalog.yaml"

# The asset families + registry the guardrail gates scan / read. `templates`
# is included because the real docgen scan (Layer C entry) reads it.
_COPIED_TREES = (
    Path("nWave") / "agents",
    Path("nWave") / "tasks",
    Path("nWave") / "skills",
    Path("nWave") / "templates",
    FLAVORS_REL,
)
# Byte-copied catalog files: the gate catalog (Layer A/B wiring-witness oracle)
# + the framework catalog (the Layer-C docgen scan input).
_COPIED_FILES = (CATALOG_REL, FRAMEWORK_CATALOG_REL)

# A self-contained allow-marked + benign-classic skill the Layer-A clean copy
# carries, proving the gate ACCEPTS marked references and bare-prose `classic`.
_CLEAN_LOCUS_PROBE_REL = (
    Path("nWave") / "skills" / "nw-slice05-locus-probe" / "SKILL.md"
)


@dataclass(frozen=True)
class _CliOutcome:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def transcript(self) -> str:
        return f"exit={self.exit_code}\nstdout:\n{self.stdout}\nstderr:\n{self.stderr}"

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


class GuardrailGateComposition:
    """Single source of truth for all slice-05 step-method business logic.

    Step bodies delegate here (the SSOT-via-Types-Services-DSL mandate,
    criterion 3: <=2 statements, no control flow inline).
    """

    def __init__(self, tmp_path: Path) -> None:
        self._worktree = tmp_path / "worktree"
        self._gate: GateUnderTest | None = None
        self._before: dict[str, str] | None = None
        self._after: dict[str, str] | None = None
        self._clean_run: _CliOutcome | None = None
        self._baseline_run: _CliOutcome | None = None
        self._defect_run: _CliOutcome | None = None
        self._defect_token: str | None = None

    # --- Given: working copy + which gate + planted defect --------------------

    def build_working_copy(self) -> None:
        """Byte-copy the asset families + registry + gate catalog, then add a
        self-contained clean probe (allow-marked literal + benign-classic
        prose) so the accept-clean leg proves the rule's accept side."""
        for rel in _COPIED_TREES:
            shutil.copytree(REPO_ROOT / rel, self._worktree / rel)
        for rel in _COPIED_FILES:
            target = self._worktree / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((REPO_ROOT / rel).read_bytes())
        self._write_clean_locus_probe()

    def select_gate(self, gate: GateUnderTest) -> None:
        self._gate = gate

    def establish_clean_baseline(self) -> None:
        """Pillar-2 chaining (the slice-02/03/04 accepted-before-drift pattern):
        run the selected gate against the CLEAN copy and record the baseline.
        Outcome is asserted in Then (never in this Given) so RED stays an
        `AssertionError` in Then, never a Given setup failure."""
        self._baseline_run = self._drive(self._require_gate())

    def plant_naked_mode_literal(self) -> None:
        """Layer-A defect: a hand-written naked `atdd_pure` outside any
        GENERATED region / allow-marker — the duplication smell the gate must
        refuse, naming file+line."""
        probe = self._worktree / _CLEAN_LOCUS_PROBE_REL
        probe.write_text(
            probe.read_text(encoding="utf-8")
            + f"\nThis line re-states the mode by hand: {NAKED_LITERAL_SENTINEL}.\n",
            encoding="utf-8",
        )

    def introduce_registry_defect(self, defect: RegistryCompletenessDefect) -> None:
        """Layer-B defect: corrupt the working registry into a half-declared
        mode the completeness gate must refuse, naming the defect."""
        self._defect_token = _DEFECT_INTRODUCERS[defect](self)

    def introduce_phase_shape_drift(self) -> None:
        """Layer-C defect: edit the default flavor's `deliver_phase_shape` so it
        DISAGREES with the runtime canonical DELIVER phases — the
        registry↔runtime parity break that closes the KEEP-row-10 open leg. The
        Layer-C agreement check (the docgen --check new leg) must refuse it; at
        RED docgen does not yet assert agreement, so the clean baseline (Given)
        accepts and this drift is NOT refused → the AssertionError in Then."""
        flavor_file = self._flavor_path(WorkflowFlavor.ATDD_PURE)
        text = flavor_file.read_text(encoding="utf-8")
        drifted = re.sub(
            r"^deliver_phase_shape:.*$",
            'deliver_phase_shape: "PHASE_DRIFT_X -> PHASE_DRIFT_Y"',
            text,
            count=1,
            flags=re.MULTILINE,
        )
        if drifted == text:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"WHAT: working registry {flavor_file} carries no "
                "`deliver_phase_shape:` field to drift. "
                "WHY: this plants the Layer-C defect (registry/runtime phase "
                "shape disagreement) that the docgen --check agreement leg must "
                "refuse -- with no field there is no value to drift away from "
                "the runtime-canonical shape. "
                f"HOW: diff {flavor_file} against the shipped "
                "nWave/flavors/atdd_pure.yaml. If the field was RENAMED there, "
                "update this method's regex to the new name. If the field is "
                "GENUINELY gone (no flavor declares a delivery phase shape any "
                "more), the Layer-C agreement leg this scenario exercises is "
                "itself obsolete -- replace the defect and its gate-side check "
                "TOGETHER; do NOT keep drifting a field the runtime no longer "
                "cross-checks."
            )
        flavor_file.write_text(drifted, encoding="utf-8")
        self._defect_token = "deliver_phase_shape"

    # --- When: drive each gate through its REAL entry -------------------------

    def run_gate_against_clean_copy(self) -> None:
        self._before = self._capture_universe()
        self._clean_run = self._drive(self._require_gate())
        self._after = self._capture_universe()

    def run_gate_against_defective_copy(self) -> None:
        self._before = self._capture_universe()
        self._defect_run = self._drive(self._require_gate())
        self._after = self._capture_universe()

    # --- Then: teeth — refuses on defect, accepts on clean --------------------

    def assert_gate_refuses_naming_defect(self) -> None:
        run = self._defect_run
        assert run is not None, "the gate never ran against the defective copy"
        token = self._defect_token or NAKED_LITERAL_SENTINEL
        assert run.exit_code != 0, (
            "the guardrail gate ACCEPTED a working copy carrying the planted "
            f"defect ({token!r}) — the next mode shotgun-surgery is NOT yet "
            f"structurally refused.\n{run.transcript}"
        )
        assert token in run.output, (
            "the guardrail gate refused but did not NAME the offending "
            f"defect ({token!r}) in its output — a refusal the operator cannot "
            f"act on.\n{run.transcript}"
        )

    def assert_gate_accepts_clean_copy(self) -> None:
        run = self._clean_run
        assert run is not None, "the gate never ran against the clean copy"
        assert run.exit_code == 0, (
            "the guardrail gate REFUSED the clean, fully-declared working copy "
            "— a false positive that would block every honest edit "
            "(for Layer A this is the bare-`classic` / allow-marker accept "
            f"side of the pinned rule).\n{run.transcript}"
        )

    def assert_accepted_clean_baseline_before_defect(self) -> None:
        run = self._baseline_run
        assert run is not None and run.exit_code == 0, (
            "the guardrail did NOT accept the clean working copy before the "
            "defect was introduced — the refusal above proves nothing (the "
            "gate might refuse everything). For Layer A this also proves the "
            "bare-`classic` / allow-marker accept side of the pinned rule.\n"
            f"{run.transcript if run else '(never ran)'}"
        )

    def assert_gate_rewrites_nothing(self) -> None:
        assert self._before is not None and self._after is not None
        assert_state_delta(
            self._before,
            self._after,
            universe=set(self._before),
            expected={},  # fail-closed: the gate is a pure read
        )

    # --- Then: the wiring witness (no dormant gate CLI) -----------------------

    def assert_gate_wired_to_dispatcher_and_catalog(self) -> None:
        """The dormant-seam witness (D11 / S3): the gate is reachable via its
        real `des <gate-id>` subcommand (dispatcher-registry membership =
        indirect wiring) AND declared in the gate catalog (1:1 mirror). Layer C
        reuses the already-wired docgen entry, so its witness is the entry's
        own reachability (asserted by the clean/defect runs exiting non-2)."""
        gate = self._require_gate()
        if gate is GateUnderTest.LAYER_C_AGREEMENT:
            run = self._clean_run or self._defect_run or self._baseline_run
            assert run is not None and run.exit_code != 2, (
                "the Layer-C agreement check is not reachable through the real "
                f"docgen entry (argparse refused with exit 2).\n"
                f"{run.transcript if run else '(never ran)'}"
            )
            return
        gate_id = gate.value
        dispatch = self._des_help()
        assert gate_id in dispatch.output, (
            f"the {gate_id!r} gate is NOT reachable as a `des` subcommand — it "
            "is absent from the dispatcher registry, so wiring it as a DES "
            f"gate is incomplete (dormant CLI).\n{dispatch.transcript}"
        )
        catalog_text = (self._worktree / CATALOG_REL).read_text(encoding="utf-8")
        assert gate_id in catalog_text, (
            f"the {gate_id!r} gate is reachable via `des` but NOT declared in "
            "the gate catalog — the 1:1 dispatcher↔catalog mirror is broken "
            "(the shipped arch test would red)."
        )

    # --- internals ------------------------------------------------------------

    def _require_gate(self) -> GateUnderTest:
        assert self._gate is not None, "no gate selected"
        return self._gate

    def _drive(self, gate: GateUnderTest) -> _CliOutcome:
        if gate is GateUnderTest.LAYER_C_AGREEMENT:
            # Write-then-check (the slice-02 pattern): the write pass generates
            # the reference pages so `--check`'s page-staleness leg passes,
            # isolating the NEW agreement leg (resolver-default == flavor-default
            # AND deliver_phase_shape == runtime canonical phases) as the only
            # thing that can fail. At RED the agreement leg is unimplemented, so
            # the clean baseline accepts (exit 0) and a phase-shape drift is NOT
            # refused — the RED AssertionError fires in Then.
            self._docgen()
            return self._docgen("--check")
        return self._des(gate.value, "--root", str(self._worktree))

    def _des(self, *args: str) -> _CliOutcome:
        exit_code, stdout, stderr = run_cli_in_process(
            list(args),
            cwd=REPO_ROOT,
        )
        return _CliOutcome(exit_code, stdout, stderr)

    def _des_help(self) -> _CliOutcome:
        return self._des("--help")

    def _docgen(self, *args: str) -> _CliOutcome:
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--root",
                str(self._worktree),
                "--output-dir",
                str(self._worktree / "docs" / "reference"),
                *args,
            ],
            cwd=REPO_ROOT,
            main=docgen.main,
        )
        return _CliOutcome(exit_code, stdout, stderr)

    def _write_clean_locus_probe(self) -> None:
        probe = self._worktree / _CLEAN_LOCUS_PROBE_REL
        probe.parent.mkdir(parents=True, exist_ok=True)
        benign = "\n".join(BENIGN_CLASSIC_SAMPLES)
        probe.write_text(
            "---\nname: nw-slice05-locus-probe\n"
            "description: clean locus probe authored by the slice-05 fixture\n---\n"
            "# nw-slice05-locus-probe\n\n"
            f"An explicit, marked mode reference: atdd_pure {ALLOW_MARKER}\n\n"
            f"{benign}\n",
            encoding="utf-8",
        )

    def _flavor_path(self, flavor: WorkflowFlavor) -> Path:
        return self._worktree / FLAVORS_REL / f"{flavor.value}.yaml"

    def _drop_required_field(self) -> str:
        flavor_file = self._flavor_path(WorkflowFlavor.ATDD_PURE)
        text = flavor_file.read_text(encoding="utf-8")
        stripped = re.sub(
            r"^descriptor:.*?(?=^[a-z_]+:)",
            "",
            text,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )
        if stripped == text:  # fixture integrity, not SUT behaviour
            raise RuntimeError(
                f"WHAT: working registry {flavor_file} carries no top-level "
                "`descriptor:` field to strip. "
                "WHY: this plants the MISSING_REQUIRED_FIELD defect that the "
                "Layer-B completeness gate (src/des/cli/"
                "mode_registry_completeness.py, _REQUIRED_FIELDS) must refuse "
                "-- without the field present first there is nothing to strip. "
                f"HOW: diff {flavor_file} against the shipped "
                "nWave/flavors/atdd_pure.yaml. If `descriptor` was RENAMED "
                "there, update this method's regex. If `descriptor` is "
                "GENUINELY no longer in _REQUIRED_FIELDS (the schema dropped "
                "the requirement), strip a DIFFERENT still-required field from "
                "that list instead; do NOT keep stripping a field the gate no "
                "longer requires."
            )
        flavor_file.write_text(stripped, encoding="utf-8")
        return "descriptor"

    def _introduce_two_defaults(self) -> str:
        # Only ATDD_PURE ships, so "two defaults" cannot be planted by iterating
        # the real registry — one file cannot contradict itself. This defect
        # FABRICATES a second file under the fixture-only CLASSIC identity: a
        # byte-copy of the shipped flavor with `flavor_id` renamed, so two files
        # legally declare `default: true` and the gate has a real pair to count.
        atdd_pure_file = self._flavor_path(WorkflowFlavor.ATDD_PURE)
        classic_file = self._flavor_path(WorkflowFlavor.CLASSIC)
        classic_file.write_text(
            atdd_pure_file.read_text(encoding="utf-8").replace(
                "flavor_id: atdd_pure", "flavor_id: classic", 1
            ),
            encoding="utf-8",
        )
        return "default"

    def _name_nonexistent_agent(self) -> str:
        ghost = "nw-slice05-ghost-agent"
        flavor_file = self._flavor_path(WorkflowFlavor.ATDD_PURE)
        text = flavor_file.read_text(encoding="utf-8")
        if "skill_load_set:" not in text:  # fixture integrity
            raise RuntimeError(
                f"WHAT: working registry {flavor_file} carries no top-level "
                "`skill_load_set:` key. "
                "WHY: this plants the SKILL_LOAD_SET_NAMES_NONEXISTENT_AGENT "
                "defect (a ghost-agent row) that the Layer-B completeness gate "
                "must refuse -- without the key there is no block to insert the "
                "ghost row into. "
                f"HOW: diff {flavor_file} against the shipped "
                "nWave/flavors/atdd_pure.yaml. If the key was RENAMED there, "
                'update the literal `"skill_load_set:"` check and the '
                "insertion point in `_name_nonexistent_agent`. If the key is "
                "GENUINELY gone (agent-to-skill direction moved elsewhere), "
                "this defect can no longer be planted here -- replace the "
                "scenario and the gate check it exercises TOGETHER; do NOT "
                "rename the key check onto a structure that no longer exists."
            )
        row = f"  {ghost}:\n    conditional: []\n"
        flavor_file.write_text(
            text.replace("skill_load_set:\n", f"skill_load_set:\n{row}", 1),
            encoding="utf-8",
        )
        return ghost

    def _capture_universe(self) -> dict[str, str]:
        """Port-exposed observables only (Mandate 8): the two registry file
        texts + the locus-probe asset text + the catalog text. The gates are
        pure reads; the empty-expected delta proves they rewrite nothing."""
        return {
            "registry.atdd_pure": self._flavor_path(WorkflowFlavor.ATDD_PURE).read_text(
                encoding="utf-8"
            ),
            "asset.locus_probe": (self._worktree / _CLEAN_LOCUS_PROBE_REL).read_text(
                encoding="utf-8"
            ),
            "catalog.gates": (self._worktree / CATALOG_REL).read_text(encoding="utf-8"),
        }


# DSL emergence (the SSOT-via-Types-Services-DSL mandate): one typed-parameter
# dispatch table over the named defects — not one method per literal.
_DEFECT_INTRODUCERS = {
    RegistryCompletenessDefect.MISSING_REQUIRED_FIELD: (
        GuardrailGateComposition._drop_required_field
    ),
    RegistryCompletenessDefect.TWO_DEFAULTS: (
        GuardrailGateComposition._introduce_two_defaults
    ),
    RegistryCompletenessDefect.SKILL_LOAD_SET_NAMES_NONEXISTENT_AGENT: (
        GuardrailGateComposition._name_nonexistent_agent
    ),
}
