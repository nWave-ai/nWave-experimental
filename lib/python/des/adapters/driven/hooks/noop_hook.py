"""No-op hook adapter for DES orchestrator.

Used by create_with_defaults() since production validation runs through
claude_code_hook_adapter -> SubagentStopService, bypassing the orchestrator's hook.
"""

from __future__ import annotations

from des.ports.driven_ports.hook_port import HookPort, HookResult


class NoOpHook(HookPort):
    """Minimal HookPort that always passes."""

    def persist_turn_count(
        self, step_file_path: str, phase_name: str, turn_count: int
    ) -> None:
        pass

    def on_agent_complete(self, step_file_path: str) -> HookResult:
        return HookResult(validation_status="PASSED")
