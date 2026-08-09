"""Unit tests for CLI attribution subcommand.

Tests validate on/off/status commands through the driving port
(cli.main) and assert at driven port boundaries (global-config.json +
~/.claude/settings.json).

Test Budget: 6 behaviors x 2 = 12 max. Using 6 tests.

Behaviors tested:
1. 'attribution on' -> enables preference + registers the commit hook, NO
   settings.json credit written (ADR-CA-007: the hook is the sole mechanism)
2. 'attribution off' -> disables preference + removes settings.json credit
3. 'attribution status' when enabled -> shows "on"
4. 'attribution status' when disabled -> shows "off"
5. Toggle off delegates legacy cleanup to migrate_legacy_settings_attribution
   (legacy-residue cleanup is RETAINED on 'off', routed via the claude_dir seam)
6. Enable -> registers the hook and writes NO managed credit

Post-migration (ADR-CA-007): the settings.json attribution write surface is
RETIRED. 'on' registers the activation-gated PreToolUse commit-attribution hook
as the sole mechanism and never writes attribution.{commit,pr}. 'off' still
removes any legacy settings credit (cleanup) and unregisters the hook.

_handle_attribution now resolves claude_dir via PathUtils.get_claude_config_dir()
(honors CLAUDE_CONFIG_DIR / --target), not a fixed Path.home()/".claude" --
see TestAttributionTargetFlag below. Every test in this module that relies on
the Path.home() monkeypatch to select the default profile must also scrub
CLAUDE_CONFIG_DIR from the host env, or a developer's own multi-profile
env var overrides the monkeypatch and the test observes the wrong directory
(target-machine independence, see feedback_target_machine_independence).
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from nwave_ai.cli import main


# Serialize tests touching .git/hooks/ to avoid xdist races on shared state.
pytestmark = pytest.mark.xdist_group("git_hooks")


@pytest.fixture(autouse=True)
def _scrub_claude_config_dir_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure CLAUDE_CONFIG_DIR is not leaked into the test from the host env.

    Mirrors tests/installer/unit/cli/test_target_flag.py::_scrub_env -- without
    this, a developer machine with CLAUDE_CONFIG_DIR set (e.g. a multi-profile
    Claude Code setup) makes claude_dir resolve to that env var instead of the
    tmp_path-based Path.home() monkeypatch each test below sets up.
    """
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)


def _write_config(config_dir: Path, *, enabled: bool) -> None:
    """Write global-config.json with attribution preference."""
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "global-config.json"
    config_file.write_text(
        json.dumps(
            {
                "attribution": {
                    "enabled": enabled,
                    "trailer": "Co-Authored-By: nWave <nwave@nwave.ai>",
                }
            }
        ),
        encoding="utf-8",
    )


def _hook_registered(claude_dir: Path) -> bool:
    """Check if PreToolUse universal handler entry exists."""
    settings_path = claude_dir / "settings.json"
    if not settings_path.exists():
        return False
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    entries = (settings.get("hooks") or {}).get("PreToolUse") or []
    return any(
        entry.get("matcher") == "Bash"
        and any(
            "pre-tool-use" in (hook.get("command") or "")
            for hook in entry.get("hooks") or []
        )
        for entry in entries
    )


def _read_config(config_dir: Path) -> dict:
    """Read global-config.json."""
    config_file = config_dir / "global-config.json"
    with open(config_file, encoding="utf-8") as f:
        return json.load(f)


class TestAttributionCLI:
    """Tests for nwave-ai attribution on/off/status."""

    def test_attribution_on(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """'attribution on' enables the preference + calls cleanup, writes NO credit."""
        nwave_dir = tmp_path / ".nwave"
        home_dir = tmp_path / "home"
        claude_dir = home_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.cleanup_legacy_attribution_hook", return_value=False),
        ):
            result = main()

        assert result == 0
        config = _read_config(nwave_dir)
        assert config["attribution"]["enabled"] is True

        # No managed credit written to settings.json (retired surface).
        if (claude_dir / "settings.json").exists():
            settings = json.loads((claude_dir / "settings.json").read_text())
            assert "commit" not in settings.get("attribution", {})

        captured = capsys.readouterr()
        assert "enabled" in captured.out.lower()

    def test_attribution_off(self, tmp_path: Path, capsys) -> None:
        """'attribution off' disables preference + calls cleanup."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=True)

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "off"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.cleanup_legacy_attribution_hook", return_value=False),
            patch(
                "nwave_ai.cli.migrate_legacy_settings_attribution", return_value=False
            ),
        ):
            result = main()

        assert result == 0
        config = _read_config(nwave_dir)
        assert config["attribution"]["enabled"] is False
        captured = capsys.readouterr()
        assert "disabled" in captured.out.lower()

    def test_attribution_status_enabled(self, tmp_path: Path, capsys) -> None:
        """'attribution status' shows 'on' when enabled."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=True)

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "status"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "on" in captured.out.lower()

    def test_attribution_status_disabled(self, tmp_path: Path, capsys) -> None:
        """'attribution status' shows 'off' when disabled."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=False)

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "status"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
        ):
            result = main()

        assert result == 0
        captured = capsys.readouterr()
        assert "off" in captured.out.lower()

    def test_off_calls_both_legacy_cleanups(self, tmp_path: Path) -> None:
        """'attribution off' calls both legacy cleanup paths.

        ADR-CA-007 and CA-006: turning off must clean both the retired
        settings.json attribution.{commit,pr} credit (via migrate_legacy_settings_attribution)
        and the stale PreToolUse hook entry (via cleanup_legacy_attribution_hook)."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=True)

        cleanup_calls = []
        migrate_calls = []

        def mock_cleanup(claude_dir=None):
            cleanup_calls.append(claude_dir)
            return False

        def mock_migrate(config_dir=None, claude_dir=None):
            migrate_calls.append((config_dir, claude_dir))
            return False

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "off"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch(
                "nwave_ai.cli.cleanup_legacy_attribution_hook",
                side_effect=mock_cleanup,
            ),
            patch(
                "nwave_ai.cli.migrate_legacy_settings_attribution",
                side_effect=mock_migrate,
            ),
        ):
            main()

        assert _read_config(nwave_dir)["attribution"]["enabled"] is False
        assert len(cleanup_calls) == 1, "cleanup_legacy_attribution_hook must be called"
        assert len(migrate_calls) == 1, (
            "migrate_legacy_settings_attribution must be called"
        )
        # Cleanup routed through the claude_dir injection seam.
        assert migrate_calls[0][1] is not None

    def test_enable_writes_no_managed_credit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """'attribution on' writes preference only, NO managed credit."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=False)
        home_dir = tmp_path / "home"
        claude_dir = home_dir / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_dir))

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.cleanup_legacy_attribution_hook", return_value=False),
        ):
            result = main()

        assert result == 0
        assert _read_config(nwave_dir)["attribution"]["enabled"] is True

        if (claude_dir / "settings.json").exists():
            settings = json.loads((claude_dir / "settings.json").read_text())
            assert "commit" not in settings.get("attribution", {})
