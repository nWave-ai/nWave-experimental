"""The public status command describes effective behavior without changing config."""

from __future__ import annotations

import json
from pathlib import Path

from nwave_ai.cli import _handle_attribution, main_with_argv


def test_status_shows_project_precedence_and_actionable_state(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "project"
    global_path = home / ".nwave" / "config.json"
    project_path = repo / ".nwave" / "config.json"
    global_path.parent.mkdir(parents=True)
    project_path.parent.mkdir(parents=True)
    global_path.write_text(
        json.dumps(
            {
                "activation": {"mode": "opt-in"},
                "attribution": {"enabled": True},
                "verbosity": "terse",
                "update_check": {"frequency": "daily"},
                "documentation": {"density": "full", "expansion_prompt": "smart"},
            }
        )
    )
    project_path.write_text(json.dumps({"enabled": True, "verbosity": "verbose"}))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.chdir(repo)
    before = (global_path.read_bytes(), project_path.read_bytes())

    assert main_with_argv(["status"]) == 0
    output = capsys.readouterr().out
    assert "This project is active." in output
    assert "Activation source: project." in output
    assert "Attribution: on (global)" in output
    assert "Verbosity: verbose (project)." in output
    assert (
        "Retired update_check: ignored (global); no automatic update prompt." in output
    )
    assert "Documentation density: diagnostic-only (global)" in output
    assert "Wave-end explanation: smart (global; after completed waves only)." in output
    assert (global_path.read_bytes(), project_path.read_bytes()) == before

    project_path.write_text(
        json.dumps(
            {
                "enabled": False,
                "attribution": {"enabled": False},
            }
        )
    )
    assert main_with_argv(["status"]) == 0
    output = capsys.readouterr().out
    assert "This project is inactive." in output
    assert "Activation source: project." in output
    assert "Attribution: off (project)" in output
    assert "co-author credit will not be added here" in output
    assert "Verbosity: terse (global)." in output
    assert "To activate this project: nwave-ai project enable" in output


def test_attribution_status_respects_project_override_over_machine_preference(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "project"
    global_path = home / ".nwave" / "config.json"
    project_path = repo / ".nwave" / "config.json"
    global_path.parent.mkdir(parents=True)
    project_path.parent.mkdir(parents=True)
    global_path.write_text(json.dumps({"attribution": {"enabled": False}}))
    project_path.write_text(
        json.dumps({"enabled": True, "attribution": {"enabled": True}})
    )
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.chdir(repo)
    before = global_path.read_bytes(), project_path.read_bytes()

    assert _handle_attribution(["status"]) == 0
    output = capsys.readouterr().out
    assert "Attribution is currently on." in output
    assert "Preference source: project." in output
    assert "Attribution is active for this repo." in output
    assert (global_path.read_bytes(), project_path.read_bytes()) == before
