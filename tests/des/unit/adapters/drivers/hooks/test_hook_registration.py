"""Unit tests for deliver-progress hook registration and routing.

Step 01-02: Register deliver-progress as second SubagentStop hook event
and wire router dispatch.

Test Budget: 3 behaviors x 2 = 6 unit tests max.
Behaviors:
  B1: HOOK_EVENTS has 3 SubagentStop entries with correct actions/matchers
      (slice-04 of atdd-spine-ledger-enforcement-gate-v2 added the
      `subagent-stop-spine-detector` entry as the 3rd SubagentStop, was 2)
  B2: Router dispatches deliver-progress to handle_deliver_progress
  B3: generate_hook_config produces 3 SubagentStop entries without matcher
      (slice-04 lift from 2 -> 3)
"""

from __future__ import annotations

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


class TestHookEventsSubagentStopEntries:
    """B1: HOOK_EVENTS has exactly 3 SubagentStop entries (post-slice-04)."""

    def test_three_subagent_stop_entries_exist(self):
        """HOOK_EVENTS contains exactly 3 SubagentStop entries.

        slice-04 of atdd-spine-ledger-enforcement-gate-v2 lifted the
        SubagentStop count from 2 -> 3 by adding the spine-ledger detector
        entry (`subagent-stop-spine-detector`) adjacent to the existing
        `subagent-stop` (DES adapter) + `deliver-progress` entries.
        """
        from scripts.shared.hook_definitions import HOOK_EVENTS

        subagent_stop_events = [h for h in HOOK_EVENTS if h.event == "SubagentStop"]
        assert len(subagent_stop_events) == 3

    def test_subagent_stop_actions_are_correct(self):
        """SubagentStop entries have the 3 expected actions (post-slice-04)."""
        from scripts.shared.hook_definitions import HOOK_EVENTS

        subagent_stop_events = [h for h in HOOK_EVENTS if h.event == "SubagentStop"]
        actions = [h.action for h in subagent_stop_events]
        assert actions == [
            "subagent-stop",
            "deliver-progress",
            "subagent-stop-spine-detector",
        ]

    def test_subagent_stop_entries_have_no_matcher(self):
        """All 3 SubagentStop entries have matcher=None (Claude Code SubagentStop
        does not use a matcher field)."""
        from scripts.shared.hook_definitions import HOOK_EVENTS

        subagent_stop_events = [h for h in HOOK_EVENTS if h.event == "SubagentStop"]
        assert all(h.matcher is None for h in subagent_stop_events)


class TestRouterDeliverProgressDispatch:
    """B2: Router dispatches deliver-progress to handle_deliver_progress."""

    def test_deliver_progress_routes_to_handler(self):
        """deliver-progress command dispatches to handle_deliver_progress."""
        from des.adapters.drivers.hooks import hook_router

        with patch.object(
            hook_router,
            "handle_deliver_progress",
            return_value=0,
        ) as mock_handler:
            _capture_exit(hook_router, ["adapter", "deliver-progress"])

        mock_handler.assert_called_once()

    def test_deliver_progress_returns_exit_code_0(self):
        """deliver-progress forwards handler return value as exit code."""
        from des.adapters.drivers.hooks import hook_router

        with patch.object(
            hook_router,
            "handle_deliver_progress",
            return_value=0,
        ):
            exits = _capture_exit(hook_router, ["adapter", "deliver-progress"])

        assert exits == [0]


class TestGenerateHookConfigSubagentStop:
    """B3: generate_hook_config produces 3 SubagentStop entries without matcher
    (post-slice-04: was 2, +1 from spine-ledger detector)."""

    def test_config_has_three_subagent_stop_hooks(self):
        """SubagentStop list in generated config contains exactly 3 entries.

        slice-04 of atdd-spine-ledger-enforcement-gate-v2 added the
        `subagent-stop-spine-detector` entry as a 3rd SubagentStop hook.
        The new entry carries a `shell_command` so its command in the
        generated config is the verbatim shell-form string (not the
        templated `cmd {action}` from the command_fn).
        """
        from scripts.shared.hook_definitions import generate_hook_config

        config = generate_hook_config(command_fn=lambda action: f"cmd {action}")
        subagent_stop_entries = config["SubagentStop"]
        assert len(subagent_stop_entries) == 3

        # No entry has a matcher field (SubagentStop schema)
        for entry in subagent_stop_entries:
            assert "matcher" not in entry

        # Verify correct action commands are wired; the 3rd entry uses
        # the verbatim shell_command (`# des-hook:` marker prefix +
        # module-import body).
        commands = [entry["hooks"][0]["command"] for entry in subagent_stop_entries]
        assert commands[0] == "cmd subagent-stop"
        assert commands[1] == "cmd deliver-progress"
        assert commands[2].startswith("# des-hook:subagent-stop-spine-detector")
        assert "spine_ledger_subagent_stop_detector" in commands[2]
