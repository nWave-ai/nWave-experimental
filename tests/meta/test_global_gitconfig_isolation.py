"""The suite cannot reach the developer's real GLOBAL git config.

RCA 2026-08-22 (second occurrence of the class recorded in
``scripts/hooks/reject_placeholder_git_identity.py``): ``~/.gitconfig`` was the
one git surface this suite never isolated. Every test here probes the PROPERTY
("a ``git config --global`` started under pytest cannot land in a HOME-resolved
config"), never the designation — and none of them touches the real file: the
probes redirect ``HOME`` to a tmp dir, so on the pre-fix code they write into
that throwaway home, which is exactly what makes the RED safe to run.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

from scripts.hooks.reject_placeholder_git_identity import _is_placeholder
from tests.support.git_env import (
    GIT_CONFIG_ISOLATION_KEYS,
    SUITE_GIT_IDENTITY_EMAIL,
    SUITE_GIT_IDENTITY_NAME,
    diff_global_gitconfig,
    git_env,
    real_global_gitconfig_paths,
    restore_global_gitconfig,
    snapshot_global_gitconfig,
)


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------


def _fake_home(tmp_path: Path) -> Path:
    """An empty HOME the probes may pollute freely."""
    home = tmp_path / "fake-home"
    home.mkdir()
    return home


def _home_resolved_config_paths(home: Path) -> tuple[Path, ...]:
    """The two files git would treat as the global config for ``home``."""
    return (home / ".gitconfig", home / ".config" / "git" / "config")


def _write_global_email(env: dict[str, str], email: str) -> subprocess.CompletedProcess:
    """Run the exact command that caused the incident."""
    return subprocess.run(
        ["git", "config", "--global", "user.email", email],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@contextmanager
def _session_global_config_restored() -> Iterator[Path | None]:
    """Yield the session's throwaway global config, restoring it afterwards.

    The probes below deliberately WRITE through the session isolation, which
    lands in this file; without the restore they would leave a ``user.email``
    behind for every later test in the same worker.

    Yields ``None`` when no isolation is in force, so a caller still runs its
    probe and fails on the PROPERTY it is testing (where the write landed)
    rather than on this helper's bookkeeping.
    """
    configured = os.environ.get("GIT_CONFIG_GLOBAL")
    if not configured:
        yield None
        return
    path = Path(configured)
    before = path.read_bytes() if path.is_file() else None
    try:
        yield path
    finally:
        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(before)


# ---------------------------------------------------------------------------
# Leg 1 — unreachability by construction
# ---------------------------------------------------------------------------


def test_the_session_redirects_the_global_config_away_from_the_developers_file() -> (
    None
):
    """All three isolation variables are exported, and git honours them."""
    for key in GIT_CONFIG_ISOLATION_KEYS:
        assert key in os.environ, f"{key} is not exported by tests/conftest.py"

    configured = Path(os.environ["GIT_CONFIG_GLOBAL"]).resolve()
    for real in real_global_gitconfig_paths():
        assert configured != real.resolve(), (
            "the session global config must NOT be the developer's own file"
        )

    listed = subprocess.run(
        ["git", "config", "--global", "--list"],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert f"user.email={SUITE_GIT_IDENTITY_EMAIL}" in listed.stdout


def test_git_config_global_under_pytest_cannot_reach_a_home_resolved_config(
    tmp_path: Path,
) -> None:
    """The incident command, replayed: it must not write any HOME-resolved file.

    RED before the fix: with no ``GIT_CONFIG_GLOBAL`` in the environment git
    resolves ``$HOME/.gitconfig`` and creates it. The redirect makes that file
    unrepresentable as a write target.
    """
    home = _fake_home(tmp_path)
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")

    with _session_global_config_restored() as session_config:
        result = _write_global_email(env, "probe@nwave.invalid")
        assert result.returncode == 0, result.stderr
        written = session_config.read_text(encoding="utf-8") if session_config else ""

    for candidate in _home_resolved_config_paths(home):
        assert not candidate.exists(), (
            f"git wrote the HOME-resolved global config {candidate} — the "
            "session isolation is not in force"
        )
    assert "probe@nwave.invalid" in written, (
        "the write must land in the session's throwaway global config"
    )


def test_a_fixture_repo_still_commits_without_setting_its_own_identity(
    tmp_path: Path,
) -> None:
    """The throwaway global config keeps a commit identity resolvable.

    Guards the isolation's own blast radius: an EMPTY isolated global config
    would turn every identity-less tmp-repo fixture commit into
    ``fatal: empty ident name``.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    for argv in (
        ["git", "init", "-q", "-b", "main", str(repo)],
        ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "seed"],
    ):
        done = subprocess.run(argv, capture_output=True, text=True, check=False)
        assert done.returncode == 0, f"{argv} failed: {done.stderr}"

    author = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%an <%ae>"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert author.stdout.strip() == (
        f"{SUITE_GIT_IDENTITY_NAME} <{SUITE_GIT_IDENTITY_EMAIL}>"
    )


def test_the_suite_identity_would_be_rejected_if_it_ever_leaked_into_a_commit() -> None:
    """Fail-loud choice, pinned: the seeded identity IS a placeholder.

    The pre-commit guard ``reject_placeholder_git_identity`` must recognise it,
    so a real-repo commit accidentally made under the suite identity is refused
    rather than silently mis-attributed.
    """
    assert _is_placeholder(SUITE_GIT_IDENTITY_NAME, SUITE_GIT_IDENTITY_EMAIL)


# ---------------------------------------------------------------------------
# The caveat: an explicit env= bypasses leg 1 — and git_env() closes it
# ---------------------------------------------------------------------------


def test_a_literal_env_bypasses_the_isolation_but_git_env_restores_it(
    tmp_path: Path,
) -> None:
    """Demonstrates the ONE hole in leg 1, and the helper that closes it.

    A ``subprocess.run(env={...})`` dict not built from ``os.environ`` drops the
    isolation variables, so git resolves the global config from ``HOME`` again.
    Same dict passed through :func:`git_env` re-admits them.
    """
    home = _fake_home(tmp_path)
    bypass_env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "XDG_CONFIG_HOME": str(home / ".config"),
    }

    leaked = _write_global_email(bypass_env, "bypass@nwave.invalid")
    assert leaked.returncode == 0, leaked.stderr
    home_config = home / ".gitconfig"
    assert home_config.is_file(), (
        "expected the bypass to be REAL: a literal env= dict must reach the "
        "HOME-resolved config (this is why the session guard exists)"
    )
    after_bypass = home_config.read_bytes()

    with _session_global_config_restored() as session_config:
        protected = _write_global_email(git_env(bypass_env), "protected@nwave.invalid")
        assert protected.returncode == 0, protected.stderr
        written = session_config.read_text(encoding="utf-8") if session_config else ""

    assert home_config.read_bytes() == after_bypass, (
        "git_env() must keep the write out of the HOME-resolved config"
    )
    assert "protected@nwave.invalid" in written


def test_git_env_defaults_to_os_environ_and_applies_overrides_last() -> None:
    """Contract of the helper itself, independent of any subprocess."""
    built = git_env(NWAVE_PROBE="1", GIT_CONFIG_NOSYSTEM="0")

    assert built["NWAVE_PROBE"] == "1"
    assert built["GIT_CONFIG_NOSYSTEM"] == "0", "explicit overrides win"
    assert built["GIT_CONFIG_GLOBAL"] == os.environ["GIT_CONFIG_GLOBAL"]
    assert built["PATH"] == os.environ.get("PATH", built.get("PATH"))


# ---------------------------------------------------------------------------
# Leg 2 — the detection net (pure helpers, exercised on simulated mutations)
# ---------------------------------------------------------------------------


def test_the_guard_is_quiet_when_the_global_config_is_untouched(
    tmp_path: Path,
) -> None:
    config = tmp_path / ".gitconfig"
    config.write_text("[user]\n\temail = real@users.noreply.github.com\n")
    paths = (config, tmp_path / ".config" / "git" / "config")

    before = snapshot_global_gitconfig(paths)

    assert diff_global_gitconfig(before, snapshot_global_gitconfig(paths)) == []


@pytest.mark.parametrize(
    ("mutate", "expected_state"),
    [
        (
            lambda cfg, xdg: cfg.write_text("[user]\n\temail = test@example.com\n"),
            "MODIFIED",
        ),
        (lambda cfg, xdg: cfg.unlink(), "DELETED"),
    ],
)
def test_the_guard_detects_a_simulated_mutation(
    tmp_path: Path, mutate, expected_state: str
) -> None:
    """The exact contamination shape of the incident, simulated on tmp files."""
    config = tmp_path / ".gitconfig"
    config.write_text("[user]\n\temail = real@users.noreply.github.com\n")
    xdg = tmp_path / ".config" / "git" / "config"
    paths = (config, xdg)
    before = snapshot_global_gitconfig(paths)

    mutate(config, xdg)

    violations = diff_global_gitconfig(before, snapshot_global_gitconfig(paths))
    assert violations == [f"{expected_state} {config}"]


def test_the_guard_reports_a_created_config_without_deleting_it(
    tmp_path: Path,
) -> None:
    """CREATED is reported but never restored: the guard owns no prior bytes."""
    config = tmp_path / ".gitconfig"
    paths = (config,)
    before = snapshot_global_gitconfig(paths)

    config.write_text("[user]\n\temail = test@example.com\n")
    violations = diff_global_gitconfig(before, snapshot_global_gitconfig(paths))

    assert violations == [f"CREATED {config}"]
    assert restore_global_gitconfig(before, violations) == []
    assert config.is_file(), "the guard must not delete a file it never snapshotted"


def test_the_guard_restores_the_pre_session_bytes(tmp_path: Path) -> None:
    config = tmp_path / ".gitconfig"
    original = b"[user]\n\temail = real@users.noreply.github.com\n"
    config.write_bytes(original)
    paths = (config,)
    before = snapshot_global_gitconfig(paths)

    config.write_bytes(b"[user]\n\temail = test@example.com\n")
    violations = diff_global_gitconfig(before, snapshot_global_gitconfig(paths))
    restored = restore_global_gitconfig(before, violations)

    assert restored == [str(config)]
    assert config.read_bytes() == original
    assert diff_global_gitconfig(before, snapshot_global_gitconfig(paths)) == []
