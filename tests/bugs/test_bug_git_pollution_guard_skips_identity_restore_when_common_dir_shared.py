"""RED regression test — `_git_pollution_guard` must restore identity keys
(and fail loudly) when the common `.git` is shared with live linked
worktrees, while leaving sibling-legitimate config entries untouched.

Defect (`docs/feature/fix-test-suite-mutates-shared-git-identity/rca.md`,
Root Cause B): `_common_git_dir_is_shared` gates the WHOLE diff-kind set at
once (`tests/conftest.py:1198-1216`) — including `"config"` — because the
restore primitive (`_atomic_restore_git_state`) performs a wholesale
snapshot write-back with no per-key granularity. On 2026-08-03 this let a
test's `git config user.name|user.email` write reach the SHARED trunk
`.git/config` undetected-and-uncorrected: the guard only emitted a stderr
warning nobody reads (`_warn_shared_common_dir_restore_skipped`), never
restored, never failed. The next commit on ANY of the 20 linked worktrees
would have been mis-attributed to `Test User <test@example.com>`.

Intended fix (RCA §7 P2 — not yet implemented): classify config keys into
SELF-OWNED identity keys (`user.name`, `user.email`, `user.signingkey`,
`author.*`, `committer.*`) — restore + fail, ALWAYS, even when shared,
because no sibling worktree legitimately writes these — versus
SIBLING-LEGITIMATE keys (`branch.*`, `remote.*`, `submodule.*`,
`extensions.*`, `pull.*`, `push.*`, `core.hooksPath`) — never restore, never
fail, because `git push -u` / `git remote add` from a concurrently-running
sibling worktree write exactly these keys into the same shared file. An
unattributable key (neither bucket) must degrade LOUD, never pass silently.

This is a GRANULARITY property, not two independent facts: a fix that
restores identity but ALSO restores sibling-legitimate keys (a blunt
wholesale-restore) is exactly as wrong as one that restores nothing — it
reintroduces the 2026-07-20 harm (RCA CF-1 / R-2) the sharing exemption
exists to prevent. Both halves are asserted in the SAME scenario in T1 below
so neither a no-op fix nor a wholesale-restore fix can pass.

Reuse: `_init_isolated_repo` / `_create_initial_commit` imported from
`tests.test_guard_fixtures` (the established isolated-repo harness for this
guard family) — no parallel harness built. The "shared common dir"
condition is simulated exactly as `tests/bugs/des/
test_git_pollution_guard_shared_common_dir.py` does: a plain
`.git/worktrees/<name>/` directory marker under `tmp_path`, never a live
linked worktree and never this repo's own `.git`.

Driving port: the autouse fixture itself
(`tests.conftest._git_pollution_guard`), driven directly as a generator via
its `.__wrapped__` (pytest 9's `FixtureFunctionDefinition` exposes the
original function there), with `tests.conftest._PROJECT_ROOT`
monkeypatched to the throwaway repo so the guard's real
snapshot/diff/restore/fail logic runs end-to-end against `tmp_path` only —
never the real project root. Every git invocation below is `-C <tmp
repo>`-scoped or `GIT_CEILING_DIRECTORIES`-scoped; nothing escapes
`tmp_path`.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

import pytest

from tests import conftest
from tests.test_guard_fixtures import _create_initial_commit, _init_isolated_repo


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers — mirror tests/bugs/des/test_git_pollution_guard_shared_common_dir.py
# (reused shape, not re-imported: that file keeps its own private `_git` /
# `_mark_shared` too, following the established per-file convention).
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(repo_root.parent)}
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _mark_shared(repo_root: Path, name: str = "sibling") -> None:
    """Simulate a live linked worktree: a plain `.git/worktrees/<name>/`
    directory marker, exactly what git writes when a linked worktree is
    added. No live worktree, no shared state beyond this marker."""
    (repo_root / ".git" / "worktrees" / name).mkdir(parents=True, exist_ok=True)


def _seed_repo_with_baseline_identity(tmp_path: Path) -> Path:
    """A throwaway repo with one commit and a distinguishable, non-placeholder
    identity — so restore-vs-pollution is unambiguous in assertions."""
    repo_root = tmp_path / "victim_repo"
    repo_root.mkdir()
    _init_isolated_repo(repo_root)
    _create_initial_commit(repo_root)
    _git(repo_root, "config", "user.name", "Real Developer")
    _git(repo_root, "config", "user.email", "real.dev@example.org")
    return repo_root


def _drive_guard_to_yield(monkeypatch: pytest.MonkeyPatch, repo_root: Path):
    """Point the autouse guard at `repo_root` and advance it to its yield
    point (the 'before' snapshot is taken there)."""
    monkeypatch.setattr(conftest, "_PROJECT_ROOT", repo_root)
    gen = conftest._git_pollution_guard.__wrapped__()
    next(gen)
    return gen


def _finish_guard(gen) -> BaseException | None:
    """Advance the guard generator past its `finally:` block.

    Returns the exception the guard raised — `pytest.fail.Exception`
    (`Failed`) on the LOUD path — or `None` if the generator ran to
    completion silently (the warn-only / silent-pass path: the guard's
    `finally:` block returns without raising, so a second `next()` simply
    exhausts the generator and Python raises `StopIteration`, which we
    fold into `None` here since it represents "nothing was reported").
    """
    try:
        next(gen)
    except StopIteration:
        return None
    except BaseException as exc:
        # non-StopIteration exception (Failed, or an implementation error)
        # is a LOUD signal and must be surfaced to the caller, not swallowed.
        return exc
    return None


def _config_text(repo_root: Path) -> str:
    return (repo_root / ".git" / "config").read_text()


# ---------------------------------------------------------------------------
# T1 — GRANULARITY pin: identity restored + guard fails loudly, AND the
# sibling's branch/remote entries survive byte-identical.
# ---------------------------------------------------------------------------


def test_guard_restores_identity_but_preserves_sibling_config_when_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both halves of the granularity contract, in one scenario, so
    neither a no-op (today's bug) nor a wholesale-restore (a naive,
    equally-wrong fix) can pass.
    """
    repo_root = _seed_repo_with_baseline_identity(tmp_path)
    _mark_shared(repo_root)

    gen = _drive_guard_to_yield(monkeypatch, repo_root)

    # A sibling worktree legitimately advances its own branch tracking —
    # the exact shape of `git push -u origin <branch>` + `git remote add`.
    _git(repo_root, "config", "branch.main.remote", "origin")
    _git(repo_root, "config", "branch.main.merge", "refs/heads/main")
    _git(repo_root, "config", "remote.origin.url", "https://example.invalid/repo.git")

    # THIS test corrupts the shared identity — the exact 2026-08-03 value.
    _git(repo_root, "config", "user.name", "Test User")
    _git(repo_root, "config", "user.email", "test@example.com")

    raised = _finish_guard(gen)

    # HALF 1 (positive): the guard must fail loudly, naming the corruption.
    assert isinstance(raised, pytest.fail.Exception), (
        "Guard did not fail loudly on identity pollution under a shared "
        f"common .git dir; got {raised!r} instead of a pytest.fail() "
        "Failed exception. Root cause: _common_git_dir_is_shared gates "
        "the whole diff-kind set (including identity) at once "
        "(tests/conftest.py:1198-1216) instead of restoring+failing on "
        "SELF-OWNED identity keys specifically."
    )
    assert "ident" in str(raised).lower(), (
        f"Guard failed, but the failure message does not name the "
        f"corruption as an identity problem: {raised!r}"
    )

    config_after = _config_text(repo_root)

    # HALF 1 (restore): identity keys must come back to their pre-test
    # values even under a shared common dir.
    assert "Real Developer" in config_after and "Test User" not in config_after, (
        "HALF 1 (restore): user.name must be restored to its pre-test "
        f"value even under a shared common dir. Config now reads:\n"
        f"{config_after}"
    )
    assert (
        "real.dev@example.org" in config_after
        and "test@example.com" not in config_after
    ), (
        "HALF 1 (restore): user.email must be restored to its pre-test "
        f"value even under a shared common dir. Config now reads:\n"
        f"{config_after}"
    )

    # HALF 2 (NEGATIVE — the wrong outcome must NOT be produced): the
    # sibling's branch/remote entries must survive BYTE-IDENTICAL. A
    # blunt wholesale-restore (write back the whole pre-test snapshot)
    # would wipe these — that is the 2026-07-20 harm this exemption
    # exists to prevent, and this assertion is the explicit pin against
    # it. A test asserting only HALF 1 would pass against exactly that
    # blunt implementation.
    assert '[branch "main"]' in config_after, (
        "HALF 2 (NEGATIVE — must NOT happen): the sibling's "
        "`branch.main.*` tracking section was wiped by the guard's "
        f"restore. A wholesale-restore implementation is exactly as "
        f"wrong as no restore at all. Config now reads:\n{config_after}"
    )
    assert "remote = origin" in config_after, (
        "HALF 2 (NEGATIVE): `branch.main.remote` was not preserved. "
        f"Config now reads:\n{config_after}"
    )
    assert "merge = refs/heads/main" in config_after, (
        "HALF 2 (NEGATIVE): `branch.main.merge` was not preserved. "
        f"Config now reads:\n{config_after}"
    )
    assert (
        '[remote "origin"]' in config_after
        and "https://example.invalid/repo.git" in config_after
    ), (
        "HALF 2 (NEGATIVE — must NOT happen): the sibling's "
        "`remote.origin.*` entry was wiped by the guard's restore. "
        f"Config now reads:\n{config_after}"
    )


# ---------------------------------------------------------------------------
# T2 — degrade-LOUD pin: an unattributable key change must never pass
# silently, even though it belongs to neither bucket.
# ---------------------------------------------------------------------------


def test_guard_does_not_silently_pass_an_unattributable_config_key_when_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A config key change the guard cannot attribute to SELF-OWNED
    identity or SIBLING-LEGITIMATE tracking must degrade LOUD
    (INDETERMINATE/fail) — never a silent pass. Today's code treats this
    identically to every other shared-dir diff: warn-only, no fail, no
    record anywhere pytest surfaces. That is the silent-wrong this test
    pins against (RCA Root Cause C).
    """
    repo_root = _seed_repo_with_baseline_identity(tmp_path)
    _mark_shared(repo_root)

    gen = _drive_guard_to_yield(monkeypatch, repo_root)

    # A key that is neither identity (user.*/author.*/committer.*) nor
    # sibling-legitimate (branch.*/remote.*/submodule.*/extensions.*/
    # pull.*/push.*/core.hooksPath) — genuinely unattributable.
    _git(repo_root, "config", "custom.unrecognizedkey", "unattributable-value")

    raised = _finish_guard(gen)

    assert raised is not None, (
        "Guard silently passed on a config change it cannot attribute to "
        "either the identity bucket or the sibling-legitimate bucket "
        f"(guard generator completed with no exception, {raised!r}). Per "
        "RCA P2, an unattributable key must degrade LOUD (INDETERMINATE "
        "or fail) — never a silent pass indistinguishable from 'nothing "
        "happened'."
    )
