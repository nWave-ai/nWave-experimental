"""The installed des shims must bind the runtime of the MOST RECENT install.

Defect (SF friction 2026-08-21, install d1efa9062): after
`install --platform codex` the launcher on PATH kept importing the
Claude-scoped runtime (`~/.claude/lib/python`) instead of the host-neutral
runtime the install had just populated (`~/.nwave/runtime`) -- "codex
manifest green but launcher claude". Root cause: the shim hardcoded the
Claude location, and a non-Claude install returns before
`_install_des_shims` ever runs, so nothing on PATH could learn about the
new runtime.

Representation fix under test:
- `record_active_runtime` (scripts/shared/install_paths.py) is written by
  `DESPlugin._install_des_module` on EVERY non-dry-run install with the
  primary runtime python dir -- last install wins, deterministically.
- The des / des-commit shims resolve their runtime in a documented order:
  $NWAVE_RUNTIME env > active-runtime pointer (validated to still contain
  a des package) > Claude default (CLAUDE_CONFIG_DIR else ~/.claude) >
  host-neutral fallback -- and `des --help` declares the resolved dir and
  the rule that chose it (never a silent choice on a dual-host box).

The shim tests execute the REAL shim sources (nWave/scripts/des/) as
subprocesses against sentinel runtimes in an isolated HOME, mirroring the
subprocess pattern of TestInstalledShimResolvesRuntimeViaClaudeConfigDir.
"""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.shared.install_paths import (
    active_runtime_pointer_path,
    host_neutral_runtime_dir,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
SHIM_NAMES = ("des", "des-commit")


def _seed_runtime(runtime_dir: Path, marker: str) -> None:
    """Create a sentinel des package satisfying both shims' entry points."""
    cli = runtime_dir / "des" / "cli"
    cli.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "des" / "__init__.py").write_text("")
    (cli / "__init__.py").write_text("")
    body = f'def main():\n    print("{marker}")\n    return 0\n'
    (cli / "__main__.py").write_text(body)
    (cli / "commit.py").write_text(body)


def _run_shim(
    shim_name: str,
    home: Path,
    extra_env: dict[str, str] | None = None,
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": "/usr/bin:/bin"}
    if extra_env:
        env.update(extra_env)
    shim = REPO_ROOT / "nWave" / "scripts" / "des" / shim_name
    return subprocess.run(
        [sys.executable, str(shim), *args],
        capture_output=True,
        text=True,
        env=env,
    )


class TestShimRuntimeResolution:
    """Resolution order of the shims, exercised end-to-end as subprocesses."""

    @pytest.mark.parametrize("shim_name", SHIM_NAMES)
    def test_pointer_overrides_claude_default(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        """The falsifier: both runtimes exist, the pointer names the
        host-neutral one (as a codex-only install just recorded) -- the shim
        must run the host-neutral runtime, not the stale Claude one."""
        _seed_runtime(tmp_path / ".claude" / "lib" / "python", "RUNTIME=CLAUDE")
        neutral = tmp_path / ".nwave" / "runtime"
        _seed_runtime(neutral, "RUNTIME=NEUTRAL")
        (tmp_path / ".nwave" / "active-runtime").write_text(neutral.as_posix() + "\n")

        result = _run_shim(shim_name, tmp_path)

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=NEUTRAL" in result.stdout, (
            f"{shim_name} ignored the active-runtime pointer and bound "
            f"another runtime. stdout: {result.stdout!r}"
        )

    @pytest.mark.parametrize("shim_name", SHIM_NAMES)
    def test_nwave_runtime_env_overrides_pointer(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        _seed_runtime(tmp_path / ".claude" / "lib" / "python", "RUNTIME=CLAUDE")
        neutral = tmp_path / ".nwave" / "runtime"
        _seed_runtime(neutral, "RUNTIME=NEUTRAL")
        (tmp_path / ".nwave" / "active-runtime").write_text(neutral.as_posix() + "\n")
        explicit = tmp_path / "explicit-runtime"
        _seed_runtime(explicit, "RUNTIME=EXPLICIT")

        result = _run_shim(
            shim_name, tmp_path, extra_env={"NWAVE_RUNTIME": str(explicit)}
        )

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=EXPLICIT" in result.stdout

    @pytest.mark.parametrize("shim_name", SHIM_NAMES)
    def test_no_pointer_keeps_claude_default(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        """Back-compat: absent pointer (pre-fix installs), the Claude
        location keeps answering exactly as before."""
        _seed_runtime(tmp_path / ".claude" / "lib" / "python", "RUNTIME=CLAUDE")
        _seed_runtime(tmp_path / ".nwave" / "runtime", "RUNTIME=NEUTRAL")

        result = _run_shim(shim_name, tmp_path)

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=CLAUDE" in result.stdout

    @pytest.mark.parametrize("shim_name", SHIM_NAMES)
    def test_stale_pointer_falls_back_to_claude(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        """A pointer whose dir lost its des package (uninstall) is inert."""
        _seed_runtime(tmp_path / ".claude" / "lib" / "python", "RUNTIME=CLAUDE")
        gone = tmp_path / "removed-runtime"
        gone.mkdir()
        (tmp_path / ".nwave").mkdir()
        (tmp_path / ".nwave" / "active-runtime").write_text(gone.as_posix() + "\n")

        result = _run_shim(shim_name, tmp_path)

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=CLAUDE" in result.stdout

    @pytest.mark.parametrize("shim_name", SHIM_NAMES)
    def test_neutral_fallback_when_claude_runtime_absent(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        """Clean non-Claude box, no pointer: the host-neutral runtime is
        found instead of a dead ImportError against ~/.claude."""
        _seed_runtime(tmp_path / ".nwave" / "runtime", "RUNTIME=NEUTRAL")

        result = _run_shim(shim_name, tmp_path)

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=NEUTRAL" in result.stdout

    def test_help_declares_resolved_runtime(self, tmp_path: Path) -> None:
        """Dual-host box: the choice is declared, never silent --
        `des --help` names the resolved dir and the rule that chose it."""
        _seed_runtime(tmp_path / ".claude" / "lib" / "python", "RUNTIME=CLAUDE")
        neutral = tmp_path / ".nwave" / "runtime"
        _seed_runtime(neutral, "RUNTIME=NEUTRAL")
        (tmp_path / ".nwave" / "active-runtime").write_text(neutral.as_posix() + "\n")

        result = _run_shim("des", tmp_path, args=("--help",))

        assert result.returncode == 0, result.stderr
        assert "nwave runtime:" in result.stderr
        assert neutral.as_posix() in result.stderr
        assert "active-runtime pointer" in result.stderr


class TestInstallRecordsActiveRuntime:
    """Every module install re-points the shims at the runtime it wrote."""

    def _context(self, claude_dir: Path, platforms: set[str]) -> InstallContext:
        return InstallContext(
            claude_dir=claude_dir,
            scripts_dir=claude_dir / "scripts",
            templates_dir=claude_dir / "templates",
            logger=MagicMock(),
            project_root=REPO_ROOT,
            framework_source=REPO_ROOT / "nWave",
            target_platforms=platforms,
        )

    def test_codex_only_install_records_neutral_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The install that used to go green while the launcher stayed
        Claude-bound now records the host-neutral runtime it populated."""
        monkeypatch.setenv("HOME", str(tmp_path))

        result = DESPlugin()._install_des_module(
            self._context(tmp_path / ".claude", {"codex"})
        )

        assert result.success, result.message
        pointer = active_runtime_pointer_path()
        assert pointer.read_text().strip() == host_neutral_runtime_dir().as_posix()

    def test_claude_install_records_claude_runtime(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        claude_dir = tmp_path / ".claude"

        result = DESPlugin()._install_des_module(
            self._context(claude_dir, {"claude_code"})
        )

        assert result.success, result.message
        pointer = active_runtime_pointer_path()
        assert pointer.read_text().strip() == (claude_dir / "lib" / "python").as_posix()
