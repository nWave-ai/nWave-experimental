"""GitCommittedScopeAdapter -- git implementation of CommittedScopePort.

AD-22 (ARCH_TECH_DEBT): this is the concrete git side of the committed-scope
boundary, extracted out of the application layer where it formerly lived as the
misnamed concrete ``CommittedScopePort``. It mirrors the established pattern
``ports.driven_ports.scope_checker.ScopeChecker`` (ABC) <->
``adapters.driven.validation.git_scope_checker.GitScopeChecker`` (impl): the
application depends on the PORT, this adapter implements it with ``git
ls-tree``.

git enters here ONLY (AD-21 git-free mandate): the gate logic depends on the
``CommittedScopePort`` Protocol, so a git-absent target degrades LOUD via the
port's ``Indeterminate`` -- never a baked-in requirement in the gate.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import (
    CommittedFileSet,
    CommittedScopePort,
    Indeterminate,
)


if TYPE_CHECKING:
    from pathlib import Path


# Repo-relative committed paths that pytest would treat as contract-suite test
# files (its default discovery patterns). Passing these to the collection
# worker's `--path` argv restricts pytest to committed tests.
#
# `.feature` files are DELIBERATELY excluded: pytest cannot collect a `.feature`
# path directly (it is bound to its `@scenario` `.py` step module, not collected
# as a path itself), so passing one to pytest as a `--path` makes pytest exit 4
# -> the gate fails closed with MalformedInput. No coverage is lost by the
# exclusion -- every `.feature` scenario is collected via its bound `.py`
# `@scenario` module, which remains in the path-set (slice-01 AT-4).
def _is_contract_suite_path(rel_path: str) -> bool:
    # DISTILL staging artifacts under `docs/feature/*/pending-ats/` are committed
    # (but superseded by their live `tests/` relocation) and are NOT the contract
    # suite. Collecting them as explicit `--path` argv trips the worker: a
    # deleted-on-disk staged file -> pytest exit 4, and a hyphenated
    # `docs/feature/f-...-attestation/pending-ats/...` dir is not an importable
    # module path -> ImportError -> pytest exit 2. Either way the digest worker
    # fails closed (vacuous Gate-Scope). Excluding the `docs/` staging tree keeps
    # the committed-scope fingerprint robust WITHOUT over-restricting to `tests/`:
    # the contract suite is generically "a test-named module anywhere in the
    # target repo" (a target's tests may sit at the repo root, not only under
    # `tests/` -- the fix-gcommit-exit-gate-scoping ATs pin exactly that with
    # root-level committed contract fixtures).
    if rel_path.startswith("docs/"):
        return False
    name = rel_path.rsplit("/", maxsplit=1)[-1]
    if not name.endswith(".py"):
        return False
    return (
        name.startswith("test_") or name.endswith("_test.py") or name == "conftest.py"
    )


class GitCommittedScopeAdapter(CommittedScopePort):
    """Reads the committed contract-suite file-set out of git (``git ls-tree``).

    ``committed_contract_files`` returns the committed contract-suite paths at
    ``commit``, or an ``Indeterminate`` when git is absent / the path is not a
    work-tree / the SHA is unresolvable. Pure read of the git index -- no
    filesystem mutation.
    """

    def committed_contract_files(
        self, repo: Path, commit: str
    ) -> CommittedFileSet | Indeterminate:
        """Return the committed contract-suite file-set, or Indeterminate.

        Callers resolve the commit (the gate shells ``git rev-parse HEAD``)
        before reaching here, so git is established. ``git ls-tree`` exiting
        non-zero -- the path is not a work-tree, or the commit was raced/GC'd
        between resolution and listing -- yields ``Indeterminate``: the gate
        degrades LOUD rather than fingerprint a tree it cannot list. The
        upstream "git is established" assumption is a caller convention, not
        a guarantee this adapter may rely on: if it is ever wrong (``git``
        missing from PATH, or another OS-level spawn failure), this adapter
        degrades to the same ``Indeterminate`` itself rather than let an
        uncaught ``OSError``/``SubprocessError`` crash the gate with a
        traceback.
        """
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", "--name-only", commit],
                cwd=repo,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return Indeterminate(f"git ls-tree could not be run: {exc}")
        if result.returncode != 0:
            return Indeterminate(
                f"git ls-tree failed (exit {result.returncode}): "
                f"{result.stderr.strip()[:200]}"
            )
        paths = tuple(
            line
            for line in result.stdout.splitlines()
            if line and _is_contract_suite_path(line)
        )
        return CommittedFileSet(paths)
