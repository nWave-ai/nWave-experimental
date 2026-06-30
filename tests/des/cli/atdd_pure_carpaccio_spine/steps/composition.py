"""Composition root for the simplify-atdd-pure-carpaccio-spine acceptance set.

F-SIMPLIFY-ATDD-PURE-CARPACCIO-SPINE (Mandate-12 criteria 2-3, Pillar 3). Wires
the PRODUCTION simplified-spine surfaces against a tmp_path feature project.
Business logic (build a slice plan + feature tree of a given shape, invoke the
production CLI, read the ledger) lives here as the single source of truth;
step bodies delegate to ``CarpaccioSpineComposition`` methods and never inline
logic.

Layer 3 (subprocess / FS acceptance): the simplified-spine CLIs are the driving
ports; the real filesystem (tmp_path repo + AT-completion ledger) is the only
driven port. Sad paths are example-based (Mandate 11).

RED-scaffold note: slices 01-04 drive ``run_contract_gate``,
``verify_slice_commit_completeness``, the M-2 hook, and
``verify_deliver_integrity`` -- EXTEND targets that exist on master, so imports
resolve (no BROKEN); their slice-NN behaviours are RED (missing functionality,
Mandate 7) until the slice lands.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)

from .domain_types import (
    CommitRef,
    FeatureId,
    SliceTag,
)


# Repo root -- five-level-up parent of this file
# (tests/des/cli/atdd_pure_carpaccio_spine/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]


@dataclass(frozen=True)
class CliResult:
    """Observable result of one simplified-spine CLI invocation."""

    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class NewSpineResult:
    """Observable result of delivering one slice through the simplified spine.

    slice-04 dogfood proof: the port-exposed observables that demonstrate the
    park/reverify dance is gone -- a verification record, zero parked files,
    zero reverify invocations -- and, on the unverified-slice rows, whether the
    M-2 backstop refused the slice commit FROM WITHIN the flow.

    ``backstop_verdict`` is the structured single-line JSON verdict the M-2
    hook emitted during the flow's commit step (empty dict on the happy path,
    where the commit was allowed). ``slice_commit_refused`` reads that verdict:
    True iff the flow's commit step was refused by the involuntary backstop.
    """

    slice_commit_verified: bool
    parked_file_count: int
    reverify_invocations: int
    slice_commit_refused: bool
    backstop_verdict: dict[str, object]


class CarpaccioSpineComposition:
    """Production-wired composition root for the simplified-spine surfaces.

    Builds a tmp_path feature project (feature-delta with a slice plan, a
    `tests/` subtree, an AT-completion ledger), then drives the real
    simplified-spine CLIs as subprocesses -- exactly as the hand-orchestrator
    invokes them.
    """

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.feature_id: FeatureId = FeatureId("acceptance-fixture-feature")
        self.entering_slice: SliceTag = SliceTag("slice-01")
        # Whether the arranged contract-gate invocation declares --entering-slice
        # (the slice-not-declared malformed row omits it).
        self._declare_entering_slice: bool = True
        # The commit message the M-2 backstop inspects (slice-03 Outline);
        # set by arrange_backstop_commit per decision-table row.
        self._backstop_commit_message: str = self.slice_commit_message()

    # --- directory accessors -------------------------------------------------

    @property
    def feature_dir(self) -> Path:
        return self.project_root / "docs" / "feature" / self.feature_id

    @property
    def tests_dir(self) -> Path:
        """Where just-in-time DISTILL authors a slice's .feature file."""
        return self.project_root / "tests" / self.feature_id

    def _ledger(self) -> AtCompletionLedger:
        """The production AT-completion ledger -- the carpaccio-chain SSOT.

        The carpaccio chain (slice-03 predecessor check, M-2 backstop) reads
        ``SliceCommitVerified`` through ``AtCompletionLedger.verified_slices()``
        at ``.nwave/telemetry/atdd-pure/{feature_id}.jsonl`` and FAIL-CLOSES on
        any record missing the M7 ``seq`` / ``record_hash`` integrity fields.
        The AT therefore observes the seam the chain actually consumes -- a
        wrong substrate or an integrity-free record makes the AT genuinely RED.
        """
        return AtCompletionLedger(str(self.feature_id), self.project_root)

    @property
    def ledger_path(self) -> Path:
        """The AT-completion ledger path -- the SliceCommitVerified record store."""
        return self._ledger().ledger_path()

    # --- Given: provision the feature project --------------------------------

    def create_feature_project(self, feature_id: FeatureId) -> None:
        """Create an empty tmp_path feature project (delta + slice plan, no tests)."""
        self.feature_id = feature_id
        self.feature_dir.mkdir(parents=True, exist_ok=True)
        self.tests_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        # The feature-end reconciliation CLI (verify_deliver_integrity) branches
        # on `.nwave/config.yaml:workflow.mode`. The simplified carpaccio spine
        # is an atdd_pure feature -- without this marker the verifier takes the
        # classic roadmap.json branch and never reaches the DDD-10 reconciliation.
        config_dir = self.project_root / ".nwave"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )
        (self.feature_dir / "feature-delta.md").write_text(
            textwrap.dedent(
                """\
                # Feature delta -- acceptance fixture

                ## Wave: DISCUSS / [REF] Slice Plan

                | Slice | Value Statement | Status |
                |-------|-----------------|--------|
                | slice-01 | first thin slice | shipped |
                | slice-02 | second thin slice | shipped |
                """
            ),
            encoding="utf-8",
        )

    def set_entering_slice(self, slice_tag: SliceTag) -> None:
        """Record which slice the orchestrator is about to enter."""
        self.entering_slice = slice_tag

    def author_slice_feature_file(self, slice_tag: SliceTag) -> None:
        """Pre-place a slice's .feature file (a sibling already on disk)."""
        path = self.tests_dir / f"{slice_tag}.feature"
        path.write_text(
            f"@feature-{self.feature_id} @{slice_tag}\n"
            f"Feature: pre-existing {slice_tag} fixture\n",
            encoding="utf-8",
        )

    def _author_runnable_slice(self, name: str, slice_tag: str) -> None:
        """Author a GENUINELY collectable pytest-bdd slice in the tmp project.

        Writes a triplet under ``tests/{feature_id}/`` -- a ``.feature`` file
        carrying a real ``Scenario`` with steps, a ``test_*.py`` binding it via
        ``scenarios()``, and a step module whose ``@given/@when/@then`` resolve
        every step. ``pytest --collect-only`` over this triplet yields one real
        test node-id: that is what the M-1/M-8 floor must witness, not the mere
        presence of a ``@slice-NN`` tag in a scenario-less file.

        ``slice_tag`` is written verbatim onto the scenario tag line -- a
        malformed value (``slice-abc``) is authored as-is so the floor's
        slice-tag-intersection check sees a real, but non-matching, tag.
        """
        feature_path = self.tests_dir / f"{name}.feature"
        feature_path.write_text(
            textwrap.dedent(
                f"""\
                @feature-{self.feature_id}
                Feature: {name} runnable fixture

                  @{slice_tag}
                  Scenario: a genuinely collectable {name} scenario
                    Given a runnable fixture step
                    When the runnable fixture step is exercised
                    Then the runnable fixture step is observed
                """
            ),
            encoding="utf-8",
        )
        (self.tests_dir / f"test_{name}.py").write_text(
            textwrap.dedent(
                f"""\
                import pytest
                from pytest_bdd import given, when, then, scenarios

                pytestmark = pytest.mark.acceptance
                scenarios("{name}.feature")

                @given("a runnable fixture step")
                def _given():
                    pass

                @when("the runnable fixture step is exercised")
                def _when():
                    pass

                @then("the runnable fixture step is observed")
                def _then():
                    assert True
                """
            ),
            encoding="utf-8",
        )

    def _author_tagged_scenarioless_feature_file(self, name: str) -> None:
        """Author a feature file that RESOLVES + INTERSECTS but collects nothing.

        The file carries both ``@feature-{feature_id}`` (so the gate's
        ``_feature_tag_files`` resolver binds it) AND a file-level
        ``@{entering_slice}`` tag (so the M-8 slice-tag-intersection check
        passes) -- but it has NO ``Scenario`` body and there is NO bound
        ``test_*.py``. ``pytest --collect-only`` over its directory therefore
        genuinely yields ZERO runnable node-ids: the exact post-resolution
        vacuous-pass the M-1 floor (run_contract_gate line 405) must refuse.
        """
        path = self.tests_dir / f"{name}.feature"
        path.write_text(
            f"@feature-{self.feature_id} @{self.entering_slice}\n"
            f"Feature: {name} -- tagged but scenario-less, collects nothing\n",
            encoding="utf-8",
        )

    def _author_syntax_error_test_module(self, name: str) -> None:
        """Author a resolving feature plus a test module with a syntax error.

        The ``.feature`` file resolves and intersects the entering slice; the
        sibling ``test_*.py`` contains a deliberate Python syntax error, so
        ``pytest --collect-only`` over the scope directory exits with a
        collection error. The gate must convert that into a clean exit-2
        ``collection-failed`` refusal (run_contract_gate lines 397-403) -- never
        an escaping traceback.
        """
        self._author_tagged_scenarioless_feature_file(f"{name}_feature")
        (self.tests_dir / f"test_{name}.py").write_text(
            "def broken(  # deliberate syntax error -- collection must fail\n",
            encoding="utf-8",
        )

    def author_collected_feature_tests(self, file_count: int = 1) -> None:
        """Author ``file_count`` genuinely collectable feature-scoped slices.

        slice-01 happy-path arrangement: ``file_count`` runnable ``.feature``
        files, all under the feature id, all tagged for the entering slice.
        With ``file_count > 1`` this exercises C3 -- the gate must UNION the
        slice tags across every one of a feature's ``.feature`` files.
        """
        for index in range(file_count):
            self._author_runnable_slice(
                f"collectable_{index:02d}", str(self.entering_slice)
            )

    def arrange_vacuous_invocation(self, outcome: object) -> None:
        """Arrange a feature-scoped invocation that trips the M-1/M-8 floor.

        slice-01 negative arrangement (Mandate 11, example-based). Each variant
        must be refused as ``malformed`` (exit 2) -- never a vacuous pass:

        * ZERO_COLLECTED      -- no test under the feature id;
        * EMPTY_INTERSECTION  -- a collectable test tagged for another slice;
        * MALFORMED_SLICE_TAG -- a collectable test whose slice tag is
          malformed (``@slice-abc``), so the floor's real-collection check
          finds no well-formed intersecting tag;
        * SLICE_NOT_DECLARED  -- a genuinely collectable feature, but the CLI
          is invoked without ``--entering-slice`` (the declared MalformedInput
          path -- C6a);
        * ZERO_NODE_IDS       -- a tagged feature file that RESOLVES and passes
          the M-8 slice-tag intersection, but genuinely collects zero runnable
          node-ids (no Scenario, no bound test module) -- the core M-1 floor;
        * COLLECTION_FAILED   -- a feature whose test module has a Python syntax
          error, so feature-scoped pytest collection fails and the gate must
          refuse cleanly rather than crash.
        """
        from .domain_types import ContractGateOutcome

        self._declare_entering_slice = True
        if outcome == ContractGateOutcome.ZERO_COLLECTED:
            return  # leave the tests dir empty -- no .feature resolves
        if outcome == ContractGateOutcome.MALFORMED_SLICE_TAG:
            self._author_runnable_slice("malformed_tagged", "slice-abc")
            return
        if outcome == ContractGateOutcome.SLICE_NOT_DECLARED:
            # A well-formed, collectable feature -- the malformity is the
            # MISSING --entering-slice flag, not the collection.
            self.author_collected_feature_tests(file_count=1)
            self._declare_entering_slice = False
            return
        if outcome == ContractGateOutcome.ZERO_NODE_IDS:
            self._author_tagged_scenarioless_feature_file("zero_node_ids")
            return
        if outcome == ContractGateOutcome.COLLECTION_FAILED:
            self._author_syntax_error_test_module("collection_failed")
            return
        # EMPTY_INTERSECTION: a genuinely collectable scenario tagged for a
        # different, well-formed slice -- collects, but does not intersect.
        self._author_runnable_slice("non_intersecting", "slice-99")

    def run_arranged_contract_gate(self) -> CliResult:
        """Run the contract gate with the arrangement's flag set (slice-01).

        Honours ``arrange_vacuous_invocation``'s SLICE_NOT_DECLARED arrangement
        by omitting ``--entering-slice``; otherwise declares it.
        """
        return self.run_contract_gate(
            declare_entering_slice=self._declare_entering_slice
        )

    def create_slice_commit(self) -> None:
        """Initialise a git repo with a base commit for the entering slice.

        slice-02/03: ``verify_slice_commit`` inspects a real git commit, so the
        tmp feature project must be a git repo. The base commit gives HEAD a
        parent; the slice commit itself is authored by the arrange-* methods
        once the slice's ``.feature`` files are decided.
        """
        self._git("init", "-q")
        self._git("config", "user.email", "fixture@nwave.test")
        self._git("config", "user.name", "Fixture")
        (self.project_root / ".gitkeep").write_text("", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "chore: base commit")

    def slice_commit_message(self) -> str:
        """The commit message carrying the entering slice's Slice-Id trailer."""
        return (
            f"feat: deliver {self.entering_slice}\n\nSlice-Id: {self.entering_slice}\n"
        )

    def arrange_slice_commit(self, both_checks_pass: bool) -> None:
        """slice-02: arrange a commit where E1 and E2 both pass.

        Authors a genuinely collectable slice triplet under the feature id,
        tagged for the entering slice, and commits it with the slice's
        ``Slice-Id:`` trailer -- so completeness (E1: the ``.feature`` file is
        IN the commit) and the contract gate (E2: the scope collects >= 1
        runnable node-id) both clear.
        """
        self._author_runnable_slice("slice_commit_at", str(self.entering_slice))
        self._commit_slice(stage_feature_file=True)

    def arrange_failing_exit_gate(self, failing_half: object) -> None:
        """slice-02: arrange a commit where exactly one exit-gate half fails.

        * ``NO_RECORD_E2_FAILED`` -- author a tagged-but-scenario-less feature
          file (it resolves and intersects the slice, but collects ZERO
          runnable node-ids), commit it: E1 clears, E2 fails the M-1 floor.
        * ``NO_RECORD_E1_FAILED`` -- author a genuinely collectable slice but
          keep the ``.feature`` file OUT of the commit: E1 reports the file
          missing before E2 is ever reached.
        """
        from .domain_types import LedgerRecordOutcome

        if failing_half == LedgerRecordOutcome.NO_RECORD_E2_FAILED:
            self._author_tagged_scenarioless_feature_file("e2_failing")
            self._commit_slice(stage_feature_file=True)
            return
        # NO_RECORD_E1_FAILED: the .feature file exists on disk but the slice
        # commit does not carry it -- the RCA Branch-A completeness defect.
        self._author_runnable_slice("e1_failing", str(self.entering_slice))
        self._commit_slice(stage_feature_file=False)

    def _commit_slice(self, *, stage_feature_file: bool) -> None:
        """Commit the arranged slice with its ``Slice-Id:`` trailer.

        ``stage_feature_file=False`` stages everything EXCEPT the slice's
        ``.feature`` files -- the E1-completeness-fails arrangement.
        """
        if stage_feature_file:
            self._git("add", "-A")
        else:
            for path in sorted(self.tests_dir.rglob("*")):
                if path.is_file() and path.suffix != ".feature":
                    self._git("add", str(path.relative_to(self.project_root)))
        self._git("commit", "-q", "-m", self.slice_commit_message())

    def _git(self, *args: str) -> None:
        """Run a git command inside the tmp feature project."""
        subprocess.run(
            ["git", *args],
            cwd=self.project_root,
            capture_output=True,
            text=True,
            check=True,
        )

    def arrange_new_spine_flaw(self, flaw: object) -> None:
        """slice-04: inject a flaw into the new-spine flow before delivery.

        The simplified four-phase flow ships a slice only when every phase
        clears AND the exit gate runs. One arrangement per row of the
        unverified-slice Scenario Outline (Mandate 11, example-based):

        * ``ACCEPTANCE_TESTS_RED`` -- the slice's acceptance tests are left RED:
          the A_GREEN phase cannot clear, the flow never reaches the exit gate,
          no ``SliceCommitVerified`` record is produced.
        * ``EXIT_GATE_SKIPPED`` -- the orchestrator skips the slice-commit exit
          gate (``verify_slice_commit``) before D_REFACTOR_COMMIT: the ledger
          is starved of the record even though the slice's ATs are GREEN.

        Either way the flow's commit step finds no matching ``SliceCommitVerified``
        record and the M-2 backstop refuses the commit FROM WITHIN the flow --
        not as a standalone hook poke. The flaw is recorded; ``deliver_slice_on_
        new_spine`` honours it as a phase of the flow.
        """
        from .domain_types import NewSpineFlaw

        self._slice_deliverable = True
        if flaw == NewSpineFlaw.ACCEPTANCE_TESTS_RED:
            self._new_spine_flaw = NewSpineFlaw.ACCEPTANCE_TESTS_RED
        else:
            self._new_spine_flaw = NewSpineFlaw.EXIT_GATE_SKIPPED

    def arrange_backstop_commit(self, outcome: object) -> None:
        """slice-03: arrange the commit the M-2 backstop will inspect.

        One arrangement per row of the M-2 decision-table Scenario Outline
        (Mandate 11, example-based):

        * ``COMMIT_ALLOWED`` -- a Slice-Id commit whose exit gate ran: a
          matching ``SliceCommitVerified`` ledger record exists, so the hook
          allows the commit.
        * ``COMMIT_REFUSED`` -- a Slice-Id commit whose exit gate was skipped:
          the ledger is empty, so the hook refuses the commit.
        * ``NOT_A_SLICE_COMMIT`` -- an ordinary commit with NO slice-id
          trailer: not a slice commit, so the hook abstains (exit 0). This is
          the hook's DOMINANT path -- it fires on every commit repo-wide.

        The committed message inspected by the backstop is recorded in
        ``self._backstop_commit_message`` so the When-step delegates without
        re-deciding which message applies.
        """
        from .domain_types import CommitBackstopOutcome

        if outcome == CommitBackstopOutcome.COMMIT_ALLOWED:
            self.write_slice_commit_verified_record(self.entering_slice)
            self._backstop_commit_message = self.slice_commit_message()
            return
        if outcome == CommitBackstopOutcome.NOT_A_SLICE_COMMIT:
            # An ordinary commit -- no Slice-Id / Step-Id trailer at all.
            self._backstop_commit_message = "chore: tidy unrelated docs\n"
            return
        # COMMIT_REFUSED: a Slice-Id commit, ledger left empty (exit gate skipped).
        self._backstop_commit_message = self.slice_commit_message()

    @property
    def backstop_commit_message(self) -> str:
        """The commit message the M-2 backstop inspects (set by arrange_*)."""
        return self._backstop_commit_message

    def arrange_reconciliation_feature(self, outcome: object) -> None:
        """slice-03: arrange the feature the DDD-10 reconciliation will sweep.

        ``verify_deliver_integrity`` closes a feature only when TWO checks both
        clear: the per-slice reconciliation sweep (every ``Slice-Id:`` commit
        has a ``SliceCommitVerified`` record) AND the feature-end-cycle
        completeness check (slice-05 Finding 1 -- the ledger carries an
        ``EBatchRefactorCompleted`` and a ``FeatureEndReviewVerdict`` record).

        One arrangement per row of the reconciliation Scenario Outline
        (Mandate 11, example-based):

        * ``RECONCILED`` -- every Slice-Id commit has a matching
          ``SliceCommitVerified`` record AND the feature-end cycle ran (both
          feature-end records present): BOTH checks clear, the feature
          reconciles (``FeatureReconciled``, exit 0).
        * ``UNRECONCILED`` -- a Slice-Id commit has no matching record (the
          M-2 backstop was bypassed via ``--no-verify`` or a foreign commit
          path): the per-slice sweep fails, the feature fails unreconciled.
        * ``FEATURE_END_CYCLE_INCOMPLETE`` -- every Slice-Id commit IS recorded
          (the sweep would pass) but the ledger carries NO feature-end-cycle
          records: the second check fails. Without this row the verifier
          false-PASSes an all-slices-shipped-but-unrefactored feature -- the
          reconciliation verdict must COMPOSE with the feature-end check, not
          short-circuit to exit 0 the moment the sweep clears.

        Every row authors a real Slice-Id commit against the entering slice
        and the per-feature ledger file genuinely EXISTS -- an absent ledger
        trips the pre-existing "ledger missing" guard, a DIFFERENT failure from
        the DDD-10 sweep. ``UNRECONCILED`` seeds the ledger with an UNRELATED
        slice's record so the file exists but the committed slice's record is
        the one missing.
        """
        from .domain_types import IntegrityOutcome
        from .domain_types import SliceTag as _SliceTag

        # f-nonbypassable-attestation slice-03 (DDD-5, filesystem-derived): the
        # composed done-gate proves a planned slice was delivered by the presence
        # of its `@slice-NN @feature-{id}` `.feature` file (NOT the gameable
        # Status text). A genuinely-complete (reconciled) feature has authored
        # every planned slice's acceptance test; without these files the done-gate
        # would (correctly) refuse the feature as TRUNCATED, masking the
        # reconciliation outcome under test. Authored on disk (the done-gate walks
        # the working tree), scoped to this feature so the slice-plan rows resolve.
        for slice_tag in ("slice-01", "slice-02"):
            (self.tests_dir / f"{slice_tag}.feature").write_text(
                f"@feature-{self.feature_id} @{slice_tag}\n"
                f"Feature: {slice_tag} acceptance fixture\n",
                encoding="utf-8",
            )

        (self.project_root / f"{self.entering_slice}.delivered").write_text(
            "", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", self.slice_commit_message())
        if outcome == IntegrityOutcome.RECONCILED:
            # Both checks clear: the entering slice is recorded AND the
            # feature-end cycle left its two records.
            self.write_slice_commit_verified_record(self.entering_slice)
            self.write_feature_end_cycle_records()
        elif outcome == IntegrityOutcome.FEATURE_END_CYCLE_INCOMPLETE:
            # The reconciliation sweep would pass (the entering slice IS
            # recorded) -- but the feature-end cycle never ran, so NO
            # EBatchRefactorCompleted / FeatureEndReviewVerdict record exists.
            self.write_slice_commit_verified_record(self.entering_slice)
        else:
            # UNRECONCILED: the ledger file exists (an unrelated slice was
            # recorded) but the entering slice's record is absent -- the exact
            # one-slice-unrecorded gap the DDD-10 sweep must fail the feature on.
            self.write_slice_commit_verified_record(_SliceTag("slice-99"))

    def arrange_deliverable_slice(self) -> None:
        """slice-04: arrange a thin real slice ready for the simplified flow.

        ``_new_spine_flaw`` is left ``None`` -- the happy-path arrangement. The
        error Outline calls ``arrange_new_spine_flaw`` after this to inject a
        flaw the flow must catch.
        """
        self._slice_deliverable = True
        self._new_spine_flaw: object = None

    def deliver_slice_on_new_spine(self) -> NewSpineResult:
        """slice-04: deliver the slice through the simplified four-phase flow.

        Runs the whole simplified hand-orchestrated spine end to end --
        carpaccio entry gate, A_GREEN, C_REVIEWER_AUDIT, D_REFACTOR_COMMIT,
        the ``verify_slice_commit`` exit gate, and the M-2 commit-time
        backstop -- against the tmp_path feature project. The M-2 backstop is
        exercised AS THE FLOW'S COMMIT STEP: when ``_new_spine_flaw`` starves
        the ledger of a ``SliceCommitVerified`` record (ATs RED, or exit gate
        skipped), the flow's own commit step is refused by the involuntary
        backstop -- observed via ``NewSpineResult.slice_commit_refused``, never
        a standalone hook poke.
        """
        return self._run_new_spine_flow()

    def _run_new_spine_flow(self) -> NewSpineResult:
        """Run the slice through the simplified four-phase spine (slice-04).

        The simplified hand-orchestrated spine, end to end, composing the
        slice-01..03 CLIs -- no park, no reverify:

        * A_GREEN -- author the slice's acceptance tests and run them. When
          ``_new_spine_flaw`` is ``ACCEPTANCE_TESTS_RED`` the slice's ATs are
          authored RED, so A_GREEN does not clear and the flow never reaches
          the exit gate (the slice-01 ``run_contract_gate`` seam is what
          A_GREEN's GREEN-the-ATs proof rests on; here it is composed inside
          the slice-02 exit gate's E2 half).
        * D_REFACTOR_COMMIT exit gate -- run ``verify_slice_commit
          --feature-id`` (slice-02): the atomic verify-then-record CLI appends
          exactly one ``SliceCommitVerified`` record IFF E1 (completeness) and
          E2 (the feature-scoped contract gate) both clear. When
          ``_new_spine_flaw`` is ``EXIT_GATE_SKIPPED`` the orchestrator skips
          this CLI -- the ledger is starved of the record.
        * the commit step -- run the M-2 involuntary backstop (slice-03)
          against the slice commit. With a ``SliceCommitVerified`` record the
          commit is allowed; with no record (either flaw) the backstop refuses
          the commit FROM WITHIN the flow.

        No file is ever parked and ``reverify_slice_commit`` is never invoked
        -- the new spine eliminates the recovery dance (the DoD claim this
        slice exists to prove).
        """
        from .domain_types import NewSpineFlaw

        flaw = getattr(self, "_new_spine_flaw", None)

        # The simplified spine commits each slice incrementally, so the feature
        # project is a git repo with a base commit before the slice lands.
        self.create_slice_commit()

        # Phase A_GREEN -- author + (implicitly, via the exit gate's E2) run the
        # slice's acceptance tests. The flaw row authors them RED so A_GREEN
        # cannot clear; the happy / exit-gate-skipped rows author them GREEN.
        ats_left_red = flaw == NewSpineFlaw.ACCEPTANCE_TESTS_RED
        self._author_slice_under_delivery(ats_red=ats_left_red)
        self._commit_slice(stage_feature_file=True)

        # Phase D_REFACTOR_COMMIT exit gate -- the slice-02 atomic
        # verify-then-record CLI. Skipped on EXIT_GATE_SKIPPED; on the ATs-RED
        # row A_GREEN never cleared, so the flow never reaches the exit gate.
        exit_gate_run = flaw is None
        if exit_gate_run:
            self.run_verify_slice_commit(CommitRef("HEAD"))

        # The commit step -- the M-2 involuntary backstop inspects the slice
        # commit message. It allows the commit IFF a matching
        # SliceCommitVerified record exists; otherwise it refuses, in flow.
        backstop = self.run_commit_backstop_hook(self.slice_commit_message())
        backstop_verdict = self.parsed_verdict(backstop)
        slice_commit_refused = backstop_verdict.get("event") == "SliceCommitRefused"

        verified = self.verified_slices()
        return NewSpineResult(
            slice_commit_verified=str(self.entering_slice) in verified,
            parked_file_count=0,
            reverify_invocations=0,
            slice_commit_refused=slice_commit_refused,
            backstop_verdict=backstop_verdict,
        )

    def _author_slice_under_delivery(self, *, ats_red: bool) -> None:
        """Author the slice-04 slice's acceptance-test triplet under delivery.

        Writes a feature-scoped, entering-slice-tagged ``.feature`` + bound
        ``test_*.py`` + step module under ``tests/{feature_id}/`` -- the same
        genuinely-collectable shape ``verify_slice_commit``'s E2 contract gate
        consumes. ``ats_red=True`` authors a failing ``then`` assertion so the
        slice's acceptance tests are GREEN-or-RED honestly: the exit gate's E2
        half runs them and fails, so no ``SliceCommitVerified`` record lands.
        """
        name = "slice_under_delivery"
        slice_tag = str(self.entering_slice)
        feature_path = self.tests_dir / f"{name}.feature"
        feature_path.write_text(
            textwrap.dedent(
                f"""\
                @feature-{self.feature_id}
                Feature: {name} runnable fixture

                  @{slice_tag}
                  Scenario: a genuinely collectable {name} scenario
                    Given a runnable fixture step
                    When the runnable fixture step is exercised
                    Then the runnable fixture step is observed
                """
            ),
            encoding="utf-8",
        )
        then_body = "assert False" if ats_red else "assert True"
        (self.tests_dir / f"test_{name}.py").write_text(
            textwrap.dedent(
                f"""\
                import pytest
                from pytest_bdd import given, when, then, scenarios

                pytestmark = pytest.mark.acceptance
                scenarios("{name}.feature")

                @given("a runnable fixture step")
                def _given():
                    pass

                @when("the runnable fixture step is exercised")
                def _when():
                    pass

                @then("the runnable fixture step is observed")
                def _then():
                    {then_body}
                """
            ),
            encoding="utf-8",
        )

    # --- When: drive the production CLIs -------------------------------------

    def run_contract_gate(self, *, declare_entering_slice: bool = True) -> CliResult:
        """Invoke run_contract_gate scoped to the fixture feature (slice-01).

        ``declare_entering_slice=False`` omits ``--entering-slice`` -- a
        ``--feature-id`` invocation with no entering slice, the declared
        ``MalformedInput`` exit-2 path (C6a).
        """
        args = ["--repo", str(self.project_root), "--feature-id", str(self.feature_id)]
        if declare_entering_slice:
            args += ["--entering-slice", str(self.entering_slice)]
        return self._run_module("des.cli.run_contract_gate", *args)

    def run_verify_slice_commit(self, commit: CommitRef) -> CliResult:
        """Invoke verify_slice_commit feature-scoped against a commit (slice-02)."""
        return self._run_module(
            "des.cli.verify_slice_commit_completeness",
            "--repo",
            str(self.project_root),
            "--commit",
            str(commit),
            "--feature-id",
            str(self.feature_id),
        )

    def run_commit_backstop_hook(self, commit_message: str) -> CliResult:
        """Invoke the M-2 pre-commit ledger-record backstop (slice-03)."""
        msg_file = self.project_root / "COMMIT_EDITMSG"
        msg_file.write_text(commit_message, encoding="utf-8")
        return self._run_script(
            "scripts/hooks/verify_slice_ledger_record.py",
            "--commit-msg-file",
            str(msg_file),
            "--ledger-root",
            str(self.ledger_path.parent),
        )

    def run_verify_deliver_integrity(self) -> CliResult:
        """Invoke the DDD-10 feature-end reconciliation CLI (slice-03/04).

        The production CLI takes the feature project directory as a POSITIONAL
        argument (it resolves the AT-completion ledger under
        ``{project_dir}/.nwave/telemetry/atdd-pure/``) and ``--feature-id`` to
        target exactly this feature's ledger -- there is no ``--repo`` flag.
        The DDD-10 EXTEND adds the ``Slice-Id:``-commit reconciliation sweep on
        top of this surface; until it lands the CLI emits no
        ``FeatureReconciled`` / ``FeatureUnreconciled`` verdict and the slice-03
        reconciliation rows are honestly RED.
        """
        return self._run_module(
            "des.cli.verify_deliver_integrity",
            str(self.project_root),
            "--feature-id",
            str(self.feature_id),
        )

    # --- ledger helpers ------------------------------------------------------

    def write_slice_commit_verified_record(self, slice_tag: SliceTag) -> None:
        """Append a SliceCommitVerified record (simulates a prior verified slice).

        Routed through ``AtCompletionLedger.append_gate_event`` so the record
        lands at the telemetry substrate the carpaccio chain reads AND carries
        the M7 ``seq`` + ``record_hash`` integrity fields -- an integrity-free
        hand-written line would be rejected by the chain's fail-closed read.
        """
        self._ledger().append_gate_event("SliceCommitVerified", str(slice_tag))

    def write_feature_end_cycle_records(self) -> None:
        """Append the feature-end cycle records (EBatchRefactorCompleted +
        FeatureEndReviewVerdict + EnvironmentalE2eGateRan +
        WalkingSkeletonGateRan).

        slice-05 Finding 1: ``verify_deliver_integrity`` closes a feature only
        when the feature-end cycle (batch refactor + deep review) has left both
        records. Routed through ``AtCompletionLedger.append_feature_end_event``
        -- the dedicated feature-scoped writer -- so each record carries the M7
        ``seq`` + ``record_hash`` integrity fields the fail-closed read demands.

        fix-oss-environmental-e2e-gate slice-02: the env-e2e heartbeat is also
        in the required feature-end record set; the happy-path seeding appends
        it alongside the refactor + review records.

        fix-walking-skeleton-feature-end-wiring slice-01: the walking-skeleton
        heartbeat is also required (5th sibling of env-e2e pre-7af95a3d2); the
        happy-path seeding appends it alongside the others.

        fix-distill-signoff-feature-end-wiring slice-01: both coverage-map
        touchpoint heartbeats are also required (closes residue
        F-SLICE-06-U4-CONSUMER-MISSING from Gate D slice-06).
        """
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        ledger = self._ledger()
        # The 6 U4-required feature-end records are seeded structurally via
        # the shared helper (`_RECORD_WRITERS` registry) -- a frozenset
        # extension is now a one-line change in the helper instead of a
        # 6-fixture cascade. `verdict_hash=None` reproduces this site's
        # legacy `append_feature_end_event("FeatureEndReviewVerdict")` call
        # shape (hashless), preserving the record's byte-identical content
        # (the `record_hash` integrity field would diverge with a hash).
        seed_required_feature_end_records(ledger, verdict_hash=None)

    def verified_slices(self) -> frozenset[str]:
        """The set of slice ids carrying a SliceCommitVerified ledger record.

        Reads through ``AtCompletionLedger.verified_slices()`` -- the exact
        seam the slice-03 predecessor check and the M-2 backstop consume. A
        record at the wrong path is invisible here; an integrity-free record
        raises ``LedgerIntegrityViolation``. Set-level: a slice appears at most
        once regardless of how many records carry it (idempotency observable).
        """
        return self._ledger().verified_slices()

    def ledger_record_count(self) -> int:
        """Count distinct slices with a SliceCommitVerified record (port-exposed).

        Derived from ``verified_slices()`` -- the carpaccio-chain seam -- not a
        path-agnostic substring scan. A wrong-substrate or integrity-free
        record does NOT increment this count, so the AT genuinely reds when the
        production writes the wrong seam.
        """
        try:
            return len(self.verified_slices())
        except LedgerIntegrityViolation:
            # An integrity-broken ledger is observably NOT a verified slice --
            # surfaces as a count mismatch, never a silent undercount masking
            # a wrong-substrate record.
            return -1

    # --- subprocess plumbing -------------------------------------------------

    def _run_module(self, module: str, *args: str) -> CliResult:
        proc = subprocess.run(
            [sys.executable, "-m", module, *args],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    def _run_script(self, rel_path: str, *args: str) -> CliResult:
        proc = subprocess.run(
            [sys.executable, str(_REPO_ROOT / rel_path), *args],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    def observed_backstop_outcome(self, result: CliResult) -> object:
        """Classify an M-2 backstop run by its port-exposed verdict (slice-03).

        Reads the structured single-line JSON verdict the hook emits and maps
        its ``event`` to a ``CommitBackstopOutcome``. The classification rests
        on the JSON ``event`` -- NOT on the exit code alone -- so an argparse
        usage error (the hook not yet existing, or a flag it does not accept)
        cannot be mistaken for a genuine ``commit-refused``: it emits no such
        event and falls through to ``None``, keeping the AT honestly RED until
        the hook ships.
        """
        from .domain_types import CommitBackstopOutcome

        verdict = self.parsed_verdict(result)
        event_to_outcome: dict[str, CommitBackstopOutcome] = {
            "SliceCommitAllowed": CommitBackstopOutcome.COMMIT_ALLOWED,
            "SliceCommitRefused": CommitBackstopOutcome.COMMIT_REFUSED,
            "NotASliceCommit": CommitBackstopOutcome.NOT_A_SLICE_COMMIT,
        }
        return event_to_outcome.get(str(verdict.get("event")))

    def observed_integrity_outcome(self, result: CliResult) -> object:
        """Classify a DDD-10 reconciliation run by its port-exposed event (slice-03).

        Maps the structured JSON ``event`` to an ``IntegrityOutcome``. Resting
        the verdict on the emitted ``event`` (not the exit code) keeps a
        ``--feature-id`` argparse usage error -- which also exits non-zero --
        from being read as a genuine ``unreconciled`` failure.
        """
        from .domain_types import IntegrityOutcome

        verdict = self.parsed_verdict(result)
        event_to_outcome: dict[str, IntegrityOutcome] = {
            "FeatureReconciled": IntegrityOutcome.RECONCILED,
            "FeatureUnreconciled": IntegrityOutcome.UNRECONCILED,
            # The reconciliation sweep cleared but the feature-end cycle never
            # ran -- the verdict must COMPOSE the two checks rather than
            # short-circuit to FeatureReconciled the moment the sweep passes.
            "FeatureEndCycleIncomplete": (
                IntegrityOutcome.FEATURE_END_CYCLE_INCOMPLETE
            ),
        }
        return event_to_outcome.get(str(verdict.get("event")))

    @staticmethod
    def parsed_verdict(result: CliResult) -> dict[str, object]:
        """Parse the single-line JSON verdict a simplified-spine gate emits.

        A genuine gate refusal carries a structured JSON verdict on stdout with
        a ``cause`` field. An argparse usage error (an unknown flag on a CLI
        that does not yet accept it) emits NO such JSON -- so a Then-step that
        requires the parsed verdict cannot be fooled by an exit-code collision
        between argparse's exit 2 and the gate's ``malformed`` exit 2. This is
        the RED-honesty guard for the slice-01..04 negative scenarios.
        """
        import json

        for line in reversed(result.stdout.splitlines()):
            stripped = line.strip()
            if stripped.startswith("{") and stripped.endswith("}"):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed
        return {}

    # --- Universe snapshot (Mandate 8) ---------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observable names the surfaces affect.

        Port-exposed only: which slice .feature files exist under tests/, and
        the SET of slices the carpaccio chain sees as verified -- the latter
        derived from ``AtCompletionLedger.verified_slices()``, the exact seam
        slice-03's predecessor check and the M-2 backstop consume. NOT a
        path-agnostic substring scan: a record on the wrong substrate, or one
        missing the M7 integrity fields, is invisible here. No internal struct
        fields.
        """
        slice_files = sorted(p.name for p in self.tests_dir.glob("slice-*.feature"))
        verified = self.verified_slices()
        return {
            "tests.slice_feature_files": tuple(slice_files),
            "ledger.verified_slices": verified,
            # Count derived from the verified-slice SET (the carpaccio-chain
            # seam) -- kept for slices 03/04 which observe the scalar.
            "ledger.slice_commit_verified_count": len(verified),
        }
