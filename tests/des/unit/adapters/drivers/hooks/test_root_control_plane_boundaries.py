"""What the PreToolUse boundary refuses once the mode protocol is retired.

The resident DES runner owns wave sequencing, route selection and mode. No hook
re-litigates any of that here. What remains are independent safety boundaries,
and they must still fire -- including for the root process itself.
"""

import io
import json
from unittest.mock import patch

import pytest

from des.adapters.drivers.hooks import hook_router


CANONICAL_DISPATCH = "printf '%s' \"$REQUEST\" | des dispatch --repo-root ROOT"


def _run_router(monkeypatch, action: str, envelope: dict) -> int:
    monkeypatch.setattr("sys.argv", ["hook_router", action])
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(envelope)))
    with pytest.raises(SystemExit) as exc_info:
        hook_router.main()
    return exc_info.value.code


@pytest.fixture
def active_project():
    with patch(
        "des.adapters.drivers.hooks.activation_gate._is_active_or_inactive_on_error",
        return_value=True,
    ):
        yield


@pytest.mark.parametrize(
    "envelope_extra",
    ({}, {"agent_id": "agent-7"}),
    ids=("root", "subagent"),
)
def test_canonical_dispatch_is_never_blocked(
    monkeypatch, capsys, active_project, tmp_path, envelope_extra
):
    """The public skills' one-line entry runs the canonical piped invocation.
    A hook that refuses it prevents the spine from being started at all -- so
    it must be allowed silently, from root as well as from a dispatched role,
    with no prior skill call, marker, or transcript in evidence."""
    exit_code = _run_router(
        monkeypatch,
        "pre-tool-use",
        {
            "tool_name": "Bash",
            "tool_input": {"command": CANONICAL_DISPATCH},
            "cwd": str(tmp_path),
            "session_id": "s-1",
            **envelope_extra,
        },
    )

    stdout = capsys.readouterr().out
    assert exit_code == 0, stdout
    assert "block" not in stdout


def test_nwave_subagent_host_wide_scan_still_blocks(
    monkeypatch, capsys, active_project, tmp_path
):
    """Independent safety boundary, no mode ceremony in its trigger."""
    exit_code = _run_router(
        monkeypatch,
        "pre-tool-use",
        {
            "tool_name": "Bash",
            "tool_input": {"command": "find / -name '*.py'"},
            "cwd": str(tmp_path),
            "agent_type": "nw-software-crafter",
        },
    )

    assert exit_code == 2
    assert json.loads(capsys.readouterr().out)["decision"] == "block"


def test_ordinary_nwave_dispatch_carries_no_route_reminder(
    monkeypatch, capsys, active_project, tmp_path
):
    """An nWave-adjacent Agent dispatch is allowed with an EMPTY response: no
    reminder, no route instruction, no classification demand injected into the
    dispatched role's context."""
    exit_code = _run_router(
        monkeypatch,
        "pre-task",
        {
            "tool_name": "Agent",
            "tool_input": {
                "subagent_type": "nw-software-crafter",
                "prompt": "deliver the vertical",
            },
            "cwd": str(tmp_path),
        },
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""
