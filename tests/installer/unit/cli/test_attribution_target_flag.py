"""Unit tests for `--target <path>` / `CLAUDE_CONFIG_DIR` on
`nwave-ai attribution on|off`.

Defect (audit AUDIT-installer.md #3, MEDIA): `_handle_attribution` always
routed cleanup through `Path.home() / ".claude"`, ignoring both `CLAUDE_CONFIG_DIR`
and `--target` (ADR-001). The success/failure message also never named which
settings.json was touched.

On a multi-profile machine (this repo's own documented claude/claude2/claude3
setup) the toggle could appear to succeed while cleaning the wrong profile.

Fix: `_handle_attribution` now consumes `--target` via the same
`_extract_target_flag` seam as install/uninstall, resolves `claude_dir` via
`PathUtils.get_claude_config_dir()` (honors `CLAUDE_CONFIG_DIR`), and names
that directory in the messages.

Load-bearing contract: --target and CLAUDE_CONFIG_DIR route exact stale
cleanup (legacy PreToolUse hook removal) to the target, leaving default
~/.claude untouched.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from nwave_ai import cli
from scripts.install.attribution_utils import _attribution_hook_command


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure CLAUDE_CONFIG_DIR is not leaked into the test from the host env."""
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


def _stale_attribution_hook_present(claude_dir: Path) -> bool:
    """Check if stale independent attribution hook entry is in PreToolUse."""
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return False
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = (settings.get("hooks") or {}).get("PreToolUse") or []
    return any(
        "# des-hook:pre-commit-attribution" in (hook.get("command") or "")
        for entry in entries
        if isinstance(entry, dict)
        for hook in entry.get("hooks") or []
        if isinstance(hook, dict)
    )


def _seed_stale_attribution_hook(claude_dir: Path) -> None:
    """Seed the exact historical stale attribution hook into settings.json."""
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    stale_command = _attribution_hook_command(claude_dir)
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": stale_command}],
                }
            ]
        }
    }
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")


class TestAttributionOnTargetFlag:
    def test_target_cleans_stale_hook_in_target_not_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """on --target cleans stale hook from target, leaves home untouched."""
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        nwave_dir = tmp_path / ".nwave"

        # Seed stale hook into target
        _seed_stale_attribution_hook(target)
        assert _stale_attribution_hook_present(target) is True

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "on"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        # Stale hook cleaned from target
        assert _stale_attribution_hook_present(target) is False
        # Home untouched (no spurious cleanup)
        assert not (home_claude / "settings.json").exists()

    def test_target_is_named_in_success_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """on --target names the target in output."""
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
        """on without --target cleans home ~/.claude."""
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        nwave_dir = tmp_path / ".nwave"

        # Seed stale hook into home
        _seed_stale_attribution_hook(home_claude)
        assert _stale_attribution_hook_present(home_claude) is True

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        # Stale hook cleaned from home
        assert _stale_attribution_hook_present(home_claude) is False


class TestAttributionOffTargetFlag:
    def test_target_cleans_stale_hook_from_target_not_home(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """off --target cleans stale hook from target, leaves home untouched."""
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        target = tmp_path / "target-profile"
        nwave_dir = tmp_path / ".nwave"

        # Seed stale hook into target
        _seed_stale_attribution_hook(target)
        assert _stale_attribution_hook_present(target) is True

        with (
            patch(
                "sys.argv",
                ["nwave-ai", "attribution", "--target", str(target), "off"],
            ),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        # Stale hook cleaned from target
        assert _stale_attribution_hook_present(target) is False
        # Home untouched
        assert not (home_claude / "settings.json").exists()

    def test_target_is_named_in_disabled_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """off --target names the target in output."""
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
        """CLAUDE_CONFIG_DIR set routes cleanup there, not home."""
        home = tmp_path / "home"
        home_claude = home / ".claude"
        home_claude.mkdir(parents=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

        profile = tmp_path / "claude-alt-profile"
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(profile))
        nwave_dir = tmp_path / ".nwave"

        # Seed stale hook into env var profile
        _seed_stale_attribution_hook(profile)
        assert _stale_attribution_hook_present(profile) is True

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = cli.main()

        assert result == 0
        # Stale hook cleaned from CLAUDE_CONFIG_DIR target
        assert _stale_attribution_hook_present(profile) is False
        # Home untouched
        assert not (home_claude / "settings.json").exists()
