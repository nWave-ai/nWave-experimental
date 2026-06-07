"""Acceptance tests for session-start routing in hook adapter.

AC-03-02: Running adapter with "session-start" argument invokes session_start_handler.
          Unknown command still exits 1. Existing routing unaffected.
"""

import json
import sys
from unittest.mock import patch


def _capture_exit(module, argv):
    """Run module.main() with patched argv and capture exit code."""
    exits = []

    def fake_exit(code):
        exits.append(code)

    with patch("sys.argv", argv), patch.object(sys, "exit", fake_exit):
        module.main()

    return exits


class TestSessionStartRoutingAcceptance:
    """Acceptance: session-start dispatches to session_start_handler via adapter."""

    def test_session_start_command_dispatches_to_handler(self):
        """Running adapter with 'session-start' routes to session_start_handler."""
        from des.adapters.drivers.hooks import hook_router

        with patch.object(
            hook_router,
            "handle_session_start",
            return_value=0,
        ) as mock_handler:
            exits = _capture_exit(hook_router, ["adapter", "session-start"])

        mock_handler.assert_called_once()
        assert exits == [0]

    def test_unknown_command_exits_1(self, capsys):
        """Unknown command still exits 1 (existing behaviour unchanged)."""
        from des.adapters.drivers.hooks import hook_router

        exits = _capture_exit(hook_router, ["adapter", "not-a-real-command"])

        assert exits == [1]
        captured = capsys.readouterr()
        output = json.loads(captured.out.strip())
        assert output["status"] == "error"
