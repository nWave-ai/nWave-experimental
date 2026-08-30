"""Copy-verify-switch rescue for externally-created at-risk worktrees."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from typing import TYPE_CHECKING

from des.domain.worktree_residence import (
    DurableResidence,
    ExternalResidenceLost,
    RescuedResidence,
    ResidenceAdmission,
    ResidenceDurability,
    ResidenceRefusal,
)
from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path

    from des.ports.driven_ports.residence_durability_port import (
        ResidenceDurabilityPort,
    )


PrepareDestination = Callable[[DurableResidence], bool]


def _manifest(root: Path) -> dict[str, tuple[str, str]]:
    manifest: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts and relative.parts[0] == ".git":
            continue
        key = relative.as_posix()
        if path.is_symlink():
            manifest[key] = ("symlink", str(path.readlink()))
        elif path.is_file():
            manifest[key] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            manifest[key] = ("directory", "")
    return manifest


def _copy_working_tree(source: Path, destination: Path) -> None:
    for child in source.iterdir():
        if child.name == ".git":
            continue
        target = destination / child.name
        if child.is_symlink():
            target.symlink_to(child.readlink(), target_is_directory=child.is_dir())
        elif child.is_dir():
            shutil.copytree(child, target, symlinks=True, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target, follow_symlinks=False)


def rescue_worktree_residence(
    *,
    source: Path,
    repo: Path,
    lane_name: str,
    durability: ResidenceDurabilityPort,
    prepare_destination: PrepareDestination,
) -> RescuedResidence | ResidenceRefusal | ExternalResidenceLost:
    """Rescue WIP without moving or deleting the source.

    ``prepare_destination`` is the git registration seam.  It must create the
    admitted worktree before bytes are copied; the function never mutates the
    source and never treats disappearance as success.
    """

    source = source.resolve()
    observed = durability.classify(source)
    if observed is ResidenceDurability.DURABLE:
        return ResidenceRefusal(
            observed=observed,
            what=f"rescue was not started for already-durable {source}",
            why="copy-verify-switch is only the external at-risk continuation",
            how="Continue using the admitted durable worktree in place.",
        )
    frozen = durability.freeze(source)
    if frozen is not True:
        reason = (
            frozen.reason if isinstance(frozen, Indeterminate) else "freeze refused"
        )
        return ResidenceRefusal(
            observed=observed,
            what=f"at-risk worktree {source} was not rescued",
            why=f"nWave could not prove its mutation route frozen: {reason}",
            how="Keep the source untouched; establish a freeze, then retry rescue.",
        )

    admitted = ResidenceAdmission(durability).admit_default(repo, lane_name)
    if isinstance(admitted, ResidenceRefusal):
        return admitted
    if not source.is_dir():
        return ExternalResidenceLost(
            source=source,
            what=f"external at-risk worktree {source} was lost",
            why="the source disappeared before a verified durable copy existed",
            how="Recover it from an external backup; nWave did not delete it.",
        )
    try:
        if not prepare_destination(admitted):
            raise OSError("durable git destination could not be registered")
        _copy_working_tree(source, admitted.root)
        destination_manifest = _manifest(admitted.root)
        if not source.is_dir():
            return ExternalResidenceLost(
                source=source,
                what=f"external at-risk worktree {source} was lost",
                why="the source disappeared before byte verification completed",
                how="Recover it from an external backup; nWave did not delete it.",
            )
        source_manifest = _manifest(source)
    except FileNotFoundError:
        return ExternalResidenceLost(
            source=source,
            what=f"external at-risk worktree {source} was lost",
            why="the source disappeared before byte verification completed",
            how="Recover it from an external backup; nWave did not delete it.",
        )
    except Exception as exc:
        return ResidenceRefusal(
            observed=observed,
            what=f"at-risk worktree {source} was not rescued",
            why=f"preparation, copy or verification failed: {exc}",
            how="Keep the source untouched, repair the destination, then retry.",
        )
    if source_manifest != destination_manifest:
        return ResidenceRefusal(
            observed=observed,
            what=f"at-risk worktree {source} was not switched",
            why="the durable copy was not byte-identical to the still-present source",
            how="Keep the source untouched; remove the incomplete copy and retry.",
        )
    return RescuedResidence(source=source, residence=admitted)


__all__ = ["PrepareDestination", "rescue_worktree_residence"]
