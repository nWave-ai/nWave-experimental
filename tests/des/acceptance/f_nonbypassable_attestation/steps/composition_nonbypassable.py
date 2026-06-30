"""Composition root for the f-nonbypassable-attestation ATs.

DRIVING PORTS (Mandate-13 driving-port-only):
  * Done-gate (CT-1/2/4/5/6/7, AT-A4): the REAL ``verify_deliver_integrity.main``
    entry point, driven via Layer-3 composition (``main([... ,"--repo",root,
    "--feature-id",fid])``). The observable is the process EXIT CODE (the
    GateVerdict projection) + the printed machine-readable record names. No
    production done-gate logic is re-implemented in the step bodies.
  * Bypass-debt write (CT-3, AT-A5): the REAL shipped PreToolUse/Bash spine
    hook ``scripts.hooks.spine_ledger_pre_commit_hook``, driven via Layer-3
    subprocess on a ``git commit --no-verify`` command line. The observable is
    the ``SliceCommitBypassed`` record the hook appends to the real ledger.

PRECONDITION ARMING (Given steps): the ledger fixture is seeded through the REAL
production writer ``AtCompletionLedger.append_gate_event`` /
``append_feature_end_event`` so seeded records carry a valid ``seq`` +
``record_hash`` and the done-gate's M7 fail-closed integrity read PASSES on the
fixture. This is precondition construction (the SUT's input STATE), never the
SUT itself, and never the EXPECTED OUTPUT (Critical Rule 7: no fixture theater --
the records being asserted by the done-gate are the records DELIVER must teach
the cycle/hook to write, not records the fixture pre-bakes for the assertion).

DISTINCT-FIXTURE-PER-VERDICT discipline: every verdict case (PASS vs FAIL vs
INDETERMINATE) is produced by a GENUINELY DIFFERENT ledger / slice-plan / git
state, never by a different assertion over a byte-identical fixture (§22.0
DISTILL-review gap). The cause-discriminator assertions read the printed cause
fragment so two INDETERMINATE paths (unreconciled bypass-debt vs absent
git-trailer-port) are told apart.

ACTIVE-RED scaffold (atdd_pure -- NOT @skip): at HEAD the done-gate's `required`
set does NOT include ``FullSuiteLegRan`` (CT-5), the spine hook does NOT write
``SliceCommitBypassed`` on ``--no-verify`` (CT-3/4), the done-gate does NOT
assert slice-plan-all-shipped (CT-6), and no ``dormant`` schema key exists
(AT-A1). Each step therefore RUNS and raises a semantic ``AssertionError`` --
never a collection / import / setup error. DELIVER makes them GREEN by
implementing the production code.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import yaml

from tests.common.in_process_cli import run_hook_in_process

from .domain_types_nonbypassable import (
    BypassDebtState,
    CommitKind,
    DoneVerdict,
    FeatureEndRecord,
    FullSuiteOutcome,
    GitState,
    SlicePlanStatus,
)


# tests/des/acceptance/f_nonbypassable_attestation/steps/<this file>
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The full set of feature-end records the done-gate `required` set demands AFTER
# slice-01 adds the full-suite leg. A complete ledger carries all of these.
_ALL_REQUIRED: tuple[FeatureEndRecord, ...] = (
    FeatureEndRecord.COVERAGE_MAP_VERIFIED_AT_DELIVER_EXIT,
    FeatureEndRecord.COVERAGE_MAP_VERIFIED_AT_DISTILL_EXIT,
    FeatureEndRecord.E_BATCH_REFACTOR_COMPLETED,
    FeatureEndRecord.ENVIRONMENTAL_E2E_GATE_RAN,
    FeatureEndRecord.FEATURE_END_REVIEW_VERDICT,
    FeatureEndRecord.WALKING_SKELETON_GATE_RAN,
    FeatureEndRecord.FULL_SUITE_LEG_RAN,
)


_CATALOG_PATH = REPO_ROOT / "nWave" / "gates" / "_catalog.yaml"
_SCHEMA_PATH = REPO_ROOT / "nWave" / "gates" / "_schema.yaml"


def _shipped_schema_accepts_dormant_key() -> bool:
    """Whether the shipped GateContract schema PERMITS an optional `dormant` key.

    Reads ``nWave/gates/_schema.yaml`` as DATA. The schema accepts the dormant key
    iff ``GateContract`` either relaxes ``additionalProperties`` OR declares a
    ``dormant`` property. At HEAD it declares neither -> returns False (active-RED).
    """
    doc = yaml.safe_load(_SCHEMA_PATH.read_text(encoding="utf-8"))
    defs = doc.get("$defs", {})
    gate_contract = defs.get("GateContract", {})
    properties = gate_contract.get("properties", {})
    additional = gate_contract.get("additionalProperties", True)
    return "dormant" in properties or additional is not False


# The slice-04 catalog<->wiring coherence check is an ARCH-TIER pure function over
# shipped DATA (DESIGN Reuse Analysis :141 "the coherence check is the tests/build/
# arch test ... catalogued-gate subset of wired-or-dormant", Driving Ports :205
# "pytest tests/build/test_catalog_gate_wiring.py"). It is NOT a production CLI
# module -- the catalog (33 gates) carries no coherence gate. The .feature
# companion drives the SAME shipped reducer the arch test pins, over the SAME
# shipped artifacts (the real _catalog.yaml + firing surfaces). Mandate-13
# protocol-driver: assert over the SHIPPED artifacts, never a fabricated oracle.
from tests.build.f_nonbypassable_attestation.test_arch_catalog_gate_wiring import (
    _firing_surface_text as _arch_firing_surface_text,
)
from tests.build.f_nonbypassable_attestation.test_arch_catalog_gate_wiring import (
    _gate_host_visibility as _arch_gate_host_visibility,
)
from tests.build.f_nonbypassable_attestation.test_arch_catalog_gate_wiring import (
    coherence_offenders as _arch_coherence_offenders,
)


def _live_catalog_offenders() -> frozenset[str]:
    """The catalogued gate-ids NEITHER wired NOR dormant, over the REAL artifacts.

    Drives the SHIPPED coherence reducer (``coherence_offenders``, the SUT the
    slice-04 arch test pins) over the real ``_catalog.yaml`` + firing surfaces. A
    non-empty result is the authored-but-unwired failure class. Indirect wiring
    (operator-CLI / git-hook / live-hook module reference) counts per S3.
    """
    doc = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8"))
    gates = doc["gates"]
    host_visibility = {
        g["gate_id"]: _arch_gate_host_visibility(g["gate_id"]) for g in gates
    }
    return frozenset(
        _arch_coherence_offenders(
            gates,
            firing_text=_arch_firing_surface_text(),
            host_visibility=host_visibility,
        )
    )


def _terminal_backstop_auto_fires(service_factory: object) -> bool:
    """Whether a harness-neutral declare-done backstop auto-fires the done-gate (CT-2).

    The DDD-2 surface set: at HEAD the ONLY auto-fire is the ``F_FINAL_REVIEW``
    SubagentStop shim (``_handle_feature_end_gate``). The slice adds a
    harness-neutral declare-done backstop (a Python git pre-push hook installed by
    the DES plugin invoking ``des verify-integrity``) that fires INDEPENDENT of
    ``F_FINAL_REVIEW``. We witness the wiring by asking the shipped hook-definition
    registry whether a declare-done / pre-push backstop entry naming
    ``verify_deliver_integrity`` / ``verify-integrity`` is registered. Absent at
    HEAD -> returns False (active-RED). Reaching the seam via the registry counts
    as INDIRECT wiring (S3 framing-attack: registry reach is valid witnessing).
    """
    from scripts.shared import hook_definitions

    text = "\n".join(
        str(getattr(hook_definitions, name))
        for name in dir(hook_definitions)
        if name.isupper()
    )
    # The backstop must name the portable done-gate core it reuses (DDD-7 thin
    # shim) on a declare-done / pre-push surface. Both tokens required so a mere
    # mention of the CLI elsewhere does not false-positive.
    return ("verify-integrity" in text or "verify_deliver_integrity" in text) and (
        "pre-push" in text or "pre_push" in text or "declare-done" in text
    )


@dataclass
class AttestationComposition:
    """Drives the REAL done-gate / spine-hook through the production composition root."""

    _feature_id: str = "f-nonbypassable-attestation-probe"
    _project_root: Path | None = None
    _exit_code: int | None = None
    _stdout: str = ""
    _git_state: GitState = GitState.PRESENT

    # ---- ledger seeding (precondition arming via the PRODUCTION writer) ------

    def _ledger(self):
        """Build the REAL AtCompletionLedger via its production constructor.

        Used ONLY to ARRANGE the input ledger state (Given). The done-gate (SUT)
        is driven separately through its own real entry point.
        """
        assert self._project_root is not None
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

        return AtCompletionLedger(
            project_root=self._project_root, feature_id=self._feature_id
        )

    def _seed_records(self, records: tuple[FeatureEndRecord, ...]) -> None:
        ledger = self._ledger()
        for rec in records:
            if rec in (
                FeatureEndRecord.E_BATCH_REFACTOR_COMPLETED,
                FeatureEndRecord.FEATURE_END_REVIEW_VERDICT,
            ):
                ledger.append_feature_end_event(rec.value, feature_id=self._feature_id)
            else:
                ledger.append_gate_event(
                    rec.value, slice_id="", feature_id=self._feature_id
                )

    def _seed_event(self, event: str, slice_id: str = "") -> None:
        self._ledger().append_gate_event(
            event, slice_id=slice_id, feature_id=self._feature_id
        )

    # ---- shared GIVEN substrate ---------------------------------------------

    def use_project_root(self, root: Path) -> None:
        self._project_root = root
        (root / ".nwave").mkdir(parents=True, exist_ok=True)

    def write_atdd_pure_config(self) -> None:
        assert self._project_root is not None
        cfg = self._project_root / ".nwave" / "config.yaml"
        cfg.write_text("workflow:\n  mode: atdd_pure\n", encoding="utf-8")

    def init_git_repo(self) -> None:
        assert self._project_root is not None
        subprocess.run(
            ["git", "init", "-q"], cwd=self._project_root, check=True, timeout=30
        )
        subprocess.run(
            ["git", "config", "user.email", "probe@nwave.ai"],
            cwd=self._project_root,
            check=True,
            timeout=30,
        )
        subprocess.run(
            ["git", "config", "user.name", "probe"],
            cwd=self._project_root,
            check=True,
            timeout=30,
        )
        self._git_state = GitState.PRESENT

    def remove_git_repo(self) -> None:
        """The non-work-tree state: the trailer port degrades LOUD (CT-7/AT-A4)."""
        self._git_state = GitState.ABSENT

    def commit_slice_trailer(self, slice_id: str) -> None:
        """Make a real commit carrying a ``Slice-Id: <slice_id>`` trailer.

        Required when a fixture seeds a ``SliceCommitVerified`` record: the
        done-gate then DEMANDS that slice's ``Slice-Id:`` trailer be
        cross-checkable in the real git history (verify_deliver_integrity
        `verified` → `shipped` reconciliation). Without this commit the verified
        slice has no cross-checkable trailer and the gate refuses for the wrong
        reason (a reconciliation gap, not the business gap under test).
        """
        assert self._project_root is not None
        (self._project_root / f"{slice_id}.txt").write_text("work\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"], cwd=self._project_root, check=True, timeout=30
        )
        subprocess.run(
            ["git", "commit", "-q", "-m", f"feat: {slice_id}\n\nSlice-Id: {slice_id}"],
            cwd=self._project_root,
            check=True,
            timeout=30,
        )

    def _create_empty_ledger_file(self) -> None:
        """Create the AT-completion ledger FILE with zero feature-end records.

        The incident state (CT-1) is "DELIVER ran but ``des feature-end run``
        never did": the ledger FILE exists (DELIVER wrote slice telemetry) but
        carries NO feature-end records. This is distinct from a wholly-absent
        ledger (which is the "DELIVER never ran either" integrity-violation path).
        We arm the incident state by appending one benign slice telemetry event
        through the production writer, so the gate emits the
        ``FeatureEndCycleIncomplete`` refusal that NAMES the missing records,
        not the ledger-missing integrity violation.
        """
        self._ledger().append_gate_event(
            "WorkflowPhaseCompletedDistill",
            slice_id="slice-01",
            feature_id=self._feature_id,
        )

    def write_slice_plan(self, statuses: tuple[SlicePlanStatus, ...]) -> None:
        """Write a feature-delta Slice-Plan + the delivered-ness artefacts (CT-6).

        DDD-5 is filesystem-derived (Ale 2026-06-15, "confermo: ledger-derived,
        not the gameable Status text"): a planned slice is DELIVERED iff its
        ``@slice-NN @feature-{id}`` ``.feature`` file exists under ``tests/``
        (``feature_files_for_slice``), NOT iff a `Status` cell reads `shipped`.
        So the fixture models the two cases by ARTEFACT PRESENCE: a SHIPPED slice
        gets a real ``@slice-NN``-tagged ``.feature`` file; a PENDING slice gets
        NONE (the truncated case -- declared in the plan, no acceptance test on
        disk). The `Status` text is still written (the table stays 5-column,
        gate-safe) but the done-gate no longer reads it.
        """
        assert self._project_root is not None
        rows = "\n".join(
            f"| slice-0{i + 1} | deliver value {i + 1} | {s.value} | @x | because |"
            for i, s in enumerate(statuses)
        )
        delta = (
            f"# Feature Delta: {self._feature_id}\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|---|---|---|---|---|\n"
            f"{rows}\n"
        )
        path = (
            self._project_root
            / "docs"
            / "feature"
            / self._feature_id
            / "feature-delta.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(delta, encoding="utf-8")

        tests_dir = self._project_root / "tests" / self._feature_id
        tests_dir.mkdir(parents=True, exist_ok=True)
        for i, status in enumerate(statuses):
            slice_id = f"slice-0{i + 1}"
            if status is SlicePlanStatus.SHIPPED:
                (tests_dir / f"{slice_id}.feature").write_text(
                    f"@feature-{self._feature_id} @{slice_id}\n"
                    f"Feature: {slice_id} acceptance\n",
                    encoding="utf-8",
                )

    def write_empty_slice_plan(self) -> None:
        """Write a feature-delta whose Slice Plan is header-only (zero data rows).

        The canonical heading + 5-column header are present (so the parser finds a
        well-formed plan table), but there are NO slice rows. ``_plan_table_rows``
        returns the header row alone; the row loop walks nothing; the assertion
        returns [] -- the C3-ZERO terminal branch. No ``.feature`` files are
        written (there are no slices to deliver).
        """
        assert self._project_root is not None
        delta = (
            f"# Feature Delta: {self._feature_id}\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|---|---|---|---|---|\n"
        )
        path = (
            self._project_root
            / "docs"
            / "feature"
            / self._feature_id
            / "feature-delta.md"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(delta, encoding="utf-8")

    # ---- slice-01 GIVEN: feature-end completeness ---------------------------

    def given_no_feature_end_records(self) -> None:
        """A ledger that ran NO feature-end cycle -- zero required records (CT-1).

        The incident state: DELIVER ran (the ledger FILE exists with slice
        telemetry) but ``des feature-end run`` never did (no feature-end records).
        The done-gate must refuse on the ABSENCE of the required records, naming
        them (``FeatureEndCycleIncomplete``) -- not on a wholly-missing ledger.
        """
        self._create_empty_ledger_file()

    def given_complete_feature_end_records(self) -> None:
        """A ledger carrying EVERY required record incl. the full-suite leg (CT-1 PASS arm)."""
        self._seed_records(_ALL_REQUIRED)

    def given_feature_end_records_except_full_suite(self) -> None:
        """Every required record EXCEPT FullSuiteLegRan -- the hidden-RED hole (CT-5)."""
        self._seed_records(
            tuple(
                r for r in _ALL_REQUIRED if r is not FeatureEndRecord.FULL_SUITE_LEG_RAN
            )
        )

    def given_full_suite_outcome(self, outcome: FullSuiteOutcome) -> None:
        """Seed the feature-end records reflecting the full-suite leg outcome (CT-5).

        GREEN  -> the cycle emitted FullSuiteLegRan alongside the other records.
        ABSENT -> the cycle emitted FullSuiteLegNotApplicable (NA reconciles).
        RED    -> CycleRefusal: the cycle emitted NO records at all (incl. no
                  FeatureEndReviewVerdict) -- record-ABSENCE is the refusal cause.
        """
        base = tuple(
            r
            for r in _ALL_REQUIRED
            if r
            not in (
                FeatureEndRecord.FULL_SUITE_LEG_RAN,
                FeatureEndRecord.FULL_SUITE_LEG_NOT_APPLICABLE,
            )
        )
        if outcome is FullSuiteOutcome.GREEN:
            self._seed_records(base + (FeatureEndRecord.FULL_SUITE_LEG_RAN,))
        elif outcome is FullSuiteOutcome.ABSENT:
            self._seed_records(base + (FeatureEndRecord.FULL_SUITE_LEG_NOT_APPLICABLE,))
        else:  # RED -> CycleRefusal -> NO records emitted
            pass

    # ---- slice-02 GIVEN: bypass-debt ----------------------------------------

    def given_complete_ledger_with_bypass_debt(self, state: BypassDebtState) -> None:
        """A complete feature-end ledger PLUS a bypass-debt in the given state (CT-4).

        DISTINCT fixtures per verdict case:
          NONE         -> complete ledger, no bypass record           -> PASS (0)
          UNRECONCILED -> complete ledger + SliceCommitBypassed only  -> INDETERMINATE (4)
          RECONCILED   -> complete ledger + SliceCommitBypassed
                          + matching SliceCommitVerified              -> PASS (0)
        """
        self._seed_records(_ALL_REQUIRED)
        if state is BypassDebtState.UNRECONCILED:
            # No SliceCommitVerified -> `verified` empty -> git not demanded; the
            # ONLY gap is the done-gate not yet reading bypass-debt (the business
            # reason). A git repo is unnecessary and would not change the verdict.
            self._seed_event("SliceCommitBypassed", slice_id="slice-99")
        elif state is BypassDebtState.RECONCILED:
            # SliceCommitVerified makes `verified` non-empty -> the done-gate
            # DEMANDS a cross-checkable Slice-Id: trailer in real git history.
            # We init git + commit the matching trailer so the reconciliation
            # demand is satisfiable; the ONLY remaining gap is the done-gate not
            # yet treating a reconciled bypass-debt as clearable (the business
            # reason DELIVER will close), NOT a git-absent setup failure.
            self.init_git_repo()
            self.commit_slice_trailer("slice-99")
            self._seed_event("SliceCommitBypassed", slice_id="slice-99")
            self._seed_event("SliceCommitVerified", slice_id="slice-99")

    # ---- slice-01/03 GIVEN: slice-plan all-shipped --------------------------

    def given_complete_ledger_and_slice_plan(
        self, statuses: tuple[SlicePlanStatus, ...]
    ) -> None:
        """A complete feature-end ledger + a slice-plan in the given Status mix (CT-6).

        DISTINCT fixtures: an all-`shipped` plan clears; a plan with any non-shipped
        row is REFUSED (FAIL) even though the ledger itself is complete.
        """
        self._seed_records(_ALL_REQUIRED)
        self.write_slice_plan(statuses)

    def given_complete_ledger_and_empty_slice_plan(self) -> None:
        """A complete feature-end ledger + a header-only Slice Plan (C3-ZERO).

        The empty iterative surface: a feature-delta whose Slice Plan has its
        canonical heading + column header but NO data rows. The shipped
        ``_undelivered_slice_plan_slices`` walks zero rows -> returns [] -> the
        done-gate must NOT manufacture a truncated-feature refusal. Distinct
        fixture from the all-shipped case (which has rows): here the iterative
        surface is empty, exercising the terminal branch the row loop skips.
        """
        self._seed_records(_ALL_REQUIRED)
        self.write_empty_slice_plan()

    # ---- slice-03 GIVEN: git-absent degrade-LOUD (CT-7 / AT-A4) -------------

    def given_complete_ledger_on_non_worktree(self) -> None:
        """A complete ledger that DEMANDS git reconciliation, on a non-work-tree.

        DISTINCT fixture per the CT-7 INDETERMINATE case: a ``SliceCommitVerified``
        record makes the gate's ``verified`` set non-empty, so the gate DEMANDS a
        cross-checkable trailer history. ``_project_root`` is a tmp dir that was
        NEVER ``git init``-ed -> the ``CommitTrailerReadPort`` returns the LOUD
        ``Indeterminate`` -> the gate refuses exit-4 INDETERMINATE (degrade-LOUD,
        AD-21/24), never a silent empty-history PASS. The done-gate WHEN step does
        not init git, so the absence is genuine.
        """
        self._seed_records(_ALL_REQUIRED)
        self._seed_event("SliceCommitVerified", slice_id="slice-01")
        self.remove_git_repo()

    # ---- slice-02 GIVEN: in-flight feature precondition (single-ledger rule) -

    def seed_single_in_flight_ledger(self) -> None:
        """Seed exactly ONE in-flight AT-completion telemetry ledger (CT-3 / AT-A5).

        The REAL world a ``--no-verify`` commit happens in: a feature is IN FLIGHT,
        so its per-feature ledger FILE exists under
        ``<root>/.nwave/telemetry/atdd-pure/<feature_id>.jsonl``. This is the SAME
        single-ledger precondition the production spine hook
        (``spine_ledger_pre_commit_hook._active_feature_id``) and the done-gate
        backstop (``des_declare_done_pre_push._active_feature_id``) require: exactly
        one ledger present -> THAT is the feature whose slice is being committed.

        Armed through the PRODUCTION writer (``AtCompletionLedger.append_gate_event``)
        with a benign slice-telemetry event, so the hook resolves the feature-id the
        SAME way production does -- never a hard-coded probe id divined from nothing.
        This is precondition construction (the SUT's input STATE), never the EXPECTED
        OUTPUT (Critical Rule 7: the SliceCommitBypassed record under assertion is the
        record DELIVER must teach the hook to WRITE, not a record the fixture bakes).
        """
        self._ledger().append_gate_event(
            "WorkflowPhaseCompletedDeliver",
            slice_id="slice-99",
            feature_id=self._feature_id,
        )

    # ---- slice-02 GIVEN: AT-A5 emitter-wired probe --------------------------

    def given_git_worktree_with_no_verify_command(self) -> None:
        """A real git work-tree + an LLM-style --no-verify commit command (AT-A5).

        The self-application probe (Principle 13): proves the bypass-debt EMITTER
        is actually wired into the real PreToolUse/Bash surface -- not merely that
        a record type exists. Armed identically to the CT-3 write path: a real git
        work-tree PLUS the single in-flight telemetry ledger the hook resolves the
        feature-id through (the sanctioned single-ledger rule); the When drives the
        REAL shipped hook.
        """
        self.init_git_repo()
        self.seed_single_in_flight_ledger()

    # ---- slice-04 GIVEN: catalog<->wiring coherence (AT-A1) -----------------

    def use_shipped_catalog_and_schema(self) -> None:
        """Point the coherence check at the REAL shipped catalog + schema (AT-A1).

        The arch-tier check reads ``nWave/gates/_catalog.yaml`` +
        ``nWave/gates/_schema.yaml`` + the ``scripts/shared/hook_definitions.py``
        registry as DATA (no subprocess). The project root for these is the repo.
        """
        self._project_root = REPO_ROOT

    # ---- WHEN: drive the REAL terminal auto-fire backstop (CT-2) ------------

    def when_done_declared_via_terminal_backstop(self) -> None:
        """Drive the REAL terminal declare-done backstop, not a manual CLI run (CT-2).

        CT-2 witnesses that the done-gate is auto-fired on the terminal action
        (the SubagentStop / pre-merge declare-done boundary), reusing the SAME
        ``verify_deliver_integrity`` core. At HEAD the only auto-fire surface is
        the ``F_FINAL_REVIEW`` SubagentStop shim; the harness-neutral declare-done
        backstop the slice adds is ABSENT, so this drive RED-fails: the backstop
        entry point does not yet exist / does not auto-fire the done-gate over an
        incomplete ledger. GREEN once DELIVER ships the backstop surface (DDD-2).
        """
        assert self._project_root is not None
        self.write_atdd_pure_config()
        # Drive the declare-done backstop module the slice ships. It is ABSENT at
        # HEAD -> ImportError would be a BROKEN (not RED) classification, so the
        # composition asserts the backstop's observable contract directly: the
        # backstop MUST auto-fire the done-gate and PROPAGATE its veto. We probe
        # the contract through the REAL done-gate core the backstop reuses, then
        # assert the auto-fire wiring exists. The wiring claim is the active-RED
        # observable: at HEAD no terminal backstop fires the gate outside
        # F_FINAL_REVIEW, so the witnessed auto-fire surface count is zero.
        from des.adapters.drivers.hooks import service_factory  # real composition root

        self._terminal_backstop_fires = _terminal_backstop_auto_fires(service_factory)
        # Drive the gate core the backstop reuses so the propagated verdict is the
        # observable (the backstop must veto an incomplete ledger).
        self.when_done_is_declared()

    def then_terminal_backstop_auto_fired(self) -> None:
        """(CT-2) the terminal action auto-fired the done-gate (not a manual run)."""
        assert getattr(self, "_terminal_backstop_fires", False), (
            "declaring done on the terminal action MUST auto-fire the done-gate "
            "on a harness-neutral declare-done backstop (DDD-2), not only via a "
            "manual CLI run nor only on the F_FINAL_REVIEW SubagentStop return -- "
            "the incident's hand-dispatch never reached F_FINAL_REVIEW. No "
            f"declare-done backstop auto-fires the gate at HEAD. {self._observed()}"
        )

    # ---- WHEN: drive the REAL done-gate -------------------------------------

    def when_done_is_declared(self) -> None:
        """Drive the REAL verify_deliver_integrity.main entry point (Layer-3 composition)."""
        assert self._project_root is not None
        self.write_atdd_pure_config()
        from des.cli import verify_deliver_integrity

        argv = ["--repo", str(self._project_root), "--feature-id", self._feature_id]
        prev_cwd = Path.cwd()
        captured = StringIO()
        import contextlib

        try:
            os.chdir(self._project_root)
            with (
                contextlib.redirect_stdout(captured),
                contextlib.redirect_stderr(captured),
            ):
                self._exit_code = verify_deliver_integrity.main(argv)
        finally:
            os.chdir(prev_cwd)
        self._stdout = captured.getvalue()

    # ---- WHEN: drive the REAL spine-ledger PreToolUse/Bash hook --------------

    def when_slice_commit_issued(self, kind: CommitKind) -> None:
        """Drive the REAL shipped spine-ledger pre-commit hook on a git-commit cmd (CT-3).

        Feeds the production ``scripts.hooks.spine_ledger_pre_commit_hook`` the
        PreToolUse JSON payload it expects (``{"tool_input":{"command": ...}}``)
        exactly as the shipped ``_BASH_SPINE_LEDGER_PRE_COMMIT_HOOK`` does, in a
        REAL git work-tree -- Layer-3 subprocess, the real driving surface.
        """
        assert self._project_root is not None
        self.write_atdd_pure_config()
        payload = json.dumps(
            {"tool_input": {"command": f"{kind.value} -m 'slice-99: work'"}}
        )
        from scripts.hooks import spine_ledger_pre_commit_hook

        # In-process analogue of the stdin-protocol hook fork: the hook's no-argv
        # ``main`` reads its PreToolUse JSON from ``sys.stdin`` and resolves its
        # target root from ``Path.cwd()`` -- run_hook_in_process feeds the SAME
        # payload on stdin and chdir's to the work-tree, faithful to the process
        # boundary. PYTHONPATH=REPO_ROOT is mirrored on ``os.environ`` (restored
        # in finally) so the gate subprocess the hook spawns internally still
        # imports -- exactly what the old ``env=`` override gave the fork.
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(REPO_ROOT)
        try:
            exit_code, stdout, stderr = run_hook_in_process(
                spine_ledger_pre_commit_hook.main,
                stdin_text=payload,
                cwd=self._project_root,
            )
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._exit_code = exit_code
        self._stdout = stdout + stderr

    def bypass_debt_records(self) -> list[str]:
        """The slice ids carrying a SliceCommitBypassed record in the real ledger."""
        ledger = self._ledger()
        return [
            str(record.get("slice_id"))
            for record in ledger.read_records(feature_id=self._feature_id)
            if record.get("event") == "SliceCommitBypassed"
        ]

    # ---- THEN: observable-surface readers -----------------------------------

    def verdict(self) -> DoneVerdict:
        assert self._exit_code is not None, "must drive the gate (When) before Then"
        return DoneVerdict(self._exit_code)

    def then_verdict_is(self, expected: DoneVerdict) -> None:
        assert self.verdict() is expected, (
            f"expected done-gate verdict {expected.name} (exit {expected.value}) "
            f"but got exit {self._exit_code}. {self._observed()}"
        )

    def then_cause_names(self, fragment: str) -> None:
        """Cause-discriminator: the printed verdict names THIS cause fragment.

        Tells two same-verdict paths apart (e.g. unreconciled bypass-debt vs
        absent git-trailer-port both yield INDETERMINATE).
        """
        assert fragment.lower() in self._stdout.lower(), (
            f"the done-gate verdict must name the cause fragment {fragment!r} so "
            f"a blocked developer learns WHY; it was absent. {self._observed()}"
        )

    def then_bypass_debt_recorded_for(self, slice_id: str) -> None:
        recorded = self.bypass_debt_records()
        assert slice_id in recorded, (
            f"a --no-verify slice-commit must leave an indelible SliceCommitBypassed "
            f"debt record for {slice_id!r} (never silent); recorded debt={recorded!r}. "
            f"{self._observed()}"
        )

    def then_no_bypass_debt_recorded(self) -> None:
        recorded = self.bypass_debt_records()
        assert not recorded, (
            f"a normal (verified) commit must leave NO bypass-debt record; "
            f"recorded={recorded!r}. {self._observed()}"
        )

    # ---- slice-04 GIVEN/WHEN/THEN: catalog<->wiring coherence (AT-A1, DDD-6) -

    # The coherence reducer's three inputs, STAGED by the Given step (arrange) and
    # consumed by the When step (act). For the live-catalog scenario the staged
    # inputs are the REAL shipped artifacts; for the synthetic scenarios they are
    # distinct per-verdict fixtures. The reducer itself is the SAME shipped SUT
    # (``coherence_offenders``) in every case (single SSOT, no reimplementation).
    _staged_gates: list[dict[str, str]] | None = None
    _staged_firing: str = ""
    _staged_host_visibility: dict[str, frozenset[str]] | None = None
    _use_live_catalog: bool = False

    def given_real_catalog_and_firing_surfaces(self) -> None:
        """Stage the REAL shipped catalog + firing surfaces as the reducer input."""
        self._use_live_catalog = True

    def given_catalogue_with_wired_and_orphan_gate(self) -> None:
        """Stage a distinct fixture: one wired gate + one orphan gate no hook fires."""
        self._stage_synthetic(
            [
                {"gate_id": "alpha-wired", "module": "des.cli.alpha_wired"},
                {"gate_id": "orphan-gate", "module": "des.cli.orphan_gate"},
            ],
            firing="gate_id: alpha-wired\ninvokes des.cli.alpha_wired\n",
            host_visibility={"alpha-wired": frozenset(), "orphan-gate": frozenset()},
        )

    def given_unwired_dormant_gate(self, rationale: str) -> None:
        """Stage a distinct fixture: one unwired gate carrying the given `dormant` rationale."""
        self._stage_synthetic(
            [
                {
                    "gate_id": "dozing-gate",
                    "module": "des.cli.dozing_gate",
                    "dormant": rationale,
                }
            ],
            firing="",
            host_visibility={"dozing-gate": frozenset()},
        )

    def given_gate_contract_carrying_dormant(self) -> None:
        """Stage the schema-validation arm. No state to stage: the When reads the
        REAL shipped ``_schema.yaml`` directly (the gate contract carrying the
        dormant key is the literal input the schema must accept). Present as an
        explicit Given so the Gherkin reads as arrange -> act -> assert."""

    def _stage_synthetic(
        self,
        gates: list[dict[str, str]],
        *,
        firing: str,
        host_visibility: dict[str, frozenset[str]],
    ) -> None:
        self._use_live_catalog = False
        self._staged_gates = gates
        self._staged_firing = firing
        self._staged_host_visibility = host_visibility

    def when_catalog_coherence_check_runs(self) -> None:
        """Drive the SHIPPED coherence reducer over the staged inputs (the act).

        Mandate-13 protocol-driver: the reducer is ``coherence_offenders`` -- the
        SAME shipped SUT the slice-04 arch test pins -- driven over the REAL
        ``_catalog.yaml`` + firing surfaces (live scenario) or the staged synthetic
        fixture. The observable is the offender set (gate-ids neither wired nor
        dormant). Indirect wiring (operator-CLI / git-hook / live-hook module
        reference) counts (S3).
        """
        self._wiring_offenders = (
            _live_catalog_offenders()
            if self._use_live_catalog
            else frozenset(
                _arch_coherence_offenders(
                    self._staged_gates or [],
                    firing_text=self._staged_firing,
                    host_visibility=self._staged_host_visibility or {},
                )
            )
        )

    def when_schema_validates_dormant_gate(self) -> None:
        """Validate a gate contract carrying a `dormant: <rationale>` key against
        the REAL shipped catalog schema (slice-04 CRITICAL-2 prerequisite).

        observable = whether the shipped ``_schema.yaml`` ACCEPTS the dormant key.
        At HEAD ``GateContract`` declares ``additionalProperties: false`` and has
        no ``dormant`` property -> the schema REJECTS it (active-RED). GREEN once
        DELIVER adds optional ``dormant: {type: string, minLength: 10}``.
        """
        self._schema_accepts_dormant = _shipped_schema_accepts_dormant_key()

    def then_schema_accepts_dormant(self) -> None:
        assert getattr(self, "_schema_accepts_dormant", False), (
            "the shipped gate-catalog schema (_schema.yaml GateContract) must "
            "permit an optional `dormant: <rationale>` key (CRITICAL-2) so a "
            "catalogued-but-unwired gate can be explicitly excused; at HEAD "
            "`additionalProperties: false` rejects it. GREEN once DELIVER extends "
            "the schema FIRST (slice-04 ordering)."
        )

    def then_no_gate_is_flagged(self) -> None:
        offenders = getattr(self, "_wiring_offenders", None)
        assert offenders == frozenset(), (
            "every catalogued gate must be wired into a live firing surface "
            "(flavor row / live-hook module reference / operator-direct cli|git-hook "
            "visibility -- indirect wiring counts, S3) OR marked `dormant: "
            f"<rationale>`; the coherence check flags: {sorted(offenders or [])}"
        )

    def then_the_offender_is_flagged_and_named(self, gate_id: str) -> None:
        offenders = getattr(self, "_wiring_offenders", None)
        assert offenders == frozenset({gate_id}), (
            f"an unwired, non-dormant catalogued gate must be FLAGGED and NAMED "
            f"(the authored-but-unwired class, DDD-6 / KPI-4); the check must name "
            f"exactly {gate_id!r}, got {sorted(offenders or [])}"
        )

    def then_the_gate_is_excused(self, gate_id: str) -> None:
        offenders = getattr(self, "_wiring_offenders", None)
        assert offenders is not None and gate_id not in offenders, (
            f"an unwired gate carrying a non-empty `dormant: <rationale>` must be "
            f"EXCUSED (the explicit escape, DDD-6); {gate_id!r} was still flagged "
            f"(offenders={sorted(offenders or [])})"
        )

    def then_the_gate_is_still_flagged(self, gate_id: str) -> None:
        offenders = getattr(self, "_wiring_offenders", None)
        assert offenders is not None and gate_id in offenders, (
            f"an unwired gate whose `dormant:` rationale is empty/whitespace must "
            f"STILL be FLAGGED -- the escape requires a REAL rationale; {gate_id!r} "
            f"was wrongly excused (offenders={sorted(offenders or [])})"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        return (
            f"exit={self._exit_code!r}; git={self._git_state.value}; "
            f"feature_id={self._feature_id!r}; root={self._project_root!r}; "
            f"stdout[:400]={self._stdout[:400]!r}"
        )
