"""des.runtime.distribution — editable distribution boundary (D3).

Per `docs/analysis/ddd-workflow-change-difficulty-2026-05-26.md` § D3:
the `.git/` adjacency walk that distinguishes a developer checkout from a
customer install is structurally hook-side, NOT runtime-side. It belongs
in a shared module both `freshness.py` (the runtime gate) and the hook
subprocess PYTHONPATH resolver (the install-time template) can reference.

Customer install (no `.git/` in any ancestor) → returns `None`.
Developer checkout (any `.git/` ancestor) → returns the absolute path to
the `.git/`-adjacent directory (the repo root).

Language-portability story: the walk is filesystem-level, language-neutral.
A TS / Go / Rust adapter that needs the same discrimination uses the same
shape — just translated to its host language. The contract is "find the
nearest `.git/`-adjacent ancestor or None".

Target-machine-independence: customer installs (no `.git/` in any
ancestor) preserve fail-closed installed-copy behavior byte-identical.
Developer checkouts auto-resolve to repo source via the same walk.

Closes friction #58 (F-DES-HOOK-SUBPROCESS-INSTALLED-COPY-STALENESS)
structurally: hook subprocess no longer disagrees with editor on which
`des` to import.
"""

from __future__ import annotations

import os


def find_git_root(start: str | None = None) -> str | None:
    """Walk parents from ``start`` (default CWD) looking for ``.git/``.

    Returns the absolute path to the `.git/`-adjacent ancestor directory
    (the repo root) if found; ``None`` otherwise.

    The walk terminates at the filesystem root. A customer install host
    with no checkout in any ancestor returns ``None`` — callers preserve
    their fail-closed installed-copy behavior byte-identical.

    A developer checkout host (any ancestor has ``.git/``) returns the
    repo root path — callers can prepend ``{repo_root}/src`` to PYTHONPATH
    so the hook subprocess loads `des` from repo source, not installed
    copy.
    """
    cwd = os.path.abspath(start or ".")
    while True:
        if os.path.isdir(os.path.join(cwd, ".git")):
            return cwd
        parent = os.path.dirname(cwd)
        if parent == cwd:
            return None  # reached filesystem root, no .git/ found
        cwd = parent


__all__ = ["find_git_root"]
