"""Acceptance tests for session-start routing in hook adapter.

AC-03-02: Running adapter with "session-start" argument invokes session_start_handler.
          Unknown command still exits 1. Existing routing unaffected.
"""

import json
import os
import sys
from unittest.mock import patch


def _capture_exit(module, argv):
    """Run module.main() with patched argv and capture exit code.

    Delenv's ``DES_PROJECT_DIR`` for the call: this test drives ``main()``
    directly against the ambient process cwd (no explicit chdir/stdin plumbing
    of its own), so it needs `resolve_nwave_root()` (now consulted by
    `activation_gate.apply_gate`) to fall through to that ambient cwd exactly
    as the pre-fix bare `Path.cwd()` did -- not the per-test isolation root the
    autouse `_isolate_nwave_root` fixture sets (tests/conftest.py), which has
    no `.nwave/des-config.json` and resolves as an inactive project, causing
    the activation gate to `sys.exit(0)` before the routing-under-test runs.
    """
    exits = []

    def fake_exit(code):
        exits.append(code)

    prior_des_project_dir = os.environ.get("DES_PROJECT_DIR")
    os.environ.pop("DES_PROJECT_DIR", None)
    try:
        with patch("sys.argv", argv), patch.object(sys, "exit", fake_exit):
            module.main()
    finally:
        if prior_des_project_dir is not None:
            os.environ["DES_PROJECT_DIR"] = prior_des_project_dir

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
