"""
Step definitions for rigor scope selection acceptance tests.

Covers milestone-2-rigor-scope.feature.

Driving port: Config file write results (verifying file contents after
scope-aware save operations). Since /nw-rigor is a markdown command,
we test the observable outcome: what ends up in the config files.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when


if TYPE_CHECKING:
    from pathlib import Path

from tests.des.acceptance.rigor_global_config.steps.helpers import (
    read_json_file,
    write_global_config,
    write_project_config,
)


# Link feature file
scenarios("../milestone-2-rigor-scope.feature")


# ---------------------------------------------------------------------------
# Shared test context
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx(
    project_dir: Path,
    project_config_path: Path,
    global_config_dir: Path,
    global_config_path: Path,
) -> dict[str, Any]:
    """Context with all paths pre-loaded from shared fixtures."""
    return {
        "project_dir": project_dir,
        "project_config_path": project_config_path,
        "global_config_dir": global_config_dir,
        "global_config_path": global_config_path,
        "initial_project_config": None,
        "initial_global_config": None,
    }


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a temporary project directory exists")
def given_temp_project(ctx: dict[str, Any]) -> None:
    """Project directory is already created by the ctx fixture."""
    pass


@given("a temporary global configuration directory exists")
def given_temp_global(ctx: dict[str, Any]) -> None:
    """Global config directory is already created by the ctx fixture."""
    pass


@given("the global config file does not exist yet")
def given_no_global_file(ctx: dict[str, Any]) -> None:
    """Ensure global config file does not exist."""
    path = ctx["global_config_path"]
    if path.exists():
        path.unlink()


@given("the project config has no rigor key")
def given_project_no_rigor(ctx: dict[str, Any]) -> None:
    """Project config without rigor key."""
    write_project_config(
        ctx["project_config_path"],
        {"audit_logging_enabled": True},
    )
    ctx["initial_project_config"] = read_json_file(ctx["project_config_path"])


@given(
    parsers.parse('the global config file has an update check frequency of "{freq}"')
)
def given_global_with_update_check(ctx: dict[str, Any], freq: str) -> None:
    """Global config with non-rigor data."""
    write_global_config(
        ctx["global_config_path"],
        {"update_check": {"frequency": freq}},
    )
    ctx["initial_global_config"] = read_json_file(ctx["global_config_path"])


@given("the project config has audit logging enabled")
def given_project_with_audit(ctx: dict[str, Any]) -> None:
    """Project config with audit_logging_enabled."""
    write_project_config(
        ctx["project_config_path"],
        {"audit_logging_enabled": True},
    )
    ctx["initial_project_config"] = read_json_file(ctx["project_config_path"])


@given("the global config directory does not exist")
def given_no_global_dir(ctx: dict[str, Any], tmp_path: Path) -> None:
    """Use a path where the directory does not exist."""

    # Remove the existing global dir and use a fresh non-existent path
    nonexistent = tmp_path / "nonexistent-home" / ".nwave"
    ctx["global_config_dir"] = nonexistent
    ctx["global_config_path"] = nonexistent / "global-config.json"


@given(parsers.parse('the global config has rigor profile "{profile}"'))
def given_global_rigor_profile(ctx: dict[str, Any], profile: str) -> None:
    """Global config with rigor profile."""
    write_global_config(
        ctx["global_config_path"],
        {"rigor": {"profile": profile}},
    )


@given("the global config file contains invalid content")
def given_global_invalid(ctx: dict[str, Any]) -> None:
    """Write invalid JSON to global config."""
    ctx["global_config_path"].parent.mkdir(parents=True, exist_ok=True)
    ctx["global_config_path"].write_text("not valid json {{{", encoding="utf-8")


# ---------------------------------------------------------------------------
# When steps: simulating scope-aware save
# ---------------------------------------------------------------------------


def _save_rigor_with_scope(
    ctx: dict[str, Any],
    rigor_data: dict,
    scope: str,
) -> None:
    """
    Simulate the /nw-rigor command's write behavior.

    This is the read-modify-write pattern that the markdown command
    instructs Claude to execute. We test the observable outcome.
    """
    if scope == "global":
        target_path = ctx["global_config_path"]
    else:
        target_path = ctx["project_config_path"]

    # Read-modify-write (create directory if needed for global)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    current_data: dict = {}
    if target_path.exists():
        try:
            current_data = json.loads(target_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            current_data = {}

    current_data["rigor"] = rigor_data
    target_path.write_text(json.dumps(current_data, indent=2), encoding="utf-8")


@when(
    parsers.parse(
        'rigor profile "{profile}" with agent model "{model}" is saved with scope "{scope}"'
    )
)
def when_save_rigor_with_model(
    ctx: dict[str, Any], profile: str, model: str, scope: str
) -> None:
    """Save rigor profile with agent model to specified scope."""
    _save_rigor_with_scope(
        ctx,
        {"profile": profile, "agent_model": model},
        scope,
    )


@when(parsers.parse('rigor profile "{profile}" is saved with scope "{scope}"'))
def when_save_rigor(ctx: dict[str, Any], profile: str, scope: str) -> None:
    """Save rigor profile to specified scope."""
    _save_rigor_with_scope(
        ctx,
        {"profile": profile, "agent_model": "sonnet", "reviewer_model": "haiku"},
        scope,
    )


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(parsers.parse('the global config file contains rigor profile "{expected}"'))
def then_global_has_profile(ctx: dict[str, Any], expected: str) -> None:
    """Verify global config file has the expected rigor profile."""
    data = read_json_file(ctx["global_config_path"])
    assert data["rigor"]["profile"] == expected


@then(parsers.parse('the global config file contains agent model "{expected}"'))
def then_global_has_model(ctx: dict[str, Any], expected: str) -> None:
    """Verify global config file has the expected agent model."""
    data = read_json_file(ctx["global_config_path"])
    assert data["rigor"]["agent_model"] == expected


@then("the project config rigor key is unchanged")
def then_project_rigor_unchanged(ctx: dict[str, Any]) -> None:
    """Verify project config rigor was not modified."""
    data = read_json_file(ctx["project_config_path"])
    initial = ctx.get("initial_project_config") or {}
    assert data.get("rigor") == initial.get("rigor")


@then(parsers.parse('the project config contains rigor profile "{expected}"'))
def then_project_has_profile(ctx: dict[str, Any], expected: str) -> None:
    """Verify project config has the expected rigor profile."""
    data = read_json_file(ctx["project_config_path"])
    assert data["rigor"]["profile"] == expected


@then(parsers.parse('the project config contains agent model "{expected}"'))
def then_project_has_model(ctx: dict[str, Any], expected: str) -> None:
    """Verify project config has the expected agent model."""
    data = read_json_file(ctx["project_config_path"])
    assert data["rigor"]["agent_model"] == expected


@then("the global config file is not modified")
def then_global_not_modified(ctx: dict[str, Any]) -> None:
    """Verify global config was not changed."""
    initial = ctx.get("initial_global_config")
    if initial is None:
        # No initial state was captured — file should not exist
        assert not ctx["global_config_path"].exists()
    else:
        data = read_json_file(ctx["global_config_path"])
        assert data == initial


@then(
    parsers.parse(
        'the global config file still has update check frequency "{expected}"'
    )
)
def then_global_update_check_preserved(ctx: dict[str, Any], expected: str) -> None:
    """Verify non-rigor keys are preserved in global config."""
    data = read_json_file(ctx["global_config_path"])
    assert data["update_check"]["frequency"] == expected


@then("the project config still has audit logging enabled")
def then_project_audit_preserved(ctx: dict[str, Any]) -> None:
    """Verify non-rigor keys are preserved in project config."""
    data = read_json_file(ctx["project_config_path"])
    assert data["audit_logging_enabled"] is True


@then("the global config directory is created")
def then_global_dir_created(ctx: dict[str, Any]) -> None:
    """Verify global config directory was created."""
    assert ctx["global_config_dir"].exists()
    assert ctx["global_config_dir"].is_dir()


@then("the global config file is valid")
def then_global_is_valid_json(ctx: dict[str, Any]) -> None:
    """Verify global config file contains valid JSON."""
    data = read_json_file(ctx["global_config_path"])
    assert isinstance(data, dict)
