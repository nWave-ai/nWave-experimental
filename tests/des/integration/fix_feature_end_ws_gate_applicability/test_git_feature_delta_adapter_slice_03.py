"""Adapter-integration tests for the slice-03 GitFeatureDeltaAdapter (Layer 2).

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified B-port,
2026-06-05). This is the EARNED-TRUST seam the DESIGN flags as the slice's
biggest risk (DDD-1 + the effect-isolation section): the `GitFeatureDeltaAdapter`
MUST distinguish

  * git-FAILURE      -> `Indeterminate(reason)`  (degrade LOUD), from
  * git-SUCCESS-EMPTY -> `AddedPaths(())`         (a genuinely empty delta).

The load-bearing distinction: the adapter must NEVER return an empty
`AddedPaths(())` to MASK a git failure -- an empty delta reads downstream as
"ships no new installable" = NA, fabricating a silent pass the mandate forbids.
An empty `AddedPaths(())` is ONLY legitimate when git SUCCEEDS and the delta is
genuinely empty.

This is a driven-adapter integration test (Layer 2): unlike the acceptance
slice, it MAY import the adapter directly and inject real git faults
(target-machine-agnosticism carve-out: git enters behind this adapter ONLY).
Each fault the DESIGN enumerates (DDD-1 effect-isolation list) yields the SAME
LOUD `Indeterminate` signal the gate routes to the INDETERMINATE verdict:

  1. git binary absent (FileNotFoundError, via an empty PATH)
  2. not a git work-tree (`git diff` exit != 0)
  3. base_ref unresolvable (`master` absent in the repo)

RED-for-right-reason (pre-DELIVER gate): the adapter
(`des.adapters.driven.git.git_feature_delta_adapter.GitFeatureDeltaAdapter`) and
its port VO (`des.ports.driven_ports.feature_delta_port.AddedPaths`) do NOT exist
at HEAD `c7a3375f6`. The import is GUARDED so collection stays CLEAN (no
ImportError -> no BROKEN classification); each test then asserts the adapter is
importable + exhibits the earned-trust contract, failing with a semantic
AssertionError (MISSING_FUNCTIONALITY) until A_GREEN ships the adapter.
"""

from __future__ import annotations

import importlib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import pytest


_PORT_MODULE = "des.ports.driven_ports.feature_delta_port"
_ADAPTER_MODULE = "des.adapters.driven.git.git_feature_delta_adapter"
_INDETERMINATE_MODULE = "des.ports.driven_ports.committed_scope_port"

_BASE_REF = "master"


def _import_optional(module: str, name: str) -> Any | None:
    """Import `name` from `module`, or None when it does not yet exist.

    Keeps collection CLEAN while the production module is still a RED scaffold:
    a missing module/attribute yields None (the test asserts on it), never an
    ImportError that would mis-classify the RED as BROKEN.
    """
    try:
        mod = importlib.import_module(module)
    except ModuleNotFoundError:
        return None
    return getattr(mod, name, None)


def _adapter_pieces() -> tuple[Any | None, Any | None, Any | None]:
    """Resolve (AddedPaths, GitFeatureDeltaAdapter, Indeterminate) or Nones."""
    added_paths = _import_optional(_PORT_MODULE, "AddedPaths")
    adapter_cls = _import_optional(_ADAPTER_MODULE, "GitFeatureDeltaAdapter")
    indeterminate = _import_optional(_INDETERMINATE_MODULE, "Indeterminate")
    return added_paths, adapter_cls, indeterminate


def _require_adapter() -> tuple[Any, Any, Any]:
    """Assert the slice-03 adapter pieces exist (MISSING_FUNCTIONALITY RED)."""
    added_paths, adapter_cls, indeterminate = _adapter_pieces()
    assert added_paths is not None, (
        f"{_PORT_MODULE}.AddedPaths does not exist yet "
        "(slice-03 RED -- the FeatureDeltaPort VO is unimplemented)"
    )
    assert adapter_cls is not None, (
        f"{_ADAPTER_MODULE}.GitFeatureDeltaAdapter does not exist yet "
        "(slice-03 RED -- the git delta adapter is unimplemented)"
    )
    assert indeterminate is not None, (
        f"{_INDETERMINATE_MODULE}.Indeterminate is unavailable for reuse"
    )
    return added_paths, adapter_cls, indeterminate


# --- git work-tree staging helpers (PRECONDITION I/O only) -------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)


def _init_repo_with_baseline(repo: Path) -> None:
    """Init a repo on `master`, baseline commit, feature branch with one add."""
    _git(repo, "init", "-q", "-b", _BASE_REF)
    _git(repo, "config", "user.email", "distill@nwave.test")
    _git(repo, "config", "user.name", "distill")
    (repo / "keep.txt").write_text("baseline\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "baseline")


# --- earned-trust: git SUCCESS paths (the legitimate AddedPaths returns) ------


def test_git_success_with_added_paths_returns_those_paths(tmp_path: Path) -> None:
    """A real delta that adds a file returns `AddedPaths` naming that file."""
    added_paths_cls, adapter_cls, _ = _require_adapter()

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_baseline(repo)
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    (repo / "new_pkg").mkdir()
    (repo / "new_pkg" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: add a package")

    result = adapter_cls().added_paths(repo, _BASE_REF)

    assert isinstance(result, added_paths_cls), (
        "git SUCCESS with a non-empty delta must return AddedPaths, not "
        f"Indeterminate: got {result!r}"
    )
    assert "new_pkg/pyproject.toml" in tuple(result.paths)


def test_git_success_empty_delta_returns_empty_added_paths_not_indeterminate(
    tmp_path: Path,
) -> None:
    """The load-bearing distinction: git SUCCESS + empty delta -> AddedPaths(()).

    An empty delta MUST be an empty `AddedPaths`, NEVER an `Indeterminate` -- and
    (the inverse, pinned in the fault tests below) a git FAILURE must NEVER be an
    empty `AddedPaths`. This is the anti-silent-pass seam: downstream, empty
    AddedPaths reads as "ships no new installable" = NA, so it is ONLY honest when
    git genuinely succeeded with no added files.
    """
    added_paths_cls, adapter_cls, indeterminate_cls = _require_adapter()

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_baseline(repo)
    # Feature branch whose only change MODIFIES the baseline file -- no ADDED path.
    _git(repo, "checkout", "-q", "-b", "feature/topic")
    (repo / "keep.txt").write_text("changed\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "feat: modify only, add nothing")

    result = adapter_cls().added_paths(repo, _BASE_REF)

    assert not isinstance(result, indeterminate_cls), (
        "git SUCCESS with an empty delta must NOT degrade to Indeterminate"
    )
    assert isinstance(result, added_paths_cls)
    assert tuple(result.paths) == (), (
        f"empty git delta must yield AddedPaths(()), got {result!r}"
    )


# --- earned-trust: git FAILURE paths (every fault -> LOUD Indeterminate) ------


def test_git_binary_absent_returns_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git executable not found (empty PATH) -> Indeterminate, never empty paths."""
    added_paths_cls, adapter_cls, indeterminate_cls = _require_adapter()

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_baseline(repo)
    # Make the `git` executable unfindable for the adapter's own subprocess call.
    monkeypatch.setenv("PATH", "")

    result = adapter_cls().added_paths(repo, _BASE_REF)

    assert isinstance(result, indeterminate_cls), (
        "git binary absent must degrade LOUD to Indeterminate, not crash and "
        f"not fabricate an empty AddedPaths: got {result!r}"
    )
    assert not isinstance(result, added_paths_cls)
    assert result.reason, "the Indeterminate must carry a non-empty reason"


def test_not_a_work_tree_returns_indeterminate(tmp_path: Path) -> None:
    """A directory that is not a git work-tree -> Indeterminate, never empty paths."""
    added_paths_cls, adapter_cls, indeterminate_cls = _require_adapter()

    non_repo = tmp_path / "plain_dir"
    non_repo.mkdir()  # no `git init` -- deliberately not a work-tree

    result = adapter_cls().added_paths(non_repo, _BASE_REF)

    assert isinstance(result, indeterminate_cls), (
        "a non-work-tree must degrade LOUD to Indeterminate, never an empty "
        f"AddedPaths that would silently read as NA: got {result!r}"
    )
    assert not isinstance(result, added_paths_cls)
    assert result.reason


def test_base_ref_unresolvable_returns_indeterminate(tmp_path: Path) -> None:
    """An absent base_ref in the repo -> Indeterminate, never empty paths."""
    added_paths_cls, adapter_cls, indeterminate_cls = _require_adapter()

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo_with_baseline(repo)

    # `nonexistent-base` is not a ref in this repo -> git diff cannot resolve it.
    result = adapter_cls().added_paths(repo, "nonexistent-base")

    assert isinstance(result, indeterminate_cls), (
        "an unresolvable base_ref must degrade LOUD to Indeterminate, never an "
        f"empty AddedPaths: got {result!r}"
    )
    assert not isinstance(result, added_paths_cls)
    assert result.reason
