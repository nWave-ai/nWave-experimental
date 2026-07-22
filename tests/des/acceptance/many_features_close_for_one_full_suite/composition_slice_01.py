"""Composition root + shared fixtures for many-features-close-for-one-full-suite
slice-01 (the walking skeleton -- charter
`a-maintainer-closes-several-ready-features-off-one-shared-suite-run.md`,
feature-delta Slice Plan row slice-01, Locked Decisions D-1/D-3,
ADR-FEATURE-END-BATCH-001).

Pillar 3 (App as in production): the SUT is the REAL `des feature-end
run-batch` / `des feature-end run` driving surface -- driven via the SAME
production `des.cli.__main__` dispatcher `tests/common/in_process_cli.py:
run_cli_in_process` uses in-process for every scenario except the feature's
SINGLE `@walking_skeleton`, which forks the REAL installed `des`
console-script (mirrors the `parallel-work-cleans-up-after-merge-back`
slice-01 precedent verbatim). This module NEVER imports
`des.application.feature_end_batch_service` (P1 -- the module does not exist
yet; a top-level import would BREAK collection). `run-batch` is not yet a
registered `feature-end` verb -- its absence surfaces as a RUNTIME dispatcher
error ("invalid choice") inside the call, never a collection-time error
(P1-P4, `nw-distill-red-scaffolding`).

-- REUSE, not rebuild --
`des.application.feature_end_cycle_service` (SHIPPED) is imported here ONLY
to monkeypatch its EXISTING pre-full-suite legs (`_run_walking_skeleton_gate`
/ `_run_environmental_e2e_gate` / `_run_coverage_map_verify_leg`) away, so
each member's cycle outcome is determined SOLELY by the shared full-suite
leg's genuine PASS/RED and (for the per-member-independence scenario) the
walking-skeleton leg's per-`feature_dir` stubbed outcome -- mirrors the
proven idiom in `tests/bugs/des/test_feature_end_refusal_names_failures.py::
_stub_pre_full_suite_legs` and `tests/des/unit/application/
test_feature_end_cycle_truncation_refusal.py`'s `_SLICE_PLAN` fixture
verbatim. The monkeypatch is applied in THIS process only -- harmless no-op
for the walking-skeleton scenario's real subprocess fork.

-- R5-vs-R6 RECONCILIATION (AT-BATCH-5, D-D6 per-member independence) --
AT-BATCH-5's ORIGINAL trigger (`seed_truncated_feature`, an undelivered
Slice-Plan slice) was an ELIGIBILITY signal: once slice-02's D-5 precheck
lands, it intercepts an undelivered slice BEFORE the per-member cycle is
ever reached, refusing the WHOLE batch instead of letting ONE member's own
leg refuse while a co-member proceeds -- the exact D-D6 behaviour AT-BATCH-5
exists to demonstrate becomes unreachable with that trigger. The fixture
below (`seed_eligible_but_leg_failing_feature`) replaces it with a member
that PASSES all 3 D-5 checks (a real `SliceCommitVerified` record, an
APPROVED manifest verdict, a real `ExamineVerdictRecorded` PASS charter) but
whose OWN walking-skeleton leg is stubbed to refuse -- a genuinely
NON-eligibility, per-member (`feature_dir`-scoped) refusal. doc-coherence /
execution-reach / fresh-clone are REPO-global (not `feature_dir`-scoped) and
would refuse identically for EVERY batch member sharing this hermetic repo,
so they cannot differentiate one member from another; walking-skeleton (and
env-e2e) are the only `feature_dir`-scoped legs, hence the differentiated
stub lives there -- fixture substrate throughout, never a real gate
subprocess, exactly like every OTHER pre-full-suite leg in this module.

-- THE OBSERVABLE OUTCOME (Mandate 8 Universe) --
Every `BatchRunOutcome` field is re-derived from REAL filesystem state (the
persisted JUnit artifact COUNT under `.nwave/telemetry/feature-end/`) and the
REAL `AtCompletionLedger` JSONL, independent of whether the not-yet-existing
CLI produces a parseable JSON payload -- so the RED reason is genuine missing
business behaviour, never a parsing artifact.

Layer 3 (a hermetic tmp_path git-free pytest repo + one real subprocess fork
for the walking skeleton, @real-io): example-only (Mandate 9 v2). No PBT
machinery imported -- sad paths enumerated explicitly (Mandate 11).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Precondition-substrate + observation reader (NOT the SUT) -- the SAME
# per-feature ledger the shipped feature-end machinery writes to.
from des.adapters.driven.logging.at_completion_ledger import (
    SLICE_COMMIT_VERIFIED,
    AtCompletionLedger,
)

# EXISTING module (SHIPPED) -- imported ONLY to monkeypatch its pre-full-suite
# legs away (fixture substrate, never the SUT). NEVER
# `des.application.feature_end_batch_service` (does not exist yet, P1).
from des.application import feature_end_cycle_service as svc

# EXISTING User-Examiner producer (SHIPPED) -- reused verbatim to seed a REAL
# `ExamineVerdictRecorded` PASS for the eligible-but-leg-failing fixture
# (R5-vs-R6 reconciliation, above), never a hand-rolled ledger shape.
from des.cli.record_examine_verdict import record_examine_verdict
from tests.common.in_process_cli import run_cli_in_process

from .steps.domain_types_slice_01 import BatchRunOutcome


_REVIEWER_AGENT_ID = "nw-software-crafter-reviewer"
_VERDICT = "APPROVED"

_MEMBER_EVENTS = frozenset(
    {
        "FeatureEndCycleComplete",
        "FeatureEndCycleRefused",
        "FeatureEndCycleIndeterminate",
    }
)
_BATCH_TERMINAL_EVENTS = frozenset(
    {
        "FeatureEndBatchComplete",
        "FeatureEndBatchRefused",
        "FeatureEndBatchIndeterminate",
        "FeatureEndBatchManifestRefused",
    }
)
_FEATURE_END_RECORD_EVENTS = frozenset(
    {"EBatchRefactorCompleted", "FeatureEndReviewVerdict"}
)

_FAILING_TEST_NAME = "test_widget_computes_correctly"

_TRUNCATED_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | first | shipped | | j |
| slice-02 | never delivered (no .feature) | to-design | | j |
"""

# The ATTESTED Slice-Plan a fully-eligible member carries (a SINGLE shipped
# slice, backed by a REAL `SliceCommitVerified` record below -- never a
# vacuously-absent Slice Plan) -- mirrors slice-02's
# `EligibilityBatchFixture._ATTESTED_SLICE_PLAN` shape (duplicated here
# deliberately: slice-01 is the BASE class future slices extend, it cannot
# import slice-02).
_ATTESTED_SLICE_PLAN = """# Feature Delta: {fid}

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|---|---|---|---|---|
| slice-01 | first | shipped | | j |
"""

_EXAMINER = "nw-user-examiner"
_EXAMINE_TIMESTAMP = "2026-07-20T00:00:00Z"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _venv_des_cmd() -> list[str]:
    """The `des` console-script belonging to the CURRENTLY-RUNNING Python
    environment -- derived from `sys.executable`, never PATH (mirrors the
    `parallel-work-cleans-up-after-merge-back` slice-01 precedent)."""
    venv_des = Path(sys.executable).parent / "des"
    if venv_des.exists():
        return [str(venv_des)]
    return [sys.executable, "-m", "des.cli.__main__"]


def _all_json_lines(stdout: str) -> list[dict]:
    lines = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            lines.append(json.loads(stripped))
        except json.JSONDecodeError:
            continue
    return lines


def _last_json_line(stdout: str) -> dict | None:
    lines = _all_json_lines(stdout)
    return lines[-1] if lines else None


class BatchFixture:
    """Composition-root service for many-features-close-for-one-full-suite
    slice-01 ATs.

    Pillar 3: builds a real hermetic pytest suite under `tmp_path` (mirrors
    `tests/bugs/des/test_feature_end_refusal_names_failures.py::_init_repo`),
    seeds real per-feature directories, fires the SAME `des feature-end`
    driving surface production code will use, and observes the outcome from
    REAL filesystem state + the REAL AT-completion ledger.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do a typed lookup + one method call; nothing
    more.
    """

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._repo = tmp_path / "repo"
        self._known_feature_ids: list[str] = []
        self._feature_dirs: dict[str, Path] = {}
        # Feature-dirs whose walking-skeleton leg the stub below refuses
        # (R5-vs-R6 reconciliation: a per-member, non-eligibility leg
        # failure) -- empty by default, every OTHER member's leg PASSes.
        self._leg_failing_feature_dirs: set[Path] = set()
        # Harmless no-op for the walking-skeleton's real subprocess fork
        # (this process's monkeypatch never crosses the fork boundary).
        self._stub_pre_full_suite_legs(monkeypatch)

    # --- pre-full-suite leg stubbing (fixture substrate, not the SUT) ------

    def _stub_pre_full_suite_legs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            svc,
            "_run_walking_skeleton_gate",
            self._walking_skeleton_stub,
        )
        monkeypatch.setattr(
            svc,
            "_run_environmental_e2e_gate",
            lambda *, ledger, repo_root, feature_id, feature_dir, walking_skeleton: (
                None
            ),
        )
        monkeypatch.setattr(
            svc,
            "_run_coverage_map_verify_leg",
            lambda *, ledger, repo_root, feature_id, feature_dir: None,
        )

    def _walking_skeleton_stub(self, *, repo_root: Path, feature_dir: Path):
        """PASSes (returns `repo_root`) for every member EXCEPT one whose
        `feature_dir` was registered via `seed_eligible_but_leg_failing_
        feature` -- reads `self._leg_failing_feature_dirs` at CALL time, so
        a scenario seeding that member AFTER construction still takes
        effect (Mandate 8: the differentiation lives in fixture state, never
        a real gate subprocess)."""
        if feature_dir in self._leg_failing_feature_dirs:
            return svc.CycleRefusal(
                "the walking-skeleton leg refused for this member (fixture "
                "substrate simulating a genuine per-member, NON-eligibility "
                "leg failure, D-D6) -- unrelated to the shared full-suite leg"
            )
        return repo_root

    # --- repo + suite provisioning ------------------------------------------

    def build_shared_repo(self, *, genuinely_red: bool) -> None:
        """Lay out one real, hermetic pytest-collectible git work-tree
        (mirrors `_init_repo` verbatim) -- the SAME tree every batch member
        in a scenario shares, so the full-suite leg's PASS/RED genuinely
        applies to the WHOLE batch, not to one feature."""
        self._repo.mkdir(parents=True, exist_ok=True)
        _git(self._repo, "init", "-q")
        _git(self._repo, "config", "user.email", "batch-slice01@example.test")
        _git(self._repo, "config", "user.name", "Batch Slice 01 AT")
        _git(self._repo, "config", "--local", "core.hooksPath", ".git/hooks")
        tests_dir = self._repo / "tests" / "unit"
        tests_dir.mkdir(parents=True)
        (self._repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        (self._repo / "conftest.py").write_text(
            "import pytest\n\n\n"
            "def pytest_collection_modifyitems(items):\n"
            "    for item in items:\n"
            "        item.add_marker(pytest.mark.unit)\n",
            encoding="utf-8",
        )
        (self._repo / "pytest.ini").write_text(
            "[pytest]\nmarkers =\n"
            "    unit: unit tests\n"
            "    integration: integration tests\n"
            "    acceptance: acceptance tests\n",
            encoding="utf-8",
        )
        (tests_dir / "test_base.py").write_text(
            "def test_base():\n    assert True\n", encoding="utf-8"
        )
        if genuinely_red:
            (tests_dir / "test_widget.py").write_text(
                f"def {_FAILING_TEST_NAME}():\n"
                "    assert 1 + 1 == 3, 'deliberately red witness'\n",
                encoding="utf-8",
            )
        _git(self._repo, "add", "-A")
        _git(self._repo, "commit", "-q", "-m", "base: walking skeleton")

    # --- per-feature provisioning --------------------------------------------

    def seed_ready_feature(self, feature_id: str) -> Path:
        """A minimal feature-dir with NO feature-delta.md (no Slice-Plan ->
        no undelivered-slice truncation refusal), mirrors the sibling gate
        tests' `_seed_feature_dir` verbatim."""
        feature_dir = self._repo / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True)
        self._known_feature_ids.append(feature_id)
        self._feature_dirs[feature_id] = feature_dir
        return feature_dir

    def seed_truncated_feature(self, feature_id: str) -> Path:
        """A feature-dir whose Slice-Plan declares a slice with NO delivered
        `.feature` file -- the EXISTING un-gameable truncation oracle refuses
        it BEFORE any gate runs (mirrors `test_feature_end_cycle_truncation_
        refusal.py`'s `_SLICE_PLAN` fixture verbatim)."""
        feature_dir = self._repo / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True)
        (feature_dir / "feature-delta.md").write_text(
            _TRUNCATED_SLICE_PLAN.format(fid=feature_id), encoding="utf-8"
        )
        self._known_feature_ids.append(feature_id)
        self._feature_dirs[feature_id] = feature_dir
        return feature_dir

    def seed_eligible_but_leg_failing_feature(self, feature_id: str) -> Path:
        """R5-vs-R6 reconciliation (AT-BATCH-5): a member that PASSES all 3
        D-5 eligibility checks -- a REAL `SliceCommitVerified` record for its
        sole Slice-Plan slice, the fixture's own default APPROVED manifest
        verdict, and a REAL `ExamineVerdictRecorded` PASS for its critical
        charter -- so a future eligibility precheck lets the batch proceed
        to the shared suite + per-member cycles, where its OWN
        `feature_dir`-scoped walking-skeleton leg then genuinely refuses (see
        `_walking_skeleton_stub`) -- a per-member, NON-eligibility refusal,
        exactly what D-D6 independence needs to demonstrate."""
        feature_dir = self.seed_ready_feature(feature_id)
        (feature_dir / "feature-delta.md").write_text(
            _ATTESTED_SLICE_PLAN.format(fid=feature_id), encoding="utf-8"
        )
        self._write_slice_commit_verified(feature_id, "slice-01")
        self._write_examine_verdict(feature_id, "PASS")
        self._leg_failing_feature_dirs.add(feature_dir)
        return feature_dir

    def _write_slice_commit_verified(self, feature_id: str, slice_id: str) -> None:
        """Appends via the SAME producer surface every shipped
        `SliceCommitVerified` writer uses (`AtCompletionLedger.
        append_gate_event`, M7 write contract) -- never a hand-rolled JSON
        line (a hand-written record missing the M7 `seq`/`record_hash`/
        `timestamp` fields breaks `AtCompletionLedger.read_records()`'s own
        integrity contract)."""
        AtCompletionLedger(feature_id, self._repo).append_gate_event(
            SLICE_COMMIT_VERIFIED, slice_id, feature_id=feature_id
        )

    def _charter_path(self, feature_id: str) -> Path:
        charter_dir = self._repo / "docs" / "product" / "expectations" / feature_id
        charter_dir.mkdir(parents=True, exist_ok=True)
        charter_path = charter_dir / "the-critical-charter.md"
        if not charter_path.is_file():
            charter_path.write_text(
                "# The critical charter\n\nIntent.\n", encoding="utf-8"
            )
        return charter_path

    def _write_examine_verdict(self, feature_id: str, verdict: str) -> None:
        """`slice_id="feature-end"` -- FEATURE scope, matching the SHIPPED
        per-member charter-examine gate's own expectation exactly (the SAME
        scope slice-02's `EligibilityBatchFixture._write_examine_verdict`
        empirically confirmed)."""
        record_examine_verdict(
            repo=self._repo,
            feature_id=feature_id,
            slice_id="feature-end",
            charter_path=self._charter_path(feature_id),
            verdict=verdict,
            observations=f"the critical charter {verdict.lower()}ed EXAMINE",
            examiner=_EXAMINER,
            timestamp=_EXAMINE_TIMESTAMP,
        )

    # --- manifest authoring ---------------------------------------------------

    def _spec_for(self, feature_id: str) -> dict[str, str]:
        return {
            "feature_id": feature_id,
            "feature_dir": str(self._feature_dirs[feature_id]),
            "reviewer_agent_id": _REVIEWER_AGENT_ID,
            "verdict": _VERDICT,
        }

    def write_manifest_for(self, feature_ids: list[str]) -> Path:
        entries = [self._spec_for(fid) for fid in feature_ids]
        return self._write_manifest(entries)

    def write_malformed_manifest(self, feature_ids: list[str]) -> Path:
        """The SECOND entry is missing its required `reviewer_agent_id`
        field -- a structural-validation-only defect (D-D7/D-D8), never a
        readiness concern."""
        entries = [self._spec_for(fid) for fid in feature_ids]
        assert len(entries) >= 2, "the malformed-manifest fixture needs >=2 entries"
        del entries[1]["reviewer_agent_id"]
        return self._write_manifest(entries)

    def _write_manifest(self, entries: list[dict[str, str]]) -> Path:
        manifest_path = self._repo / "manifest.json"
        manifest_path.write_text(json.dumps(entries), encoding="utf-8")
        return manifest_path

    # --- real filesystem/ledger observation (independent of the payload) ---

    def _junit_artifact_count(self) -> int:
        junit_dir = self._repo / ".nwave" / "telemetry" / "feature-end"
        if not junit_dir.is_dir():
            return 0
        return len(list(junit_dir.glob("*-suite.junit.xml")))

    def feature_end_records_for(self, feature_id: str) -> int:
        ledger = AtCompletionLedger(feature_id, self._repo)
        try:
            records = ledger.read_records()
        except Exception:
            return 0
        return sum(1 for r in records if r.get("event") in _FEATURE_END_RECORD_EVENTS)

    def _total_feature_end_records(self) -> int:
        return sum(self.feature_end_records_for(fid) for fid in self._known_feature_ids)

    # --- driving-port invocation (the CLI under specification) -------------

    def run_batch_in_process(self, manifest_path: Path) -> BatchRunOutcome:
        """Drive `feature-end run-batch` IN-PROCESS through the SAME
        production `des` dispatcher every other `des <subcommand>`
        invocation goes through. `run-batch` is not yet a registered
        `feature-end` verb (P1-P4): the sub-dispatcher's own "invalid
        choice" argparse error is a RUNTIME failure inside this call, never
        a collection-time error."""
        exit_code, stdout, _stderr = run_cli_in_process(
            ["feature-end", "run-batch", str(manifest_path), "--repo", str(self._repo)],
            cwd=str(self._repo),
        )
        return self._interpret(exit_code, stdout)

    def run_batch_subprocess(self, manifest_path: Path) -> BatchRunOutcome:
        """Drive `feature-end run-batch` as a REAL, forked `des`
        console-script subprocess -- the feature's SINGLE `@walking_skeleton`
        scenario, proving the installed artifact is wired end-to-end."""
        argv = _venv_des_cmd() + [
            "feature-end",
            "run-batch",
            str(manifest_path),
            "--repo",
            str(self._repo),
        ]
        completed = subprocess.run(
            argv, capture_output=True, text=True, check=False, cwd=self._repo
        )
        return self._interpret(completed.returncode, completed.stdout)

    def run_classic(self, feature_id: str, feature_dir: Path) -> dict:
        """Drive the EXISTING, UNCHANGED `feature-end run` verb (D-1)
        in-process, returning its single JSON-line payload verbatim."""
        exit_code, stdout, _stderr = run_cli_in_process(
            [
                "feature-end",
                "run",
                "--repo",
                str(self._repo),
                "--feature-id",
                feature_id,
                "--feature-dir",
                str(feature_dir),
                "--reviewer-agent-id",
                _REVIEWER_AGENT_ID,
                "--verdict",
                _VERDICT,
            ],
            cwd=str(self._repo),
        )
        payload = _last_json_line(stdout) or {}
        return {"exit_code": exit_code, **payload}

    def run_batch_of_one(self, feature_id: str, feature_dir: Path) -> dict:
        """Drive `feature-end run-batch` over a SINGLE-entry manifest naming
        the SAME feature `run_classic` just closed -- the batch-of-one
        equivalence probe (D-1). Returns the ONE member line's payload (empty
        today: `run-batch` does not exist, so stdout carries no member
        line -- the genuine RED)."""
        manifest_path = self.write_manifest_for([feature_id])
        exit_code, stdout, _stderr = run_cli_in_process(
            ["feature-end", "run-batch", str(manifest_path), "--repo", str(self._repo)],
            cwd=str(self._repo),
        )
        member_line = next(
            (
                line
                for line in _all_json_lines(stdout)
                if line.get("event") in _MEMBER_EVENTS
            ),
            {},
        )
        return {"exit_code": exit_code, **member_line}

    def _interpret(self, exit_code: int, stdout: str) -> BatchRunOutcome:
        lines = _all_json_lines(stdout)
        member_lines = [line for line in lines if line.get("event") in _MEMBER_EVENTS]
        terminal = next(
            (
                line
                for line in reversed(lines)
                if line.get("event") in _BATCH_TERMINAL_EVENTS
            ),
            None,
        )
        batch_event = (
            terminal.get("event")
            if terminal
            else (lines[-1].get("event") if lines else None)
        )
        return BatchRunOutcome(
            exit_code=exit_code,
            batch_event=batch_event,
            member_count=len(member_lines),
            member_success_count=sum(
                1
                for line in member_lines
                if line.get("event") == "FeatureEndCycleComplete"
            ),
            member_refused_count=sum(
                1
                for line in member_lines
                if line.get("event") == "FeatureEndCycleRefused"
            ),
            junit_artifact_count=self._junit_artifact_count(),
            total_feature_end_records=self._total_feature_end_records(),
            failing_tests_named=bool(terminal and terminal.get("failing_tests")),
            refusal_error_text=str((terminal or {}).get("error", ""))
            if terminal
            else "",
        )


@pytest.fixture
def batch_fixture(tmp_path, monkeypatch) -> BatchFixture:
    """The single composition-root service all slice-01 step methods delegate to."""
    return BatchFixture(tmp_path, monkeypatch)


@pytest.fixture
def state_01() -> dict:
    """Per-scenario scratchpad: `outcome`, `before`, `manifest_path`,
    `classic`, `batch_of_one`, `feature_id`, `feature_dir`."""
    return {}


__all__ = [
    "BatchFixture",
]
