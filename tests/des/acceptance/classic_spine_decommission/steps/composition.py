"""Composition root for the classic-spine-decommission acceptance suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root -- the real `des.cli.classify_features` and
`des.cli.convert_to_atdd_pure` CLIs, the real `at_review_verdict` CLI, the real
`AtCompletionLedger` M7 API, the real `carpaccio_slice_gate`, and a real
`git` subprocess for M2 SHA re-verification. Only the host's environment
(whether a tier can be provisioned) is fixtured -- the toolkit is pure
filesystem + subprocess + git, so nothing genuinely external is faked.

ALL business logic lives in this module's service methods -- the single source
of truth. Step bodies in the seven `steps/test_slice_*.py` files delegate to
these methods and never inline business logic (Mandate-12 criterion 3): each
step body is a typed lookup plus one composition call.

RED scaffold (Mandate 7 / ADR-025): this composition imports the production
modules the toolkit is built from. `des.cli.classify_features`,
`des.cli.convert_to_atdd_pure`, `des.domain.feature_classifier`,
`des.domain.conversion_planner`, and the `GitHistoryProbe` adapter do not yet
exist; DISTILL ships them as RED scaffolds (see `_scaffolds/`). Every scenario
therefore reds for the RIGHT reason (missing functionality / scaffold
AssertionError), not a fixture bug. DELIVER replaces the scaffolds with the
implementation; the conftest collection hook lifts the xfail markers at GREEN.

Layer note: slice-01 and slice-02 are layer 5 (WS @wiring_e2e, real stack
subprocess); slices 03/04/06/07 are layer 3 (subprocess / FS acceptance);
slice-05 is layer 4 (integration -- worked conversion + replay). Per Mandate
9/11 every slice here is example-only -- no PBT machinery is imported at this
layer. `@property`-tagged scenarios document universal invariants whose
generators DELIVER authors against layer-1 pure-function unit tests.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.cli.at_review_verdict import main as _at_review_verdict_main
from des.cli.carpaccio_slice_gate import main as _carpaccio_slice_gate_main
from des.cli.convert_to_atdd_pure import main as _convert_to_atdd_pure_main
from des.cli.verify_commit_trailers import main as _verify_commit_trailers_main
from tests.common.in_process_cli import run_cli_in_process

from ._git_workspace import (
    git_init_with_identity,
    repo_root,
    run_git,
    subprocess_env,
)
from .domain_types import (
    AdvisoryState,
    ConversionOutcome,
    ConversionStep,
    CorruptionKind,
    FeatureClass,
    FeatureId,
    InterruptPoint,
    LedgerReadOutcome,
    LedgerWriter,
    ReplayOutcome,
    ShaVerdict,
    SliceStatus,
    WorkflowMode,
)


# --- Observation value objects -----------------------------------------------


@dataclass(frozen=True)
class ManifestRow:
    """One row of `migration-manifest.json` -- a feature's classification."""

    feature_id: FeatureId
    feature_class: FeatureClass
    has_slice_plan: bool = False
    roadmap_steps: int | None = None
    committed_steps: tuple[str, ...] = ()
    git_state: str = ""
    crash_free: bool = True


@dataclass(frozen=True)
class ConversionPlan:
    """The plan-value a pure `ConversionPlanner.dry_run` returns -- never mutates.

    A `ConversionPlan` is an immutable description of the side effects
    `execute(plan)` would apply; `--dry-run` returns it and writes nothing.
    """

    feature_id: FeatureId
    slice_statuses: tuple[tuple[str, SliceStatus], ...] = ()
    slice_provenance: tuple[tuple[str, tuple[str, ...]], ...] = ()
    blocker: ConversionOutcome | None = None
    derived_from_roadmap: bool = False


@dataclass(frozen=True)
class ConversionResult:
    """The user-observable outcome of one `convert_to_atdd_pure` invocation."""

    outcome: ConversionOutcome
    journal_steps: tuple[ConversionStep, ...] = ()
    diagnostic: str = ""


@dataclass(frozen=True)
class LedgerReadResult:
    """The outcome of U1's M8 carpaccio-order read over a multi-writer ledger."""

    read_outcome: LedgerReadOutcome
    record_count: int = 0


# --- slice-01 + slice-03: the detection CLI ----------------------------------


@dataclass
class FeatureScanComposition:
    """Production-wired composition root for `des-classify-features`.

    Constructed per scenario over a pytest `tmp_path` holding a fixture
    `docs/feature/*` tree. The CLI is the real driving adapter; the
    `FeatureClassifier` domain object is pure; the `FeatureScanPort` is a real
    read-only filesystem adapter.
    """

    workspace: Path
    _feature_dirs: list[FeatureId] = field(default_factory=list, init=False)
    _last_exit_code: int | None = field(default=None, init=False)

    @property
    def _features_root(self) -> Path:
        return self.workspace / "docs" / "feature"

    @property
    def _manifest_path(self) -> Path:
        return self.workspace / "migration-manifest.json"

    # --- Given-side: materialise fixture feature dirs ------------------------

    def create_feature_dir(
        self, feature_id: FeatureId, feature_class: FeatureClass
    ) -> None:
        """Materialise a fixture feature dir with the artifacts of a given class."""
        feature_dir = self._features_root / str(feature_id)
        self._feature_dirs.append(feature_id)
        writer = self._CLASS_WRITERS.get(feature_class)
        if writer is None:
            raise AssertionError(
                f"create_feature_dir does not yet support {feature_class}"
            )
        writer(self, feature_dir)
        self._ensure_repo_committed()

    def _write_classic_mid_implementation(self, feature_dir: Path) -> None:
        """Write a roadmap + execution log of a mid-implementation classic feature."""
        deliver = feature_dir / "deliver"
        deliver.mkdir(parents=True, exist_ok=True)
        (deliver / "roadmap.json").write_text(
            json.dumps({"phases": [{"id": "01"}, {"id": "02"}]}, indent=2),
            encoding="utf-8",
        )
        (deliver / "execution-log.json").write_text(
            json.dumps(
                {
                    "events": [
                        {
                            "step_id": "01-01",
                            "phase": "COMMIT",
                            "status": "EXECUTED",
                            "data": "PASS",
                        },
                        {
                            "step_id": "02-01",
                            "phase": "RED",
                            "status": "EXECUTED",
                            "data": "PASS",
                        },
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_classic_distill_done(self, feature_dir: Path) -> None:
        """Write a feature with `.feature` ATs and no `deliver/` -- DISTILL done."""
        distill = feature_dir / "distill"
        distill.mkdir(parents=True, exist_ok=True)
        (distill / "scenario.feature").write_text(
            "Feature: a distilled but undelivered feature\n"
            "  Scenario: an example\n"
            "    Given a precondition\n"
            "    Then an outcome\n",
            encoding="utf-8",
        )

    def _write_atdd_pure(self, feature_dir: Path) -> None:
        """Write a feature already on the atdd_pure spine -- a Slice Plan heading."""
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "feature-delta.md").write_text(
            "# Feature delta\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Status | Class |\n"
            "|---|---|---|\n"
            "| slice-01 | pending | C |\n",
            encoding="utf-8",
        )

    def _write_pre_distill(self, feature_dir: Path) -> None:
        """Write a feature that has not reached DISTILL -- no ATs, no roadmap."""
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "discuss-notes.md").write_text(
            "# Discuss notes\n\nA feature still in the DISCUSS wave.\n",
            encoding="utf-8",
        )

    def _write_classic_needs_manual_review(self, feature_dir: Path) -> None:
        """Write a classic feature whose roadmap is corrupt -- manual-review row.

        Materialises a mid-implementation classic feature, then truncates its
        `deliver/roadmap.json` so it is no longer valid JSON (F-17 stale stub).
        The classifier yields `classic-needs-manual-review` for it, and the
        drain therefore parks the feature on `migration-parked.json` (M6).
        """
        self._write_classic_mid_implementation(feature_dir)
        (feature_dir / "deliver" / "roadmap.json").write_text(
            '{"phases": [{"id": "01"',
            encoding="utf-8",
        )

    # Dispatch table: one writer per supported FeatureClass. Keeps
    # `create_feature_dir` a single typed lookup (Mandate-12 criterion 3).
    _CLASS_WRITERS = {
        FeatureClass.CLASSIC_MID_IMPLEMENTATION: _write_classic_mid_implementation,
        FeatureClass.CLASSIC_DISTILL_DONE: _write_classic_distill_done,
        FeatureClass.ATDD_PURE: _write_atdd_pure,
        FeatureClass.PRE_DISTILL: _write_pre_distill,
        FeatureClass.CLASSIC_NEEDS_MANUAL_REVIEW: _write_classic_needs_manual_review,
    }

    def _ensure_repo_committed(self) -> None:
        """Init the workspace as a git repo and commit the fixture feature tree.

        Gives the `developer repository is left untouched` scenario a real
        git working tree to snapshot before and after classification.
        """
        self.workspace.mkdir(parents=True, exist_ok=True)
        # The migration manifest is a generated worklist, not a source
        # artifact -- ignoring it keeps `git status` clean so the
        # `developer repository is left untouched` property holds.
        (self.workspace / ".gitignore").write_text(
            f"{self._manifest_path.name}\n", encoding="utf-8"
        )
        if (self.workspace / ".git").exists():
            self._git("add", "-A")
            self._git("commit", "-m", "fixture: feature tree", "--allow-empty")
            return
        git_init_with_identity(self.workspace)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fixture: feature tree")

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a git subprocess inside the workspace."""
        return run_git(self.workspace, *args)

    def corrupt_feature_artifacts(
        self, feature_id: FeatureId, corruption: CorruptionKind
    ) -> None:
        """Inject a malformed classic artifact into a fixture feature dir (probe).

        The classifier must never crash on a malformed artifact -- it yields a
        `classic-needs-manual-review` row. slice-03 exercises the truncated
        roadmap (F-17 stale stub); the remaining `CorruptionKind` members are
        slice-04's probe surface.
        """
        feature_dir = self._features_root / str(feature_id)
        corrupter = self._CORRUPTERS.get(corruption)
        if corrupter is None:
            raise AssertionError(
                f"corrupt_feature_artifacts does not yet support {corruption}"
            )
        corrupter(self, feature_dir)
        self._ensure_repo_committed()

    def _truncate_roadmap(self, feature_dir: Path) -> None:
        """Truncate the roadmap.json so it is no longer valid JSON (F-17 stub)."""
        (feature_dir / "deliver" / "roadmap.json").write_text(
            '{"phases": [{"id": "01"',
            encoding="utf-8",
        )

    def _roadmap_not_json(self, feature_dir: Path) -> None:
        """Overwrite roadmap.json with text that is not JSON at all."""
        (feature_dir / "deliver" / "roadmap.json").write_text(
            "this roadmap was clobbered and is no longer JSON",
            encoding="utf-8",
        )

    def _roadmap_hand_edited(self, feature_dir: Path) -> None:
        """Hand-edit the roadmap so its phases no longer match the log's steps.

        The execution log records steps `01-01` and `02-01`; this roadmap
        declares only phase `09` -- a schema-valid but log-inconsistent
        artifact the classifier must route to manual review.
        """
        (feature_dir / "deliver" / "roadmap.json").write_text(
            json.dumps({"phases": [{"id": "09"}]}, indent=2),
            encoding="utf-8",
        )

    def _log_mixed_version(self, feature_dir: Path) -> None:
        """Rewrite the execution log mixing v2.0-pipe strings and v3.0 dicts."""
        (feature_dir / "deliver" / "execution-log.json").write_text(
            json.dumps(
                {
                    "events": [
                        "01-01|COMMIT|EXECUTED|PASS",
                        {
                            "step_id": "02-01",
                            "phase": "RED",
                            "status": "EXECUTED",
                            "data": "PASS",
                        },
                    ]
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _log_empty(self, feature_dir: Path) -> None:
        """Overwrite the execution log with an empty JSON object."""
        (feature_dir / "deliver" / "execution-log.json").write_text(
            "{}",
            encoding="utf-8",
        )

    # Dispatch table: one corrupter per supported CorruptionKind.
    _CORRUPTERS = {
        CorruptionKind.ROADMAP_TRUNCATED: _truncate_roadmap,
        CorruptionKind.ROADMAP_NOT_JSON: _roadmap_not_json,
        CorruptionKind.ROADMAP_HAND_EDITED: _roadmap_hand_edited,
        CorruptionKind.LOG_MIXED_VERSION: _log_mixed_version,
        CorruptionKind.LOG_EMPTY: _log_empty,
    }

    def give_feature_both_roadmap_and_slice_plan(self, feature_id: FeatureId) -> None:
        """Create a feature with BOTH a roadmap.json and a slice-plan heading (S21).

        The Root-Cause-B feature: a mid-implementation classic feature whose
        DESIGN slice plan was promoted into a `## Wave: DISCUSS / [REF] Slice
        Plan` heading. The classifier must call it `classic-mid-implementation`
        (the roadmap binds it to the classic spine) AND stamp
        `has_slice_plan: true` -- never mistake it for `atdd_pure` (S21).
        """
        feature_dir = self._features_root / str(feature_id)
        self._write_classic_mid_implementation(feature_dir)
        (feature_dir / "feature-delta.md").write_text(
            "# Feature delta\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Status | Class |\n"
            "|---|---|---|\n"
            "| slice-01 | pending | C |\n",
            encoding="utf-8",
        )
        self._feature_dirs.append(feature_id)
        self._ensure_repo_committed()

    # --- When-side: run the classifier --------------------------------------

    def run_classify_features(self) -> int:
        """Invoke `des classify-features` as a real subprocess.

        Layer 5 (slice-01 @wiring_e2e): the installed CLI runs against the
        fixture `docs/feature/*` tree and writes `migration-manifest.json`.
        Returns the process exit code. Post-slice-03 form: single-entry-point
        dispatcher.
        """
        env = subprocess_env()
        completed = subprocess.run(
            [
                "des",
                "classify-features",
                "--features-root",
                str(self._features_root),
                "--out",
                str(self._manifest_path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self._last_exit_code = completed.returncode
        return completed.returncode

    # --- Then-side: port-exposed observables --------------------------------

    def manifest_rows(self) -> tuple[ManifestRow, ...]:
        """The parsed rows of the emitted `migration-manifest.json`."""
        parsed = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        return tuple(
            ManifestRow(
                feature_id=FeatureId(row["feature_id"]),
                feature_class=FeatureClass(row["class"]),
                has_slice_plan=row.get("has_slice_plan", False),
                roadmap_steps=row.get("roadmap_steps"),
                committed_steps=tuple(row.get("committed_steps", ())),
                git_state=row.get("git_state", ""),
            )
            for row in parsed.get("features", [])
        )

    def classifier_crashed(self) -> bool:
        """Whether the classifier crashed (it must NEVER -- probe contract)."""
        return self._last_exit_code != 0

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observable universe (Mandate 8).

        Universe keys are port-exposed names ONLY: whether the manifest file
        exists, its row count, and the developer repo's git working tree.
        """
        return {
            "git.status_porcelain": self._git("status", "--porcelain").stdout,
            "git.head_sha": self._git("rev-parse", "HEAD").stdout.strip(),
            "manifest.exists": self._manifest_path.exists(),
            "manifest.row_count": (
                len(self.manifest_rows()) if self._manifest_path.exists() else 0
            ),
        }


# --- slice-02: F-13 closure (multi-writer ledger) ----------------------------


@dataclass
class LedgerInterleaveComposition:
    """Production-wired composition root for the F-13 multi-writer interleave.

    slice-02 closes F-13: `at_review_verdict` writes via the M7
    `AtCompletionLedger` API so its records carry `seq` + `record_hash`, and
    U1's M8 carpaccio-order read consumes the mixed ledger without raising.

    Pillar 3: the REAL `at_review_verdict` CLI and the REAL `AtCompletionLedger`
    write the SAME ledger file -- never a fixture-uniform ledger (M4). The
    reviewer vetoes a hand-shaped uniform-schema ledger here.
    """

    deliver_dir: Path
    _feature_id: FeatureId | None = field(default=None, init=False)

    @property
    def _project_root(self) -> Path:
        """The installed feature root -- holds `.nwave/telemetry`."""
        return self.deliver_dir / str(self._feature_id)

    def create_installed_feature(self, feature_id: FeatureId) -> None:
        """Create a subprocess-real installed feature layout with a ledger dir.

        Materialises the `.nwave/telemetry/atdd-pure` ledger directory. NO
        signing key is provisioned (oss-review-verdict-demotion S2: the real
        `at_review_verdict` CLI is keyless — key absence is a non-event).
        """
        self._feature_id = feature_id
        telemetry = self._project_root / ".nwave" / "telemetry" / "atdd-pure"
        telemetry.mkdir(parents=True, exist_ok=True)

    def writer_appends_record(self, writer: LedgerWriter, slice_id: str) -> None:
        """Have the named REAL writer append a record to the shared ledger.

        AT_REVIEW_VERDICT runs the real `at_review_verdict` CLI; AT_COMPLETION
        calls the real `AtCompletionLedger` API. Both write the same file.
        """
        if writer is LedgerWriter.AT_COMPLETION:
            self._completion_writer_appends(slice_id)
            return
        self._review_verdict_writer_appends(slice_id)

    def _completion_writer_appends(self, slice_id: str) -> None:
        """The real `AtCompletionLedger` M7 writer appends a gate event."""
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self._project_root
        )
        ledger.append_gate_event(event="CarpaccioGateCleared", slice_id=slice_id)

    def _review_verdict_writer_appends(self, slice_id: str) -> None:
        """The real `at_review_verdict` CLI appends an ATReviewVerdict record.

        Subprocess-real (`@wiring_e2e`): the installed CLI runs against the
        same `.nwave/telemetry` ledger the completion writer appends to, so
        the F-13 interleave is genuine -- never a fixture-uniform ledger.
        """
        exit_code, _stdout, stderr = run_cli_in_process(
            [
                "--feature-id",
                str(self._feature_id),
                "--slice-id",
                slice_id,
                "--verdict",
                "APPROVED",
                "--reviewer-agent-id",
                "nw-acceptance-designer-reviewer",
                "--repo-root",
                str(self._project_root),
            ],
            cwd=self._project_root,
            main=_at_review_verdict_main,
        )
        assert exit_code == 0, (
            f"at_review_verdict CLI failed (rc={exit_code}): {stderr}"
        )

    def run_carpaccio_order_read(self) -> LedgerReadResult:
        """Run U1's M8 carpaccio-order read over the mixed-writer ledger.

        The carpaccio-order read is the M7 fail-closed integrity read --
        `AtCompletionLedger.read_records()`. Before F-13 a verdict record
        (no `seq`/`record_hash`) made this raise `LedgerIntegrityViolation`;
        the fixed producer routes through the M7 API so the read accepts the
        mixed ledger.
        """
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self._project_root
        )
        try:
            records = ledger.read_records()
        except LedgerIntegrityViolation:
            return LedgerReadResult(read_outcome=LedgerReadOutcome.INTEGRITY_RAISED)
        return LedgerReadResult(
            read_outcome=LedgerReadOutcome.ACCEPTED, record_count=len(records)
        )

    def run_atdd_pure_dispatch_installed(self) -> int:
        """Run the M7 fail-closed ledger-integrity read an atdd_pure dispatch runs.

        In-process (the migration off subprocess-e2e): performs the SAME M7
        fail-closed integrity read an atdd_pure dispatch runs at entry, against
        the production `AtCompletionLedger` (mirrors `run_carpaccio_order_read`
        in this class). Returns 1 iff the mixed-writer ledger raises
        `LedgerIntegrityViolation` (the F-13 defect), else 0 -- the exact
        exit-code contract the fresh-interpreter probe asserted.
        """
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self._project_root
        )
        try:
            ledger.read_records()
        except LedgerIntegrityViolation:
            return 1
        return 0

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed ledger observables (Mandate 8).

        Universe keys are port-exposed names ONLY: whether the ledger file
        exists and the record count the M7 fail-closed read yields.
        """
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self._project_root
        )
        path = ledger.ledger_path()
        return {
            "ledger.exists": path.is_file(),
            "ledger.record_count": (
                len(ledger.read_records()) if path.is_file() else 0
            ),
        }


# --- slice-04 + slice-05 + slice-06 + slice-08: the conversion CLI -----------


# Maps an `InterruptPoint` to the journalled `ConversionStep` value AFTER which
# the converter's `DES_CONVERT_ABORT_AFTER` hook raises `ConversionInterrupted`
# (S16). The four journalled steps are promote-heading -> seed-ledger ->
# flip-config -> archive-roadmap; an interrupt point names the last step that
# completed before the crash.
_ABORT_STEP_BY_INTERRUPT: dict[InterruptPoint, str] = {
    InterruptPoint.AFTER_PROMOTE: ConversionStep.PROMOTE_HEADING.value,
    InterruptPoint.AFTER_SEED: ConversionStep.SEED_LEDGER.value,
    InterruptPoint.AFTER_FLIP: ConversionStep.FLIP_CONFIG.value,
}


@dataclass
class ConversionComposition:
    """Production-wired composition root for `des-convert-to-atdd-pure`.

    The `ConversionPlanner` is pure (returns a `ConversionPlan`, never
    mutates); `execute(plan)` is the single journalled, resumable, rollback-able
    impure function (M3). `GitHistoryProbe` re-verifies COMMIT/PASS SHAs against
    a real git repo (M2). The `AtCompletionLedger` M7 API seeds the converted
    feature's ledger -- never a hand-written JSONL (re-implementing it IS F-13).
    """

    workspace: Path
    _feature_id: FeatureId | None = field(default=None, init=False)
    _roadmap_step_count: int = field(default=0, init=False)
    _slice_map: dict[str, tuple[str, ...]] = field(default_factory=dict, init=False)
    _committed_steps: dict[str, dict[str, str]] = field(
        default_factory=dict, init=False
    )
    _double_committed_steps: set[str] = field(default_factory=set, init=False)
    _feature_dir_original_mode: int | None = field(default=None, init=False)
    _drain_payload: dict[str, object] | None = field(default=None, init=False)

    # Keyless (oss-review-verdict-demotion S1/S2): the carpaccio AT-review
    # gate reads the seeded ATReviewVerdict on its PRESENT fields — no key
    # is provisioned and the seeded record carries no signature field.

    @property
    def _feature_dir(self) -> Path:
        return self.workspace / "docs" / "feature" / str(self._feature_id)

    @property
    def _journal_path(self) -> Path:
        return (
            self.workspace
            / ".nwave"
            / "conversion-journal"
            / f"{self._feature_id}.json"
        )

    @property
    def _config_path(self) -> Path:
        return self.workspace / ".nwave" / "config.yaml"

    # --- Given-side ----------------------------------------------------------

    def create_classic_feature(
        self,
        feature_id: FeatureId,
        feature_class: FeatureClass,
        *,
        has_slice_plan: bool,
    ) -> None:
        """Materialise a classic feature dir on the classic spine.

        The fixture writes a classic feature: a `feature-delta.md` carrying a
        DESIGN `[REF] Recommended Slice Plan` heading (which conversion Step 1
        promotes), a `deliver/roadmap.json`, a slice `.feature` file with one
        `@slice-01` scenario, a `.nwave/config.yaml` whose `workflow.mode` is
        `classic`. The AT-review verdict is seeded keyless
        once the slice map + commits are declared (see `_finalise_fixture`).
        """
        self._feature_id = feature_id
        deliver = self._feature_dir / "deliver"
        deliver.mkdir(parents=True, exist_ok=True)
        heading = (
            "## Wave: DISCUSS / [REF] Slice Plan"
            if not has_slice_plan
            else "## Wave: DESIGN / [REF] Recommended Slice Plan"
        )
        (self._feature_dir / "feature-delta.md").write_text(
            "# Feature delta\n\n"
            f"{heading}\n\n"
            "| Slice | Value | Status | Annotation | Justification |\n"
            "|---|---|---|---|---|\n"
            "| slice-01 | the walking skeleton vertical | pending |"
            " @walking-skeleton | first end-to-end slice |\n",
            encoding="utf-8",
        )
        feature_tests = self.workspace / "tests" / str(feature_id)
        feature_tests.mkdir(parents=True, exist_ok=True)
        (feature_tests / "convert-target.feature").write_text(
            f"@feature-{feature_id}\n"
            "Feature: the converted feature's walking skeleton\n\n"
            "  @slice-01\n"
            "  Scenario: the walking skeleton runs end to end\n"
            "    Given a precondition\n"
            "    When an action occurs\n"
            "    Then an outcome holds\n",
            encoding="utf-8",
        )
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config_path.write_text(
            "atdd_pure:\n  carpaccio_slice_max: 3\n\nworkflow:\n  mode: classic\n",
            encoding="utf-8",
        )
        self._init_repo()

    def _init_repo(self) -> None:
        """Initialise the workspace as a real git repo for M2 re-verification.

        `GitHistoryProbe` runs `git cat-file` / `git merge-base` inside the
        workspace, so the converter's SHA re-verification needs a real repo
        with a real commit graph -- never a fixtured verdict string.
        """
        git_init_with_identity(self.workspace)
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fixture: classic feature tree")

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a git subprocess inside the workspace."""
        return run_git(self.workspace, *args)

    def set_roadmap_steps(self, count: int) -> None:
        """Set how many roadmap steps the classic feature's roadmap.json has."""
        self._roadmap_step_count = count
        self._write_roadmap()

    def map_steps_to_slice(self, step_ids: tuple[str, ...], slice_id: str) -> None:
        """Declare the N roadmap steps that constitute one slice (N:1 rule)."""
        self._slice_map[slice_id] = step_ids
        self._write_roadmap()

    def commit_step_with_sha_verdict(
        self, step_id: str, sha: str, verdict: ShaVerdict
    ) -> None:
        """Log a COMMIT/PASS for a step and arm its SHA's M2 re-verification.

        Arms REAL git state so `GitHistoryProbe` re-verifies the SHA exactly
        as it would a production repo -- the roadmap stores only the logical
        SHA label (a git tag name), never a fixtured verdict string:

          * GREEN     -- a real commit, tagged `sha`, reachable from HEAD,
                         carrying a green step-test-state marker.
          * TESTS_RED -- a real reachable tagged commit whose step-test-state
                         marker reads `red`.
          * REVERTED  -- a real commit tagged `sha` on a side branch, NOT an
                         ancestor of HEAD (the converter sees it as reverted).
          * ABSENT    -- no commit and no tag -- the SHA is unknown to git.
        """
        self._committed_steps[step_id] = {"sha": sha}
        self._arm_sha_git_state(sha, verdict)
        self._write_roadmap()
        self._seed_at_review_verdict()

    def _arm_sha_git_state(self, sha: str, verdict: ShaVerdict) -> None:
        """Materialise the git state matching one step's SHA verdict."""
        if verdict is ShaVerdict.ABSENT:
            return
        if verdict is ShaVerdict.REVERTED:
            self._commit_on_side_branch(sha)
            return
        test_state = "red" if verdict is ShaVerdict.TESTS_RED else "green"
        self._commit_reachable(sha, test_state)

    def _commit_reachable(self, sha: str, test_state: str) -> None:
        """Create a real commit on HEAD, tagged `sha`, with a test-state marker."""
        marker = self.workspace / ".nwave" / "step-test-state"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{test_state}\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", f"fixture: committed step {sha}")
        self._git("tag", sha)

    def _commit_on_side_branch(self, sha: str) -> None:
        """Create a tagged commit that is NOT an ancestor of HEAD (reverted).

        Models a reverted commit: a real commit is made, tagged `sha`, then
        the branch tip is reset back one commit. The tag keeps the commit
        object alive while it is no longer reachable from HEAD -- exactly the
        state `GitHistoryProbe` must read as `reverted`.
        """
        marker = self.workspace / ".nwave" / "step-test-state"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("green\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", f"fixture: reverted step {sha}")
        self._git("tag", sha)
        self._git("reset", "-q", "--hard", "HEAD~1")

    def _write_roadmap(self) -> None:
        """(Re)write `deliver/roadmap.json` from the declared steps + slices."""
        if self._feature_id is None:
            return
        steps = []
        for index in range(1, max(self._roadmap_step_count, 0) + 1):
            step_id = f"{index:02d}-01"
            committed = self._committed_steps.get(step_id)
            record = {
                "step_id": step_id,
                "committed": committed is not None,
                "sha": committed["sha"] if committed else "",
            }
            steps.append(record)
            # An entry-gate restart re-runs a step and re-logs its COMMIT/PASS:
            # the roadmap then carries the same step twice at the same SHA. The
            # planner must dedup by SHA before counting (S6).
            if step_id in self._double_committed_steps:
                steps.append(dict(record))
        roadmap = {
            "phases": [{"id": f"{i:02d}"} for i in range(1, 13)],
            "steps": steps,
            "slices": {sid: list(ids) for sid, ids in self._slice_map.items()},
        }
        roadmap_path = self._feature_dir / "deliver" / "roadmap.json"
        roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        roadmap_path.write_text(json.dumps(roadmap, indent=2) + "\n", encoding="utf-8")

    def _seed_at_review_verdict(self) -> None:
        """Seed a keyless APPROVED ATReviewVerdict for slice-01.

        The carpaccio AT-review gate (ADR-029 D5, demoted keyless per
        oss-review-verdict-demotion) requires a well-formed APPROVED verdict
        record in the AT-completion ledger before it clears a slice — read on
        its PRESENT fields, no signature. The fixture seeds it through the
        real `AtCompletionLedger.append_review_verdict` M7 API so the record
        carries `seq` + `record_hash`.
        """
        import hashlib

        body = "given a precondition\nwhen an action occurs\nthen an outcome holds"
        at_content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self.workspace
        )
        ledger.append_review_verdict(
            slice_id="slice-01",
            verdict_fields={
                "schema_version": "1.0",
                "verdict": "APPROVED",
                "reviewer_agent_id": "nw-acceptance-designer-reviewer",
                "at_ids": ["AT-1"],
                "at_content_hash": at_content_hash,
                "timestamp": "2026-05-21T00:00:00Z",
                "findings_summary": "fixture-seeded slice-05 verdict",
            },
        )

    def log_step_committed_twice(self, step_id: str, sha: str) -> None:
        """Log the same COMMIT/PASS step twice (entry-gate-restart retry, S6).

        Records the step's second COMMIT/PASS at the SAME SHA so the rewritten
        roadmap carries two entries for it -- the state an entry-gate restart
        leaves behind. The pure planner must dedup by SHA before counting.
        """
        self._committed_steps[step_id] = {"sha": sha}
        self._double_committed_steps.add(step_id)
        self._write_roadmap()

    def leave_scenarios_untagged(self) -> None:
        """Strip every `@slice-NN` tag from the feature's `.feature` files (F-03 / S19).

        `create_classic_feature` wrote a `.feature` whose single scenario
        carries an `@slice-01` tag. This rewrites every `.feature` file under
        the feature's `tests/{feature_id}/` directory, dropping any line that
        is solely a `@slice-NN` tag -- so the drain detects untagged
        acceptance scenarios and parks the feature pending DISTILL tagging.
        """
        feature_tests = self.workspace / "tests" / str(self._feature_id)
        for feature_file in feature_tests.glob("*.feature"):
            kept = [
                line
                for line in feature_file.read_text(encoding="utf-8").splitlines()
                if not line.strip().startswith("@slice-")
            ]
            feature_file.write_text("\n".join(kept) + "\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fixture: drop slice tags")

    def arm_interrupt(self, point: InterruptPoint) -> None:
        """Run a first conversion that crashes at a named side-effect step (S16).

        Drives the real `des-convert-to-atdd-pure` CLI with the
        `DES_CONVERT_ABORT_AFTER` env hook armed, so `execute()` raises after
        the matching journalled step. The first run therefore leaves a PARTIAL
        conversion journal on disk; a later `run_convert_again` must resume it.
        """
        completed = self._run_cli(
            env_overrides={"DES_CONVERT_ABORT_AFTER": _ABORT_STEP_BY_INTERRUPT[point]}
        )
        assert completed.returncode != 0, (
            "armed convert was expected to be interrupted but exited 0: "
            f"{completed.stdout}"
        )

    def classify_with_real_classifier(self) -> None:
        """Run the REAL `des classify-features` CLI to emit the migration manifest.

        D1 gap-AT support: the converter's M7 staleness guard is only meaningful
        if the manifest row's `git_state` is stamped by the production
        classifier. This drives the real `des classify-features` subprocess
        (post-slice-03 single-entry-point form) over the workspace's
        `docs/feature/*` tree, writing `migration-manifest.json` exactly where
        `convert_to_atdd_pure` reads it -- NO hand-written manifest. If
        `_classify_one` hardcodes `git_state: ""` (the D1 defect) the produced
        stamp is empty and the staleness guard short-circuits; once D1 is fixed
        the stamp is a real tree-object SHA and the guard becomes reachable
        end-to-end.
        """
        env = subprocess_env()
        completed = subprocess.run(
            [
                "des",
                "classify-features",
                "--features-root",
                str(self.workspace / "docs" / "feature"),
                "--out",
                str(self.workspace / "migration-manifest.json"),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        assert completed.returncode == 0, (
            f"classify_features failed (rc={completed.returncode}): {completed.stderr}"
        )

    def advance_feature_dir_after_real_classification(self) -> None:
        """Mutate the feature dir AFTER a real classification (D1 staleness).

        Companion to `classify_with_real_classifier`: adds a tracked file under
        the feature dir and commits it, so the feature dir's current git
        tree-object SHA no longer matches the `git_state` the real classifier
        stamped into `migration-manifest.json`. The converter must refuse the
        now-stale row -- end-to-end, with the stamp produced by production code.
        """
        (self._feature_dir / "post-classification-change.md").write_text(
            "a change landed after the real classification\n",
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "fixture: feature dir advanced after real scan")

    # --- When-side -----------------------------------------------------------

    def _run_cli(
        self, *extra: str, env_overrides: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run `des convert-to-atdd-pure` as a real subprocess (post-slice-03)."""
        env = subprocess_env()
        if env_overrides:
            env.update(env_overrides)
        return subprocess.run(
            [
                "des",
                "convert-to-atdd-pure",
                "--workspace",
                str(self.workspace),
                "--feature-id",
                str(self._feature_id),
                *extra,
            ],
            capture_output=True,
            text=True,
            env=env,
        )

    def run_dry_run(self) -> ConversionPlan:
        """Invoke `des-convert-to-atdd-pure --dry-run` -- a plan, writes nothing."""
        completed = self._run_cli("--dry-run")
        assert completed.returncode == 0, (
            f"convert --dry-run failed (rc={completed.returncode}): {completed.stderr}"
        )
        payload = json.loads(completed.stdout)
        return ConversionPlan(
            feature_id=FeatureId(payload["feature_id"]),
            slice_statuses=tuple(
                (row["slice_id"], SliceStatus(row["status"]))
                for row in payload["slices"]
            ),
            slice_provenance=tuple(
                (row["slice_id"], tuple(row["provenance"])) for row in payload["slices"]
            ),
            blocker=(
                ConversionOutcome(payload["blocker"]) if payload["blocker"] else None
            ),
            derived_from_roadmap=payload["derived_from_roadmap"],
        )

    def run_convert(self) -> ConversionResult:
        """Invoke `des-convert-to-atdd-pure` and report its observable outcome.

        A successful conversion AND a clean refusal (M7 stale row, C7a
        non-writable feature dir) both exit 0 -- a refusal is a clean outcome,
        never a crash. The user-observable `outcome` is read from the CLI's
        JSON stdout, so a refusal surfaces as `REFUSED_STALE` / `REFUSED_READONLY`
        rather than a spurious `CONVERTED`.
        """
        completed = self._run_cli()
        self._restore_feature_dir_mode()
        assert completed.returncode == 0, (
            f"convert failed (rc={completed.returncode}): {completed.stderr}"
        )
        payload = json.loads(completed.stdout)
        return ConversionResult(outcome=ConversionOutcome(payload["outcome"]))

    def _restore_feature_dir_mode(self) -> None:
        """Restore a feature dir made read-only for C7a so `tmp_path` cleans up."""
        if self._feature_dir_original_mode is None:
            return
        self._feature_dir.chmod(self._feature_dir_original_mode)
        self._feature_dir_original_mode = None

    def run_convert_again(self) -> ConversionResult:
        """Re-invoke the converter on the same feature (idempotency via journal).

        A second `execute()` reads the conversion journal and resumes from the
        last completed side-effect step -- so an already-converted feature is
        a no-op: no journalled step re-applies, the journal stays unchanged.
        """
        return self.run_convert()

    def run_rollback(self) -> ConversionResult:
        """Invoke `des-convert-to-atdd-pure --rollback` -- un-do a partial conversion."""
        completed = self._run_cli("--rollback")
        assert completed.returncode == 0, (
            f"convert --rollback failed (rc={completed.returncode}): {completed.stderr}"
        )
        return ConversionResult(outcome=ConversionOutcome.ROLLED_BACK)

    def run_drain(self, feature_ids: tuple[FeatureId, ...]) -> ConversionResult:
        """Drain a set of classic features in one sequential lockfile-held pass.

        Invokes `des-convert-to-atdd-pure --drain` over the named features.
        The drain converts every convertible feature and parks an untagged or
        manual-review one on `migration-parked.json` (M6); it always completes
        regardless of a parked feature. The user-observable `outcome` is
        `converted` when every feature converted, else the first parked
        feature's block reason -- the per-feature sets are read from
        `converted_features()` / `parked_features()`.
        """
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "--workspace",
                str(self.workspace),
                "--drain",
                "--feature-ids",
                " ".join(str(fid) for fid in feature_ids),
            ],
            cwd=self.workspace,
            main=_convert_to_atdd_pure_main,
        )
        assert exit_code == 0, f"convert --drain failed (rc={exit_code}): {stderr}"
        payload = json.loads(stdout)
        self._drain_payload = payload
        return ConversionResult(outcome=ConversionOutcome(payload["outcome"]))

    # --- Then-side: port-exposed observables --------------------------------

    def slice_plan_heading_present(self) -> bool:
        """Whether a `## Wave: DISCUSS / [REF] Slice Plan` heading was promoted."""
        delta = self._feature_dir / "feature-delta.md"
        if not delta.is_file():
            return False
        return "## Wave: DISCUSS / [REF] Slice Plan" in delta.read_text(
            encoding="utf-8"
        )

    def slice_status(self, slice_id: str) -> SliceStatus:
        """The reconciled `Status` of a slice row in the converted feature."""
        plan = self.run_dry_run()
        for declared_id, status in plan.slice_statuses:
            if declared_id == slice_id:
                return status
        raise AssertionError(f"no plan row for slice {slice_id!r}")

    def slice_provenance(self, slice_id: str) -> tuple[str, ...]:
        """The committed constituent SHAs recorded on a pending slice row."""
        plan = self.run_dry_run()
        for declared_id, provenance in plan.slice_provenance:
            if declared_id == slice_id:
                return provenance
        raise AssertionError(f"no plan row for slice {slice_id!r}")

    def effective_workflow_mode(self) -> WorkflowMode:
        """The feature's effective `workflow.mode` after the config flip."""
        if not self._config_path.is_file():
            return WorkflowMode.ABSENT
        in_workflow = False
        for raw in self._config_path.read_text(encoding="utf-8").splitlines():
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip())
            if indent == 0 and stripped:
                in_workflow = stripped.rstrip(":") == "workflow"
            elif in_workflow and stripped.startswith("mode:"):
                return WorkflowMode(stripped.split(":", 1)[1].strip())
        return WorkflowMode.ABSENT

    def ledger_seeded_via_m7_api(self) -> bool:
        """Whether the seeded ledger records carry `seq` + `record_hash` (M7 API).

        Read through the real `AtCompletionLedger` M7 fail-closed integrity
        read -- a record missing `seq` or `record_hash` would make that read
        raise `LedgerIntegrityViolation`, so a clean read of >=1 gate event
        is proof the seeding routed through the M7 API.
        """
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self.workspace
        )
        if not ledger.ledger_path().is_file():
            return False
        try:
            records = ledger.read_records()
        except LedgerIntegrityViolation:
            return False
        gate_events = [r for r in records if r.get("event") == "CarpaccioGateCleared"]
        return bool(gate_events) and all(
            "seq" in r and "record_hash" in r for r in gate_events
        )

    def journal_steps(self) -> tuple[ConversionStep, ...]:
        """The side-effect steps recorded in the conversion journal."""
        if not self._journal_path.is_file():
            return ()
        parsed = json.loads(self._journal_path.read_text(encoding="utf-8"))
        return tuple(ConversionStep(step) for step in parsed.get("steps", ()))

    def feature_is_half_converted(self) -> bool:
        """Whether the feature is in a limbo state -- neither classic nor atdd_pure.

        A fully-converted feature has all four journalled side-effect steps
        recorded and its roadmap archived; a half-converted one has some but
        not all. A feature is in limbo iff the journal has a partial step set.
        """
        steps = self.journal_steps()
        if not steps:
            return False
        return set(steps) != {
            ConversionStep.PROMOTE_HEADING,
            ConversionStep.SEED_LEDGER,
            ConversionStep.FLIP_CONFIG,
            ConversionStep.ARCHIVE_ROADMAP,
        }

    def roadmap_archived(self) -> bool:
        """Whether roadmap.json moved to `deliver/.classic-archive/`."""
        deliver = self._feature_dir / "deliver"
        archive = deliver / ".classic-archive"
        return (archive / "roadmap.json").is_file() and not (
            deliver / "roadmap.json"
        ).is_file()

    def parked_features(self) -> tuple[FeatureId, ...]:
        """The features written to `migration-parked.json` by the drain (M6).

        Read from the on-disk `migration-parked.json` the drain writes -- the
        durable record proving a stuck feature was parked, not lost.
        """
        parked_path = self.workspace / "migration-parked.json"
        if not parked_path.is_file():
            return ()
        parsed = json.loads(parked_path.read_text(encoding="utf-8"))
        return tuple(FeatureId(row["feature_id"]) for row in parsed.get("parked", []))

    def converted_features(self) -> tuple[FeatureId, ...]:
        """The features the drain reconciled onto the atdd_pure spine (M6).

        Per-feature drain observable mirroring `parked_features()`: the drain
        is a sequential pass over N features, so the outcome is a SET of
        reconciled feature ids -- not a single `ConversionResult.outcome`.
        Asserting only the latter would pass even if a feature were silently
        skipped.
        """
        if self._drain_payload is None:
            return ()
        return tuple(FeatureId(fid) for fid in self._drain_payload.get("converted", ()))

    def journal_records(self) -> tuple[tuple[str, ...], ...]:
        """The conversion journal as an order-preserving tuple of step records.

        Each inner tuple is one journalled side-effect record. Used to assert
        the journal is byte-for-byte unchanged across an idempotent re-run --
        `journal_steps()` alone does not capture record content.
        """
        if not self._journal_path.is_file():
            return ()
        parsed = json.loads(self._journal_path.read_text(encoding="utf-8"))
        return tuple((str(step),) for step in parsed.get("steps", ()))

    def classic_artifacts_present(self) -> bool:
        """Whether the pre-conversion classic `roadmap.json` lives in `deliver/`.

        A fully-converted feature has its roadmap archived under
        `.classic-archive/` -- so this is True only when the conversion never
        committed or was rolled back. Distinct from `feature_is_half_converted()`,
        which a fully-converted feature also satisfies as False.
        """
        return (self._feature_dir / "deliver" / "roadmap.json").is_file()

    def make_feature_dir_read_only(self) -> None:
        """Make the feature directory non-writable (C7a degraded resource).

        Arms the adapter-boundary failure the journalled converter must refuse
        cleanly -- leaving the classic artifacts intact, no half-conversion.
        The original mode is remembered so `run_convert` can restore writability
        once the refusal is observed (pytest's `tmp_path` cleanup needs it).
        """
        self._feature_dir_original_mode = self._feature_dir.stat().st_mode
        self._feature_dir.chmod(0o555)

    def carpaccio_gate_dry_run_passes(self) -> bool:
        """Whether the converted feature passes the carpaccio entry-gate dry-run.

        Runs the real `des.cli.carpaccio_slice_gate` as a subprocess against
        the converted workspace -- a pure-function gate that reads the
        promoted slice plan, the `.feature` files, and the seeded ledger and
        writes nothing. Exit 0 means the slice cleared the entry gate.
        """
        exit_code, _stdout, _stderr = run_cli_in_process(
            [
                "--feature-id",
                str(self._feature_id),
                "--entering-slice",
                "slice-01",
                "--repo-root",
                str(self.workspace),
            ],
            cwd=self.workspace,
            main=_carpaccio_slice_gate_main,
        )
        return exit_code == 0

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed conversion observables (Mandate 8).

        Universe keys are port-exposed names ONLY: whether the slice-plan
        heading is promoted, the feature's effective workflow mode, the
        seeded-ledger record count, and whether the roadmap is archived.
        """
        ledger = AtCompletionLedger(
            feature_id=str(self._feature_id), project_root=self.workspace
        )
        ledger_count = 0
        if ledger.ledger_path().is_file():
            try:
                ledger_count = len(ledger.read_records())
            except LedgerIntegrityViolation:
                ledger_count = -1
        return {
            "feature.slice_plan_heading_present": self.slice_plan_heading_present(),
            "feature.workflow_mode": self.effective_workflow_mode().value,
            "feature.ledger_record_count": ledger_count,
            "feature.roadmap_archived": self.roadmap_archived(),
        }


# --- slice-05: audit-log replay verification gate ----------------------------


@dataclass
class ReplayComposition:
    """Composition root for the M5 audit-log replay verification gate.

    Proves that replaying a real pre-2026-05-07 commit (legacy 5-phase /
    v2.0-pipe names) through `verify_commit_trailers` + the `PhaseEventParser`
    MARK-HISTORICAL path runs GREEN -- the precondition the N+1 DELETE sweep
    depends on. Layer 4: real git + real verifier.

    A pre-decommission commit predates the HMAC `Reviewed-by:` trailer
    mechanism entirely, so the historical replay has TWO halves, both through
    REUSED production code (neither verifier is modified):

      * `verify_commit_trailers` (non-strict) over the real legacy commit --
        a trailer-free commit verifies clean (exit 0);
      * the `PhaseEventParser` over the legacy v2.0-pipe execution-log the
        commit carries -- every 5-phase pipe event parses to a `PhaseEvent`.
    """

    workspace: Path
    _legacy_sha: str | None = field(default=None, init=False)

    # A real pre-2026-05-07 audit log: legacy 5-phase phase names, v2.0
    # pipe-delimited "step|phase|status|outcome|timestamp" events. This is the
    # exact shape an execution-log.json carried before the ADR-025 3-phase
    # canon -- the input the N+1 DELETE sweep must prove still replays.
    _LEGACY_PIPE_EVENTS: tuple[str, ...] = (
        "01-01|PREPARE|EXECUTED|PASS|2026-02-02T10:00:00Z",
        "01-01|RED_ACCEPTANCE|EXECUTED|PASS|2026-02-02T10:05:00Z",
        "01-01|RED_UNIT|EXECUTED|PASS|2026-02-02T10:10:00Z",
        "01-01|GREEN|EXECUTED|PASS|2026-02-02T10:20:00Z",
        "01-01|COMMIT|EXECUTED|PASS|2026-02-02T10:30:00Z|12|45000",
    )

    def _git(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Run a git subprocess inside the workspace."""
        return run_git(self.workspace, *args)

    def given_pre_decommission_commit(self) -> None:
        """Create a real pre-2026-05-07 commit carrying a legacy audit log.

        Materialises a real git repo and commits a legacy `execution-log.json`
        whose `events` are v2.0 pipe-delimited 5-phase strings -- the artifact
        shape that predates the classic-spine decommission. The commit carries
        no `Reviewed-by:` trailer, exactly as a pre-decommission commit would.
        """
        self.workspace.mkdir(parents=True, exist_ok=True)
        git_init_with_identity(self.workspace)
        log_path = self.workspace / "execution-log.json"
        log_path.write_text(
            json.dumps({"events": list(self._LEGACY_PIPE_EVENTS)}, indent=2),
            encoding="utf-8",
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "feat(legacy): a pre-decommission step")
        self._legacy_sha = self._git("rev-parse", "HEAD").stdout.strip()

    def run_replay(self) -> ReplayOutcome:
        """Replay the legacy commit through verify_commit_trailers + PhaseEventParser.

        Two halves, both REUSED production code:

          1. `des.cli.verify_commit_trailers` over the real legacy commit -- a
             pre-decommission commit has no `Slice-Id:` trailer, so the repurposed
             verifier exits 7 (INDETERMINATE: cannot-evaluate / nothing-to-audit).
             Exit 7 is accepted as non-failure for replay: it means there is no
             Slice-Id to audit, not that verification failed. Exit 45 (rejection)
             is the failure case.
          2. `des.domain.phase_event.PhaseEventParser.parse_all` over the
             commit's legacy v2.0-pipe execution log -- every 5-phase pipe
             event must parse to a `PhaseEvent`.

        The replay is GREEN iff both halves succeed.
        """
        from des.domain.phase_event import PhaseEventParser

        exit_code = self._verify_trailers_exit_code()
        # Exit 0 = all slices approved; exit 7 = INDETERMINATE (no Slice-Id trailer
        # -- nothing to audit, not a failure). Both are acceptable for a legacy commit.
        # Exit 45 = ATReviewNotApproved (a hard rejection) = RED.
        if exit_code not in (0, 7):
            return ReplayOutcome.RED
        events = PhaseEventParser().parse_all(list(self._LEGACY_PIPE_EVENTS))
        if len(events) != len(self._LEGACY_PIPE_EVENTS):
            return ReplayOutcome.RED
        return ReplayOutcome.GREEN

    def _verify_trailers_exit_code(self) -> int:
        """Run the real `des-verify-commit-trailers` CLI over the legacy commit."""
        exit_code, _stdout, _stderr = run_cli_in_process(
            [
                "--commit",
                str(self._legacy_sha),
            ],
            cwd=self.workspace,
            main=_verify_commit_trailers_main,
        )
        return exit_code


# --- slice-07: classic deprecation marking -----------------------------------


@dataclass
class DeprecationComposition:
    """Production-wired composition root for the release-N deprecation marking.

    EXTENDS the `workflow.mode` resolver: `classic` still resolves and runs
    (fallback floor intact) but emits a loud per-dispatch `ClassicSpineDeprecated`
    advisory; the `.nwave/config.yaml` default flips so an absent `workflow.mode`
    resolves to `atdd_pure`. No classic artifact is deleted (release N).

    Pillar 3: the SUT is the REAL `des.cli.init_log.resolve_dispatch_mode`
    DELIVER-dispatch resolver, invoked over a fixture `.nwave/config.yaml`
    written into a pytest `tmp_path`. Nothing is faked -- the resolver is pure
    filesystem-read + stderr/audit-log emission. The live repo config is never
    touched: the AT exercises the resolver against fixture configs only.
    """

    workspace: Path
    _resolved_mode: WorkflowMode | None = field(default=None, init=False)
    _audit_log: list[str] = field(default_factory=list, init=False)

    @property
    def _config_path(self) -> Path:
        return self.workspace / ".nwave" / "config.yaml"

    def configure_workflow_mode(self, mode: WorkflowMode) -> None:
        """Set (or omit) `.nwave/config.yaml:workflow.mode` for the project.

        Writes a fixture `.nwave/config.yaml` into the workspace `tmp_path`.
        For `WorkflowMode.ABSENT` the config carries no `workflow:` block, so
        the resolver sees an absent key and must apply the atdd_pure default.
        """
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        if mode is WorkflowMode.ABSENT:
            self._config_path.write_text(
                "atdd_pure:\n  carpaccio_slice_max: 3\n",
                encoding="utf-8",
            )
            return
        self._config_path.write_text(
            f"atdd_pure:\n  carpaccio_slice_max: 3\n\n"
            f"workflow:\n  mode: {mode.value}\n",
            encoding="utf-8",
        )

    def run_dispatch(self) -> int:
        """Run a DELIVER dispatch through the (extended) mode resolver.

        Invokes the REAL `resolve_dispatch_mode` -- the release-N DELIVER
        resolver -- against the fixture config, capturing the resolved mode
        and any advisory record appended to the dispatch audit log.
        """
        from des.cli.init_log import resolve_dispatch_mode

        self._audit_log = []
        resolved = resolve_dispatch_mode(self.workspace, audit_log=self._audit_log)
        self._resolved_mode = WorkflowMode(resolved)
        return 0

    def resolved_mode(self) -> WorkflowMode:
        """The mode the resolver selected for the dispatch."""
        assert self._resolved_mode is not None, "run_dispatch was not called"
        return self._resolved_mode

    def advisory_state(self) -> AdvisoryState:
        """Whether the `ClassicSpineDeprecated` per-dispatch advisory fired."""
        from des.cli.init_log import CLASSIC_SPINE_DEPRECATED_ADVISORY

        fired = any(
            CLASSIC_SPINE_DEPRECATED_ADVISORY in record for record in self._audit_log
        )
        return AdvisoryState.FIRED if fired else AdvisoryState.NOT_FIRED

    def classic_dispatch_completed(self) -> bool:
        """Whether the `classic` dispatch ran to completion (fallback still works).

        A classic dispatch runs to completion when the release-N resolver
        resolves an explicit `workflow.mode: classic` config straight back to
        `classic` -- the deprecated spine is still a live fallback floor, never
        a hard error. `run_dispatch` already invoked the real resolver; this
        asserts the resolution honoured `classic` rather than refusing it.
        """
        return self.resolved_mode() is WorkflowMode.CLASSIC

    @staticmethod
    def _migration_note_path() -> Path:
        """The shipped customer migration note (M8) in the live repo."""
        return repo_root() / "docs" / "guides" / "classic-spine-migration.md"

    def migration_note_present(self) -> bool:
        """Whether `docs/guides/classic-spine-migration.md` was shipped (M8)."""
        return self._migration_note_path().is_file()

    def migration_note_text(self) -> str:
        """The customer migration note content."""
        return self._migration_note_path().read_text(encoding="utf-8")

    def classic_artifact_deleted(self, artifact: str) -> bool:
        """Whether a named classic artifact was deleted (must be False in release N).

        Release N deprecates the classic spine but deletes nothing -- the
        DELETE sweep is the N+1 sibling epic. A classic artifact (a CLI, a
        domain schema, a skill, a task) is read from the live repo root: it is
        "deleted" only if its path no longer exists on disk.
        """
        return not (repo_root() / artifact).exists()

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed deprecation observables (Mandate 8).

        Universe keys are port-exposed names ONLY: the configured
        `workflow.mode` text of the fixture config (the resolver's input) and
        the count of advisory records on the dispatch audit log.
        """
        from des.cli.init_log import _read_workflow_mode

        configured = (
            _read_workflow_mode(self.workspace) if self._config_path.is_file() else None
        )
        return {
            "config.workflow_mode": configured or "absent",
            "dispatch.advisory_record_count": len(self._audit_log),
        }
