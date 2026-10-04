"""Bounded maintenance evicts only proved owned-inactive disposable materializations.

Every test runs real Git: the worktree registry is the ownership proof being
tested, so a fake would prove nothing. Eviction requires the exclusive
verification lease (real quiescence), registry ownership, and -- for the
warm reuse workspace -- byte-exact ownership metadata with phase ``idle``.
Age is never consulted; interrupted or unknown worktrees are preserved and
reported, and the budget reports honestly when it cannot be met.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path, PurePosixPath

import pytest

from des.adapters.driven.config.workspace_paths import (
    CANDIDATE_RECEIPT,
    OWNERSHIP_MARKER,
    resolve_workspace_paths,
)
from des.application.verification_maintenance import workspace_maintenance


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ("git", "-C", str(root), *args),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root.parent, "init", "-q", str(root))
    _git(root, "config", "user.email", "a@b")
    _git(root, "config", "user.name", "a")
    (root / "value.txt").write_text("one\n")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "base")
    return root


def _declare(root: Path, workspace: dict) -> Path:
    (root / ".nwave").mkdir(parents=True, exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps({"verification": {"reuse": {"workspace": workspace}}})
    )
    return root


def _candidate(root: Path, name: str, payload: str = "generated\n") -> Path:
    """A registered candidate worktree with the producer's idle receipt."""
    paths = resolve_workspace_paths(root)
    paths.candidate.mkdir(parents=True, exist_ok=True)
    directory = paths.candidate / name
    _git(root, "worktree", "add", "--detach", str(directory), "HEAD")
    common = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    (directory / CANDIDATE_RECEIPT).write_text(
        json.dumps(
            {
                "version": 1,
                "candidate": _git(root, "rev-parse", "HEAD"),
                "common_git_dir": str(common),
                "workspace": str(directory),
                "phase": "idle",
            }
        )
    )
    (directory / "out.bin").write_text(payload)
    return directory


def _idle_metadata(root: Path) -> Path:
    paths = resolve_workspace_paths(root)
    paths.verification.mkdir(parents=True, exist_ok=True)
    common = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    metadata = paths.evidence / "verification-reuse.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text(
        json.dumps(
            {
                "version": 1,
                "common_git_dir": str(common),
                "workspace": str(paths.verification),
                "outputs": list(paths.outputs or ()),
                "phase": "idle",
            }
        )
    )
    _git(root, "worktree", "add", "--detach", str(paths.verification), "HEAD")
    return metadata


def test_dry_run_reports_without_changing_anything(tmp_path: Path) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1})
    candidate = _candidate(root, "nwave-candidate-a")
    maintenance = workspace_maintenance(resolve_workspace_paths(root), apply=False)
    assert not maintenance.evicted
    assert maintenance.within_limit is False
    assert any("dry-run" in line for line in maintenance.report)
    assert candidate.is_dir()
    assert str(candidate) in _git(root, "worktree", "list", "--porcelain")


def test_automatic_evicts_registered_candidates_within_limit(tmp_path: Path) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    candidate = _candidate(root, "nwave-candidate-a")
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert str(candidate) in maintenance.evicted
    assert not candidate.exists()
    assert str(candidate) not in _git(root, "worktree", "list", "--porcelain")
    assert maintenance.within_limit is True


def test_registered_candidate_without_receipt_is_preserved(tmp_path: Path) -> None:
    """The Git registry is location, not ownership: no receipt, no force."""
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    paths.candidate.mkdir(parents=True, exist_ok=True)
    stranger = paths.candidate / "nwave-candidate-stranger"
    _git(root, "worktree", "add", "--detach", str(stranger), "HEAD")
    (stranger / "theirs.bin").write_text("not ours\n")
    maintenance = workspace_maintenance(paths)
    assert stranger.is_dir()
    assert (stranger / "theirs.bin").read_text() == "not ours\n"
    assert not maintenance.evicted
    assert any("receipt is absent or malformed" in item for item in maintenance.report)


def test_mistyped_receipt_fields_are_preserved_without_crashing(
    tmp_path: Path,
) -> None:
    """Wrong-typed receipt values decode as not-ours, never an exception."""
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    paths.candidate.mkdir(parents=True, exist_ok=True)
    candidate = paths.candidate / "nwave-candidate-a"
    _git(root, "worktree", "add", "--detach", str(candidate), "HEAD")
    (candidate / CANDIDATE_RECEIPT).write_text(
        json.dumps(
            {
                "version": True,
                "common_git_dir": 42,
                "workspace": None,
                "candidate": [],
                "phase": "idle",
            }
        )
    )
    (candidate / "payload.bin").write_text("kept\n")
    maintenance = workspace_maintenance(paths)
    assert candidate.is_dir()
    assert (candidate / "payload.bin").read_text() == "kept\n"
    assert not maintenance.evicted
    assert any("receipt is absent or malformed" in item for item in maintenance.report)


def test_mistyped_marker_fields_never_grant_ownership(tmp_path: Path) -> None:
    root = _declare_outputs(
        _repo(tmp_path),
        ["generated"],
        {"cache_limit_bytes": 1, "automatic": True},
    )
    target = resolve_workspace_paths(root).root / "generated"
    target.mkdir(parents=True)
    (target / "artifact.bin").write_text("cache\n")
    (target / OWNERSHIP_MARKER).write_text(
        json.dumps({"version": True, "output": 42, "common_git_dir": []})
    )
    _idle_metadata(root)
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert (target / "artifact.bin").read_text() == "cache\n"
    # The mistyped marker's cache is never evicted; the IDLE reuse
    # workspace legitimately is.
    assert not any("/generated" in item for item in maintenance.evicted)


def test_running_candidate_is_preserved_even_with_receipt(tmp_path: Path) -> None:
    """A non-idle phase is an interrupted run: preserved, recover named."""
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    candidate = _candidate(root, "nwave-candidate-a")
    receipt_path = candidate / CANDIDATE_RECEIPT
    recorded = json.loads(receipt_path.read_text())
    recorded["phase"] = "running"
    receipt_path.write_text(json.dumps(recorded))
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert candidate.is_dir()
    assert (candidate / "out.bin").read_text() == "generated\n"
    assert not maintenance.evicted
    # The receipt keeps its interrupted phase: nothing rewrote it idle.
    assert json.loads((candidate / CANDIDATE_RECEIPT).read_text())["phase"] == (
        "running"
    )
    assert maintenance.within_limit is False


def test_workspace_bound_candidate_refuses_foreign_registration(
    tmp_path: Path,
) -> None:
    """A receipt bound to another path does not own this registration."""
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    candidate = _candidate(root, "nwave-candidate-a")
    receipt_path = candidate / CANDIDATE_RECEIPT
    recorded = json.loads(receipt_path.read_text())
    recorded["workspace"] = str(candidate) + "-elsewhere"
    receipt_path.write_text(json.dumps(recorded))
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert candidate.is_dir()
    assert not maintenance.evicted


def test_unobservable_registry_degrades_budget_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A broken registry is INDETERMINATE, never a fake-empty green."""
    import des.application.verification_maintenance as maintenance_module
    from des.adapters.driven.git.git_observation import GitObservation

    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    _candidate(root, "nwave-candidate-a")

    def broken(*_args: object, **_kwargs: object) -> GitObservation:
        return GitObservation(
            returncode=128,
            stdout="",
            stderr="fatal: broken registry",
        )

    monkeypatch.setattr(maintenance_module, "observe_text", broken)
    maintenance = maintenance_module.workspace_maintenance(
        resolve_workspace_paths(root)
    )
    assert maintenance.within_limit is None
    assert maintenance.failure == "workspace unobservable"
    assert not maintenance.evicted
    assert any("unobservable" in line for line in maintenance.report)


def test_unknown_contents_are_preserved_not_swept(tmp_path: Path) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    stranger = resolve_workspace_paths(root).candidate / "nwave-candidate-stranger"
    stranger.mkdir(parents=True)
    (stranger / "precious.txt").write_text("keep me\n")
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert stranger.is_dir()
    assert (stranger / "precious.txt").read_text() == "keep me\n"
    assert not maintenance.evicted


def test_empty_residue_is_removed_but_unknown_dirs_are_not(tmp_path: Path) -> None:
    root = _declare(_repo(tmp_path), {"automatic": True})
    paths = resolve_workspace_paths(root)
    paths.candidate.mkdir(parents=True)
    empty = paths.candidate / "nwave-candidate-empty"
    empty.mkdir()
    maintenance = workspace_maintenance(paths)
    assert not empty.exists()
    assert any("empty residue" in item for item in maintenance.evicted)


def test_interrupted_reuse_workspace_is_preserved_and_budget_reports_honestly(
    tmp_path: Path,
) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    metadata = _idle_metadata(root)
    recorded = json.loads(metadata.read_text())
    recorded["phase"] = "running"
    metadata.write_text(json.dumps(recorded))
    maintenance = workspace_maintenance(paths)
    assert paths.verification.is_dir()
    assert maintenance.within_limit is False
    assert any("phase 'running'" in item for item in maintenance.report)


def test_idle_owned_reuse_workspace_is_evicted_as_rebuildable_cache(
    tmp_path: Path,
) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    _idle_metadata(root)
    maintenance = workspace_maintenance(paths)
    assert not paths.verification.exists()
    assert not (paths.evidence / "verification-reuse.json").exists()
    assert maintenance.within_limit is True
    assert str(paths.verification) in maintenance.evicted


def test_foreign_ownership_metadata_is_preserved(tmp_path: Path) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    _idle_metadata(root)
    metadata = paths.evidence / "verification-reuse.json"
    recorded = json.loads(metadata.read_text())
    recorded["workspace"] = str(paths.verification) + "-elsewhere"
    metadata.write_text(json.dumps(recorded))
    maintenance = workspace_maintenance(paths)
    assert paths.verification.is_dir()
    assert any("does not prove" in item for item in maintenance.report)


def test_preexisting_workspace_without_metadata_is_preserved(
    tmp_path: Path,
) -> None:
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    paths.verification.mkdir(parents=True)
    (paths.verification / "pending.bin").write_text("possibly pending evidence\n")
    maintenance = workspace_maintenance(paths)
    assert paths.verification.is_dir()
    assert not maintenance.evicted
    assert maintenance.within_limit is False


def test_lease_held_elsewhere_evicts_nothing(tmp_path: Path) -> None:
    from des.application.handover import Blocked
    from des.application.verification_workspace import acquire_verification_lock

    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    candidate = _candidate(root, "nwave-candidate-a")
    lock = acquire_verification_lock(root)
    assert not isinstance(lock, Blocked)
    try:
        maintenance = workspace_maintenance(resolve_workspace_paths(root))
    finally:
        lock.release()
    assert candidate.is_dir()
    assert not maintenance.evicted
    assert any("lease held elsewhere" in line for line in maintenance.report)


def test_unbounded_config_reports_within_limit_and_evicts_nothing(
    tmp_path: Path,
) -> None:
    root = _declare(_repo(tmp_path), {"automatic": True})
    candidate = _candidate(root, "nwave-candidate-a")
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert candidate.is_dir()
    assert maintenance.within_limit is True
    assert any("limit=unbounded" in line for line in maintenance.report)


def _declare_outputs(root: Path, outputs: list[str], workspace: dict) -> Path:
    (root / ".nwave").mkdir(parents=True, exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps(
            {"verification": {"reuse": {"outputs": outputs, "workspace": workspace}}}
        )
    )
    return root


def _des_created_output(root: Path, output: str, payload: str) -> Path:
    """A generated output root with DES's creation ownership marker."""
    paths = resolve_workspace_paths(root)
    target = paths.root / Path(*PurePosixPath(output).parts)
    target.mkdir(parents=True, exist_ok=True)
    (target / "artifact.bin").write_text(payload)
    common = Path(
        _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).resolve()
    (target / OWNERSHIP_MARKER).write_text(
        json.dumps({"version": 1, "output": output, "common_git_dir": str(common)})
    )
    return target


def test_des_created_output_cache_is_evicted_under_configured_limit(
    tmp_path: Path,
) -> None:
    root = _declare_outputs(_repo(tmp_path), ["generated"], {"cache_limit_bytes": 1})
    target = _des_created_output(root, "generated", "native cache bytes\n")
    _idle_metadata(root)
    paths = resolve_workspace_paths(root)
    maintenance = workspace_maintenance(paths, apply=False)
    assert target.is_dir()
    assert any("outputs_bytes=" in line for line in maintenance.report)
    automatic = workspace_maintenance(paths)
    assert not target.exists()
    assert any("owned generated cache" in item for item in automatic.evicted)
    assert automatic.within_limit is True


def test_owned_output_cache_is_preserved_without_quiescence_receipt(
    tmp_path: Path,
) -> None:
    """A crash that never wrote an idle receipt preserves owned cache."""
    root = _declare_outputs(_repo(tmp_path), ["generated"], {"cache_limit_bytes": 1})
    target = _des_created_output(root, "generated", "native cache bytes\n")
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert target.is_dir()
    assert (target / "artifact.bin").read_text() == "native cache bytes\n"
    assert maintenance.within_limit is False
    assert not maintenance.evicted
    assert any("no native quiescence receipt" in item for item in maintenance.report)


def test_owned_output_cache_is_preserved_when_phase_is_not_idle(
    tmp_path: Path,
) -> None:
    root = _declare_outputs(_repo(tmp_path), ["generated"], {"cache_limit_bytes": 1})
    target = _des_created_output(root, "generated", "native cache bytes\n")
    _idle_metadata(root)
    metadata = resolve_workspace_paths(root).evidence / "verification-reuse.json"
    recorded = json.loads(metadata.read_text())
    recorded["phase"] = "running"
    metadata.write_text(json.dumps(recorded))
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert target.is_dir()
    assert not maintenance.evicted
    assert any("phase 'running'" in item for item in maintenance.report)


def test_unknown_preexisting_output_cache_is_accounted_but_never_evicted(
    tmp_path: Path,
) -> None:
    root = _declare_outputs(_repo(tmp_path), ["generated"], {"cache_limit_bytes": 1})
    target = resolve_workspace_paths(root).root / "generated"
    target.mkdir()
    (target / "user-build.bin").write_text("precious\n")
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert target.is_dir()
    assert (target / "user-build.bin").read_text() == "precious\n"
    assert maintenance.within_limit is False
    assert not maintenance.evicted


def test_adopted_output_cache_is_evicted_and_reports_bytes(
    tmp_path: Path,
) -> None:
    root = _declare_outputs(
        _repo(tmp_path),
        ["generated"],
        {"cache_limit_bytes": 1, "adopt_outputs": ["generated"]},
    )
    target = resolve_workspace_paths(root).root / "generated"
    target.mkdir(parents=True)
    (target / "stale.bin").write_text("adopted rebuildable cache\n")
    _idle_metadata(root)
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert not target.exists()
    assert any("owned generated cache" in item for item in maintenance.evicted)
    assert maintenance.within_limit is True


def test_owned_output_cache_absorbed_into_tracked_source_is_preserved(
    tmp_path: Path,
) -> None:
    """The permanent cache->tracked counterexample: bytes survive.

    DES marked the root at creation; the project later COMMITTED a file
    inside it and left uncommitted edits on top. No config or marker
    changed. Eviction must refuse: the root is project source again, the
    named tracked path is reported, and every byte -- including the
    uncommitted edit -- survives.
    """
    root = _declare_outputs(_repo(tmp_path), ["generated"], {"cache_limit_bytes": 1})
    target = _des_created_output(root, "generated", "native cache bytes\n")
    committed = target / "keep.yaml"
    committed.write_text("value: 1\n")
    _git(root, "add", "generated/keep.yaml")
    _git(root, "commit", "-qm", "user committed inside the cache root")
    committed.write_text("value: 2-uncommitted-edit\n")
    _idle_metadata(root)

    maintenance = workspace_maintenance(resolve_workspace_paths(root))

    assert committed.read_text() == "value: 2-uncommitted-edit\n"
    assert (target / "artifact.bin").exists()
    assert (target / OWNERSHIP_MARKER).exists()
    assert not any("/generated" in item for item in maintenance.evicted)
    assert maintenance.within_limit is False
    assert any("generated/keep.yaml" in item for item in maintenance.preserved)


def test_staged_source_inside_adopted_cache_is_preserved(tmp_path: Path) -> None:
    """Staged adds count: the index participates in the source guard."""
    root = _declare_outputs(
        _repo(tmp_path),
        ["generated"],
        {"cache_limit_bytes": 1, "adopt_outputs": ["generated"]},
    )
    target = resolve_workspace_paths(root).root / "generated"
    target.mkdir(parents=True)
    (target / "staged.yaml").write_text("staged: true\n")
    _git(root, "add", "generated/staged.yaml")
    _idle_metadata(root)
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert (target / "staged.yaml").read_text() == "staged: true\n"
    assert not any("/generated" in item for item in maintenance.evicted)
    assert any("generated/staged.yaml" in item for item in maintenance.preserved)


def test_adopted_output_under_intermediate_symlink_is_preserved(
    tmp_path: Path,
) -> None:
    """Late unsafe edge: an intermediate parent symlink cannot redirect.

    The outside location holds NOTHING of ours (no marker, no payload):
    the anchored no-follow walk must refuse at the symlinked component,
    the outside bytes stay untouched, and the un-evictable root is
    reported rather than deleted.
    """
    root = _declare_outputs(
        _repo(tmp_path),
        ["a/b"],
        {"cache_limit_bytes": 1, "adopt_outputs": ["a/b"]},
    )
    outside = tmp_path / "outside-edge"
    outside.mkdir()
    (outside / "keep.txt").write_text("unrelated outside bytes\n")
    (outside / "b").mkdir()
    (outside / "b" / "payload.txt").write_text("outside project bytes\n")
    (root / "a").symlink_to(outside)
    _idle_metadata(root)
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert (outside / "keep.txt").read_text() == "unrelated outside bytes\n"
    assert (outside / "b" / "payload.txt").read_text() == "outside project bytes\n"
    assert not any("/a/b" in item for item in maintenance.evicted)
    # The declared root sits behind an intermediate symlink: its bytes are
    # FOREIGN and uncountable, so the budget is INDETERMINATE -- never a
    # green claim over bytes that were never walked.
    assert maintenance.within_limit is None


def test_nonobject_reuse_metadata_preserves_bytes(tmp_path: Path) -> None:
    """Valid-JSON non-object metadata: summary routes, nothing crashes.

    The maintenance port must treat a non-object reuse document as
    unknown (never proven idle): bytes preserved, budget non-green, no
    traceback through the summary phase decode.
    """
    root = _declare(_repo(tmp_path), {"cache_limit_bytes": 1, "automatic": True})
    paths = resolve_workspace_paths(root)
    paths.verification.mkdir(parents=True)
    (paths.verification / "pending.bin").write_text("evidence bytes\n")
    metadata = paths.evidence / "verification-reuse.json"
    metadata.parent.mkdir(parents=True, exist_ok=True)
    metadata.write_text("[1, 2, 3]\n")
    maintenance = workspace_maintenance(paths)
    assert (paths.verification / "pending.bin").read_text() == "evidence bytes\n"
    assert not maintenance.evicted
    assert maintenance.within_limit is False


def test_eviction_stops_at_the_exact_budget(tmp_path: Path) -> None:
    """Reaching the limit EXACTLY must not evict one cache too many."""
    root = _declare(_repo(tmp_path), {"automatic": True})
    paths = resolve_workspace_paths(root)
    _idle_metadata(root)
    first = _candidate(root, "nwave-candidate-a")
    second = _candidate(root, "nwave-candidate-b")

    def tree_bytes(directory: Path) -> int:
        total = 0
        for current, _, files in os.walk(directory):
            for name in files:
                entry = os.path.join(current, name)
                if not Path(entry).is_symlink():
                    total += os.lstat(entry).st_size
        return total

    # Two same-shape candidates: evicting ONE lands exactly on the limit.
    limit = tree_bytes(paths.verification) + tree_bytes(first)
    assert tree_bytes(second) == tree_bytes(first)
    _declare(root, {"automatic": True, "cache_limit_bytes": limit})

    maintenance = workspace_maintenance(resolve_workspace_paths(root))

    assert str(first) in maintenance.evicted
    assert not first.exists()
    assert second.exists()
    assert paths.verification.is_dir()
    assert maintenance.within_limit is True


def test_symlinked_output_root_is_never_evicted(tmp_path: Path) -> None:
    root = _declare_outputs(
        _repo(tmp_path),
        ["generated"],
        {"cache_limit_bytes": 1, "adopt_outputs": ["generated"]},
    )
    outside = tmp_path / "outside-cache"
    outside.mkdir()
    (outside / "keep.bin").write_text("elsewhere\n")
    (resolve_workspace_paths(root).root / "generated").symlink_to(outside)
    maintenance = workspace_maintenance(resolve_workspace_paths(root))
    assert (outside / "keep.bin").read_text() == "elsewhere\n"
    assert not maintenance.evicted
