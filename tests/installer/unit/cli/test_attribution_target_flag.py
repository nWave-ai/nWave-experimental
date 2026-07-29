"""Unit tests for `--target <path>` / `CLAUDE_CONFIG_DIR` on
`nwave-ai attribution on|off`.

Defect (audit AUDIT-installer.md #3, MEDIA): `_handle_attribution` always
registered/removed the commit-attribution hook in `Path.home() / ".claude"`,
ignoring both `CLAUDE_CONFIG_DIR` and `--target` -- unlike `_handle_install`
and `_handle_uninstall`, which both document and honor `--target` (ADR-001).
The success/failure message also never named which settings.json was
touched, even though the resolved path was already in scope
(`register_attribution_hook` receives it as a parameter).

On a multi-profile machine (this repo's own documented claude/claude2/claude3
setup) the toggle could appear to succeed while registering the hook in the
wrong profile, or in none.

Fix: `_handle_attribution` now consumes `--target` via the same
`_extract_target_flag` seam as install/uninstall, resolves `claude_dir` via
`PathUtils.get_claude_config_dir()` (honors `CLAUDE_CONFIG_DIR`), and names
that directory in both the "on" and "off" messages.

Mirrors tests/installer/unit/cli/test_target_flag.py (install/uninstall).
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nwave_ai import cli


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure CLAUDE_CONFIG_DIR is not leaked into the test from the host env."""
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


def _hook_registered(claude_dir: Path) -> bool:
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return False
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = (settings.get("hooks") or {}).get("PreToolUse") or []
    return any(
        entry.get("matcher") == "Bash"
        and any(
            "pre-commit-attribution" in (hook.get("command") or "")
            for hook in entry.get("hooks") or []
        )
        for entry in entries
    )


class TestAttributionOnTargetFlag:
    def test_target_registers_hook_in_target_not_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        nwave_dir = tmp_path / ".nwave"

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "on"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        assert _hook_registered(target) is True
        assert _hook_registered(home_claude) is False

    def test_target_is_named_in_success_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        nwave_dir = tmp_path / ".nwave"

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "on"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            cli.main()

        captured = capsys.readouterr()
        assert str(target.resolve()) in captured.out

    def test_omitting_target_defaults_to_home_claude(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        nwave_dir = tmp_path / ".nwave"

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        assert _hook_registered(home_claude) is True


class TestAttributionOffTargetFlag:
    def test_target_removes_hook_from_target_not_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        target.mkdir()
        nwave_dir = tmp_path / ".nwave"

        # Seed the hook into the TARGET (simulating a prior 'on --target').
        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "on"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            cli.main()
        assert _hook_registered(target) is True

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "off"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        assert _hook_registered(target) is False

    def test_target_is_named_in_disabled_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        nwave_dir = tmp_path / ".nwave"

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "off"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            cli.main()

        captured = capsys.readouterr()
        assert str(target.resolve()) in captured.out


class TestAttributionClaudeConfigDirEnv:
    def test_claude_config_dir_env_is_honored_without_target_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLAUDE_CONFIG_DIR set (no --target) routes the hook there too --
        install/uninstall already honor this env var; attribution must match."""
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        profile = tmp_path / "claude-alt-profile"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(profile))
        nwave_dir = tmp_path / ".nwave"

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        assert _hook_registered(profile) is True
        assert _hook_registered(home_claude) is False
