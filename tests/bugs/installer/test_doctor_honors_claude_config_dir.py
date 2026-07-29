"""Regression: `nwave-ai doctor` must diagnose the ACTIVE profile, not always
`~/.claude`, and two check remediations must name the resolved path.

Defect 4 (audit AUDIT-installer.md addendum, CRITICO): `DoctorContext.
__post_init__` always set `claude_dir = home_dir / ".claude"`, ignoring both
`CLAUDE_CONFIG_DIR` and `--target` (`_handle_doctor` never called
`_extract_target_flag`, unlike `_handle_install`/`_handle_uninstall`). On a
multi-profile machine (this repo's own documented claude/claude2/claude3
setup), or after `nwave-ai install --target <path>`, doctor silently
diagnosed the WRONG installation -- false FAIL and false PASS, with no
warning. Same bug class as defect 2 (install_des_hooks.py) and defect 3
(attribution CLI): deciding on a fixed DESIGNATION instead of the active
PROPERTY (GDP-8).

Fix: `DoctorContext` resolves `claude_dir` via
`PathUtils.get_claude_config_dir()` (honors `CLAUDE_CONFIG_DIR`) when
`home_dir` is not explicitly overridden -- but an explicit `home_dir=...`
(the pattern every doctor check test uses for hermetic isolation, e.g.
`DoctorContext(home_dir=tmp_path)`) still wins, deriving `claude_dir` from
it, never the env var. `_handle_doctor` now also consumes `--target` via the
same `_extract_target_flag` seam install/uninstall/attribution already use.

Defects 5 and 6 (audit addendum, ALTA, closed in the same pass per the
audit's instruction -- "sanare il 4 senza il 5 e il 6 li trasforma da
innocui in attivamente sbagliati"): two doctor check remediations hardcoded
the literal string `~/.claude/...` instead of interpolating the already-
resolved path variable sitting a few lines away in the SAME function
(`path_env.py`'s ENV_PATH_MISSING branch; `des_module.py`'s remediation).
Both were "correct by coincidence" only because defect 4 made claude_dir
always equal ~/.claude in practice -- fixing 4 alone would have made them
actively wrong (pointing a diagnosed-elsewhere user back at ~/.claude).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from nwave_ai.doctor.checks.des_module import DesModuleCheck
from nwave_ai.doctor.checks.path_env import PathEnvCheck
from nwave_ai.doctor.context import DoctorContext

from nwave_ai import cli


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure CLAUDE_CONFIG_DIR is not leaked into the test from the host env."""
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


class TestDoctorContextHonorsClaudeConfigDir:
    """Defect 4a: DoctorContext.claude_dir resolution."""

    def test_default_context_honors_claude_config_dir_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No explicit home_dir + CLAUDE_CONFIG_DIR set -> claude_dir targets
        the env-var profile, not home_dir/.claude."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        active_profile = tmp_path / "claude-alt3"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(active_profile))

        context = DoctorContext.from_defaults()

        assert context.claude_dir == active_profile
        assert context.claude_dir != home / ".claude"
        assert context.settings_path == active_profile / "settings.json"

    def test_default_context_falls_back_to_home_claude_without_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No override, no CLAUDE_CONFIG_DIR -> unchanged legacy default."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        context = DoctorContext.from_defaults()

        assert context.claude_dir == home / ".claude"

    def test_explicit_home_dir_override_still_wins_over_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Explicit home_dir=... (the hermetic-test pattern used across every
        doctor check test) must still derive claude_dir from it, NEVER the
        env var -- or every DoctorContext(home_dir=tmp_path) test would leak
        into the real ~/.claude on a machine with CLAUDE_CONFIG_DIR set."""
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "should-not-be-used"))
        custom_home = tmp_path / "sandbox-home"

        context = DoctorContext(home_dir=custom_home)

        assert context.claude_dir == custom_home / ".claude"
        assert context.settings_path == custom_home / ".claude" / "settings.json"


class TestDoctorCliHonorsTargetFlag:
    """Defect 4b: `nwave-ai doctor --target <path>` / CLAUDE_CONFIG_DIR."""

    def test_target_flag_diagnoses_target_not_home_claude(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        target.mkdir()
        (target / "settings.json").write_text(
            json.dumps({"env": {"PATH": f"{target / 'bin'}"}}), encoding="utf-8"
        )

        with patch("sys.argv", ["nwave-ai", "doctor", "--target", str(target)]):
            cli.main()

        captured = capsys.readouterr()
        # The diagnosis ran against the target profile's bin path, not home's.
        assert str(target / "bin") in captured.out
        assert str(home / ".claude" / "bin") not in captured.out

    def test_omitting_target_defaults_to_home_claude(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        home = tmp_path / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "settings.json").write_text(
            json.dumps({"env": {"PATH": f"{home / '.claude' / 'bin'}"}}),
            encoding="utf-8",
        )
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        with patch("sys.argv", ["nwave-ai", "doctor"]):
            cli.main()

        captured = capsys.readouterr()
        assert str(home / ".claude" / "bin") in captured.out

    def test_target_does_not_leak_into_subsequent_default_invocation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--target sets CLAUDE_CONFIG_DIR for the process (documented, same
        as install/uninstall/attribution) -- verify the flag round-trips
        through os.environ exactly like the sibling subcommands' contract."""
        target = tmp_path / "target-profile"

        with patch("sys.argv", ["nwave-ai", "doctor", "--target", str(target)]):
            cli.main()

        assert os.environ.get("CLAUDE_CONFIG_DIR") == str(target.resolve())


class TestPathEnvRemediationUsesResolvedPath:
    """Defect 5: path_env.py ENV_PATH_MISSING remediation."""

    def test_missing_path_key_remediation_names_resolved_bin(
        self, tmp_path: Path
    ) -> None:
        context = DoctorContext(home_dir=tmp_path)
        context.claude_dir.mkdir(parents=True, exist_ok=True)
        context.settings_path.write_text(json.dumps({}), encoding="utf-8")

        result = PathEnvCheck().run(context)

        assert result.passed is False
        expected_bin = str(context.claude_dir / "bin")
        assert expected_bin in result.remediation
        assert "~/.claude/bin" not in result.remediation


class TestDesModuleRemediationUsesResolvedPath:
    """Defect 6: des_module.py DES_MODULE_MISSING remediation."""

    def test_missing_module_remediation_names_resolved_lib_python(
        self, tmp_path: Path
    ) -> None:
        context = DoctorContext(home_dir=tmp_path)

        result = DesModuleCheck().run(context)

        assert result.passed is False
        expected = str(context.claude_dir / "lib" / "python" / "des")
        assert expected in result.remediation
        assert "~/.claude/lib/python/des/" not in result.remediation
