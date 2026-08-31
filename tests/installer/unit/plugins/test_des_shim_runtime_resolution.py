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

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.install.plugins.base import InstallContext
from scripts.install.plugins.des_plugin import DESPlugin
from scripts.shared.install_paths import (
    active_runtime_pointer_path,
    host_neutral_runtime_dir,
)
from scripts.shared.version import VersionResolutionError, get_version


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
    def test_agents_home_override_selects_the_isolated_pointer(
        self, tmp_path: Path, shim_name: str
    ) -> None:
        operator_home = tmp_path / "operator-home"
        isolated_home = tmp_path / "verification-home"
        _seed_runtime(operator_home / ".nwave" / "runtime", "RUNTIME=OPERATOR")
        isolated = isolated_home / ".nwave" / "runtime"
        _seed_runtime(isolated, "RUNTIME=ISOLATED")
        (isolated_home / ".nwave" / "active-runtime").write_text(
            isolated.as_posix() + "\n"
        )

        result = _run_shim(
            shim_name,
            operator_home,
            extra_env={"NWAVE_AGENTS_HOME": str(isolated_home)},
        )

        assert result.returncode == 0, result.stderr
        assert "RUNTIME=ISOLATED" in result.stdout

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


class TestPrebuiltProvenanceCheck:
    """ADR-PLAT-011 -- `_install_des_module` checks the pre-built module's
    provenance before trusting it over live source.

    The producer selection used to be a directory-existence check only, so a
    pre-built tree built from a different revision could be installed silently.
    The fix is a provenance check, NOT a preference inversion: dist-first stays,
    because on the release-tarball channel the pre-built tree is the only module
    source that exists at all.
    """

    @staticmethod
    def _prebuilt_source(root: Path, stamped_version: str) -> Path:
        """A minimal dist/-shaped framework_source: MANIFEST.json + module."""
        des = root / "lib" / "python" / "des"
        des.mkdir(parents=True)
        (des / "__init__.py").write_text("MARKER = 'PREBUILT'\n")
        (root / "MANIFEST.json").write_text(
            json.dumps({"version": stamped_version, "built_at": "2026-07-26T00:00Z"})
        )
        return root

    @staticmethod
    def _context(home: Path, framework_source: Path | None) -> InstallContext:
        return InstallContext(
            claude_dir=home / ".claude",
            scripts_dir=home / ".claude" / "scripts",
            templates_dir=home / ".claude" / "templates",
            logger=MagicMock(),
            project_root=REPO_ROOT,
            framework_source=framework_source,
            target_platforms={"claude_code"},
        )

    def test_prebuilt_accepted_when_stamp_matches_version_ssot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Counter-proof: the release channel keeps working unchanged."""
        monkeypatch.setenv("HOME", str(tmp_path))
        source = self._prebuilt_source(tmp_path / "dist", get_version(REPO_ROOT))

        result = DESPlugin()._install_des_module(self._context(tmp_path, source))

        assert result.success, result.message
        installed = tmp_path / ".claude" / "lib" / "python" / "des" / "__init__.py"
        assert "PREBUILT" in installed.read_text()

    def test_prebuilt_refused_loud_when_stamp_diverges_from_version_ssot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The defect class: a divergent stamp used to install silently."""
        monkeypatch.setenv("HOME", str(tmp_path))
        ssot = get_version(REPO_ROOT)
        source = self._prebuilt_source(tmp_path / "dist", "3.9.9-STALE")

        result = DESPlugin()._install_des_module(self._context(tmp_path, source))

        assert not result.success
        # Names BOTH versions -- the reader must not have to go find either.
        assert "3.9.9-STALE" in result.message
        assert ssot in result.message
        assert "WHAT:" in result.message
        assert "WHY:" in result.message
        assert "HOW:" in result.message
        assert "build_dist.py" in result.message
        # A refusal installs nothing: no half-written stale module is left.
        assert not (tmp_path / ".claude" / "lib" / "python" / "des").exists()

    def test_prebuilt_refuses_before_write_when_identity_is_unresolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        source = self._prebuilt_source(tmp_path / "dist", "4.0.1")
        unresolved = VersionResolutionError(
            "WHAT: product identity could not be resolved\n"
            "WHY: no valid source identity exists\n"
            "HOW: restore the owning project metadata"
        )

        with patch(
            "scripts.install.plugins.des_plugin.get_version",
            side_effect=unresolved,
        ):
            result = DESPlugin()._install_des_module(self._context(tmp_path, source))

        assert not result.success
        assert "WHAT:" in result.message
        assert "WHY:" in result.message
        assert "HOW:" in result.message
        assert "identity" in result.message.lower()
        assert not (tmp_path / ".claude" / "lib" / "python" / "des").exists()

    def test_dev_checkout_path_is_unaffected_by_the_provenance_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`nWave/` carries no pre-built module, so the gate never fires there
        and live `src/des` still wins -- the empirical fact ADR-PLAT-011 rests
        on when it keeps dist-first instead of inverting the preference."""
        monkeypatch.setenv("HOME", str(tmp_path))
        framework_source = REPO_ROOT / "nWave"
        assert not (framework_source / "lib" / "python" / "des").exists()

        result = DESPlugin()._install_des_module(
            self._context(tmp_path, framework_source)
        )

        assert result.success, result.message
        installed = tmp_path / ".claude" / "lib" / "python" / "des"
        assert (installed / "__init__.py").is_file()
        assert "MARKER = 'PREBUILT'" not in (installed / "__init__.py").read_text()
