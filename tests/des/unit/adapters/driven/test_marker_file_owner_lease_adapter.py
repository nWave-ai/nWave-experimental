from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from des.adapters.driven.marker_file_owner_lease_adapter import (
    MARKER_RELATIVE_PATH,
    MarkerFileOwnerLeaseAdapter,
    MarkerTransitionError,
)
from des.domain.worktree_residence import LaneIdentity, OwnerLease


def _worktree(tmp_path: Path, name: str = "lane") -> tuple[Path, LaneIdentity]:
    root = tmp_path / name
    (root / ".git").mkdir(parents=True)
    return root, LaneIdentity.observe(root)


def test_missing_malformed_and_identity_mismatched_markers_are_indeterminate(
    tmp_path: Path,
) -> None:
    root, identity = _worktree(tmp_path)
    adapter = MarkerFileOwnerLeaseAdapter()
    marker = root / MARKER_RELATIVE_PATH

    assert adapter.observe(root, identity) is OwnerLease.INDETERMINATE
    marker.parent.mkdir(parents=True)
    marker.write_text("{", encoding="utf-8")
    assert adapter.observe(root, identity) is OwnerLease.INDETERMINATE
    marker.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "state": "RELEASED",
                "identity": {
                    "lane_name": "other",
                    "worktree_root": identity.worktree_root,
                    "git_dir": identity.git_dir,
                },
            }
        ),
        encoding="utf-8",
    )
    assert adapter.observe(root, identity) is OwnerLease.INDETERMINATE


def test_only_positive_held_then_released_transition_can_become_released(
    tmp_path: Path,
) -> None:
    root, identity = _worktree(tmp_path)
    adapter = MarkerFileOwnerLeaseAdapter()

    adapter.write_held(root, identity)
    assert adapter.observe(root, identity) is OwnerLease.HELD
    adapter.write_released(root, identity)
    assert adapter.observe(root, identity) is OwnerLease.RELEASED
    assert not tuple((root / MARKER_RELATIVE_PATH).parent.glob("*.tmp"))


def test_deleting_held_marker_is_unknown_not_release(tmp_path: Path) -> None:
    root, identity = _worktree(tmp_path)
    adapter = MarkerFileOwnerLeaseAdapter()
    adapter.write_held(root, identity)

    (root / MARKER_RELATIVE_PATH).unlink()

    assert adapter.observe(root, identity) is OwnerLease.INDETERMINATE
    with pytest.raises(MarkerTransitionError):
        adapter.write_released(root, identity)


def test_rescued_copy_does_not_inherit_source_lease(tmp_path: Path) -> None:
    source, source_identity = _worktree(tmp_path, "source")
    adapter = MarkerFileOwnerLeaseAdapter()
    adapter.write_held(source, source_identity)
    destination = tmp_path / "destination"
    shutil.copytree(source, destination)
    destination_identity = LaneIdentity.observe(destination)

    assert (
        adapter.observe(destination, destination_identity) is OwnerLease.INDETERMINATE
    )
