"""Composition root for the walking-skeleton-production-like-gate acceptance suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root (the real `des.cli.walking_skeleton_gate` CLI invoked as a
`python -m` subprocess, the real DES feature-end `SubagentStop` hook branch,
the real `build_dist.py` build, the real `pip install --target`). Only the
non-deterministic `EnvironmentProbe` (Docker capability) is faked, per the
project Infrastructure Policy.

ALL business logic lives in this module's service methods -- the single source
of truth. Step bodies in the seven `steps/test_slice_*.py` files delegate to
these methods and never inline business logic (Mandate-12 criterion 3): each
step body is a typed lookup plus one composition call.

The seven slices share this one composition root. Each slice's step file
constructs a `WalkingSkeletonGateComposition` and drives it; the step-method
vocabulary (`given_*` / `when_*` / `then_*` named in domain language) is the
shared contract.

RED scaffold (Mandate 7 / ADR-025): this composition imports the production
modules the gate is built from. Those modules do not yet exist as working
surfaces -- DISTILL ships them as RED scaffolds whose entry points raise
`AssertionError`. Every scenario therefore reds for the RIGHT reason (missing
functionality), not `ImportError`. DELIVER replaces the scaffolds with the
implementation; the conftest collection hook lifts the xfail markers at GREEN.

Layer note: slice-01 is layer 5 (WS @wiring_e2e, real stack subprocess);
slices 02/03/04/06/07 are layer 3 (subprocess / FS acceptance); slice-05 is
layer 4 (integration over the pure `DistributionCompleteness` enumeration).
Per Mandate 9/11 every slice here is example-only -- no PBT machinery is
imported. The `@property`-tagged slice-05 scenarios document universal
invariants over the enumeration; their PBT generators are authored by DELIVER
against the layer-1 pure-function unit tests, not here.
"""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from des.cli import walking_skeleton_done_gate as _done_gate_cli  # noqa: F401

# --- Production surfaces under test ------------------------------------------
# slice-01 greened by DELIVER: `des.cli.walking_skeleton_gate` is the real CLI
# the @walking-skeleton AT spawns as a `python -m` subprocess; the gate domain
# + adapters back it. Slices 02..07 remain RED scaffolds.
from des.cli import walking_skeleton_gate as _gate_cli  # noqa: F401

from .domain_types import (
    DeferralReason,
    DistributionVerdict,
    FacetViolationKind,
    FeatureArtifactShape,
    FeatureId,
    GateVerdict,
    HookSubprocessOutcome,
    MarkerKind,
    OsSensitivity,
    Tier,
    TierCapability,
)


@dataclass(frozen=True)
class GateResult:
    """The user-observable outcome of one walking-skeleton gate evaluation.

    Mirrors the gate's single-line JSON verdict + exit code. Frozen: a result
    is an immutable observation, never mutated by an assertion.
    """

    verdict: GateVerdict
    tier_of_record: Tier
    exit_code: int
    reason: DeferralReason | None = None
    facet_violation: FacetViolationKind | None = None
    diagnostic: str = ""
    ran_prerequisite_tier_first: bool = False
    reused_cached_build: bool = False


@dataclass(frozen=True)
class DoneGateResult:
    """The user-observable verdict of the done-gate."""

    done_allowed: bool
    refusal_reason: str = ""


@dataclass(frozen=True)
class DistributionResult:
    """The user-observable verdict of the distribution-completeness check."""

    passed: bool
    verdict: DistributionVerdict | None = None
    named_command: str = ""
    diagnostic: str = ""


# The feature-artifact shapes that ship an installer-distributed artifact --
# the B3 installer-shipped predicate. A feature of one of these shapes MUST
# carry a `@walking-skeleton` AT; a `DOCS_ONLY` feature need not.
_SHIP_INSTALLER_SHAPES = frozenset(
    {
        FeatureArtifactShape.SHIPS_CLI,
        FeatureArtifactShape.SHIPS_HOOK,
        FeatureArtifactShape.SHIPS_SCRIPT_CLI,
        FeatureArtifactShape.SHIPS_INSTALLER,
    }
)


class _StagingArtifactBuilder:
    """In-memory `ArtifactBuilder` double for the layer-3 feature-end scenarios.

    The slice-02 feature-end ATs verify the gate VERDICT semantics, not the
    `pip wheel` build transform (slice-01's layer-5 vertical owns that). This
    double validates its input exactly like the real `BuildDistArtifactBuilder`
    -- it rejects an absent feature root -- so a wiring bug surfaces here too,
    then returns the feature root unchanged as the "built artifact".
    """

    def build(self, feature_root: Path) -> Path:
        assert feature_root.is_dir(), f"feature root must exist: {feature_root}"
        return feature_root


class _StagingInstaller:
    """In-memory `StagedInstaller` double for the layer-3 feature-end scenarios.

    Stages the feature's package tree into a clean prefix by copying it, so D6
    facet-1 (entry-point presence) is genuinely exercised against an installed
    tree. Validates its inputs like the real `PipTargetInstaller`.
    """

    def install(self, artifact: Path, prefix: Path) -> InstalledTree:
        from des.ports.driven_ports.staged_installer import InstalledTree

        assert artifact.is_dir(), f"artifact must exist: {artifact}"
        assert prefix is not None, "prefix must be provided"
        import shutil

        if prefix.exists():
            shutil.rmtree(prefix)
        shutil.copytree(artifact, prefix)
        return InstalledTree(prefix=prefix, python_path=prefix)


@dataclass
class WalkingSkeletonGateComposition:
    """Production-wired composition root for the walking-skeleton gate.

    Constructed per scenario over a pytest `tmp_path` deliver project. Holds
    the feature under test, the staged build/install fixture, the stubbed
    `EnvironmentProbe`, and the real AT-completion ledger + marker directory.

    Every public method is a SERVICE METHOD -- the single source of truth for
    one piece of gate behaviour. Step bodies call exactly one of these.
    """

    deliver_dir: Path
    _feature_id: FeatureId | None = field(default=None, init=False)
    _capability: TierCapability = field(default=TierCapability.PIP_ONLY, init=False)
    _shape: FeatureArtifactShape | None = field(default=None, init=False)
    _at_present: bool = field(default=False, init=False)
    _at_passes: bool = field(default=True, init=False)
    _cli_whitelisted: bool = field(default=True, init=False)
    # A per-scenario-unique package name -- the synthetic feature is a real
    # `pip wheel` build; a unique name keeps concurrent builds (xdist) from
    # racing on the shared pip wheel cache.
    _package_name: str = field(
        default_factory=lambda: f"wsdemo_{uuid.uuid4().hex[:12]}", init=False
    )

    # --- slice-01 synthetic-feature wiring -----------------------------------
    # The gate's subject is a self-contained installable feature project the
    # gate really builds (`pip wheel`) and really installs (`pip install
    # --target`). create_feature materialises that project + the gate manifest.

    @property
    def _feature_root(self) -> Path:
        """The installable synthetic-feature project root."""
        return self.deliver_dir / "feature-src"

    @property
    def _manifest_path(self) -> Path:
        """The walking-skeleton manifest the gate CLI reads from the feature dir."""
        return self.deliver_dir / "walking-skeleton.json"

    # --- Given-side service methods (precondition wiring) --------------------

    def create_feature(
        self, feature_id: FeatureId, shape: FeatureArtifactShape
    ) -> None:
        """Create a deliver project for a feature of the given artifact shape.

        Materialises a real, installable synthetic-feature project: a
        `pyproject.toml` + a `wsdemo` package carrying a CLI module. The gate
        builds and installs THIS project -- no fixture-folding of the verdict.
        """
        self._feature_id = feature_id
        self._shape = shape
        root = self._feature_root
        name = self._package_name
        package = root / name
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text('VERSION = "0.0.1"\n', encoding="utf-8")
        (package / "cli.py").write_text(
            'def main() -> int:\n    print("wsdemo ok")\n    return 0\n',
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            "[build-system]\n"
            'requires = ["setuptools>=61"]\n'
            'build-backend = "setuptools.build_meta"\n\n'
            "[project]\n"
            f'name = "{name}"\n'
            'version = "0.0.1"\n\n'
            "[tool.setuptools]\n"
            f'packages = ["{name}"]\n',
            encoding="utf-8",
        )

    def author_walking_skeleton_test(self, *, present: bool) -> None:
        """Author (or deliberately omit) the feature's @walking-skeleton AT."""
        self._at_present = present

    def make_walking_skeleton_test_pass(self, *, passes: bool) -> None:
        """Make the feature's installed walking-skeleton AT green or red.

        Records the AT outcome the feature-end gate consumes (slice-02): a
        green AT lets feature-end proceed, a red AT blocks it.
        """
        self._at_passes = passes

    def omit_cli_from_distribution_whitelist(self) -> None:
        """Drop the feature's script-mode CLI from the installer whitelist (F-11).

        The script-mode CLI then lives only under `scripts/cli/` -- never
        packaged, so it is absent from the `pip install --target` prefix and
        D6 facet-1 (entry-point presence) hard-FAILs.
        """
        self._cli_whitelisted = False

    def set_environment_capability(self, capability: TierCapability) -> None:
        """Inject the stubbed EnvironmentProbe's reported tier capability."""
        raise AssertionError(
            "RED scaffold -- set_environment_capability not yet implemented"
        )

    def set_fixture_failure(self, reason: DeferralReason) -> None:
        """Arm the staged-install fixture to fail with a classified reason (RM-6).

        A fixture failure is a PROVISIONING failure: the gate cannot stand up
        an environment to run the AT, so the verdict is UNVERIFIED (a deferral,
        marker written). It is NOT an AT red -- the AT never ran.
        """
        raise AssertionError("RED scaffold -- set_fixture_failure not yet implemented")

    def arm_t2_only_os_path_defect(self) -> None:
        """Arm an OS-path-layout bug that the T1 prefix tolerates but T2 fails.

        B4 review fix: an OS-path-layout defect is NOT a provisioning failure
        (it does not block the gate from standing up a tier) -- it makes the
        feature's `@walking-skeleton` AT run RED inside the container tier. The
        T2 verdict is therefore `FAIL` (a red AT), not `UNVERIFIED` (a
        deferral). The feature's path layout resolves on the clean-prefix tier
        but breaks on the container image's operating system, so T1 passes and
        T2 reds -- the container tier catches the bug T1 missed.
        """
        raise AssertionError(
            "RED scaffold -- arm_t2_only_os_path_defect not yet implemented"
        )

    def make_marker_directory_read_only(self) -> None:
        """Make `.nwave/markers/` unwritable so marker-write fails closed (RM-3)."""
        raise AssertionError(
            "RED scaffold -- make_marker_directory_read_only not yet implemented"
        )

    def classify_os_sensitivity(self, sensitivity: OsSensitivity) -> None:
        """Record the feature's OS-sensitivity for the RM-4 tier-debt decision."""
        raise AssertionError(
            "RED scaffold -- classify_os_sensitivity not yet implemented"
        )

    def set_arming_hook_subprocess_outcome(
        self, outcome: HookSubprocessOutcome
    ) -> None:
        """Arm the feature-end hook to see a degraded gate-subprocess exit (RM-1)."""
        raise AssertionError(
            "RED scaffold -- set_arming_hook_subprocess_outcome not yet implemented"
        )

    def record_entry_gate_applicability(self, *, applicable: bool) -> None:
        """Write the WalkingSkeletonApplicability SSOT record the entry gate owns."""
        raise AssertionError(
            "RED scaffold -- record_entry_gate_applicability not yet implemented"
        )

    def write_deferral_marker(self, kind: MarkerKind, *, artifact_hash: str) -> None:
        """Write a deferral / tier-debt marker bound to an artifact hash."""
        raise AssertionError(
            "RED scaffold -- write_deferral_marker not yet implemented"
        )

    def remove_marker_by_hand(self) -> None:
        """Delete the marker file without writing any verification record."""
        raise AssertionError(
            "RED scaffold -- remove_marker_by_hand not yet implemented"
        )

    def corrupt_marker(self) -> None:
        """Replace the marker file with malformed / empty JSON (RM-3 ST-20)."""
        raise AssertionError("RED scaffold -- corrupt_marker not yet implemented")

    def write_positive_verification_record(self) -> None:
        """Write a WalkingSkeletonTierVerified ledger record for the feature."""
        raise AssertionError(
            "RED scaffold -- write_positive_verification_record not yet implemented"
        )

    def prime_build_cache(self) -> None:
        """Prime the build cache so a re-run on an unchanged tree skips rebuild."""
        raise AssertionError("RED scaffold -- prime_build_cache not yet implemented")

    # --- When-side service methods (the gate invocations) -------------------

    def run_feature_end_gate(self, *, tier_request: Tier | None = None) -> GateResult:
        """Invoke the walking-skeleton gate via the feature-end SubagentStop branch.

        Layer 3 (subprocess / FS acceptance): the production
        `WalkingSkeletonFeatureEndGate` application service is driven directly
        -- the feature-end branch's gate step -- over the real
        `AtCompletionLedger` driven adapter. The build / install driven ports
        are in-memory doubles staging the synthetic feature into a clean
        prefix, so facet-1 entry-point presence is genuinely exercised without
        the layer-5 `pip wheel` round-trip (slice-01 owns that vertical).
        """
        from des.application.walking_skeleton_feature_end_gate import (
            WalkingSkeletonFeatureEndGate,
        )
        from des.domain.tier_ladder import (
            TierCapability as ProductionTierCapability,
        )
        from des.domain.walking_skeleton_gate import (
            FeatureUnderGate,
            WalkingSkeletonAt,
            WalkingSkeletonGate,
        )

        feature = FeatureUnderGate(
            feature_root=self._feature_root,
            entry_points=tuple(self._entry_points()),
            ships_installer_artifact=_SHIP_INSTALLER_SHAPES.__contains__(self._shape),
            walking_skeleton_at=WalkingSkeletonAt(
                present=self._at_present, passes=self._at_passes
            ),
        )
        gate = WalkingSkeletonGate(
            artifact_builder=_StagingArtifactBuilder(),
            staged_installer=_StagingInstaller(),
        )
        feature_end = WalkingSkeletonFeatureEndGate(gate, self._ledger())
        verdict = feature_end.run(
            feature,
            ProductionTierCapability(self._capability.value),
            self.deliver_dir / "ws-prefix",
        )
        outcome = verdict.outcome
        return GateResult(
            verdict=GateVerdict(outcome.verdict.value),
            tier_of_record=Tier(outcome.tier_of_record.value),
            exit_code=outcome.exit_code,
            facet_violation=(
                FacetViolationKind(outcome.facet_violation.value)
                if outcome.facet_violation is not None
                else None
            ),
            diagnostic=outcome.diagnostic,
        )

    def _entry_points(self) -> list[str]:
        """The staged-prefix-relative entry points the @walking-skeleton AT invokes.

        SHIPS_CLI -> the packaged `wsdemo/cli.py` module (installed -> present).
        SHIPS_SCRIPT_CLI with the whitelist omitted -> a `scripts/cli/*.py`
        path never packaged (absent from the prefix -> D6 facet-1 hard FAIL).
        """
        if self._shape is FeatureArtifactShape.SHIPS_SCRIPT_CLI and (
            not self._cli_whitelisted
        ):
            return ["scripts/cli/wsdemo_tool.py"]
        return [f"{self._package_name}/cli.py"]

    def _write_manifest(self) -> None:
        """Write the walking-skeleton manifest the gate CLI reads."""
        self._manifest_path.write_text(
            json.dumps(
                {
                    "feature_id": str(self._feature_id),
                    "feature_root": str(self._feature_root),
                    "entry_points": self._entry_points(),
                }
            ),
            encoding="utf-8",
        )

    def run_gate_cli_directly(self, *, tier_request: Tier | None = None) -> GateResult:
        """Invoke `des walking-skeleton-gate` as a real subprocess.

        Layer 5 (WS @wiring_e2e): a real `des` subprocess against the
        real CLI (post-slice-03 single-entry-point form) -- which really
        builds (`pip wheel`) and installs (`pip install --target`) the
        synthetic feature into a clean prefix.
        """
        self._write_manifest()
        tier_flag = "t2" if tier_request is Tier.T2 else "t1"
        # The gate CLI is nWave's own tool -- it runs from the developer
        # `src/` tree; the SUBJECT it installs into a clean prefix is the
        # feature's artifact, not the gate. Put `src/` on PYTHONPATH so the
        # `des walking-skeleton-gate` subprocess resolves `des`.
        env = dict(os.environ)
        env["PYTHONPATH"] = str(self._repo_root() / "src")
        completed = subprocess.run(
            [
                "des",
                "walking-skeleton-gate",
                "--feature-dir",
                str(self.deliver_dir),
                "--repo-root",
                str(self.deliver_dir),
                "--tier",
                tier_flag,
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        return self._parse_gate_result(completed.returncode, completed.stdout)

    @staticmethod
    def _parse_gate_result(exit_code: int, stdout: str) -> GateResult:
        """Parse the gate CLI's single-line JSON verdict into a GateResult."""
        payload = json.loads(stdout.strip().splitlines()[-1])
        facet_value = payload.get("facet")
        return GateResult(
            verdict=GateVerdict(payload["verdict"]),
            tier_of_record=Tier(payload["tier_of_record"]),
            exit_code=exit_code,
            facet_violation=(FacetViolationKind(facet_value) if facet_value else None),
            diagnostic=str(payload.get("diagnostic", "")),
        )

    def run_done_gate(self) -> DoneGateResult:
        """Invoke the done-gate (positive-record + marker-absence check)."""
        raise AssertionError("RED scaffold -- run_done_gate not yet implemented")

    def run_downstream_verification(
        self, *, against_artifact_hash: str, tier: Tier
    ) -> GateResult:
        """Run the downstream CI verification that may clear a marker / tier-debt."""
        raise AssertionError(
            "RED scaffold -- run_downstream_verification not yet implemented"
        )

    def run_carpaccio_entry_gate(self) -> GateResult:
        """Invoke the carpaccio entry gate's walking-skeleton-required branch.

        DESIGN slice-06: when a feature ships an installer artifact the entry
        gate asserts a `@walking-skeleton` scenario exists, and writes the B3
        `WalkingSkeletonApplicability` SSOT record. The verdict mirrors the
        gate JSON: PASS / NOT_APPLICABLE (docs-only feature) / FAIL (an
        installer-shipped feature with no `@walking-skeleton` AT).
        """
        raise AssertionError(
            "RED scaffold -- run_carpaccio_entry_gate not yet implemented"
        )

    # --- Then-side observation methods (port-exposed observables) -----------

    @staticmethod
    def _repo_root() -> Path:
        """The developer's repository root (this checkout).

        Used ONLY to put `src/` on the gate subprocess `PYTHONPATH` so the
        `des walking-skeleton-gate` invocation resolves `des`.
        It is deliberately NOT used as an assertion universe: the developer
        checkout is the test host, not the SUT (B3 review fix).
        """
        return Path(__file__).resolve().parents[5]

    @property
    def _prefix_root(self) -> Path:
        """The `tmp_path`-rooted prefix the gate is confined to.

        `deliver_dir` is `tmp_path / "deliver"`; its parent is the per-test
        pytest `tmp_path`. The gate is passed only paths under this root
        (`--feature-dir` / `--repo-root` both `deliver_dir`), so a correct gate
        physically cannot write outside it. This is the SUT's filesystem
        universe -- per-test isolated, never the shared developer checkout.
        """
        return self.deliver_dir.parent

    def _ledger(self) -> AtCompletionLedger:
        """The AT-completion ledger the gate appends its records to."""
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )

        return AtCompletionLedger(str(self._feature_id), self.deliver_dir)

    @staticmethod
    def _source_tree_fingerprint() -> dict[str, str]:
        """Content fingerprint of the developer source tree (`src/`, `scripts/`).

        B3 review fix: a content-keyed snapshot of the `.py` files present at
        capture time -- NOT a `git status` shell-out. The prior universe ran
        `git -C parents[5] status --porcelain`, which is environmental (the
        developer checkout, not the SUT) and flaky under xdist (a concurrent
        worker's writes leak into the porcelain output).

        Keyed by SHA-256 of file content. The cwd-isolated gate writes none of
        these, so the `before`/`after` fingerprints are identical. xdist-safe:
        tests never write `src/` or `scripts/`, and a file created by another
        worker does not appear here because only files present at the snapshot
        moment are fingerprinted.
        """
        import hashlib

        repo = WalkingSkeletonGateComposition._repo_root()
        fingerprint: dict[str, str] = {}
        for sub in ("src", "scripts"):
            base = repo / sub
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.py")):
                if not path.is_file():
                    continue
                rel = str(path.relative_to(repo))
                fingerprint[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
        return fingerprint

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed preservation universe (Mandate 8).

        B3 review fix: two port-exposed observables, neither shelling `git`
        against the live developer checkout:

        - `source_tree.content_fingerprint`: a content-keyed map of the
          developer source tree (`src/`, `scripts/` `.py` files). A
          cwd-isolated gate -- handed only `tmp_path` paths, installing into a
          `TemporaryDirectory` prefix -- writes none of these, so the map is
          unchanged across the gate run. This is the genuine SUT contract:
          "the gate touched no developer source file".
        - `prefix.tree`: the SUT's own `tmp_path`-rooted prefix tree (the
          relative-path file set). The gate legitimately writes build artifacts
          here; this key documents the bounded-change side of the universe.
        """
        prefix = self._prefix_root
        tree = sorted(
            str(p.relative_to(prefix)) for p in prefix.rglob("*") if p.is_file()
        )
        return {
            "source_tree.content_fingerprint": self._source_tree_fingerprint(),
            "prefix.tree": tree,
        }

    def heartbeat_record_present(self) -> bool:
        """Whether a WalkingSkeletonGateRan heartbeat exists for the feature."""
        from des.adapters.driven.logging.at_completion_ledger import (
            WALKING_SKELETON_GATE_RAN,
        )

        return WALKING_SKELETON_GATE_RAN in self._ledger().walking_skeleton_events()

    def positive_verification_record_present(self) -> bool:
        """Whether a WalkingSkeletonTierVerified record exists for the feature."""
        from des.adapters.driven.logging.at_completion_ledger import (
            WALKING_SKELETON_TIER_VERIFIED,
        )

        return (
            WALKING_SKELETON_TIER_VERIFIED in self._ledger().walking_skeleton_events()
        )

    def not_applicable_record_present(self) -> bool:
        """Whether a WalkingSkeletonNotApplicable record exists for the feature."""
        raise AssertionError(
            "RED scaffold -- not_applicable_record_present not yet implemented"
        )

    def tier_debt_record_present(self) -> bool:
        """Whether a walking-skeleton-tier-debt record exists for the feature."""
        raise AssertionError(
            "RED scaffold -- tier_debt_record_present not yet implemented"
        )

    def marker_present(self) -> bool:
        """Whether a walking-skeleton-unverified marker exists for the feature."""
        raise AssertionError("RED scaffold -- marker_present not yet implemented")

    def marker_reason_is_closed_enum(self) -> bool:
        """Whether the marker's `reason` field is a closed-enum value, not prose."""
        raise AssertionError(
            "RED scaffold -- marker_reason_is_closed_enum not yet implemented"
        )

    def applicability_record(self) -> dict[str, object]:
        """The WalkingSkeletonApplicability record (paths checked + matched rule)."""
        raise AssertionError("RED scaffold -- applicability_record not yet implemented")


@dataclass
class DistributionCompletenessComposition:
    """Composition root for the US-04 distribution-completeness arch test.

    Wraps the pure `DistributionCompleteness` enumeration domain over a
    `tmp_path` repo fixture. Layer 4 -- the enumeration logic is pure and
    statically derived; the `pytest` arch test is a thin driving adapter.
    """

    repo_dir: Path

    def given_hook_invoking_command(self, *, in_whitelist: bool) -> None:
        """Add a hook that subprocess-invokes a command, optionally whitelisted."""
        raise AssertionError(
            "RED scaffold -- given_hook_invoking_command not yet implemented"
        )

    def given_command_wiring_test(self, *, present: bool) -> None:
        """Add (or omit) a subprocess-real wiring test for the hook-invoked command."""
        raise AssertionError(
            "RED scaffold -- given_command_wiring_test not yet implemented"
        )

    def remove_hook_branch(self) -> None:
        """Delete the walking-skeleton branch from the feature-end hook handler."""
        raise AssertionError("RED scaffold -- remove_hook_branch not yet implemented")

    def make_marker_directory_untracked(self) -> None:
        """Remove the explicit un-ignore rule from a marker directory (RM-3 ST-21)."""
        raise AssertionError(
            "RED scaffold -- make_marker_directory_untracked not yet implemented"
        )

    def evaluate_completeness(self) -> DistributionResult:
        """Run the distribution-completeness check over the hook-invoked set."""
        raise AssertionError(
            "RED scaffold -- evaluate_completeness not yet implemented"
        )

    def evaluate_hook_branch_registration(self) -> DistributionResult:
        """Run the RM-2 static hook-branch-registration check."""
        raise AssertionError(
            "RED scaffold -- evaluate_hook_branch_registration not yet implemented"
        )

    def evaluate_marker_dir_tracked(self) -> DistributionResult:
        """Run the RM-3 ST-21 marker-directory git-tracked check."""
        raise AssertionError(
            "RED scaffold -- evaluate_marker_dir_tracked not yet implemented"
        )

    def gate_own_cli_enumeration(self) -> set[str]:
        """The enumerated hook-invoked command set, including the gate's own CLIs."""
        raise AssertionError(
            "RED scaffold -- gate_own_cli_enumeration not yet implemented"
        )


@dataclass
class CustomerScaffoldComposition:
    """Composition root for the US-05 customer-project CI scaffold (slice-07)."""

    customer_project_dir: Path

    def given_customer_project(self) -> None:
        """Create a customer project with no walking-skeleton CI job."""
        raise AssertionError(
            "RED scaffold -- given_customer_project not yet implemented"
        )

    def run_scaffold_step(self) -> None:
        """Run the nWave walking-skeleton scaffold step against the project."""
        raise AssertionError("RED scaffold -- run_scaffold_step not yet implemented")

    def run_scaffolded_ci_job(self, *, image_filled: bool) -> GateResult:
        """Run the scaffolded walking-skeleton CI job."""
        raise AssertionError(
            "RED scaffold -- run_scaffolded_ci_job not yet implemented"
        )

    def ci_job_text(self) -> str:
        """The materialised `.github/workflows/walking-skeleton.yml` content."""
        raise AssertionError("RED scaffold -- ci_job_text not yet implemented")

    def explanation_doc_text(self) -> str:
        """The materialised `docs/walking-skeleton.md` stub content."""
        raise AssertionError("RED scaffold -- explanation_doc_text not yet implemented")

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed scaffolded-files universe (Mandate 8)."""
        raise AssertionError("RED scaffold -- capture_universe not yet implemented")


@dataclass
class AuthoringPropagationComposition:
    """Composition root for the authoring-side propagation arch test (slices 15-16).

    DESIGN slices 08-09: the tiered walking-skeleton discipline must reach the
    authoring artifacts -- the test-design mandates skill, the `/nw-distill`
    command guidance, and every authoring agent's `Skill Loading Strategy`
    table -- so an acceptance designer authors a tier-correct walking skeleton
    up front rather than being ambushed by the enforcement gate.

    The check is a content arch test: it reads each authoring artifact and
    asserts the tiered-discipline content (T0/T1/T2 rows, the three D6 facets,
    the @walking-skeleton @wiring_e2e tagging contract, fail-mode-D) is present.
    For slice-16 it asserts each named agent's loading table references the
    tier-discipline skill -- the operative dispatch contract, per
    feedback_update_skill_loading_table_with_skill_changes_2026_05_19.

    Layer 4 (integration): the enumeration is pure + statically derived; the
    `pytest` arch test is a thin driving adapter. Example-only, no PBT.
    """

    repo_dir: Path

    def given_authoring_artifact_carries_discipline(self, artifact: str) -> None:
        """Record that an authoring artifact carries the tiered discipline."""
        raise AssertionError(
            "RED scaffold -- given_authoring_artifact_carries_discipline not yet "
            "implemented"
        )

    def given_authoring_artifact_omits_discipline(self, artifact: str) -> None:
        """Record that an authoring artifact omits the tiered discipline."""
        raise AssertionError(
            "RED scaffold -- given_authoring_artifact_omits_discipline not yet "
            "implemented"
        )

    def evaluate_skill_propagation(self, artifact: str) -> DistributionResult:
        """Run the propagation check over one authoring skill / command artifact."""
        raise AssertionError(
            "RED scaffold -- evaluate_skill_propagation not yet implemented"
        )

    def evaluate_loading_table_propagation(self, artifact: str) -> DistributionResult:
        """Run the propagation check over one authoring agent's loading table."""
        raise AssertionError(
            "RED scaffold -- evaluate_loading_table_propagation not yet implemented"
        )

    def evaluate_full_propagation(self) -> DistributionResult:
        """Run the propagation arch test over every authoring artifact."""
        raise AssertionError(
            "RED scaffold -- evaluate_full_propagation not yet implemented"
        )
