"""F-ATTRIBUTION-GATING-ASYMMETRY-PRETOOLUSE — the PreToolUse path is gated too.

The PreToolUse mutation branch rewrites the USER's ``git commit`` command. That
is an action on the user's work, so it is due only in a repository the user has
ACTIVATED (ADR-AG-005, opt-in ratified) — exactly the condition the twin
producing path (``application.commit_message_attribution``) already applies via
``resolve_activation``. Before this suite the adapter read
``config.attribution_enabled`` ALONE: two paths, same decision, different
conditions.

GDP-8 witness corollary: the router's ``activation_gate`` resolving activation
upstream is a property of the CONTAINER, not of this unit. The unit decides on
its own property — it is invoked directly (its own public seam) and its ``cwd``
comes from the hook envelope, which need not agree with the root the gate
resolved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler


class _MutatingService:
    """A rewrite service that always returns a mutate plan (never the blocker)."""

    def plan_rewrite(self, command: str) -> object:
        class Plan:
            action = "mutate"
            rewritten_command = 'git commit -m "x"  # trailer'

        return Plan()


def _home_with_attribution_on(tmp_path: Path) -> Path:
    """A disposable HOME whose global config enables attribution, nothing else.

    No ``activation.mode`` key ⇒ the ADR-AG-002 default ``opt-in``: the repo is
    active only if it DECLARES itself so.
    """
    nwave = tmp_path / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "global-config.json").write_text(
        json.dumps({"attribution": {"enabled": True}}), encoding="utf-8"
    )
    return tmp_path


def _repo(tmp_path: Path, *, activated: bool) -> Path:
    """A repo under HOME (so the marker walk-up stops there), opt-in declared."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    if activated:
        marker_dir = repo / ".nwave"
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / "local-config.json").write_text(
            json.dumps({"enabled_for_repo": True}), encoding="utf-8"
        )
    return repo


def test_unactivated_repo_receives_no_trailer_from_pretooluse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """FALSIFIER: attribution ON but repo NOT activated ⇒ passthrough, no mutation."""
    monkeypatch.setenv("HOME", str(_home_with_attribution_on(tmp_path)))
    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
    )

    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'},
        cwd=_repo(tmp_path, activated=False),
    )

    assert result is None
    assert capsys.readouterr().out == ""


def test_activated_repo_still_receives_the_trailer_from_pretooluse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys
) -> None:
    """COUNTERPROOF: an ACTIVATED repo keeps mutating — the fix gates, not kills."""
    monkeypatch.setenv("HOME", str(_home_with_attribution_on(tmp_path)))
    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
    )

    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'},
        cwd=_repo(tmp_path, activated=True),
    )

    assert result == 0
    assert "hookSpecificOutput" in capsys.readouterr().out


def test_activated_repo_with_attribution_off_stays_passthrough(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The two conditions are conjunctive: active alone does not attribute."""
    nwave = tmp_path / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "global-config.json").write_text(
        json.dumps({"attribution": {"enabled": False}}), encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        pre_tool_use_handler, "_commit_attribution_service", _MutatingService()
    )

    result = pre_tool_use_handler.emit_commit_attribution_mutation(
        {"command": 'git commit -m "x"'},
        cwd=_repo(tmp_path, activated=True),
    )

    assert result is None
