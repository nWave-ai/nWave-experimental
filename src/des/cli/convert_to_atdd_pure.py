"""des.cli.convert_to_atdd_pure -- the `des-convert-to-atdd-pure` conversion CLI.

Feature `classic-spine-decommission`, slice-05. Converts ONE classic feature to
the atdd_pure spine deterministically:

  * the pure `conversion_planner.dry_run` recovers the feature's slice plan and
    returns a `ConversionPlan`;
  * `--dry-run` prints that plan as JSON and writes NOTHING (plan-value
    pattern, contract shape unbounded-preservation);
  * the execute path applies the plan's four journalled side-effect steps
    through a write-scoped `SafeFileSystem`.

Hexagonal: an argparse driving adapter over the pure planner domain function
plus the `SafeFileSystem` driven adapter. The pure planner never touches the
filesystem; only `execute(plan, fs)` mutates anything.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.filesystem.safe_file_system_adapter import (
    SafeFileSystemAdapter,
)
from des.adapters.driven.git.git_history_probe import GitHistoryProbe
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedgerFactory
from des.domain import conversion_planner, feature_classifier


if TYPE_CHECKING:
    from collections.abc import Iterator


def main(argv: list[str] | None = None) -> int:
    """Convert one classic feature to atdd_pure. Returns an exit code."""
    args = _parse_args(argv)
    workspace = Path(args.workspace)

    if args.drain:
        return _run_drain(workspace, args.feature_ids)

    feature_id = args.feature_id

    feature_dir = workspace / "docs" / "feature" / feature_id
    config_path = workspace / ".nwave" / "config.yaml"
    journal_dir = workspace / ".nwave" / "conversion-journal"
    fs = SafeFileSystemAdapter(workspace=workspace, feature_id=feature_id)

    if args.rollback:
        conversion_planner.rollback(
            feature_id=feature_id,
            feature_dir=feature_dir,
            config_path=config_path,
            journal_dir=journal_dir,
            ledger_root=workspace,
            fs=fs,
        )
        sys.stdout.write(
            json.dumps({"outcome": "rolled-back", "feature_id": feature_id}) + "\n"
        )
        return 0

    # M7 / C7a clean-refusal guards -- evaluated BEFORE any plan is built or any
    # journalled side effect runs. A refusal is a clean outcome, not a crash:
    # the CLI exits 0, prints the refusal, and leaves the classic feature and
    # its artifacts byte-for-byte intact (contract shape: unbounded-preservation).
    refusal = _refusal_outcome(workspace, feature_id, feature_dir)
    if refusal is not None:
        sys.stdout.write(
            json.dumps({"outcome": refusal, "feature_id": feature_id}) + "\n"
        )
        return 0

    plan = _build_plan(workspace, feature_id)

    if args.dry_run:
        sys.stdout.write(json.dumps(_plan_payload(plan), indent=2) + "\n")
        return 0

    # D2-Step-3: a feature whose `.feature` scenarios are not yet `@slice-NN`
    # tagged carries a non-None `plan.blocker`. The execute path honours it
    # alongside `_refusal_outcome` -- it emits the blocker outcome and applies
    # NO journalled side effect, leaving the classic feature byte-for-byte
    # intact (contract shape: unbounded-preservation). A blocked conversion is
    # a clean outcome, not a crash: exit 0, symmetric with a refusal.
    if plan.blocker is not None:
        sys.stdout.write(
            json.dumps({"outcome": plan.blocker, "feature_id": feature_id}) + "\n"
        )
        return 0

    # `DES_CONVERT_ABORT_AFTER` injects an S16 partial-failure: `execute` raises
    # `ConversionInterrupted` after the named journalled step, leaving a partial
    # journal. The acceptance suite arms it to model an interrupted conversion;
    # production conversions never set the env var.
    conversion_planner.execute(
        plan,
        feature_dir=feature_dir,
        config_path=config_path,
        journal_dir=journal_dir,
        ledger_root=workspace,
        fs=fs,
        ledger_factory=AtCompletionLedgerFactory(),
        abort_after=os.environ.get("DES_CONVERT_ABORT_AFTER") or None,
    )
    sys.stdout.write(
        json.dumps({"outcome": "converted", "feature_id": feature_id}) + "\n"
    )
    return 0


def _run_drain(workspace: Path, feature_ids: list[str]) -> int:
    """Drain a set of classic features in one sequential lockfile-held pass (M6).

    Each named feature is processed in order: a feature whose `.feature`
    scenarios carry no `@slice-NN` tag, or whose classic artifacts are
    malformed (`classic-needs-manual-review`), is PARKED on
    `migration-parked.json` rather than converted -- the drain completes
    regardless. Every other feature is converted onto the atdd_pure spine.

    The whole pass holds a single advisory lockfile on `.nwave/config.yaml`
    so no two drains race the shared config flip (no concurrency -- S15).
    Emits a drain summary JSON: the converted ids, and the parked ids with
    their block reason.
    """
    converted: list[str] = []
    parked: list[dict[str, str]] = []
    with _config_lock(workspace):
        for feature_id in feature_ids:
            blocker = _drain_blocker(workspace, feature_id)
            if blocker is not None:
                parked.append({"feature_id": feature_id, "reason": blocker})
                continue
            _drain_convert_one(workspace, feature_id)
            converted.append(feature_id)
    _write_parked_manifest(workspace, parked)
    outcome = parked[0]["reason"] if parked else "converted"
    sys.stdout.write(
        json.dumps(
            {
                "outcome": outcome,
                "converted": converted,
                "parked": [row["feature_id"] for row in parked],
            }
        )
        + "\n"
    )
    return 0


def _drain_blocker(workspace: Path, feature_id: str) -> str | None:
    """Return why a feature cannot be drained, or `None` when it is convertible.

    A feature is parked when its classic artifacts are malformed
    (`classic-needs-manual-review` -- `blocked-needs-manual-review`) or when
    its acceptance `.feature` scenarios carry no `@slice-NN` tag
    (`blocked-needs-distill-tagging`); otherwise it is convertible.
    """
    feature_dir = workspace / "docs" / "feature" / feature_id
    if feature_classifier.classify(feature_dir) == (
        feature_classifier.CLASSIC_NEEDS_MANUAL_REVIEW
    ):
        return conversion_planner.ConversionOutcome.BLOCKED_MANUAL.value
    if _has_untagged_scenarios(workspace, feature_id):
        return conversion_planner.ConversionOutcome.BLOCKED_TAGGING.value
    return None


def _has_untagged_scenarios(workspace: Path, feature_id: str) -> bool:
    """Whether the feature has a `.feature` scenario with no `@slice-NN` tag.

    Scans the feature's `tests/{feature_id}/` acceptance files: a `Scenario:`
    (or `Scenario Outline:`) whose immediately-preceding non-blank line is not
    a `@slice-NN` tag is untagged -- the drain returns it to DISTILL.
    """
    feature_tests = workspace / "tests" / feature_id
    if not feature_tests.is_dir():
        return False
    # gherkin-scope: this IS the classic->atdd_pure Gherkin migration/drain
    # tool -- it operates ON Gherkin scenarios by definition.
    for feature_file in feature_tests.glob("*.feature"):
        lines = feature_file.read_text(encoding="utf-8").splitlines()
        previous = ""
        for raw in lines:
            stripped = raw.strip()
            if stripped.startswith("Scenario:") or stripped.startswith(
                "Scenario Outline:"
            ):
                if "@slice-" not in previous:
                    return True
            if stripped:
                previous = stripped
    return False


def _drain_convert_one(workspace: Path, feature_id: str) -> None:
    """Convert one convertible feature inside the drain pass (reuses `execute`)."""
    feature_dir = workspace / "docs" / "feature" / feature_id
    config_path = workspace / ".nwave" / "config.yaml"
    journal_dir = workspace / ".nwave" / "conversion-journal"
    fs = SafeFileSystemAdapter(workspace=workspace, feature_id=feature_id)
    plan = _build_plan(workspace, feature_id)
    conversion_planner.execute(
        plan,
        feature_dir=feature_dir,
        config_path=config_path,
        journal_dir=journal_dir,
        ledger_root=workspace,
        fs=fs,
        ledger_factory=AtCompletionLedgerFactory(),
    )


def _write_parked_manifest(workspace: Path, parked: list[dict[str, str]]) -> None:
    """Write `migration-parked.json` -- the durable record of parked features (M6).

    A parked feature still has the `classic` spine, so parking never loses it;
    the manifest is the worklist a human picks up to unblock it.
    """
    parked_path = workspace / "migration-parked.json"
    parked_path.parent.mkdir(parents=True, exist_ok=True)
    parked_path.write_text(
        json.dumps({"parked": parked}, indent=2) + "\n", encoding="utf-8"
    )


@contextmanager
def _config_lock(workspace: Path) -> Iterator[None]:
    """Hold an advisory lockfile on `.nwave/config.yaml` for the drain pass (S15).

    The drain flips `workflow.mode` in the shared config once per converted
    feature; the lockfile serialises the whole sequential pass so no second
    drain races the flip. Released when the pass completes.
    """
    lock_path = workspace / ".nwave" / "config.yaml.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("drain-in-progress\n", encoding="utf-8")
    try:
        yield
    finally:
        if lock_path.exists():
            lock_path.unlink()


def _refusal_outcome(workspace: Path, feature_id: str, feature_dir: Path) -> str | None:
    """Return a clean-refusal outcome string, or `None` when conversion may proceed.

    Two unsafe-input guards, checked before any side effect (slice-09):

      * M7 staleness -- the migration manifest stamped the feature dir's
        ``git_state`` (its git tree-ish) at classification time. A feature dir
        that changed since (its tree-ish no longer matches the stamped one) is
        a stale manifest row -- refuse it (`refused-stale-manifest`) rather
        than convert on out-of-date input.
      * C7a degraded resource -- a feature directory the converter cannot write
        to is refused (`refused-read-only-feature-dir`) before the first
        journalled step, so the classic artifacts are never half-converted.
    """
    if _feature_dir_is_stale(workspace, feature_id, feature_dir):
        return conversion_planner.ConversionOutcome.REFUSED_STALE.value
    if _feature_dir_not_writable(feature_dir):
        return conversion_planner.ConversionOutcome.REFUSED_READONLY.value
    return None


def _feature_dir_is_stale(workspace: Path, feature_id: str, feature_dir: Path) -> bool:
    """Whether the feature dir changed since its manifest row was stamped (M7).

    Reads ``migration-manifest.json`` at the workspace root; when the row for
    ``feature_id`` carries a non-empty ``git_state`` stamp, the feature dir is
    stale iff its current git tree-ish differs from the stamp. A workspace
    with no manifest, no matching row, or an unstamped row is never stale --
    M7 only refuses a row it can prove out of date.
    """
    stamped = _manifest_git_state(workspace, feature_id)
    if not stamped:
        return False
    current = _feature_dir_tree_ish(workspace, feature_dir)
    return current is not None and current != stamped


def _manifest_git_state(workspace: Path, feature_id: str) -> str:
    """The ``git_state`` stamp recorded for ``feature_id`` in the manifest."""
    manifest_path = workspace / "migration-manifest.json"
    if not manifest_path.is_file():
        return ""
    parsed = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in parsed.get("features", []):
        if row.get("feature_id") == feature_id:
            return str(row.get("git_state", ""))
    return ""


def _feature_dir_tree_ish(workspace: Path, feature_dir: Path) -> str | None:
    """The feature dir's current git tree object SHA, or `None` when unknown."""
    relative = feature_dir.relative_to(workspace).as_posix()
    completed = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", f"HEAD:{relative}"],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _feature_dir_not_writable(feature_dir: Path) -> bool:
    """Whether the feature directory exists but cannot be written to (C7a)."""
    return feature_dir.is_dir() and not os.access(feature_dir, os.W_OK)


def _build_plan(workspace: Path, feature_id: str) -> conversion_planner.ConversionPlan:
    """Read the feature's classic artifacts and plan its conversion (pure).

    M2: each committed step's SHA is re-verified against git history through
    `GitHistoryProbe` -- the planner never trusts a logged `sha_verdict`.
    """
    feature_dir = workspace / "docs" / "feature" / feature_id
    delta_path = feature_dir / "feature-delta.md"
    feature_delta_text = (
        delta_path.read_text(encoding="utf-8") if delta_path.is_file() else ""
    )
    roadmap_steps, slice_map = _read_roadmap(feature_dir)
    probe = GitHistoryProbe(repo_root=workspace)
    return conversion_planner.dry_run(
        feature_id=feature_id,
        feature_delta_text=feature_delta_text,
        roadmap_steps=roadmap_steps,
        slice_map=slice_map,
        verify_sha=lambda sha: probe.verify_sha(sha).value,
        untagged=_has_untagged_scenarios(workspace, feature_id),
    )


def _read_roadmap(
    feature_dir: Path,
) -> tuple[dict[str, dict[str, object]], dict[str, tuple[str, ...]]]:
    """Read the classic roadmap's step records + slice mapping.

    The conversion roadmap carries, per step, its ``committed`` flag, its
    ``sha`` and the ``sha_verdict`` of that SHA, plus a ``slice`` mapping
    declaring which steps constitute each slice.
    """
    roadmap_path = feature_dir / "deliver" / "roadmap.json"
    if not roadmap_path.is_file():
        # A converted feature has its roadmap archived; a re-planned dry_run
        # (e.g. a post-conversion status query) recovers it from the archive.
        archived = feature_dir / "deliver" / ".classic-archive" / "roadmap.json"
        if not archived.is_file():
            return {}, {}
        roadmap_path = archived
    parsed = json.loads(roadmap_path.read_text(encoding="utf-8"))
    # An entry-gate restart re-logs a step's COMMIT/PASS, so the roadmap may
    # carry the same step twice. `dedup_committed_steps` collapses identical
    # `(step_id, sha)` re-commits to one record before the planner counts.
    steps = conversion_planner.dedup_committed_steps(parsed.get("steps", []))
    slice_map: dict[str, tuple[str, ...]] = {
        str(slice_id): tuple(step_ids)
        for slice_id, step_ids in parsed.get("slices", {}).items()
    }
    return steps, slice_map


def _plan_payload(plan: conversion_planner.ConversionPlan) -> dict[str, object]:
    """Serialise a `ConversionPlan` to a JSON-ready dict for `--dry-run`."""
    return {
        "feature_id": plan.feature_id,
        "workflow_mode": plan.workflow_mode,
        "derived_from_roadmap": plan.derived_from_roadmap,
        "blocker": plan.blocker,
        "slices": [
            {
                "slice_id": planned.slice_id,
                "status": planned.status,
                "provenance": list(planned.provenance),
            }
            for planned in plan.slices
        ],
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the `--workspace` / `--feature-id` / `--dry-run` / `--drain` contract.

    Single-feature mode requires `--feature-id`; drain mode (`--drain`) takes a
    space-separated `--feature-ids` worklist instead.
    """
    parser = argparse.ArgumentParser(prog="des convert-to-atdd-pure")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--feature-id")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview the conversion plan and write nothing",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="undo a partial conversion, restoring the classic artifacts",
    )
    parser.add_argument(
        "--drain",
        action="store_true",
        help="drain every named feature in one sequential lockfile-held pass",
    )
    parser.add_argument(
        "--feature-ids",
        default="",
        help="space-separated feature ids to drain (with --drain)",
    )
    args = parser.parse_args(argv)
    if args.drain:
        args.feature_ids = args.feature_ids.split()
    elif not args.feature_id:
        parser.error("--feature-id is required unless --drain is given")
    return args


if __name__ == "__main__":  # pragma: no cover - subprocess entry point
    sys.exit(main(sys.argv[1:]))
