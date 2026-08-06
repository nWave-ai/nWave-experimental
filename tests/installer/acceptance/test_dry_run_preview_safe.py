"""Regression acceptance test for `install_nwave.py --dry-run` safety.

Bug: `nwave-ai install --dry-run` exits non-zero with
"DES config not found: .nwave/des-config.json". Affects all releases
>= v1.1.14 (~3 months shipped broken). RCA at
docs/feature/fix-dry-run-des-verifier/discuss/wave-decisions.md.

Driving port: install_nwave.py CLI invoked as a real subprocess.
Driven port boundaries asserted: process exit code, fake-root filesystem state,
~/.claude/lib/ mtime preservation.

Layer: acceptance (WS subset — real subprocess composition root, ~1-3s).
Universe: subprocess exit code + fake_root/.nwave/ existence + claude lib mtime.

Reproduction strategy: the installer derives ``project_root`` from
``script_path.parent.parent.parent`` (``install_utils.PathUtils.get_project_root``).
To reproduce the production failure mode (no pre-existing ``.nwave/des-config.json``
in the resolved project root), this test stages a symlinked copy of the
installer scripts into ``tmp_path/scripts/install/`` so that the installer's
project_root resolves to ``tmp_path`` (which has no ``.nwave/``) — exactly the
condition end users hit when running ``nwave-ai install --dry-run`` from a
fresh checkout.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.common.in_process_cli import run_python_snippet_in_process


REPO_ROOT = Path(__file__).resolve().parents[3]
REAL_INSTALLER = REPO_ROOT / "scripts" / "install" / "install_nwave.py"


def _stage_installer_in_fake_root(tmp_path: Path) -> Path:
    """Stage installer scripts in a fake project root with no .nwave/.

    Returns the path to install_nwave.py inside the fake root. The fake root
    is tmp_path; the script resolves project_root to tmp_path (which has no
    .nwave/ — production-failure condition).

    Strategy: symlink the entire scripts/ and nWave/ trees so the installer
    can resolve all its imports and source assets, while the project_root
    differs from the real dev repo.
    """
    # Symlink scripts/ — install_nwave.py uses its parent.parent.parent
    # path as project_root, so script_path.parent.parent.parent == tmp_path
    (tmp_path / "scripts").symlink_to(REPO_ROOT / "scripts")
    # Symlink nWave/ — agents/skills/templates source assets
    (tmp_path / "nWave").symlink_to(REPO_ROOT / "nWave")
    # Symlink dist/ if present — alternate source layout
    dist_dir = REPO_ROOT / "dist"
    if dist_dir.exists():
        (tmp_path / "dist").symlink_to(dist_dir)
    # Symlink pyproject.toml — version reads
    (tmp_path / "pyproject.toml").symlink_to(REPO_ROOT / "pyproject.toml")
    return tmp_path / "scripts" / "install" / "install_nwave.py"


@pytest.mark.acceptance
def test_dry_run_preview_is_side_effect_free_and_exits_zero(tmp_path):
    """Property: --dry-run produces no side effects and exits 0.

    Universe (observable surface):
      - subprocess.returncode
      - {tmp_path}/.nwave/ existence (must remain absent)
      - {fake_home}/.claude/ existence (must NOT be created by dry-run)

    Expected delta:
      - returncode: set_to(0)
      - tmp_path/.nwave/: unchanged (absent before and after)
      - fake_home/.claude/: unchanged (absent before and after)

    Hermetic isolation: HOME env is overridden to point at a tmp-controlled
    fake home; the real dev-machine ~/.claude is never touched or read.

    In-process drive: the staged installer script is executed in-process via
    ``run_python_snippet_in_process`` (program = the staged script source,
    ``__file__`` = the staged path) instead of forking a fresh interpreter. The
    installer self-locates ``project_root`` from the UNRESOLVED
    ``Path(__file__).parent.parent.parent`` (``install_nwave.py:266`` →
    ``PathUtils.get_project_root``), so passing ``filename`` = the staged
    ``tmp_path/scripts/install/install_nwave.py`` faithfully reproduces the
    production-failure self-location (``project_root`` == tmp_path, no
    ``.nwave/``) the subprocess imposed — while the swapped ``os.environ``
    (isolated ``HOME``) + ``cwd`` keep the exact hermetic isolation. The
    ``--dry-run`` exit semantics (``SystemExit`` → code; any other escape →
    code 1 + traceback to captured stderr) match the forked interpreter.
    """
    # GIVEN: fake project root with no .nwave/ (production-failure condition)
    fake_installer = _stage_installer_in_fake_root(tmp_path)
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    assert not (tmp_path / ".nwave").exists(), "precondition: fake root is clean"
    assert not (fake_home / ".claude").exists(), "precondition: fake home is clean"

    # WHEN: invoke installer with --dry-run in-process (HOME isolated, staged
    # __file__ so project_root self-locates to the fake root)
    sandboxed_env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME")
    }
    sandboxed_env["HOME"] = str(fake_home)
    sandboxed_env["PYTHONDONTWRITEBYTECODE"] = "1"
    # An explicit --platform, because the property under test is dry-run SAFETY,
    # not host discovery. The sandbox above isolates only the HOME family, so two
    # independent detection signal families survive it on a developer box -- host
    # binaries on PATH, and CLAUDE_CONFIG_DIR -- while a CI runner has neither.
    # Auto-detection then returns an empty set, the installer correctly refuses
    # before any mutation (exit 2), and this test read that correct refusal as a
    # dry-run defect. Naming the platform makes the test independent of ambient
    # host presence; the no-host fail-before-mutation behaviour is a separate
    # property with its own coverage and is deliberately not asserted here.
    returncode, stdout, stderr = run_python_snippet_in_process(
        fake_installer.read_text(encoding="utf-8"),
        cwd=str(tmp_path),
        env=sandboxed_env,
        argv=[str(fake_installer), "--dry-run", "--platform", "claude-code"],
        filename=str(fake_installer),
    )

    # THEN: exit 0
    assert returncode == 0, (
        f"--dry-run must exit 0, got {returncode}.\n"
        f"stdout tail:\n{chr(10).join(stdout.splitlines()[-30:])}\n"
        f"stderr tail:\n{chr(10).join(stderr.splitlines()[-30:])}"
    )

    # AND: no .nwave/ side effect in fake root
    assert not (tmp_path / ".nwave").exists(), (
        f"--dry-run must not create .nwave/ in project root, but found: "
        f"{list((tmp_path / '.nwave').iterdir()) if (tmp_path / '.nwave').exists() else 'N/A'}"
    )

    # AND: fake_home/.claude/ never created (no real install touched HOME)
    assert not (fake_home / ".claude").exists(), (
        "--dry-run must not write under HOME, but found: "
        f"{list((fake_home / '.claude').iterdir())}"
    )
