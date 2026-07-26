"""Validate DES-PROJECT-ROOT marker values from agent prompts.

The marker carries the worktree-rooted project path so hook handlers can
resolve execution-log against the correct repo when the orchestrator's CWD
differs from the executing worktree (Rex RCA F-DES-WORKTREE-EXECUTION-LOG-
RESOLUTION).

Validation rules (Rex risk-matrix mitigation against path-injection):
  1. Marker value MUST be an absolute path
  2. Path MUST exist
  3. Path MUST be a git work tree
  4. Path MUST share git-common-dir with the fallback cwd (i.e., belong to
     the same repository — direct same-repo OR sibling worktree)

On any validation failure, returns None — callers fall back to hook_input cwd.
Validation is fail-safe: a malformed/malicious marker degrades to the previous
cwd-only behaviour rather than blocking the hook.

`resolve_declared_project_root` is the DISCRIMINATED sibling: same rules, but it
names WHICH rule refused, so a caller that must not silently swap one tree for
another can refuse LOUD instead. Substituting the cwd for a declared root
without saying so is the same defect as reading the wrong tree, only harder to
see — `validate_project_root` keeps the fail-safe contract for the callers that
genuinely want it, and delegates to the sibling so there is ONE rule set.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


#: Why a declared DES-PROJECT-ROOT did not resolve. Each value routes the
#: operator to a DIFFERENT action, so they are never collapsed into one.
ROOT_NOT_ABSOLUTE = "declared-project-root-not-absolute"
ROOT_DOES_NOT_EXIST = "declared-project-root-does-not-exist"
ROOT_NOT_A_WORK_TREE = "declared-project-root-not-a-git-work-tree"
ROOT_DIFFERENT_REPOSITORY = "declared-project-root-in-a-different-repository"
ROOT_CWD_UNUSABLE = "fallback-cwd-unusable"


@dataclass(frozen=True)
class ProjectRootResolution:
    """The outcome of resolving one declared DES-PROJECT-ROOT marker.

    ``path`` is set exactly when the marker validated; ``reason`` and
    ``detail`` are set exactly when it did not.
    """

    path: Path | None
    reason: str = ""
    detail: str = ""

    @property
    def resolved(self) -> bool:
        return self.path is not None


def _refused(reason: str, detail: str) -> ProjectRootResolution:
    return ProjectRootResolution(path=None, reason=reason, detail=detail)


def _git_common_dir(path: Path) -> str | None:
    """Return resolved git-common-dir for *path*, or None on any failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    # git-common-dir may be relative to cwd; resolve to absolute
    common = Path(raw)
    common = (path / common).resolve() if not common.is_absolute() else common.resolve()
    return str(common)


def validate_project_root(marker_value: str, fallback_cwd: str) -> Path | None:
    """Validate a DES-PROJECT-ROOT marker against the fallback cwd.

    Args:
        marker_value: Raw marker string from agent prompt.
        fallback_cwd: hook_input['cwd'] - the orchestrator's startup CWD.

    Returns:
        Resolved absolute Path on success; None on any validation failure
        (caller falls back to fallback_cwd).
    """
    return resolve_declared_project_root(marker_value, fallback_cwd).path


def resolve_declared_project_root(
    marker_value: str, fallback_cwd: str
) -> ProjectRootResolution:
    """Resolve a declared DES-PROJECT-ROOT, NAMING the rule that refused it.

    The four validation rules are unchanged (absolute / exists / is a git work
    tree / same repository as the fallback cwd) -- this is the same gate, told
    honestly. An empty marker is not a refusal: nothing was declared, so the
    caller's cwd default is correct and ``reason`` stays empty.

    Args:
        marker_value: Raw marker string from agent prompt ("" when absent).
        fallback_cwd: hook_input['cwd'] - the orchestrator's startup CWD.
    """
    if not marker_value:
        return ProjectRootResolution(path=None)

    candidate = Path(marker_value)

    # Rule 1: absolute path
    if not candidate.is_absolute():
        return _refused(
            ROOT_NOT_ABSOLUTE,
            f"the declared project root {marker_value!r} is a RELATIVE path -- "
            f"relative to what is exactly the question a hook cannot answer; "
            f"declare an absolute path",
        )

    # Rule 2: path exists
    if not candidate.exists():
        return _refused(
            ROOT_DOES_NOT_EXIST,
            f"the declared project root {candidate} does NOT exist -- the tree "
            f"this dispatch names is not on this machine (a stale worktree "
            f"path, a typo, or a worktree removed since the envelope was "
            f"generated)",
        )

    # Rule 3: is git work tree
    marker_common = _git_common_dir(candidate)
    if marker_common is None:
        return _refused(
            ROOT_NOT_A_WORK_TREE,
            f"the declared project root {candidate} exists but is not a "
            f"readable git work tree (or `git` is unavailable here), so its "
            f"repository membership CANNOT be verified",
        )

    # Rule 4: shares git-common-dir with fallback cwd (same repo)
    cwd_path = Path(fallback_cwd)
    if not cwd_path.exists():
        return _refused(
            ROOT_CWD_UNUSABLE,
            f"the fallback cwd {cwd_path} does not exist, so the declared "
            f"project root {candidate} cannot be checked against it",
        )
    cwd_common = _git_common_dir(cwd_path)
    if cwd_common is None:
        return _refused(
            ROOT_CWD_UNUSABLE,
            f"the fallback cwd {cwd_path} is not a readable git work tree (or "
            f"`git` is unavailable here), so the declared project root "
            f"{candidate} cannot be checked against it",
        )

    if marker_common != cwd_common:
        return _refused(
            ROOT_DIFFERENT_REPOSITORY,
            f"the declared project root {candidate} belongs to a DIFFERENT "
            f"repository ({marker_common}) than the dispatching cwd {cwd_path} "
            f"({cwd_common})",
        )

    return ProjectRootResolution(path=candidate.resolve())
