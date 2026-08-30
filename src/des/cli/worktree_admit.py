"""Create one repository-local worktree through durable admission."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from des.adapters.driven.git.git_subprocess import git_text
from des.adapters.driven.marker_file_owner_lease_adapter import (
    MARKER_RELATIVE_PATH,
    MarkerFileOwnerLeaseAdapter,
)
from des.adapters.driven.platform_residence_durability_adapter import (
    PlatformResidenceDurabilityAdapter,
)
from des.adapters.driven.refactor.git_worktree_adapter import GitWorktreeAdapter
from des.application.rescue_worktree_residence import rescue_worktree_residence
from des.domain.worktree_residence import (
    DurableResidence,
    ExternalResidenceLost,
    LaneIdentity,
    OwnerLease,
    RescuedResidence,
    ResidenceAdmission,
    ResidenceRefusal,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des worktree-admit",
        description="Create one worktree only after measuring a durable residence.",
    )
    parser.add_argument("--repo", required=True)
    parser.add_argument("--lane", required=True)
    return parser


def _refuse(refusal: ResidenceRefusal | ExternalResidenceLost | Exception) -> int:
    if isinstance(refusal, (ResidenceRefusal, ExternalResidenceLost)):
        print(f"WHAT: {refusal.what}", file=sys.stderr)
        print(f"WHY: {refusal.why}", file=sys.stderr)
        print(f"HOW: {refusal.how}", file=sys.stderr)
    else:
        print("WHAT: the durable worktree was not created", file=sys.stderr)
        print(f"WHY: {refusal}", file=sys.stderr)
        print(
            "HOW: resolve the named conflict, then retry `des worktree-admit`.",
            file=sys.stderr,
        )
    return 1


def _is_detached_repo_cwd(repo: Path, cwd: Path) -> bool:
    try:
        branch = git_text(cwd, "rev-parse", "--abbrev-ref", "HEAD").strip()
        repo_common = Path(
            git_text(
                repo, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).strip()
        ).resolve()
        cwd_common = Path(
            git_text(
                cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).strip()
        ).resolve()
    except Exception:
        return False
    return branch == "HEAD" and repo_common == cwd_common


def _ensure_held(root: Path) -> None:
    identity = LaneIdentity.observe(root)
    if not identity.git_dir:
        raise RuntimeError("worktree has no observable git identity")
    marker = MarkerFileOwnerLeaseAdapter()
    observed = marker.observe(root, identity)
    if observed is OwnerLease.HELD:
        return
    if (root / MARKER_RELATIVE_PATH).exists():
        raise RuntimeError("an existing owner assertion is not reusable as HELD")
    marker.write_held(root, identity)


def _cleanup_created(
    adapter: GitWorktreeAdapter, repo: Path, root: Path, lane: str
) -> None:
    try:
        if any(
            handle.path.resolve() == root.resolve()
            for handle in adapter.list_worktrees(repo)
        ):
            adapter.remove_worktree(repo, root)
            adapter.delete_branch(repo, lane)
    except Exception:
        pass


def _create_new(
    *,
    repo: Path,
    lane: str,
    admitted: DurableResidence,
    adapter: GitWorktreeAdapter,
) -> int:
    if admitted.root.exists() or any(
        handle.path.resolve() == admitted.root
        for handle in adapter.list_worktrees(repo)
    ):
        return _refuse(
            RuntimeError(f"destination is occupied or registered: {admitted.root}")
        )
    admitted.root.parent.mkdir(parents=True, exist_ok=True)
    try:
        adapter.create_worktree_from_tip(repo, lane, admitted, lane)
        _ensure_held(admitted.root)
    except Exception as exc:
        _cleanup_created(adapter, repo, admitted.root, lane)
        return _refuse(exc)
    print(admitted.root)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    repo = Path(args.repo).resolve()
    durability = PlatformResidenceDurabilityAdapter(repo)
    admission = ResidenceAdmission(durability)
    adapter = GitWorktreeAdapter()
    cwd = Path.cwd().resolve()

    if _is_detached_repo_cwd(repo, cwd):
        existing = admission.admit(cwd)
        if isinstance(existing, DurableResidence):
            try:
                _ensure_held(existing.root)
            except Exception as exc:
                return _refuse(exc)
            print(existing.root)
            return 0

        prepared_root: Path | None = None

        def _prepare(destination: DurableResidence) -> bool:
            nonlocal prepared_root
            destination.root.parent.mkdir(parents=True, exist_ok=True)
            # Set before the mutating call: a failure partway through git's
            # own worktree registration must still be a cleanup candidate,
            # not silently skipped because the happy-path assignment never
            # ran.
            prepared_root = destination.root
            adapter.create_worktree_from_tip(repo, args.lane, destination, args.lane)
            return True

        rescued = rescue_worktree_residence(
            source=cwd,
            repo=repo,
            lane_name=args.lane,
            durability=durability,
            prepare_destination=_prepare,
        )
        if not isinstance(rescued, RescuedResidence):
            if prepared_root is not None:
                _cleanup_created(adapter, repo, prepared_root, args.lane)
            return _refuse(rescued)
        copied_marker = rescued.residence.root / MARKER_RELATIVE_PATH
        if copied_marker.exists():
            copied_marker.unlink()
        try:
            _ensure_held(rescued.residence.root)
        except Exception as exc:
            _cleanup_created(adapter, repo, rescued.residence.root, args.lane)
            return _refuse(exc)
        print(rescued.residence.root)
        return 0

    admitted = admission.admit_default(repo, args.lane)
    if isinstance(admitted, ResidenceRefusal):
        return _refuse(admitted)
    assert isinstance(admitted, DurableResidence)
    return _create_new(repo=repo, lane=args.lane, admitted=admitted, adapter=adapter)


__all__ = ["main"]
