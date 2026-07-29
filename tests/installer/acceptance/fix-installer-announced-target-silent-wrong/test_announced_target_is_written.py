"""The installer must never announce a Claude target it does not write into.

Probed 2026-07-29, three independent surfaces (in-process with a patched
``PathUtils``, in-process with a real ``CLAUDE_CONFIG_DIR``, and a bare
subprocess): ``install_nwave.py`` prints ``Installing nWave -> <dir>``, exits
0 and declares "installed and healthy" while ``<dir>`` stays EMPTY.

Root cause: ``PathUtils.get_claude_config_dir()`` honors ``CLAUDE_CONFIG_DIR``
(``scripts/install/install_utils.py``), but ``context_detector`` decided
whether Claude Code is a target from a hardcoded home-relative config path.
With ``CLAUDE_CONFIG_DIR`` set -- the documented multi-profile setup -- and no
``~/.claude``, the writer and the detector disagree: the target is announced,
never registered, never written, and the run still reports success.

That is a silent-wrong (GDP-6: degrade LOUD, never silently) reached by
deciding on the DESIGNATION ``~/.claude`` instead of on the PROPERTY "the
Claude config directory this installer resolves to exists" (GDP-8).

These tests close on the PROPERTY -- what is on disk under the path the
installer itself announced -- not on the shape of any internal call.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]
INSTALLER = REPO_ROOT / "scripts" / "install" / "install_nwave.py"

ANNOUNCED_TARGET = re.compile(r"Installing nWave\s*(?:->|→)\s*(\S+)")

# Host env vars the installer resolves against. Every one is redirected into
# the test's temp tree: an installer test that writes into the developer's real
# home is a defect of the suite regardless of the colour it produces.
_ISOLATED_HOST_VARS = (
    "HOME",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
    "NWAVE_AGENTS_HOME",
    "OPENCODE_CONFIG_DIR",
)


def _announced_target(stdout: str) -> str | None:
    """The filesystem directory the installer told the user it was installing to.

    The announcement may legitimately name hosts rather than a path ("codex,
    opencode"); only a path is a promise about a location on disk, so only a
    path is what these tests hold the installer to.
    """
    match = ANNOUNCED_TARGET.search(stdout)
    if match is None:
        return None
    announced = match.group(1)
    return announced if announced.startswith(os.sep) else None


def _run_installer(root: Path, *, claude_config_dir: Path | None) -> tuple[int, str]:
    """Run the installer as a subprocess with every host path inside ``root``.

    ``claude_config_dir`` None means "no Claude Code on this machine": neither
    ``CLAUDE_CONFIG_DIR`` nor ``$HOME/.claude`` nor ``CLAUDE_CODE`` is present.
    """
    env = dict(os.environ)
    for var in _ISOLATED_HOST_VARS:
        env.pop(var, None)
    env.pop("CLAUDE_CODE", None)

    env["HOME"] = str(root / "home")
    env["CODEX_HOME"] = str(root / "codex")
    env["NWAVE_AGENTS_HOME"] = str(root / "agents")
    env["OPENCODE_CONFIG_DIR"] = str(root / "opencode")
    if claude_config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = str(claude_config_dir)

    for path in (root / "home", root / "codex", root / "agents", root / "opencode"):
        path.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [sys.executable, str(INSTALLER)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=900,
    )
    return completed.returncode, completed.stdout + completed.stderr


@pytest.fixture(scope="module")
def install_into_configured_dir(tmp_path_factory) -> tuple[int, str, Path]:
    """Given CLAUDE_CONFIG_DIR points at an existing directory and ~/.claude does not exist."""
    root = tmp_path_factory.mktemp("configured_claude_dir")
    claude_dir = root / "claude-alt"
    claude_dir.mkdir()
    exit_code, output = _run_installer(root, claude_config_dir=claude_dir)
    return exit_code, output, claude_dir


@pytest.fixture(scope="module")
def install_without_any_claude(tmp_path_factory) -> tuple[int, str]:
    """Given no Claude Code surface exists at all on the machine."""
    root = tmp_path_factory.mktemp("no_claude_at_all")
    exit_code, output = _run_installer(root, claude_config_dir=None)
    return exit_code, output


def test_installer_never_reports_success_when_the_announced_target_stays_empty(
    install_into_configured_dir,
) -> None:
    """When the installer announces a target and exits 0, that target holds files.

    The property, not the routine: whatever path the user was told about must
    exist on disk with content once the run reports success.
    """
    exit_code, output, _claude_dir = install_into_configured_dir
    announced = _announced_target(output)

    assert announced is not None, (
        "the installer announced no target at all; expected a Claude directory\n"
        f"--- installer output ---\n{output[-3000:]}"
    )
    if exit_code != 0:
        pytest.skip("installation failed loudly; the silent-wrong class is not reached")

    entries = sorted(p.name for p in Path(announced).iterdir())
    assert entries, (
        f"the installer announced {announced!r}, exited 0 and declared success, "
        "but that directory is EMPTY -- the declared fact and the disk diverge\n"
        f"--- installer output ---\n{output[-3000:]}"
    )


def test_configured_claude_config_dir_receives_agents_and_skills(
    install_into_configured_dir,
) -> None:
    """A CLAUDE_CONFIG_DIR install populates the discovery surfaces Claude reads."""
    exit_code, output, claude_dir = install_into_configured_dir

    assert exit_code == 0, f"installer exited {exit_code}\n{output[-3000:]}"
    assert (claude_dir / "agents" / "nw").is_dir(), (
        f"no agents installed under {claude_dir}\n{output[-3000:]}"
    )
    assert (claude_dir / "skills").is_dir(), (
        f"no skills installed under {claude_dir}\n{output[-3000:]}"
    )


def test_installer_does_not_announce_a_claude_target_it_will_not_write_to(
    install_without_any_claude,
) -> None:
    """With no Claude surface anywhere, the run must not name a Claude directory.

    Announcing a path the run will never touch is the silent-wrong in its
    purest form: the user reads a location, restarts Claude Code as the closing
    line instructs, and finds nothing there.
    """
    _exit_code, output = install_without_any_claude
    announced = _announced_target(output)

    assert announced is None, (
        f"the installer announced {announced!r} on a machine with no Claude Code "
        "surface; it never writes there\n"
        f"--- installer output ---\n{output[-3000:]}"
    )


def test_detection_honors_the_configured_claude_config_dir(
    tmp_path, monkeypatch
) -> None:
    """CLAUDE_CONFIG_DIR is where Claude lives; detection must resolve it the same way."""
    from scripts.install.context_detector import TargetPlatform, detect_target_platforms

    claude_dir = tmp_path / "claude-alt"
    claude_dir.mkdir()
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))
    monkeypatch.delenv("CLAUDE_CODE", raising=False)

    assert TargetPlatform.CLAUDE_CODE in detect_target_platforms()


def test_detection_never_claims_claude_when_no_configured_directory_exists(
    tmp_path, monkeypatch
) -> None:
    """A CLAUDE_CONFIG_DIR that does not exist is not a Claude installation."""
    from scripts.install.context_detector import _detect_claude_code

    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "absent"))
    monkeypatch.delenv("CLAUDE_CODE", raising=False)

    assert _detect_claude_code() is False
