"""Regression falsifiers for the pre-activation Bash safety ordering repair.

ADR-AG-001 ordering repair: `hook_router.main()` must evaluate the
consolidated git-stash / worktree-remove safety decision BEFORE
`activation_gate.apply_gate`, so an inactive project cannot exit 0 past a
live stash/worktree mutation. These drive the real router/public adapter
boundary (subprocess-free: `main()` over patched `sys.argv`/`sys.stdin`),
not the pure `bash_command_guards` predicate directly.
"""

import io
import json
from unittest.mock import patch

import pytest

from des.adapters.drivers.hooks import hook_router


def _envelope(cwd: str, command: str) -> str:
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": cwd,
            "session_id": "test-session",
        }
    )


def _run_router(monkeypatch, argv_command: str, stdin_text: str) -> int:
    monkeypatch.setattr("sys.argv", ["hook_router", argv_command])
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin_text))
    with pytest.raises(SystemExit) as exc_info:
        hook_router.main()
    return exc_info.value.code


@pytest.fixture
def inactive_project():
    with patch(
        "des.adapters.drivers.hooks.activation_gate._is_active_or_inactive_on_error",
        return_value=False,
    ):
        yield


@pytest.fixture
def active_project():
    with patch(
        "des.adapters.drivers.hooks.activation_gate._is_active_or_inactive_on_error",
        return_value=True,
    ):
        yield


def test_inactive_cwd_neutral_bash_is_silent_allow(
    monkeypatch, capsys, inactive_project, tmp_path
):
    stdin_text = _envelope(str(tmp_path), "echo hello")
    exit_code = _run_router(monkeypatch, "pre-tool-use", stdin_text)
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_inactive_cwd_git_stash_push_blocks(
    monkeypatch, capsys, inactive_project, tmp_path
):
    stdin_text = _envelope(str(tmp_path), "git stash push")
    exit_code = _run_router(monkeypatch, "pre-tool-use", stdin_text)
    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "git stash is forbidden" in payload["reason"]


def test_inactive_cwd_git_worktree_remove_blocks(
    monkeypatch, capsys, inactive_project, tmp_path
):
    from des.domain.worktree_anti_rot_triage import TriageState, WorktreeAntiRotReceipt

    dirty_receipt = WorktreeAntiRotReceipt(
        state=TriageState.LIVE,
        evidence=[],
        actions=["DEFER"],
        how="wait for the live owner to finish",
        unavailable_evidence=[],
    )
    stdin_text = _envelope(str(tmp_path), "git worktree remove /tmp/example")
    with patch(
        "des.application.worktree_triage_collector.collect_worktree_triage_receipt",
        return_value=dirty_receipt,
    ):
        exit_code = _run_router(monkeypatch, "pre-tool-use", stdin_text)
    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["decision"] == "block"
    assert "WORKTREE REMOVAL REFUSED" in payload["reason"]


def test_active_cwd_neutral_bash_evaluates_safety_guard_exactly_once(
    monkeypatch, capsys, active_project, tmp_path
):
    """Active-project routing/safety behaviour is unchanged: an allowed,
    reachable command (safety-neutral, agent_id set to sidestep the unrelated
    mode-select gate) is still evaluated by the safety guard exactly once --
    proving the retired in-handler call is truly gone, not merely that the
    router's own call short-circuited before a duplicate could run."""
    stdin_text = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": "git stash list"},
            "cwd": str(tmp_path),
            "session_id": "test-session",
            "agent_id": "agent-123",
        }
    )
    with patch(
        "des.adapters.drivers.hooks.hook_router.evaluate_bash_safety_guards",
        wraps=hook_router.evaluate_bash_safety_guards,
    ) as guard_call:
        exit_code = _run_router(monkeypatch, "pre-tool-use", stdin_text)
    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert guard_call.call_count == 1
