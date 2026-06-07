"""Unit tests for CLI attribution subcommand.

Tests validate on/off/status commands through the driving port
(cli.main) and assert at driven port boundaries (global-config.json).

Test Budget: 6 behaviors x 2 = 12 max. Using 6 tests.

Behaviors tested:
1. 'attribution on' -> enables attribution + installs hook
2. 'attribution off' -> disables attribution + removes hook
3. 'attribution status' when enabled -> shows "on"
4. 'attribution status' when disabled -> shows "off"
5. Toggle off/on preserves existing hooks
6. Enable when hook file was manually deleted -> reinstalls
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from nwave_ai.cli import main


# Serialize tests touching .git/hooks/ to avoid xdist races on shared state.
pytestmark = pytest.mark.xdist_group("git_hooks")


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


def _read_config(config_dir: Path) -> dict:
    """Read global-config.json."""
    config_file = config_dir / "global-config.json"
    with open(config_file, encoding="utf-8") as f:
        return json.load(f)


class TestAttributionCLI:
    """Tests for nwave-ai attribution on/off/status."""

    def test_attribution_on(self, tmp_path: Path, capsys) -> None:
        """'attribution on' enables attribution in config."""
        nwave_dir = tmp_path / ".nwave"

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch(
                "nwave_ai.cli.install_attribution_hook",
                return_value=tmp_path / "hook",
            ),
        ):
            result = main()

        assert result == 0
        config = _read_config(nwave_dir)
        assert config["attribution"]["enabled"] is True
        captured = capsys.readouterr()
        assert "enabled" in captured.out.lower()

    def test_attribution_off(self, tmp_path: Path, capsys) -> None:
        """'attribution off' disables attribution in config."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=True)

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "off"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.remove_attribution_hook"),
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

    def test_toggle_preserves_existing_hooks(self, tmp_path: Path) -> None:
        """Off then on cycle preserves original hook."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=True)

        # Track calls to install/remove to verify delegation
        install_calls = []
        remove_calls = []

        def mock_install(config_dir=None):
            install_calls.append(config_dir)
            return tmp_path / "hook"

        def mock_remove(config_dir=None):
            remove_calls.append(config_dir)

        # Off
        with (
            patch("sys.argv", ["nwave-ai", "attribution", "off"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.remove_attribution_hook", side_effect=mock_remove),
        ):
            main()

        assert _read_config(nwave_dir)["attribution"]["enabled"] is False
        assert len(remove_calls) == 1

        # On
        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.install_attribution_hook", side_effect=mock_install),
        ):
            main()

        assert _read_config(nwave_dir)["attribution"]["enabled"] is True
        assert len(install_calls) == 1

    def test_enable_when_hook_deleted(self, tmp_path: Path, capsys) -> None:
        """'attribution on' reinstalls hook even if file was deleted."""
        nwave_dir = tmp_path / ".nwave"
        _write_config(nwave_dir, enabled=False)

        install_called = []

        def mock_install(config_dir=None):
            install_called.append(True)
            return tmp_path / "hook"

        with (
            patch("sys.argv", ["nwave-ai", "attribution", "on"]),
            patch("nwave_ai.cli._get_config_dir", return_value=nwave_dir),
            patch("nwave_ai.cli.install_attribution_hook", side_effect=mock_install),
        ):
            result = main()

        assert result == 0
        assert len(install_called) == 1
        config = _read_config(nwave_dir)
        assert config["attribution"]["enabled"] is True
