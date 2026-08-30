from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.adapters.driven.marker_file_owner_lease_adapter import (
    MarkerFileOwnerLeaseAdapter,
)
from des.adapters.driven.platform_residence_durability_adapter import (
    PlatformResidenceDurabilityAdapter,
)
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.cli.verify_worktree_cleanup import main as cleanup_main
from des.cli.worktree_admit import main as admit_main
from des.cli.worktree_release import main as release_main
from des.domain.worktree_residence import (
    DurableResidence,
    LaneIdentity,
    OwnerLease,
    ResidenceAdmission,
    ResidenceDurability,
)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.test"], cwd=repo, check=True
    )
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "seed.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "seed"], cwd=repo, check=True)
    return repo


def test_real_platform_refuses_repo_under_ephemeral_root(
    tmp_path: Path, capsys
) -> None:
    repo = _repo(tmp_path)

    result = admit_main(["--repo", str(repo), "--lane", "refused-lane"])

    captured = capsys.readouterr()
    assert result == 1
    assert "EPHEMERAL" in captured.err
    assert "worktree-admit" in captured.err
    assert not (repo / ".nwave" / "worktrees" / "refused-lane").exists()


def test_admit_then_release_is_one_positive_atomic_lifecycle(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repo(tmp_path)
    default = repo / ".nwave" / "worktrees"
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "classify",
        lambda self, root: ResidenceDurability.DURABLE,
    )
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "durable_default",
        lambda self, candidate_repo: default,
    )

    assert admit_main(["--repo", str(repo), "--lane", "test-lane"]) == 0
    path = default / "test-lane"
    identity = LaneIdentity.observe(path)
    probe = MarkerFileOwnerLeaseAdapter()
    assert probe.observe(path, identity) is OwnerLease.HELD

    assert release_main(["--repo", str(repo), "--worktree", str(path)]) == 0
    assert probe.observe(path, identity) is OwnerLease.RELEASED
    capsys.readouterr()

    subprocess.run(
        ["git", "worktree", "remove", "--force", str(path)], cwd=repo, check=True
    )
    subprocess.run(["git", "branch", "-D", "test-lane"], cwd=repo, check=True)


def test_release_refuses_missing_positive_assertion(tmp_path: Path, capsys) -> None:
    repo = _repo(tmp_path)
    external = tmp_path / "external"
    subprocess.run(
        ["git", "worktree", "add", "-b", "external", str(external), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    result = release_main(["--repo", str(repo), "--worktree", str(external)])

    assert result == 1
    assert "absence never means release" in capsys.readouterr().err
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(external)], cwd=repo, check=True
    )
    subprocess.run(["git", "branch", "-D", "external"], cwd=repo, check=True)


def test_primary_checkout_owner_marker_can_be_released(tmp_path: Path, capsys) -> None:
    repo = _repo(tmp_path)
    identity = LaneIdentity.observe(repo)
    probe = MarkerFileOwnerLeaseAdapter()
    probe.write_held(repo, identity)

    assert release_main(["--repo", str(repo), "--worktree", str(repo)]) == 0
    assert probe.observe(repo, identity) is OwnerLease.RELEASED
    assert release_main(["--repo", str(repo), "--worktree", str(repo)]) == 0
    assert probe.observe(repo, identity) is OwnerLease.RELEASED
    capsys.readouterr()

    target_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert (
        cleanup_main(
            [
                "--repo",
                str(repo),
                "--target-branch",
                target_branch,
                "--worktree",
                str(repo),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out.splitlines()[0])["entries"] == []


def test_linked_worktree_passed_as_repo_cannot_claim_primary_identity(
    tmp_path: Path, capsys
) -> None:
    repo = _repo(tmp_path)
    linked = tmp_path / "linked"
    subprocess.run(
        ["git", "worktree", "add", "-b", "linked", str(linked), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    identity = LaneIdentity.observe(linked)
    probe = MarkerFileOwnerLeaseAdapter()
    probe.write_held(linked, identity)

    assert release_main(["--repo", str(linked), "--worktree", str(linked)]) == 1
    assert probe.observe(linked, identity) is OwnerLease.HELD
    assert "Git-primary" in capsys.readouterr().err

    subprocess.run(
        ["git", "worktree", "remove", "--force", str(linked)], cwd=repo, check=True
    )
    subprocess.run(["git", "branch", "-D", "linked"], cwd=repo, check=True)


def test_detached_durable_cwd_is_admitted_in_place_without_relocation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repo(tmp_path)
    detached = tmp_path / "detached"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(detached), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(detached)
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "classify",
        lambda self, root: ResidenceDurability.DURABLE,
    )

    assert admit_main(["--repo", str(repo), "--lane", "auto"]) == 0

    assert Path(capsys.readouterr().out.strip()) == detached
    assert (
        MarkerFileOwnerLeaseAdapter().observe(detached, LaneIdentity.observe(detached))
        is OwnerLease.HELD
    )
    assert not (repo / ".nwave" / "worktrees" / "auto").exists()
    monkeypatch.chdir(repo)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(detached)],
        cwd=repo,
        check=True,
    )


def test_detached_ephemeral_cwd_is_rescued_before_wip_mutation(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    repo = _repo(tmp_path)
    source = tmp_path / "detached-source"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(source), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (source / "untracked-wip.bin").write_bytes(b"live-wip\x00")
    default = repo / ".nwave" / "worktrees"
    monkeypatch.chdir(source)
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "classify",
        lambda self, root: (
            ResidenceDurability.EPHEMERAL
            if root.resolve() == source.resolve()
            else ResidenceDurability.DURABLE
        ),
    )
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "durable_default",
        lambda self, candidate_repo: default,
    )

    assert admit_main(["--repo", str(repo), "--lane", "rescued-auto"]) == 0

    destination = default / "rescued-auto"
    assert Path(capsys.readouterr().out.strip()) == destination
    assert source.exists()
    assert (source / "untracked-wip.bin").read_bytes() == b"live-wip\x00"
    assert (destination / "untracked-wip.bin").read_bytes() == b"live-wip\x00"
    assert (
        MarkerFileOwnerLeaseAdapter().observe(
            destination, LaneIdentity.observe(destination)
        )
        is OwnerLease.HELD
    )
    monkeypatch.chdir(repo)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(destination)],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "branch", "-D", "rescued-auto"], cwd=repo, check=True)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(source)], cwd=repo, check=True
    )


def test_detached_ephemeral_rescue_failure_becomes_residence_refusal(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """A real `git worktree add` failure during rescue must not escape as a
    traceback: it is a typed refusal, the source and its WIP are untouched,
    and no partial destination or branch is left registered."""
    repo = _repo(tmp_path)
    source = tmp_path / "detached-source"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(source), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (source / "untracked-wip.bin").write_bytes(b"live-wip\x00")
    default = repo / ".nwave" / "worktrees"
    monkeypatch.chdir(source)
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "classify",
        lambda self, root: (
            ResidenceDurability.EPHEMERAL
            if root.resolve() == source.resolve()
            else ResidenceDurability.DURABLE
        ),
    )
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "durable_default",
        lambda self, candidate_repo: default,
    )
    # Force the rescue's real `git worktree add -b <lane> ...` to fail with a
    # genuine subprocess.CalledProcessError: the branch it would create
    # already exists.
    subprocess.run(["git", "branch", "rescue-conflict"], cwd=repo, check=True)

    result = admit_main(["--repo", str(repo), "--lane", "rescue-conflict"])

    captured = capsys.readouterr()
    assert result == 1
    assert "WHAT:" in captured.err
    assert "WHY:" in captured.err
    assert "HOW:" in captured.err
    assert source.exists()
    assert (source / "untracked-wip.bin").read_bytes() == b"live-wip\x00"
    assert not (default / "rescue-conflict").exists()
    registered = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert str(default / "rescue-conflict") not in registered

    monkeypatch.chdir(repo)
    subprocess.run(["git", "branch", "-D", "rescue-conflict"], cwd=repo, check=True)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(source)], cwd=repo, check=True
    )


def test_startup_probe_uses_an_admitted_repo_local_destination(
    tmp_path: Path, monkeypatch
) -> None:
    repo = _repo(tmp_path)
    monkeypatch.setattr(
        PlatformResidenceDurabilityAdapter,
        "classify",
        lambda self, root: ResidenceDurability.DURABLE,
    )
    admission = ResidenceAdmission(PlatformResidenceDurabilityAdapter(repo))
    admitted = admission.admit(repo / ".nwave" / "worktrees" / "probe")
    assert isinstance(admitted, DurableResidence)

    assert GitWorktreeAdapter().probe(repo, admitted)
    assert not admitted.root.exists()
    branches = subprocess.run(
        ["git", "branch", "--list", "refactor-probe-health-check"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert not branches.strip()
