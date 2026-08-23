"""Global-git-config isolation: the env contract and the guard's pure helpers.

WHY THIS MODULE EXISTS (RCA 2026-08-22, second occurrence of the class whose
first occurrence is recorded in ``scripts/hooks/reject_placeholder_git_identity.py``):
git resolves its GLOBAL config from ``$HOME`` (``~/.gitconfig``, or
``$XDG_CONFIG_HOME/git/config``) unless ``GIT_CONFIG_GLOBAL`` names a file. The
suite isolated the repo-local ``.git`` state seven different ways and never
isolated the global one, so ANY ``git`` subprocess started under pytest — or,
as on 2026-08-22, any ``git config --global`` typed by an agent probe running in
the same shell environment — wrote straight into the developer's real
``~/.gitconfig``. The 2026-06-24 occurrence left ``test@example.com`` as the
real commit identity for five months.

The fix is representational (GDP-0), not a late check: ``tests/conftest.py``
exports these three variables for the whole session at IMPORT time, so the real
global config is UNREACHABLE by construction from the first byte of collection.

THE ONE CAVEAT — an explicit ``env=`` bypasses it. ``subprocess.run(..., env={...})``
REPLACES the environment; a dict that is not built from ``os.environ`` drops the
three variables and git falls back to ``$HOME`` (or, with no ``HOME`` in the
dict, to the passwd-database home — the developer's real one). Build such an env
with :func:`git_env` instead of a bare literal, or keep ``**os.environ`` in it.
``tests/conftest.py``'s session guard catches whatever still slips through.
"""

from __future__ import annotations

import os
from pathlib import Path


#: The three variables that together make git's global AND system config
#: unreachable: the global file is redirected, the system file is emptied, and
#: ``GIT_CONFIG_NOSYSTEM`` is belt-and-braces for git builds that ignore the
#: ``GIT_CONFIG_SYSTEM`` redirect.
GIT_CONFIG_ISOLATION_KEYS: tuple[str, ...] = (
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_NOSYSTEM",
)

#: Escape hatch, declared and explicit: set to "1" to run the suite against the
#: REAL global git config. Nothing in-tree needs it (verified 2026-08-22: the
#: only tests that must not see a global identity — e.g.
#: ``tests/scripts/analysis/test_k4_row10_git_identity.py`` — already pass their
#: own literal env dict and are therefore unaffected by the session isolation).
#: It exists so an operator debugging a real-config interaction has a documented
#: switch instead of editing the conftest.
ALLOW_REAL_GITCONFIG_ENV_VAR = "NWAVE_TESTS_ALLOW_REAL_GITCONFIG"

#: The identity the suite commits under when a test sets none of its own. It
#: DELIBERATELY matches a placeholder pattern of
#: ``scripts/hooks/reject_placeholder_git_identity.py`` (``@nwave.local``): if it
#: ever escapes into a real-repo commit, that pre-commit guard REJECTS the commit
#: loudly instead of shipping mis-attributed history (GDP-6, degrade loud).
SUITE_GIT_IDENTITY_NAME = "nWave Test Suite"
SUITE_GIT_IDENTITY_EMAIL = "suite@nwave.local"


def render_isolated_global_gitconfig() -> str:
    """Content of the throwaway global git config. Pure.

    Identity only: the developer's real global config supplies a commit identity
    that tmp-repo fixtures rely on, so an EMPTY isolated file would turn every
    identity-less fixture commit into ``fatal: empty ident name``. Nothing else
    is seeded — every other global setting stays absent, which is what an
    ephemeral CI home looks like.
    """
    return (
        "[user]\n"
        f"\tname = {SUITE_GIT_IDENTITY_NAME}\n"
        f"\temail = {SUITE_GIT_IDENTITY_EMAIL}\n"
    )


def git_config_isolation_env(global_config_path: Path | str) -> dict[str, str]:
    """The three variables, bound to ``global_config_path``. Pure."""
    return {
        "GIT_CONFIG_GLOBAL": str(global_config_path),
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }


def git_env(base: dict[str, str] | None = None, **overrides: object) -> dict[str, str]:
    """Build a subprocess env that KEEPS the session's git-config isolation.

    Use this instead of a literal ``env={...}`` whenever the child process can
    reach ``git`` (directly, or through an installer/hook that shells out to it).

    ``base`` defaults to a copy of ``os.environ``; pass an already-scrubbed dict
    to keep your own scrub and still re-admit the three isolation keys. Keyword
    ``overrides`` are applied last and stringified.
    """
    env = dict(os.environ if base is None else base)
    for key in GIT_CONFIG_ISOLATION_KEYS:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    env.update({key: str(value) for key, value in overrides.items()})
    return env


def real_global_gitconfig_paths(home: Path | None = None) -> tuple[Path, ...]:
    """Every path git would resolve as the GLOBAL config for ``home``. Pure.

    Both candidates are returned, not just the one that exists: git writes
    ``$XDG_CONFIG_HOME/git/config`` when that file already exists and
    ``~/.gitconfig`` otherwise, so a guard that watched only one of them would
    miss the other machine's layout. ``XDG_CONFIG_HOME`` is read from the
    environment at CALL time — resolve once, before any test can patch it.
    """
    base = Path.home() if home is None else home
    xdg = os.environ.get("XDG_CONFIG_HOME")
    xdg_base = Path(xdg) if xdg else base / ".config"
    return (base / ".gitconfig", xdg_base / "git" / "config")


def snapshot_global_gitconfig(paths: tuple[Path, ...]) -> dict[str, bytes | None]:
    """path -> bytes, or ``None`` when the file is absent. Pure (reads only)."""
    return {
        str(path): (path.read_bytes() if path.is_file() else None) for path in paths
    }


def diff_global_gitconfig(
    before: dict[str, bytes | None], after: dict[str, bytes | None]
) -> list[str]:
    """Human-readable violation lines; empty list = the real config is intact. Pure.

    Three shapes, deliberately distinct because their remedies differ:
    ``MODIFIED`` (restorable from the snapshot), ``CREATED`` (never deleted by
    the guard — it holds no prior bytes to restore) and ``DELETED`` (restorable).
    """
    violations: list[str] = []
    for path in sorted(set(before) | set(after)):
        was = before.get(path)
        now = after.get(path)
        if was == now:
            continue
        if was is None:
            violations.append(f"CREATED {path}")
        elif now is None:
            violations.append(f"DELETED {path}")
        else:
            violations.append(f"MODIFIED {path}")
    return violations


def restore_global_gitconfig(
    before: dict[str, bytes | None], violations: list[str]
) -> list[str]:
    """Write the snapshot bytes back for every restorable violation.

    Returns the paths actually restored. ``CREATED`` entries are skipped on
    purpose: the guard holds no prior bytes for them, and a guard that deleted a
    file it never snapshotted would destroy state it cannot prove it owns.
    """
    restored: list[str] = []
    for violation in violations:
        state, _, path_str = violation.partition(" ")
        if state == "CREATED":
            continue
        previous = before.get(path_str)
        if previous is None:
            continue
        path = Path(path_str)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)
        restored.append(path_str)
    return restored
