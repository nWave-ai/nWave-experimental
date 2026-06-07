"""Hook port for post-execution validation.

Driven port: DES calls outward to validation hooks after sub-agent completion.
Extracted from orchestrator.py as part of P3 decomposition.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class HookResult:
    """Result from hook validation."""

    validation_status: str
    hook_fired: bool = True
    abandoned_phases: list[str] = field(default_factory=list)
    incomplete_phases: list[str] = field(default_factory=list)
    invalid_skips: list[str] = field(default_factory=list)
    error_count: int = 0
    error_type: str | None = None
    error_message: str | None = None
    recovery_suggestions: list[str] = field(default_factory=list)
    not_executed_phases: int = 0
    turn_limit_exceeded: bool = False
    timeout_exceeded: bool = False


class HookPort(ABC):
    """Port for post-execution validation hooks."""

    @abstractmethod
    def persist_turn_count(
        self, step_file_path: str, phase_name: str, turn_count: int
    ) -> None:
        """Persist turn_count to phase_execution_log entry."""
        pass

    @abstractmethod
    def on_agent_complete(self, step_file_path: str) -> HookResult:
        """Validate step file after sub-agent completion."""
        pass
