"""Generated-directory authority never grants access to another source tree."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
)
from tests.des.unit.application.test_delivery_continuation import repo


COMMAND = (
    (
        sys.executable,
        "-c",
        "from pathlib import Path; print(Path.cwd()); assert Path('value.txt').read_text() == 'one\\n'",
    ),
)


def _configured(root: Path, outputs: list[str]) -> Path:
    root = repo(root, "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        json.dumps({"verification": {"reuse": {"outputs": outputs}}})
    )
    return root


def _measure(root: Path):
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    return DeliveryContinuationRunner()._with_candidate_worktree(
        root, candidate, COMMAND
    )


def test_same_named_independent_repositories_never_alias_workspaces(
    tmp_path: Path,
) -> None:
    roots = [
        _configured(tmp_path / name / "same-name", ["target"])
        for name in ("left", "right")
    ]
    results = [_measure(root) for root in roots]
    assert all(not isinstance(result, DeliveryOutcome) for result in results), results
    workspaces = [Path(result[1][0].stdout.strip()) for result in results]
    assert workspaces[0] != workspaces[1]
    for root, workspace in zip(roots, workspaces, strict=True):
        assert workspace.is_relative_to(root)
        assert (workspace / "target").resolve() == root / "target"
    altered = workspaces[0] / "value.txt"
    previous = altered.stat()
    altered.write_text("two\n")
    os.utime(altered, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    clean = _measure(roots[0])
    assert not isinstance(clean, DeliveryOutcome), clean
    assert (workspaces[0] / "value.txt").read_text() == "one\n"
    assert (workspaces[1] / "value.txt").read_text() == "one\n"


@pytest.mark.parametrize(
    "output", ["value.txt", "..", "../outside", ".git", ".", "target/../outside"]
)
def test_invalid_retention_authority_refuses_before_touching_sources(
    tmp_path: Path, output: str
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"foreign bytes")
    root = _configured(tmp_path / "repo", [output])
    result = _measure(root)
    assert isinstance(result, DeliveryOutcome), result
    assert sentinel.read_bytes() == b"foreign bytes"
    assert (root / "value.txt").read_text() == "one\n"


def test_output_symlink_escape_preserves_foreign_directory(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep"
    sentinel.write_bytes(b"foreign bytes")
    root = _configured(tmp_path / "repo", ["target"])
    (root / "target").symlink_to(outside, target_is_directory=True)
    result = _measure(root)
    assert isinstance(result, DeliveryOutcome), result
    assert (root / "target").is_symlink()
    assert sentinel.read_bytes() == b"foreign bytes"


def test_preexisting_workspace_collision_is_not_adopted_or_deleted(
    tmp_path: Path,
) -> None:
    root = _configured(tmp_path / "repo", ["target"])
    collision = root / "lanes/.des-verification"
    collision.mkdir(parents=True)
    sentinel = collision / "foreign"
    sentinel.write_bytes(b"not a managed workspace")
    result = _measure(root)
    assert isinstance(result, DeliveryOutcome), result
    assert sentinel.read_bytes() == b"not a managed workspace"


def test_abandoned_running_workspace_requires_recovery(tmp_path: Path) -> None:
    root = _configured(tmp_path / "repo", ["target"])
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    interrupted = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os, sys; from pathlib import Path; "
            "from des.application.verification_workspace import VerificationWorkspace; "
            "from des.adapters.driven.config.workspace_paths import resolve_workspace_paths; "
            "workspace = VerificationWorkspace(resolve_workspace_paths(Path(sys.argv[1]))); "
            "workspace.acquire(sys.argv[2]); os._exit(23)",
            str(root),
            candidate,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert interrupted.returncode == 23, interrupted.stderr
    result = _measure(root)
    assert isinstance(result, DeliveryOutcome), result
    assert (root / "lanes/.des-verification/value.txt").read_text() == "one\n"


def test_linked_lane_cannot_reconcile_another_lanes_held_workspace(
    tmp_path: Path,
) -> None:
    from des.adapters.driven.config.workspace_paths import resolve_workspace_paths
    from des.application.verification_workspace import VerificationWorkspace
    from tests.des.unit.application.test_delivery_continuation import git

    root = _configured(tmp_path / "repo", ["target"])
    lane = root / "lanes/caller"
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git(root, "worktree", "add", "--detach", str(lane), candidate)
    owner = VerificationWorkspace(resolve_workspace_paths(root))
    try:
        owner.acquire(candidate)
        source = owner.directory / "value.txt"
        original = source.read_bytes(), source.stat().st_mtime_ns
        refused = _measure(lane)
        assert isinstance(refused, DeliveryOutcome), refused
        assert (source.read_bytes(), source.stat().st_mtime_ns) == original
        owner.finish()
        owner.release()
        accepted = _measure(lane)
        assert not isinstance(accepted, DeliveryOutcome), accepted
        assert Path(accepted[1][0].stdout.strip()) == owner.directory
        assert (owner.directory / "target").resolve() == root / "target"
    finally:
        owner.release()
        git(root, "worktree", "remove", "--force", str(lane))


def test_native_source_mutation_cannot_claim_the_unchanged_candidate(
    tmp_path: Path,
) -> None:
    root = _configured(tmp_path / "repo", ["target"])
    candidate = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = DeliveryContinuationRunner()._with_candidate_worktree(
        root,
        candidate,
        (
            (
                sys.executable,
                "-c",
                "from pathlib import Path; Path('value.txt').write_text('two\\n'); print('MUTATED_SOURCE')",
            ),
        ),
    )
    assert isinstance(result, DeliveryOutcome), result
    assert (
        result.failure is not None and result.failure.what == "CandidateSourceChanged"
    )
    records = list((root / ".nwave/des/logs/native").glob("*.json"))
    assert len(records) == 1
    assert "MUTATED_SOURCE" in json.loads(records[0].read_text())[0]["stdout"]
    assert (root / "value.txt").read_text() == "one\n"


def test_workspace_git_metadata_cannot_alias_another_linked_lane(
    tmp_path: Path,
) -> None:
    from tests.des.unit.application.test_delivery_continuation import git

    root = _configured(tmp_path / "repo", ["target"])
    first = _measure(root)
    assert not isinstance(first, DeliveryOutcome), first
    workspace = Path(first[1][0].stdout.strip())
    lane = root / "lanes/caller"
    git(root, "worktree", "add", "--detach", str(lane), first[0])
    original_metadata = (workspace / ".git").read_bytes()
    admin = Path(
        subprocess.run(
            ["git", "-C", str(lane), "rev-parse", "--absolute-git-dir"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    )
    protected = [admin / "HEAD", admin / "index", lane / "value.txt"]
    original = {path: path.read_bytes() for path in protected}
    try:
        (workspace / ".git").write_bytes((lane / ".git").read_bytes())
        result = _measure(root)
        assert isinstance(result, DeliveryOutcome), result
        assert {path: path.read_bytes() for path in protected} == original
    finally:
        (workspace / ".git").write_bytes(original_metadata)
        git(root, "worktree", "remove", "--force", str(lane))
