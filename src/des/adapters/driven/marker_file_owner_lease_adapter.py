"""Atomic marker-file adapter for positive worktree owner assertions."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from des.domain.worktree_residence import LaneIdentity, OwnerLease
from des.ports.driven_ports.owner_lease_probe import OwnerLeaseProbe


MARKER_RELATIVE_PATH = Path(".nwave") / "lane-owner.json"
_SCHEMA_VERSION = 1


class MarkerTransitionError(RuntimeError):
    """The requested owner transition was not proven safe."""


class MarkerFileOwnerLeaseAdapter(OwnerLeaseProbe):
    def observe(
        self, worktree_root: Path, expected_identity: LaneIdentity
    ) -> OwnerLease:
        path = worktree_root / MARKER_RELATIVE_PATH
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return OwnerLease.INDETERMINATE
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != _SCHEMA_VERSION
        ):
            return OwnerLease.INDETERMINATE
        identity = payload.get("identity")
        expected = {
            "lane_name": expected_identity.lane_name,
            "worktree_root": expected_identity.worktree_root,
            "git_dir": expected_identity.git_dir,
        }
        if identity != expected:
            return OwnerLease.INDETERMINATE
        try:
            return OwnerLease(payload.get("state"))
        except (TypeError, ValueError):
            return OwnerLease.INDETERMINATE

    def write_held(self, worktree_root: Path, identity: LaneIdentity) -> None:
        marker = worktree_root / MARKER_RELATIVE_PATH
        if marker.exists():
            raise MarkerTransitionError(
                f"owner marker already exists at {marker}; existing authority is not overwritten"
            )
        self._atomic_write(marker, identity, OwnerLease.HELD)

    def write_released(self, worktree_root: Path, identity: LaneIdentity) -> None:
        observed = self.observe(worktree_root, identity)
        if observed is OwnerLease.RELEASED:
            return
        if observed is not OwnerLease.HELD:
            raise MarkerTransitionError(
                "owner release requires a readable, identity-matching HELD assertion"
            )
        self._atomic_write(
            worktree_root / MARKER_RELATIVE_PATH, identity, OwnerLease.RELEASED
        )

    @staticmethod
    def _atomic_write(path: Path, identity: LaneIdentity, state: OwnerLease) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": _SCHEMA_VERSION,
            "state": state.value,
            "identity": {
                "lane_name": identity.lane_name,
                "worktree_root": identity.worktree_root,
                "git_dir": identity.git_dir,
            },
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        data = (
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        fd: int | None = None
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as handle:
                fd = None
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            try:
                directory_fd = os.open(path.parent, os.O_RDONLY)
            except OSError:
                return
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            if fd is not None:
                os.close(fd)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


__all__ = [
    "MARKER_RELATIVE_PATH",
    "MarkerFileOwnerLeaseAdapter",
    "MarkerTransitionError",
]
