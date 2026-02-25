"""Unit tests for SubagentStart hook handler.

Tests all behaviors via handle_subagent_start() driving port.
Test budget: 4 behaviors x 2 = 8 unit tests max (using 7).

Behaviors:
  B1: nWave sub-agents (nw-*) receive additionalContext injection
  B2: Non-nWave sub-agents receive no injection (no stdout)
  B3: Output JSON format matches spec (imperative reminder with agent_type)
  B4: Fail-open — any exception exits 0, no stdout
"""

import io
import json
from unittest.mock import patch

import pytest


class TestNwAgentReceivesAdditionalContext:
    """B1: nWave sub-agents (nw-*) receive additionalContext injection."""

    def test_nw_agent_writes_additional_context_to_stdout(self, capsys):
        """nw-software-crafter receives additionalContext JSON on stdout."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-123",
                "hook_event_name": "SubagentStart",
                "agent_type": "nw-software-crafter",
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        assert "additionalContext" in payload

    @pytest.mark.parametrize(
        "agent_type",
        ["nw-solution-architect", "nw-acceptance-designer", "nw-researcher"],
    )
    def test_all_nw_prefixed_agents_receive_injection(self, capsys, agent_type):
        """Any agent_type starting with 'nw-' receives additionalContext."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-abc",
                "hook_event_name": "SubagentStart",
                "agent_type": agent_type,
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        assert "additionalContext" in payload


class TestNonNwAgentReceivesNoInjection:
    """B2: Non-nWave sub-agents receive no injection."""

    def test_non_nw_agent_produces_no_stdout(self, capsys):
        """agent_type not starting with 'nw-' produces no stdout output."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-456",
                "hook_event_name": "SubagentStart",
                "agent_type": "general-purpose",
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""

    def test_explore_agent_produces_no_stdout(self, capsys):
        """Explore agent type produces no stdout output."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-789",
                "hook_event_name": "SubagentStart",
                "agent_type": "Explore",
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""


class TestAdditionalContextMessageFormat:
    """B3: Output JSON format matches spec — imperative reminder with agent_type."""

    def test_additional_context_contains_agent_type(self, capsys):
        """additionalContext message includes the agent_type."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-001",
                "hook_event_name": "SubagentStart",
                "agent_type": "nw-software-crafter",
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            handle_subagent_start()

        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        msg = payload["additionalContext"]
        assert "nw-software-crafter" in msg, (
            "additionalContext must include the agent_type in the message"
        )

    def test_additional_context_message_matches_spec_format(self, capsys):
        """additionalContext message matches imperative reminder spec format."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps(
            {
                "session_id": "sess-002",
                "hook_event_name": "SubagentStart",
                "agent_type": "nw-solution-architect",
            }
        )

        with patch("sys.stdin", io.StringIO(hook_input)):
            handle_subagent_start()

        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        msg = payload["additionalContext"]
        # Must be an imperative reminder referencing skills path
        assert "MANDATORY" in msg
        assert "nw-solution-architect" in msg
        assert "~/.claude/skills/nw/nw-solution-architect/" in msg


class TestSubagentStartHandlerFailOpen:
    """B4: Any exception exits 0 (fail-open) — session must not be blocked."""

    def test_exception_in_handler_exits_0_with_no_output(self, capsys):
        """Exception during handling: exits 0, no stdout output."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        # Malformed JSON — simulates protocol error
        with patch("sys.stdin", io.StringIO("not valid json {")):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""

    def test_missing_agent_type_field_exits_0_with_no_output(self, capsys):
        """Hook input missing agent_type: exits 0, no stdout output."""
        from des.adapters.drivers.hooks.subagent_start_handler import (
            handle_subagent_start,
        )

        hook_input = json.dumps({"session_id": "sess-999"})

        with patch("sys.stdin", io.StringIO(hook_input)):
            exit_code = handle_subagent_start()

        assert exit_code == 0
        assert capsys.readouterr().out.strip() == ""
