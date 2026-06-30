"""Composition root for slice-03 -- the `des feature-end run` feature-end-cycle CLI.

slice-03 of oss-feature-end-emit-cli (DDD-7 RATIFIED 2026-06-03; ATs REVISED
2026-06-03 to close the verdict-laundering gap the C_REVIEWER_AUDIT caught).

Mandate-13 (driving-port-only) + Pillar 3: the SUT is exercised through the
PRODUCTION single entry point -- the real `des feature-end run` subcommand
invoked end-to-end over the `des.cli.__main__` dispatcher as a subprocess
(Layer 3 subprocess, the SAME driving surface as slice-01's `des
emit-feature-end` and slice-02's `des feature-end sign`). The composition NEVER
imports the cycle use-case / its `main` and calls it at the step boundary; the
only entry is the real subprocess through the dispatcher, exactly as an
operator (or the eventual SubagentStop hook shim) invokes it (DDD-7 -- one
use-case, two thin driving adapters).

WHY THESE ATs WERE REVISED (verdict-laundering close-out)
---------------------------------------------------------
The first A_GREEN cycle DERIVED each gate's pass/fail from a
`--walking-skeleton-outcome` INPUT FLAG the test SUPPLIED -- the cycle minted
the `WalkingSkeletonGateRan` / `EnvironmentalE2eGateRan` heartbeats WITHOUT ever
running the real gate CLIs (RM-1 violation: "a record present means the gate
ACTUALLY RAN" was vacuously satisfiable). Root enabler: the ATs handed the cycle
the verdict, so NO AT ever drove a REAL gate FAIL -- the test could not catch the
laundering because it supplied the answer.

The revision DROPS the verdict-injection seam entirely. The cycle now receives
ONLY the gate ENVIRONMENT (a real installable feature workspace + a real env-e2e
block); it MUST invoke the real `des walking-skeleton-gate --feature-dir` and
`des verify-environmental-e2e --mode run` CLIs and read their REAL verdicts (DDD-6
"the cycle RUNS each gate"). The test controls what makes the real gate pass/fail
(`stage_*` workspace shaping), NEVER the verdict directly.

  AT-1 happy path     -> a REAL installable feature whose REAL walking-skeleton
                          gate run reaches PASS (no entry-points, ships no
                          installer artifact -> the gate builds+installs the wheel
                          and PASSES) and a REAL env-e2e `--mode run` reaches PASS.
  AT-3 fail-closed     -> a REAL feature workspace with NO `pyproject.toml` so the
                          REAL walking-skeleton gate's build leg fails
                          (`ArtifactBuildError` -> `GateOutcome.at_failure`,
                          exit 1) BEFORE any wheel/network -- a genuine real-gate
                          FAIL the cycle must read and fail-close on, NOT an
                          injected verdict.

GATE-COST / HERMETICITY (flag for the A_GREEN crafter)
------------------------------------------------------
Both real gates BUILD + pip-install a wheel on their PASS path (fire-5 TD-15:
network-flaky + slow). AT-3's genuine FAIL is CHEAP (no `pyproject.toml` ->
build fails immediately, no wheel, no network). AT-1's genuine PASS is the
heavy/flaky one -- it stages the MINIMAL real installable project
(`_stage_passing_feature_workspace`) so the wheel build is a few-file no-deps
build, but it IS a real `pip wheel` + `pip install --target`. If the crafter
finds AT-1 too heavy/flaky for the layer-3 budget, the hermeticity decision
(e.g. a documented `--build-command` seam that still produces a REAL wheel from
the staged project, or a pre-built wheel fixture) is theirs to make -- but the
AT MUST still drive a REAL gate verdict; reverting to an injected verdict to
dodge the cost is the laundering this revision closes.

OBSERVABLE READ-BACK (substrate verification, NOT a second SUT)
--------------------------------------------------------------
After the cycle runs, the gate-heartbeat records (`WalkingSkeletonGateRan`,
`EnvironmentalE2eGateRan`) and the feature-end records (`EBatchRefactorCompleted`,
`FeatureEndReviewVerdict`) are read back through the production
`AtCompletionLedger` reader -- the SAME audit substrate `des verify-integrity`
consumes. A heartbeat record present means the gate ACTUALLY RAN (the gate
appends it on entry, BEFORE its verdict, RM-1) -- the anti-theater proof that
the cycle did not mint a pass without running the gate. This read-back is
allowed (Mandate-13): it verifies the observable SUBSTRATE the done-gate reads,
it is not the SUT.

PARTIAL-DONE HONESTY (DDD-6 decomposition boundary)
---------------------------------------------------
The honesty boundary is verified end-to-end by feeding the post-cycle ledger to
the REAL `des verify-integrity` consumer: it MUST still report the 2
`CoverageMapVerifiedAt{Distill,Deliver}Exit` records MISSING (their coverage-map
CLI does not exist until slice-04). The cycle does not falsely certify full
feature-done.

ANTI-THEATER FAIL-CLOSED (DDD-6)
-------------------------------
When the staged feature makes the REAL gate FAIL, the cycle must NOT emit a fake
pass / must NOT report feature-end complete. `refused_by_cycle` is the
discriminator that keeps the fail-closed scenario RED-for-the-right-reason: a
refusal must carry the cycle's structured `{"event": "FeatureEndCycleRefused",
...}` marker (a real fail-closed refusal, NOT a vacuous dispatcher miss).

There are no test doubles for the driving surface: the git working tree, the
reviewer signing key (env `NWAVE_REVIEWER_SIGNING_KEY`), the gate CLIs, and the
AT-completion ledger are real -- a layer-3 `@real-io` surface (Mandate 9/11:
example only, no PBT machinery). The only things the test sets are the
signing-key env var (an external/non-deterministic port per the Architecture of
Reference) and the per-feature staged workspace (environment SETUP -- what makes
the REAL gate pass or fail, never the verdict itself).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker, seed_feature_delta_git_repo

from .domain_types_slice_03 import (
    CoverageMapRecord,
    CycleOutcome,
    FeatureEndCycleResult,
    FeatureEndGate,
    FeatureEndRecord,
    FeatureId,
)
from .signed_coverage_map import (
    write_signed_coverage_map,
    write_unsigned_coverage_map,
)


_FEATURE_ID = FeatureId("oss-feature-end-cycle-demo")

# The reviewer agent + verdict the cycle's deep-review-sign leg signs.
_REVIEWER_AGENT = "nw-software-crafter-reviewer"
_DEEP_REVIEW_VERDICT = "APPROVED"


@dataclass
class IntegrityVerdict:
    """The observable result of `des verify-integrity` over the post-cycle ledger."""

    exit_code: int
    missing_records: frozenset[str]


class FeatureEndCycleComposition:
    """Production-wired composition root for the `des feature-end run` slice.

    The driving port is the real `des feature-end run` subcommand invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code, the gate-heartbeat + feature-end records the cycle's REAL gate
    runs + sign/emit leg append to the AT-completion ledger, and the post-cycle
    `des verify-integrity` partial-done verdict.

    The composition stages ONLY the gate ENVIRONMENT (the installable feature
    workspace + the env-e2e block) -- the cycle's REAL gate runs derive their own
    verdicts from that environment. There is no `--walking-skeleton-outcome`
    verdict input: the laundering seam is gone.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._feature_id = _FEATURE_ID
        # Env-parity (F21/RCA-#68): the `des` subprocess runs with
        # cwd=project_root (the per-test tmp workspace). Mark it a developer
        # checkout so the runtime-freshness gate AUTOSKIPS instead of the
        # customer-install REFUSAL (exit 78). Same honest fix as slice-01/02 --
        # NOT a NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._project_root)
        # The WS-gate fail-closed scenario (AT-3) stages its FAIL through the
        # ADR-098 invariant (a NEW installable in the delta with no WS AT cannot
        # dodge), set by stage_walking_skeleton_failing_feature. Passing scenarios
        # leave this False -> their delta adds no new installable -> NOT_APPLICABLE.
        self._ships_new_installable = False

    # --- environment SETUP (what makes the REAL gate pass or fail) -----------

    def stage_passing_feature(self) -> None:
        """Stage a real installable feature whose REAL gate runs reach PASS.

        Writes a minimal-but-real installable Python project under the feature
        root so the REAL `des walking-skeleton-gate` build+install leg succeeds
        and -- with no entry points and no shipped installer artifact -- reaches
        a genuine PASS. Writes the feature-delta with an `## Environmental E2E`
        block + a trivially-passing env-e2e test so the REAL
        `des verify-environmental-e2e --mode run` reaches a genuine PASS.

        This is environment SETUP, not verdict injection: the gates run for real
        against this workspace; the test asserts on the records the real runs
        emit, never on a supplied verdict.
        """
        self._write_feature_delta_with_e2e_block()
        self._write_passing_env_e2e_test()
        self._write_installable_project()
        self._write_walking_skeleton_manifest(entry_points=[])

    def stage_walking_skeleton_failing_feature(self) -> None:
        """Stage a real feature whose REAL walking-skeleton gate genuinely FAILS.

        ADR-098 (`fix-feature-end-ws-gate-applicability`) made the WS floor's
        applicability DELTA-DERIVED: a feature that adds a NEW installable root in
        its `master...HEAD` delta while declaring no walking-skeleton AT
        (`entry_points: []`) is `ships_installer_artifact=True` -> a domain FAIL
        (the un-gameable "a no-AT installer feature cannot dodge" invariant,
        guardrail in ADR-098). That is the REAL gate FAIL the cycle must read and
        fail-close on. `seed_feature_delta_git_repo(ships_new_installable=True)`
        (driven from run_cycle) ADDS the new installable in the delta.

        This SUPERSEDES the pre-ADR-098 staging (NO `pyproject.toml` -> build-leg
        `ArtifactBuildError`): under ADR-098 a no-installable feature is
        NOT_APPLICABLE (proceeds), not a FAIL, so the old staging no longer fails
        the gate. The anti-laundering purpose is preserved: the FAIL still comes
        from the real gate running against a real workspace, never an injected
        verdict -- only the FAIL TRIGGER moved to the ADR-098 invariant.
        """
        self._write_feature_delta_with_e2e_block()
        self._write_walking_skeleton_manifest(entry_points=[])
        # Drive the ADR-098 fail-closed path: the delta ships a NEW installable
        # with no WS AT -> domain FAIL (see seed_feature_delta_git_repo).
        self._ships_new_installable = True

    def stage_passing_signed_feature(self) -> None:
        """Stage a passing-gate feature THAT ALSO carries a genuinely-signed map.

        slice-04 made the coverage-map verify leg a HARD precondition of cycle
        success (option (b) RATIFIED Ale 2026-06-03): a feature whose gates pass
        but which has NO signed coverage-map now REFUSES. This stages the passing
        gate environment (the slice-03 PASS shape) AND a genuinely-signed
        coverage-map (via the SHARED ``write_signed_coverage_map`` builder -- the
        SAME real §5.3 digest slice-04 stages, NOT a minted constant), so the
        now-mandatory coverage-map leg PASSES and the cycle reaches a full
        6-record SUCCESS. The verdict is the real ported verify core's, derived
        from the staged artifact -- never injected.
        """
        self.stage_passing_feature()
        write_signed_coverage_map(self._feature_dir, str(self._feature_id))

    def stage_passing_unsigned_feature(self) -> None:
        """Stage a passing-gate feature whose coverage-map is genuinely UNSIGNED.

        The gates pass, but the coverage-map carries the producer's ``_pending_``
        digest (the only thing the automated producer renders; no human signed).
        Under slice-04's ratified design the cycle's REAL coverage-map verify leg
        REFUSES (``SignoffMissing``) and the cycle fail-closes, minting NEITHER
        ``CoverageMapVerifiedAt*`` record -- so the post-cycle ``des
        verify-integrity`` STILL honestly reports the 2 coverage-map records
        MISSING. This is the scenario-4 honesty boundary under the moved boundary:
        a genuinely-unsigned feature is not fully reconciled, and the integrity
        report says so.
        """
        self.stage_passing_feature()
        self._write_unsigned_coverage_map()

    # --- driving-port invocation (the SUT) -----------------------------------

    def run_cycle(self) -> FeatureEndCycleResult:
        """Invoke the REAL `des feature-end run` subcommand over the dispatcher.

        Runs the feature-end cycle: the cycle RUNS the 2 already-CLI'd gates
        (`des walking-skeleton-gate --feature-dir` + `des verify-environmental-e2e
        --mode run`) against the staged workspace, reads their REAL verdicts,
        then (on pass) signs (slice-02) + emits (slice-01). No
        `--walking-skeleton-outcome` is passed -- the verdict is the real gates',
        not the test's.
        """
        argv = [
            "feature-end",
            "run",
            "--repo",
            str(self._project_root),
            "--feature-id",
            str(self._feature_id),
            "--feature-dir",
            str(self._feature_dir),
            "--reviewer-agent-id",
            _REVIEWER_AGENT,
            "--verdict",
            _DEEP_REVIEW_VERDICT,
        ]
        # The WS gate computes applicability from `git diff --diff-filter=A
        # master...HEAD` (ADR-098). Stage a real repo whose delta has the scenario's
        # ADR-098-correct shape: passing -> no new installable -> NOT_APPLICABLE;
        # failing -> a new installable with no WS AT -> domain FAIL. Without a real
        # repo the git diff fails -> INDETERMINATE -> REFUSE for the wrong reason.
        seed_feature_delta_git_repo(
            self._project_root, ships_new_installable=self._ships_new_installable
        )
        completed = self._dispatch(argv)
        return self._cycle_result(completed)

    # --- observable read-back (ledger SUBSTRATE, NOT the SUT) ----------------

    def ledger_gate_records(self) -> frozenset[str]:
        """The gate-heartbeat records the cycle's REAL gate-runs appended.

        Read back through the production `AtCompletionLedger` readers (the same
        sets `des verify-integrity` reads). A record present means the gate
        ACTUALLY RAN (RM-1 heartbeat on entry) -- the anti-theater proof.
        """
        ledger = self._ledger()
        return ledger.walking_skeleton_events() | ledger.environmental_e2e_events()

    def ledger_feature_end_records(self) -> frozenset[str]:
        """The feature-end records the cycle's sign+emit leg appended to the ledger."""
        return self._ledger().feature_end_events()

    def ledger_coverage_map_records(self) -> frozenset[str]:
        """The coverage-map touchpoint records the cycle's REAL verify leg appended.

        Read back through the production `AtCompletionLedger` reader (the same set
        `des verify-integrity` reads -- the SAME reader slice-04 uses). A record
        present means the cycle's REAL coverage-map verify PASSED on a genuine
        signoff (it appends on a real pass, RM-1) -- the anti-theater proof that
        the cycle did not mint a record for an unsigned map.
        """
        return self._ledger().coverage_map_touchpoint_events(
            feature_id=str(self._feature_id)
        )

    def walking_skeleton_gate_ran(self) -> bool:
        """Whether the REAL walking-skeleton gate left its heartbeat (it ran).

        Read back through the production `AtCompletionLedger.walking_skeleton_events`
        reader. The heartbeat is appended on gate ENTRY (RM-1) by the REAL
        `des walking-skeleton-gate` CLI itself, so its presence proves the cycle
        invoked the real gate -- the anti-theater proof that the cycle did not
        mint a pass without running the gate.
        """
        return (
            FeatureEndGate.WALKING_SKELETON.value
            in self._ledger().walking_skeleton_events()
        )

    def environmental_e2e_gate_ran(self) -> bool:
        """Whether the REAL environmental-e2e gate left its heartbeat (it ran).

        Read back through the production `AtCompletionLedger.environmental_e2e_events`
        reader. The heartbeat is appended on gate ENTRY (RM-1) when the cycle
        invokes the REAL `des verify-environmental-e2e --mode run` -- its presence
        proves the gate ran for real, not that an input flag was echoed.
        """
        return (
            FeatureEndGate.ENVIRONMENTAL_E2E.value
            in self._ledger().environmental_e2e_events()
        )

    def verify_integrity(self) -> IntegrityVerdict:
        """Feed the post-cycle ledger to the REAL `des verify-integrity` consumer.

        Pins the partial-done honesty boundary (DDD-6): even after a successful
        cycle, integrity MUST still report the 2 `CoverageMapVerifiedAt*`
        records MISSING (their CLI ships in slice-04). Returns the integrity
        exit code + the set of records it reports missing.
        """
        completed = self._dispatch(
            [
                "verify-integrity",
                "--repo",
                str(self._project_root),
                "--feature-id",
                str(self._feature_id),
            ]
        )
        return IntegrityVerdict(
            exit_code=completed.returncode,
            missing_records=_extract_missing_records(completed.stdout),
        )

    def feature_end_namespace_advertises_run(self) -> bool:
        """Whether `des feature-end --help` advertises BOTH `sign` and `run`.

        Single-entry-point / 1:1 mirror probe (DDD-7, AD-26): the new `run` verb
        consolidates under the one `des feature-end` namespace alongside the
        slice-02 `sign` verb -- no new top-level entry proliferates. Reachable
        iff the help invocation exits zero and advertises both verbs.
        """
        completed = self._dispatch(["feature-end", "--help"])
        return (
            completed.returncode == 0
            and "run" in completed.stdout
            and "sign" in completed.stdout
        )

    # --- workspace staging helpers (environment, not assertion) --------------

    def _write_unsigned_coverage_map(self) -> None:
        """Write a genuinely-unsigned coverage-map (delegates to the shared builder).

        Reuses the SAME §5.3 body shape slice-04 uses for its unsigned/`_pending_`
        defect, from the ONE shared reproduction -- so the unsigned divergence
        partner of the signed fixture stays in lock-step.
        """
        write_unsigned_coverage_map(self._feature_dir, str(self._feature_id))

    def _write_feature_delta_with_e2e_block(self) -> None:
        """Write the feature-delta carrying an `## Environmental E2E` block.

        The env-e2e block makes the REAL `des verify-environmental-e2e --mode
        run` in-scope (a missing block would make it misscoped/exit-3, not a
        genuine PASS/FAIL run). The `- test:` line points at the env-e2e test
        the gate builds the wheel + runs against.
        """
        feature_dir = self._feature_dir
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "feature-delta.md").write_text(
            "# Feature Delta -- oss-feature-end-cycle-demo\n\n"
            "## Environmental E2E\n\n"
            "- test: tests/test_cycle_demo_e2e.py\n",
            encoding="utf-8",
        )

    def _write_passing_env_e2e_test(self) -> None:
        """Write a trivially-passing env-e2e test the REAL env-e2e gate runs.

        The REAL `des verify-environmental-e2e --mode run` builds the feature
        wheel, installs it into a clean prefix, and runs THIS test against the
        installed artifact. A single passing assertion gives the gate a genuine
        PASS verdict to read -- the test asserts on the gate's REAL verdict, not
        a supplied one.
        """
        tests_dir = self._feature_root / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_cycle_demo_e2e.py").write_text(
            "def test_installed_artifact_importable() -> None:\n"
            "    import cycle_demo\n\n"
            "    assert cycle_demo.OK is True\n",
            encoding="utf-8",
        )

    def _write_installable_project(self) -> None:
        """Write a minimal-but-REAL installable Python project under feature_root.

        A real `pyproject.toml` + a one-module package so the REAL gate's
        `pip wheel --no-deps` build + `pip install --target` succeed and the
        walking-skeleton gate reaches a genuine PASS (no entry points, ships no
        installer artifact). Minimal so the real wheel build stays as light as a
        real build can be -- but it IS a real build (see GATE-COST flag above).
        """
        feature_root = self._feature_root
        feature_root.mkdir(parents=True, exist_ok=True)
        (feature_root / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools>=61"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            'name = "cycle-demo"\n'
            'version = "0.0.1"\n\n'
            "[tool.setuptools]\n"
            'py-modules = ["cycle_demo"]\n',
            encoding="utf-8",
        )
        (feature_root / "cycle_demo.py").write_text(
            "OK = True\n",
            encoding="utf-8",
        )

    def _write_walking_skeleton_manifest(self, *, entry_points: list[str]) -> None:
        """Write the `walking-skeleton.json` manifest the real gate reads.

        `feature_root` points the REAL `des walking-skeleton-gate` at the
        installable project; `entry_points` (empty for the PASS shape) are the
        staged-prefix-relative paths the gate asserts present after install.
        """
        feature_dir = self._feature_dir
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / "walking-skeleton.json").write_text(
            json.dumps(
                {
                    "feature_id": str(self._feature_id),
                    "feature_root": str(self._feature_root),
                    "entry_points": entry_points,
                }
            ),
            encoding="utf-8",
        )

    @property
    def _feature_dir(self) -> Path:
        return self._project_root / "docs" / "feature" / str(self._feature_id)

    @property
    def _feature_root(self) -> Path:
        """The installable project root the walking-skeleton gate builds + installs."""
        return self._project_root / "src" / "cycle_demo_project"

    # --- subprocess plumbing -------------------------------------------------

    def _cycle_result(
        self, completed: subprocess.CompletedProcess[str]
    ) -> FeatureEndCycleResult:
        outcome = (
            CycleOutcome.SUCCEEDED
            if completed.returncode == 0
            else CycleOutcome.REFUSED
        )
        return FeatureEndCycleResult(
            outcome=outcome,
            exit_code=completed.returncode,
            gate_records=self.ledger_gate_records(),
            feature_end_records=self.ledger_feature_end_records(),
            refused_by_cycle=_carries_cycle_refusal(completed.stdout, completed.stderr),
        )

    def _ledger(self) -> AtCompletionLedger:
        return AtCompletionLedger(self._feature_id, self._project_root)

    def _dispatch(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        """Dispatch `des <argv>` through the real `des.cli.__main__` entry point."""
        # Keyless post-demotion (oss-review-verdict-demotion S4): scrub any
        # ambient signing key so the cycle's sign-leg runs entirely keyless.
        # Restored in `finally` -- shared-process safe.
        prior_key = os.environ.pop("NWAVE_REVIEWER_SIGNING_KEY", None)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                list(argv), cwd=str(self._project_root)
            )
        finally:
            if prior_key is not None:
                os.environ["NWAVE_REVIEWER_SIGNING_KEY"] = prior_key
        return subprocess.CompletedProcess(argv, exit_code, stdout, stderr)

    # --- typed expectations (Mandate-12 typed-parameter accessors) -----------

    @staticmethod
    def expected_gate_records() -> frozenset[str]:
        """The 2 gate-heartbeat records a successful cycle MUST have emitted."""
        return frozenset(
            {
                FeatureEndGate.WALKING_SKELETON.value,
                FeatureEndGate.ENVIRONMENTAL_E2E.value,
            }
        )

    @staticmethod
    def expected_feature_end_records() -> frozenset[str]:
        """The 2 feature-end records a successful cycle MUST have emitted."""
        return frozenset(
            {
                FeatureEndRecord.BATCH_REFACTOR_COMPLETED.value,
                FeatureEndRecord.DEEP_REVIEW_VERDICT.value,
            }
        )

    @staticmethod
    def coverage_map_records_still_missing() -> frozenset[str]:
        """The 2 coverage-map records absent when the coverage-map is unsigned.

        On an UNSIGNED coverage-map the cycle's REAL verify leg refuses and mints
        NEITHER record, so `des verify-integrity` reports both still missing. The
        scenario-4 honesty boundary asserts exactly this set.
        """
        return frozenset(
            {CoverageMapRecord.DISTILL_EXIT.value, CoverageMapRecord.DELIVER_EXIT.value}
        )

    @staticmethod
    def expected_coverage_map_records() -> frozenset[str]:
        """The 2 coverage-map records a genuine human-signed PASS MUST emit.

        On a genuinely-signed coverage-map the cycle's REAL verify leg PASSES and
        appends both records (RM-1: present <=> a real signed verify passed) --
        the scenario-1 6-record success asserts exactly this set is present.
        """
        return frozenset(
            {CoverageMapRecord.DISTILL_EXIT.value, CoverageMapRecord.DELIVER_EXIT.value}
        )


def _carries_cycle_refusal(stdout: str, stderr: str) -> bool:
    """Whether the refusal came from the CYCLE's own fail-closed check.

    The production cycle emits a structured `{"event": "FeatureEndCycleRefused",
    ...}` payload when a gate it runs FAILS (the same shape slice-01's
    `EmitRefused` / slice-02's `SignRefused` carry) -- a real fail-closed
    refusal, NOT a dispatcher miss. An unknown-verb dispatcher error (or a usage
    error from the dropped `--walking-skeleton-outcome` flag) emits NO such
    payload, so this returns False and the fail-closed scenario stays RED until
    the real cycle runs the real gate, reads its REAL fail verdict, and
    fail-closes with its own marker. This is the discriminator that closes the
    vacuous-refusal trap.
    """
    for stream in (stdout, stderr):
        for line in stream.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("event") == "FeatureEndCycleRefused":
                return True
    return False


def _extract_missing_records(stdout: str) -> frozenset[str]:
    """Pull the `missing_records` set off the integrity verdict's stdout.

    `des verify-integrity` emits a structured
    `{"event": "FeatureEndCycleIncomplete", "missing_records": [...]}` verdict
    when records are absent. Returns the named missing set (empty when the
    verdict carries none / the feature reconciled).
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        missing = payload.get("missing_records")
        if isinstance(missing, list):
            return frozenset(str(record) for record in missing)
    return frozenset()


__all__ = [
    "FeatureEndCycleComposition",
    "FeatureEndCycleResult",
    "IntegrityVerdict",
]
