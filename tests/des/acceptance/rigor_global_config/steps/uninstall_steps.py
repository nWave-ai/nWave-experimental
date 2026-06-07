"""
Step definitions for uninstall global config lifecycle acceptance tests.

Covers milestone-3-uninstall-lifecycle.feature.

Driving port: NWaveUninstaller (scripts/install/uninstall_nwave.py).
Tests verify that the uninstaller correctly handles the global config
file during the uninstall lifecycle: prompt keep/delete, force mode,
dry-run mode, and no-prompt when file is absent.

Wiring: Each When step creates a real NWaveUninstaller with injected
CLAUDE_CONFIG_DIR and calls check_global_config() with the test's
global_config_path. A prompt_fn stub controls user choice and tracks
whether the prompt was shown.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from scripts.install.uninstall_nwave import NWaveUninstaller
from tests.des.acceptance.rigor_global_config.steps.helpers import (
    read_json_file,
    write_global_config,
)


if TYPE_CHECKING:
    from pathlib import Path


# Link feature file
scenarios("../milestone-3-uninstall-lifecycle.feature")


# ---------------------------------------------------------------------------
# Shared test context
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx(tmp_path: Path) -> dict[str, Any]:
    """
    Context for uninstall tests.

    Sets up a simulated home directory and project directory
    that mimic a real nWave installation.
    """
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    global_nwave_dir = home_dir / ".nwave"
    global_nwave_dir.mkdir()

    # Simulate Claude config dir with minimal installation markers
    claude_dir = home_dir / ".claude"
    claude_dir.mkdir()
    agents_dir = claude_dir / "agents" / "nw"
    agents_dir.mkdir(parents=True)
    (agents_dir / "test-agent.yaml").write_text("name: test", encoding="utf-8")

    return {
        "home_dir": home_dir,
        "global_nwave_dir": global_nwave_dir,
        "global_config_path": global_nwave_dir / "global-config.json",
        "claude_dir": claude_dir,
        "output_lines": [],
        "prompt_shown": False,
        "user_choice": None,
    }


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given("a temporary home directory for uninstall testing")
def given_temp_home(ctx: dict[str, Any]) -> None:
    """Home directory created by ctx fixture."""
    pass


@given("a temporary project with nWave installed")
def given_nwave_installed(ctx: dict[str, Any]) -> None:
    """Minimal nWave installation markers exist."""
    pass


@given(parsers.parse('the global config file exists with rigor profile "{profile}"'))
def given_global_config_exists(ctx: dict[str, Any], profile: str) -> None:
    """Create global config with rigor profile."""
    write_global_config(
        ctx["global_config_path"],
        {"rigor": {"profile": profile, "agent_model": "opus"}},
    )


@given("the global config file is the only file in the global config directory")
def given_global_config_only_file(ctx: dict[str, Any]) -> None:
    """Ensure the global config file is the only content in ~/.nwave/."""
    # Write a default config
    write_global_config(
        ctx["global_config_path"],
        {"rigor": {"profile": "custom"}},
    )
    # Remove any other files
    for item in ctx["global_nwave_dir"].iterdir():
        if item != ctx["global_config_path"]:
            if item.is_dir():
                import shutil

                shutil.rmtree(item)
            else:
                item.unlink()


@given("the global config directory contains other files")
def given_global_dir_has_other_files(ctx: dict[str, Any]) -> None:
    """Add other files to the global config directory."""
    other_file = ctx["global_nwave_dir"] / "other-data.json"
    other_file.write_text(json.dumps({"some": "data"}), encoding="utf-8")


@given("no global config file exists")
def given_no_global_config(ctx: dict[str, Any]) -> None:
    """Ensure global config file does not exist."""
    path = ctx["global_config_path"]
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# When steps: calling real NWaveUninstaller.check_global_config()
# ---------------------------------------------------------------------------


def _make_prompt_fn(ctx: dict[str, Any], answer: bool) -> object:
    """Create a prompt function stub that records whether it was called.

    Args:
        ctx: Test context dict -- sets ctx["prompt_shown"] to True when called.
        answer: What the stub returns (True = delete, False = keep).

    Returns:
        A callable matching the confirm_action signature.
    """

    def prompt_stub(prompt: str) -> bool:
        ctx["prompt_shown"] = True
        return answer

    return prompt_stub


def _invoke_check_global_config(
    ctx: dict[str, Any],
    user_choice: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    """Create a real NWaveUninstaller and call check_global_config().

    Uses CLAUDE_CONFIG_DIR env var to point the uninstaller at the test's
    temporary claude directory. Injects a prompt_fn stub that controls
    the user's keep/delete choice and tracks whether a prompt was shown.

    Captures logger output into ctx["output_lines"] for assertion.
    """
    original_env = os.environ.get("CLAUDE_CONFIG_DIR")
    try:
        os.environ["CLAUDE_CONFIG_DIR"] = str(ctx["claude_dir"])
        uninstaller = NWaveUninstaller(force=force, dry_run=dry_run)

        # Build prompt stub based on user_choice
        if user_choice == "keep":
            prompt_fn = _make_prompt_fn(ctx, answer=False)
        elif user_choice == "delete":
            prompt_fn = _make_prompt_fn(ctx, answer=True)
        else:
            # No interactive choice expected (force/dry-run/no-file)
            prompt_fn = _make_prompt_fn(ctx, answer=False)

        # Capture logger output by wrapping the logger's info method
        original_info = uninstaller.logger.info

        def capturing_info(message: str) -> None:
            ctx["output_lines"].append(message)
            original_info(message)

        uninstaller.logger.info = capturing_info

        try:
            uninstaller.check_global_config(
                global_config_path=ctx["global_config_path"],
                prompt_fn=prompt_fn,
            )
            ctx["invocation_error"] = None
        except Exception as exc:
            ctx["invocation_error"] = exc
    finally:
        if original_env is None:
            os.environ.pop("CLAUDE_CONFIG_DIR", None)
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = original_env


@when("the uninstaller runs and the user chooses to keep global config")
def when_uninstall_keep(ctx: dict[str, Any]) -> None:
    """Run real uninstaller with user choosing keep."""
    _invoke_check_global_config(ctx, user_choice="keep")


@when("the uninstaller runs and the user chooses to delete global config")
def when_uninstall_delete(ctx: dict[str, Any]) -> None:
    """Run real uninstaller with user choosing delete."""
    _invoke_check_global_config(ctx, user_choice="delete")


@when("the uninstaller runs")
def when_uninstall_normal(ctx: dict[str, Any]) -> None:
    """Run real uninstaller with no special options."""
    _invoke_check_global_config(ctx)


@when("the uninstaller runs with force mode enabled")
def when_uninstall_force(ctx: dict[str, Any]) -> None:
    """Run real uninstaller in force mode."""
    _invoke_check_global_config(ctx, force=True)


@when("the uninstaller runs in dry-run mode")
def when_uninstall_dry_run(ctx: dict[str, Any]) -> None:
    """Run real uninstaller in dry-run mode."""
    _invoke_check_global_config(ctx, dry_run=True)


# ---------------------------------------------------------------------------
# Then steps
# ---------------------------------------------------------------------------


@then(
    parsers.parse('the global config file is preserved with rigor profile "{expected}"')
)
def then_global_preserved(ctx: dict[str, Any], expected: str) -> None:
    """Verify global config file still exists with expected profile."""
    assert ctx["global_config_path"].exists()
    data = read_json_file(ctx["global_config_path"])
    assert data["rigor"]["profile"] == expected


@then("the rest of the uninstall completes normally")
def then_uninstall_completes(ctx: dict[str, Any]) -> None:
    """Verify check_global_config completed without errors."""
    assert ctx.get("invocation_error") is None


@then("the global config file no longer exists")
def then_global_deleted(ctx: dict[str, Any]) -> None:
    """Verify global config file was removed."""
    assert not ctx["global_config_path"].exists()


@then("the global config directory is removed")
def then_global_dir_removed(ctx: dict[str, Any]) -> None:
    """Verify the global config directory was cleaned up."""
    assert not ctx["global_nwave_dir"].exists()


@then("the global config directory still exists")
def then_global_dir_still_exists(ctx: dict[str, Any]) -> None:
    """Verify global config directory remains (has other files)."""
    assert ctx["global_nwave_dir"].exists()


@then("no prompt about global configuration is shown")
def then_no_prompt(ctx: dict[str, Any]) -> None:
    """Verify no prompt was displayed."""
    assert ctx["prompt_shown"] is False


@then("the uninstall completes normally")
def then_uninstall_ok(ctx: dict[str, Any]) -> None:
    """Verify check_global_config completed without errors."""
    assert ctx.get("invocation_error") is None


@then("the dry-run output mentions global configuration")
def then_dry_run_mentions_global(ctx: dict[str, Any]) -> None:
    """Verify dry-run output includes global config information."""
    output = "\n".join(ctx["output_lines"])
    assert "global config" in output.lower()
