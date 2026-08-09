"""Dense authority tests for `cleanup_legacy_attribution_hook`.

ADR-CA-006 D6/D7/O-4: the retired independent `pre-commit-attribution`
PreToolUse entry must be removed on upgrade by EXACT command match only --
never by marker substring or near-match -- and every sibling (other hooks,
entry metadata, timeout) must survive untouched. Fail-open on missing or
corrupt settings.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.install.attribution_utils import (
    _attribution_hook_command,
    cleanup_legacy_attribution_hook,
)


def _write_settings(claude_dir: Path, settings: dict) -> Path:
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings_path = claude_dir / "settings.json"
    settings_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    return settings_path


@pytest.mark.parametrize(
    "claude_dir_name",
    [None, "custom-profile"],
    ids=["default_home", "custom_target"],
)
def test_exact_stale_command_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, claude_dir_name: str | None
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    claude_dir = (
        home / ".claude" if claude_dir_name is None else tmp_path / claude_dir_name
    )
    expected_command = _attribution_hook_command(claude_dir)
    _write_settings(
        claude_dir,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": expected_command}],
                    }
                ]
            }
        },
    )

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is True
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert settings.get("hooks", {}).get("PreToolUse") == []


def test_sibling_hook_timeout_and_entry_metadata_preserved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    claude_dir = home / ".claude"
    expected_command = _attribution_hook_command(claude_dir)

    _write_settings(
        claude_dir,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "timeout": 30,
                        "hooks": [
                            {"type": "command", "command": expected_command},
                            {"type": "command", "command": "echo user-sibling"},
                        ],
                    }
                ]
            }
        },
    )

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is True
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["PreToolUse"]
    assert len(entries) == 1
    assert entries[0]["timeout"] == 30
    assert entries[0]["matcher"] == "Bash"
    assert entries[0]["hooks"] == [{"type": "command", "command": "echo user-sibling"}]


@pytest.mark.parametrize(
    "command",
    [
        "# des-hook:pre-commit-attribution",
        "echo something else",
    ],
    ids=["marker_only_no_full_command", "unrelated_command"],
)
def test_marker_only_and_unrelated_commands_survive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, command: str
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    claude_dir = home / ".claude"

    _write_settings(
        claude_dir,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": command}],
                    }
                ]
            }
        },
    )

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is False
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"][0]["hooks"] == [
        {"type": "command", "command": command}
    ]


def test_one_character_near_match_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    claude_dir = home / ".claude"
    near_match = _attribution_hook_command(claude_dir) + "x"

    _write_settings(
        claude_dir,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": near_match}],
                    }
                ]
            }
        },
    )

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is False
    settings = json.loads((claude_dir / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"][0]["hooks"] == [
        {"type": "command", "command": near_match}
    ]


def test_custom_target_exact_command_uses_target_lib_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    target = tmp_path / "target-profile"

    expected_command = _attribution_hook_command(target)
    assert f"PYTHONPATH={target / 'lib' / 'python'}" in expected_command
    assert "$HOME" not in expected_command

    _write_settings(
        target,
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": expected_command}],
                    }
                ]
            }
        },
    )

    result = cleanup_legacy_attribution_hook(claude_dir=target)

    assert result is True
    settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))
    assert settings["hooks"]["PreToolUse"] == []


def test_missing_settings_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    claude_dir = home / ".claude"

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is False
    assert not (claude_dir / "settings.json").exists()


def test_corrupt_settings_is_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True)
    (claude_dir / "settings.json").write_text("{not valid json", encoding="utf-8")

    result = cleanup_legacy_attribution_hook(claude_dir=claude_dir)

    assert result is False
    assert (claude_dir / "settings.json").read_text(encoding="utf-8") == (
        "{not valid json"
    )
