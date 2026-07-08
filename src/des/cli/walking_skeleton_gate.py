"""des.cli.walking_skeleton_gate -- the tiered production-like walking-skeleton gate.

Feature `walking-skeleton-production-like-gate`, slice-01 -- THE walking
skeleton: the gate run against a delivered artifact installed into a clean
prefix (DESIGN / CLI contract).

An importable ``des.cli`` module run as a subprocess (the same shape U2
``des.cli.verify_slice_commit_completeness`` uses); the entry point is
``main(argv)``. Arguments:

    --feature-dir docs/feature/{id}/   (required)
    [--repo-root .] [--tier auto|t1|t2]
    -> single-line JSON {event, verdict, tier_of_record, reason, facet, ...}
    Exit codes: 0 PASS / 0 NOT_APPLICABLE / 1 FAIL / 2 usage / 3 UNVERIFIED.

The gate builds the delivered artifact, installs it into a clean prefix at
the highest provisionable tier, asserts the D6 facet-1 entry-point presence
check, runs the feature's `@walking-skeleton` AT against the installed
artifact, and emits a `WalkingSkeletonGateRan` heartbeat record BEFORE the
verdict (RM-1 -- "no gate ran" becomes a representable RED).

Stdlib-only at import time (the `des.cli` bundle-scan contract, per F-11's
fix); the build / install are invoked as subprocesses inside the adapters,
never imported. Layout-independent (an importable `des.cli` module that takes
`--repo-root`) -- the same shape as `des.cli.verify_slice_commit_completeness`.

The `--feature-dir` directory carries a `walking-skeleton.json` manifest
declaring the feature: `{feature_id, feature_root, entry_points: [...]}`.
`feature_root` is the installable project root the gate builds; `entry_points`
are the staged-prefix-relative paths the feature's `@walking-skeleton` AT
invokes, asserted present in the installed tree (D6 facet-1).
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from des.adapters.driven.build.build_dist_artifact_builder import (
    BuildDistArtifactBuilder,
)
from des.adapters.driven.environment.stub_environment_probe import (
    StubEnvironmentProbe,
)
from des.adapters.driven.git.git_feature_delta_adapter import GitFeatureDeltaAdapter
from des.adapters.driven.install.pip_target_installer import PipTargetInstaller
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.domain.gate_outcome import GateOutcome, GateVerdict
from des.domain.tier_ladder import TierCapability
from des.domain.walking_skeleton_gate import FeatureUnderGate, WalkingSkeletonGate
from des.ports.driven_ports.feature_delta_port import (
    AddedPaths,
    FeatureDeltaPort,
    Indeterminate,
)


_MANIFEST_NAME = "walking-skeleton.json"

_INSTALLABLE_SIGNATURES = ("pyproject.toml", "setup.py", "setup.cfg")

_CAPABILITY_BY_TIER_FLAG: dict[str, TierCapability] = {
    "t1": TierCapability.PIP_ONLY,
    "t2": TierCapability.DOCKER,
}


def _build_parser() -> argparse.ArgumentParser:
    """Build the gate CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="des walking-skeleton-gate",
        description="Run the walking-skeleton gate against a delivered artifact.",
    )
    parser.add_argument(
        "--feature-dir",
        required=True,
        help="The feature directory holding the walking-skeleton.json manifest.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="The repository root (layout-independent invocation).",
    )
    parser.add_argument(
        "--tier",
        choices=("auto", "t1", "t2"),
        default="auto",
        help="The tier to run at; 'auto' probes the environment.",
    )
    parser.add_argument(
        "--delta-base-ref",
        default="master",
        help="The base ref the feature's installability delta is measured "
        "against (git diff --diff-filter=A {base_ref}...HEAD).",
    )
    return parser


def _load_manifest(feature_dir: Path) -> dict[str, object] | None:
    """Read and parse the walking-skeleton manifest from the feature dir.

    Returns `None` when the manifest is ABSENT (manifest-optional: applicability
    is computed from the git delta instead of fail-closing -- ADR-098). Still
    raises `ValueError` (mapped to usage exit 2) when a manifest IS present but
    unparseable or not a JSON object -- a malformed manifest is a real error.
    """
    manifest_path = feature_dir / _MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"unparseable {_MANIFEST_NAME}: {exc}") from exc
    if not isinstance(manifest, dict):
        raise ValueError(f"{_MANIFEST_NAME} is not a JSON object")
    return manifest


def _added_installable_paths(added: AddedPaths) -> tuple[str, ...]:
    """The delta-ADDED paths whose basename is an installable build-system signature.

    A NEW installable root = an added path whose basename is one of
    `_INSTALLABLE_SIGNATURES`. Matched against the feature's git DELTA (the
    added-paths set), not the ambient `feature_root` direct children -- so a
    monorepo-internal change to an already-installable repo adds NONE.
    """
    return tuple(p for p in added.paths if Path(p).name in _INSTALLABLE_SIGNATURES)


def _feature_ships_new_installable(
    delta_port: FeatureDeltaPort, repo_root: Path, base_ref: str
) -> tuple[str, ...] | Indeterminate:
    """Delta-aware installability probe (slice-03) -- the un-gameable cross-check.

    Asks "does THIS feature's git DELTA introduce a NEW installable root?" via the
    `FeatureDeltaPort` (the ONLY I/O, behind the git adapter). Returns the
    delta-added installable paths (empty tuple = ships none), or propagates
    `Indeterminate` LOUD when git could not establish the delta -- never an empty
    tuple masking a git failure (the degrade-LOUD mandate, AD-21).
    """
    added = delta_port.added_paths(repo_root, base_ref)
    if isinstance(added, Indeterminate):
        return added
    return _added_installable_paths(added)


def _resolved_feature_root(manifest: dict[str, object], feature_dir: Path) -> Path:
    """Resolve the manifest `feature_root` against the feature directory."""
    feature_root = manifest.get("feature_root")
    if not isinstance(feature_root, str):
        raise ValueError(f"{_MANIFEST_NAME} missing string 'feature_root'")
    root = Path(feature_root)
    if not root.is_absolute():
        root = (feature_dir / root).resolve()
    return root


def _feature_under_gate(
    manifest: dict[str, object] | None,
    feature_dir: Path,
    delta_port: FeatureDeltaPort,
    repo_root: Path,
    base_ref: str,
) -> FeatureUnderGate:
    """Build the `FeatureUnderGate` value object from the manifest (or its absence).

    When the manifest is ABSENT (`None`, manifest-optional -- ADR-098), COMPUTE
    applicability from the feature's git delta via the SAME un-gameable
    `_feature_ships_new_installable` cross-check the empty-`entry_points` branch
    uses (NO duplicate logic) -- `feature_root` = the feature dir, no
    `entry_points`. When the manifest EXPLICITLY declares
    `walking_skeleton_applicable: false`, require a non-empty
    `not_applicable_rationale` (else USAGE exit 2) and freeze the DELTA-DETECTED
    installability into the VO (slice-03) -- the domain decides NOT_APPLICABLE /
    FAIL / INDETERMINATE purely over the carried bool + nullable string. When the
    feature's git delta cannot be established, the LOUD `Indeterminate` reason is
    carried as `delta_indeterminate`. Otherwise the slice-01 installable path holds
    (`feature_root` + `entry_points`).
    """
    if manifest is None:
        return _delta_derived_feature_under_gate(
            feature_dir, delta_port, repo_root, base_ref
        )

    root = _resolved_feature_root(manifest, feature_dir)

    if manifest.get("walking_skeleton_applicable") is False:
        rationale = manifest.get("not_applicable_rationale")
        if not (isinstance(rationale, str) and rationale.strip()):
            raise ValueError(
                "walking_skeleton_applicable:false requires a non-empty "
                "not_applicable_rationale"
            )
        ships = _feature_ships_new_installable(delta_port, repo_root, base_ref)
        if isinstance(ships, Indeterminate):
            return FeatureUnderGate(
                feature_root=root,
                entry_points=(),
                walking_skeleton_applicable=False,
                not_applicable_rationale=rationale,
                delta_indeterminate=ships.reason,
            )
        return FeatureUnderGate(
            feature_root=root,
            entry_points=(),
            ships_installer_artifact=bool(ships),
            walking_skeleton_applicable=False,
            not_applicable_rationale=rationale,
            added_installable_paths=ships,
        )

    entry_points = manifest.get("entry_points")
    if not isinstance(entry_points, list):
        raise ValueError(f"{_MANIFEST_NAME} missing list 'entry_points'")
    if entry_points:
        # The feature authored a @walking-skeleton AT -> the installable path
        # (slice-01): build/install + facet-1 + run the AT (unchanged).
        return FeatureUnderGate(
            feature_root=root,
            entry_points=tuple(str(entry) for entry in entry_points),
        )
    # Empty entry_points = no @walking-skeleton AT. COMPUTE applicability from the
    # declarative git delta instead of falling through to a build/install that
    # spuriously FAILs a non-installer feature (F-FEATURE-END-WS-GATE-APPLICABILITY;
    # "validation DERIVES from the declarative flow, no per-feature artifact"). Reuses
    # the SAME un-gameable delta cross-check the explicit-flag branch uses (:185) --
    # NO duplicate logic. delta-adds-no-installable -> NOT_APPLICABLE; delta-adds-an-
    # installable -> ships_installer_artifact=True -> domain FAILs (a no-AT installer
    # feature cannot dodge -- invariant preserved); git Indeterminate -> degrade-LOUD.
    return _delta_derived_feature_under_gate(root, delta_port, repo_root, base_ref)


def _delta_derived_feature_under_gate(
    feature_root: Path,
    delta_port: FeatureDeltaPort,
    repo_root: Path,
    base_ref: str,
) -> FeatureUnderGate:
    """Build the VO by COMPUTING applicability from the feature's git delta.

    The shared delta-compute path: the empty-`entry_points` branch and the
    manifest-ABSENT branch (manifest-optional, ADR-098) both reach the SAME
    `_feature_ships_new_installable` cross-check -- NO duplicate logic.
    delta-adds-no-installable -> NOT_APPLICABLE; delta-adds-an-installable ->
    ships_installer_artifact=True -> domain FAILs (a no-AT installer feature cannot
    dodge -- invariant preserved); git Indeterminate -> degrade-LOUD.
    """
    ships = _feature_ships_new_installable(delta_port, repo_root, base_ref)
    if isinstance(ships, Indeterminate):
        return FeatureUnderGate(
            feature_root=feature_root,
            entry_points=(),
            walking_skeleton_applicable=False,
            not_applicable_rationale="(delta-derived: applicability undecidable)",
            delta_indeterminate=ships.reason,
        )
    return FeatureUnderGate(
        feature_root=feature_root,
        entry_points=(),
        ships_installer_artifact=bool(ships),
        walking_skeleton_applicable=False,
        not_applicable_rationale=(
            "no @walking-skeleton AT and the feature delta adds no installable root "
            "-- the production-like gate does not apply (derived from declarative flow)"
        ),
        added_installable_paths=ships,
    )


def _capability(tier_flag: str) -> TierCapability:
    """Resolve the tier capability from the `--tier` flag (auto = probe)."""
    if tier_flag == "auto":
        return StubEnvironmentProbe().detect()
    return _CAPABILITY_BY_TIER_FLAG[tier_flag]


def _emit(outcome: GateOutcome) -> None:
    """Print the gate's single-line JSON verdict to stdout."""
    payload: dict[str, object] = {
        "event": "WalkingSkeletonGateVerdict",
        "verdict": outcome.verdict.value,
        "tier_of_record": outcome.tier_of_record.value,
        "reason": outcome.reason,
        "diagnostic": outcome.diagnostic,
    }
    if outcome.facet_violation is not None:
        payload["facet"] = outcome.facet_violation.value
    if outcome.how:
        payload["how"] = outcome.how
    print(json.dumps(payload, separators=(",", ":"), sort_keys=True))


def _emit_usage_error(message: str) -> None:
    """Print a usage-error JSON payload to stdout (exit 2)."""
    print(
        json.dumps(
            {"event": "WalkingSkeletonGateUsageError", "reason": message},
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    """Run the walking-skeleton gate; return the verdict exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    feature_dir = Path(args.feature_dir).resolve()
    repo_root = Path(args.repo_root).resolve()

    try:
        manifest = _load_manifest(feature_dir)
        feature = _feature_under_gate(
            manifest,
            feature_dir,
            GitFeatureDeltaAdapter(),
            repo_root,
            args.delta_base_ref,
        )
    except ValueError as exc:
        _emit_usage_error(str(exc))
        return 2

    feature_id = str(
        manifest.get("feature_id", feature_dir.name)
        if manifest is not None
        else feature_dir.name
    )

    # RM-1 -- emit the heartbeat BEFORE the verdict is known. "The gate was
    # reached" is now an attestation; its absence is a representable FAIL.
    ledger = AtCompletionLedger(feature_id, repo_root)
    ledger.append_walking_skeleton_gate_ran()

    gate = WalkingSkeletonGate(
        artifact_builder=BuildDistArtifactBuilder(),
        staged_installer=PipTargetInstaller(),
    )
    with tempfile.TemporaryDirectory(prefix=f"ws-prefix-{feature_id}-") as prefix_dir:
        outcome = gate.evaluate(feature, _capability(args.tier), Path(prefix_dir))

    if outcome.verdict is GateVerdict.PASS:
        ledger.append_walking_skeleton_tier_verified(
            tier_of_record=outcome.tier_of_record.value
        )

    _emit(outcome)
    return outcome.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
