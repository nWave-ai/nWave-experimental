"""D1 — the attribution mutation branch is fail-safe at the adapter.

Contract (ADR-CA-006): "any error → original command runs unchanged." An
exception in the rewrite plan / JSON serialization must NEVER propagate to the
outer ``handle_pre_tool_use`` ``except Exception`` (which fail-closes to
``exit_code=1`` and BLOCKS the commit). Attribution is best-effort: a missed
trailer is recoverable; a blocked commit is not.

``emit_commit_attribution_mutation`` is the driving seam: feed it a ``tool_input``
whose service raises, and assert it returns ``None`` (passthrough — falls through
to the existing validation path), never raising.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


class _RaisingService:
    """A service whose ``plan_rewrite`` always raises (simulated failure)."""

    def plan_rewrite(self, command: str) -> object:
        raise RuntimeError("boom: rewrite core blew up")


def test_d1_service_exception_returns_passthrough_not_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A raising service yields ``None`` (passthrough), never an exception."""
    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _RaisingService()
    )
    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"', "description": "commit the work"}
    )
    assert result is None


def test_d1_service_exception_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The mutation branch swallows the failure (no propagation to the caller)."""
    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _RaisingService()
    )
    # The bare call must not raise; if it did, the outer handler would block.
    pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'}
    )


def test_d1_non_string_command_still_passes_through() -> None:
    """A non-string command is a no-op passthrough (existing guard preserved)."""
    result = pre_tool_use_handler.emit_commit_attribution_mutation({"command": None})
    assert result is None


class _MutatingService:
    """A service whose ``plan_rewrite`` returns a mutate plan."""

    def __init__(self, rewritten: str = 'git commit -m "x" -C HEAD'):
        self.rewritten = rewritten

    def plan_rewrite(self, command: str) -> object:
        class Plan:
            action = "mutate"
            rewritten_command = self.rewritten

        return Plan()


def test_attribution_enabled_true_mutates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """When attribution.enabled=true, emit_commit_attribution_mutation mutates."""
    global_config_dir = tmp_path / ".nwave"
    global_config_dir.mkdir()
    global_config_file = global_config_dir / "global-config.json"
    global_config_file.write_text(
        json.dumps({"attribution": {"enabled": True}}), encoding="utf-8"
    )

    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
    )
    monkeypatch.setenv("HOME", str(tmp_path))

    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'},
        cwd=tmp_path,
    )
    assert result == 0
    captured = capsys.readouterr()
    assert "hookSpecificOutput" in captured.out


import pytest


@pytest.mark.parametrize(
    "config_content",
    [
        {"attribution": {"enabled": False}},  # disabled
        {"attribution": {}},  # missing key
        None,  # missing file
        "{invalid json",  # malformed
    ],
)
def test_attribution_disabled_or_absent_passthrough(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, config_content
) -> None:
    """When attribution is disabled, missing, or config malformed, return None."""
    monkeypatch.setenv("HOME", str(tmp_path))

    if config_content is not None:
        global_config_dir = tmp_path / ".nwave"
        global_config_dir.mkdir()
        global_config_file = global_config_dir / "global-config.json"
        if isinstance(config_content, str):
            global_config_file.write_text(config_content, encoding="utf-8")
        else:
            global_config_file.write_text(json.dumps(config_content), encoding="utf-8")

    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'},
        cwd=tmp_path,
    )
    assert result is None
