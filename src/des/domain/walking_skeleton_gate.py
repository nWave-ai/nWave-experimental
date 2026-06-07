"""WalkingSkeletonGate -- the tiered production-like walking-skeleton gate.

Domain service for feature `walking-skeleton-production-like-gate` (DESIGN /
Component Decomposition). It drives the staged-install fixture, runs the
feature's `@walking-skeleton` AT against the installed artifact, asserts the
D6 facets, and returns a `GateOutcome`.

slice-01 (the walking skeleton) -- the thinnest end-to-end vertical:

  1. `ArtifactBuilder.build`   -- build the delivered artifact.
  2. `StagedInstaller.install` -- install it into a clean prefix.
  3. D6 facet-1 (entry-point presence) -- before the AT runs, assert every
     entry point the AT invokes physically resolves within the staged prefix.
     A CLI absent from the shipped set is a hard FAIL (the F-11 class).
  4. run the feature's `@walking-skeleton` AT against the staged prefix.
  5. return `GateOutcome` (PASS / FAIL).

Pure-ish domain service: it owns the orchestration logic; all I/O is behind
the injected driven ports. Later slices add T2 escalation, fail-mode D, the
applicability predicate, and facets 2/3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.gate_outcome import (
    FacetViolation,
    GateOutcome,
    GateTier,
)
from des.domain.tier_ladder import TierCapability, TierLadder
from des.ports.driven_ports.artifact_builder import (
    ArtifactBuilder,
    ArtifactBuildError,
)
from des.ports.driven_ports.staged_installer import (
    InstalledTree,
    StagedInstaller,
    StagedInstallError,
)


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class WalkingSkeletonAt:
    """The feature's `@walking-skeleton` AT as the feature-end gate observes it.

    slice-02: the feature-end branch consumes the AT's recorded outcome --
    `present` is whether the feature authored a `@walking-skeleton` scenario at
    all, `passes` whether that scenario ran green against the installed
    artifact.
    """

    present: bool
    passes: bool


@dataclass(frozen=True)
class FeatureUnderGate:
    """The feature the gate evaluates -- its source root + AT declarations.

    `entry_points` are the staged-prefix-relative module/script paths the
    feature's `@walking-skeleton` AT invokes; the gate asserts each resolves
    within the installed prefix (D6 facet-1, entry-point presence).

    `ships_installer_artifact` is the B3 installer-shipped predicate -- a
    feature shipping a CLI/hook/installer artifact MUST carry a
    `@walking-skeleton` AT. `walking_skeleton_at`, when present, carries that
    AT's recorded outcome (slice-02 feature-end verdict).
    """

    feature_root: Path
    entry_points: tuple[str, ...]
    ships_installer_artifact: bool = False
    walking_skeleton_at: WalkingSkeletonAt | None = None
    walking_skeleton_applicable: bool | None = None
    not_applicable_rationale: str = ""
    delta_indeterminate: str | None = None
    added_installable_paths: tuple[str, ...] = ()

    def runs_walking_skeleton_at(self) -> bool:
        """Whether the feature carries a `@walking-skeleton` AT to run."""
        return bool(self.entry_points)


class WalkingSkeletonGate:
    """Domain service: evaluate the walking-skeleton gate for a feature."""

    def __init__(
        self,
        artifact_builder: ArtifactBuilder,
        staged_installer: StagedInstaller,
    ) -> None:
        self._artifact_builder = artifact_builder
        self._staged_installer = staged_installer

    def evaluate(
        self,
        feature: FeatureUnderGate,
        tier_capability: TierCapability,
        prefix: Path,
    ) -> GateOutcome:
        """Build, install, facet-check, and run the feature's walking skeleton.

        slice-01 path: provisions T1 (`pip install --target`), asserts D6
        facet-1 entry-point presence, runs the AT against the staged prefix.

        slice-02/03 path: a feature that EXPLICITLY declared
        `walking_skeleton_applicable: false` (guaranteed JUSTIFIED by the CLI
        parse boundary) is decided purely here, BEFORE any build/install. When
        the feature's git delta could not be established
        (`delta_indeterminate is not None`), the gate refuses to decide LOUD
        (INDETERMINATE) BEFORE the cross-check. Otherwise the delta-DETECTED
        `ships_installer_artifact` is the un-gameable cross-check: a feature whose
        delta ADDS a new installable root yet carries that declaration is a LIE
        (FAIL, naming the added paths); a feature whose delta adds none is
        honoured (NOT_APPLICABLE).
        """
        if feature.walking_skeleton_applicable is False:
            if feature.delta_indeterminate is not None:
                return GateOutcome.indeterminate(feature.delta_indeterminate)
            if feature.ships_installer_artifact:
                added = ", ".join(feature.added_installable_paths)
                return GateOutcome.at_failure(
                    GateTier.T0,
                    "walking_skeleton_applicable:false but the feature's change "
                    f"adds a new installable package ({added}) -- the declaration "
                    "is contradicted",
                )
            return GateOutcome.not_applicable(feature.not_applicable_rationale)
        tier = TierLadder.tier_of_record(tier_capability)
        if tier is None:
            return GateOutcome.facet_failure(
                GateTier.T0,
                FacetViolation.NO_TRANSFORM,
                "no provisionable tier",
            )
        installed = self._build_and_install(feature, prefix)
        if isinstance(installed, GateOutcome):
            return installed
        return self._check_facet_one_and_run(feature, installed, tier)

    def _build_and_install(
        self, feature: FeatureUnderGate, prefix: Path
    ) -> InstalledTree | GateOutcome:
        """Build the artifact and install it into the clean prefix (T1)."""
        try:
            artifact = self._artifact_builder.build(feature.feature_root)
        except ArtifactBuildError as exc:
            return GateOutcome.at_failure(GateTier.T1, f"build-failed: {exc}")
        try:
            return self._staged_installer.install(artifact, prefix)
        except StagedInstallError as exc:
            return GateOutcome.at_failure(GateTier.T1, f"install-failed: {exc}")

    def _check_facet_one_and_run(
        self,
        feature: FeatureUnderGate,
        installed: InstalledTree,
        tier: GateTier,
    ) -> GateOutcome:
        """D6 facet-1 entry-point presence, then run the walking-skeleton AT."""
        absent = self._entry_points_absent_from(installed, feature)
        if absent:
            return GateOutcome.facet_failure(
                tier,
                FacetViolation.ENTRY_POINT_ABSENT,
                "entry point absent from the installed tree: " + ", ".join(absent),
            )
        return self._run_walking_skeleton_at(feature, tier)

    @staticmethod
    def _run_walking_skeleton_at(
        feature: FeatureUnderGate, tier: GateTier
    ) -> GateOutcome:
        """Evaluate the feature's `@walking-skeleton` AT outcome (slice-02).

        An installer-shipping feature with no `@walking-skeleton` AT is a hard
        FAIL -- the absence is itself the defect. An AT that ran red is a FAIL;
        an AT that ran green is the PASS.
        """
        at = feature.walking_skeleton_at
        if at is None or not at.present:
            if feature.ships_installer_artifact:
                return GateOutcome.at_failure(
                    tier,
                    "no walking-skeleton test exists for an installer-shipped feature",
                )
            return GateOutcome.passed(tier)
        if not at.passes:
            return GateOutcome.at_failure(
                tier, "the walking-skeleton acceptance test ran red"
            )
        return GateOutcome.passed(tier)

    @staticmethod
    def _entry_points_absent_from(
        installed: InstalledTree, feature: FeatureUnderGate
    ) -> list[str]:
        """Entry points the AT invokes that do not resolve in the prefix."""
        return [
            entry_point
            for entry_point in feature.entry_points
            if not (installed.prefix / entry_point).exists()
        ]


__all__ = ["FeatureUnderGate", "WalkingSkeletonAt", "WalkingSkeletonGate"]
