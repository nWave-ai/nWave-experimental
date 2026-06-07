"""SubagentStopPort - driver port for validating step completion.

Abstract interface defining how the Claude Code hook adapter communicates
with the application layer for subagent-stop validation.

Called by: ClaudeCodeHookAdapter when SubagentStop hook fires.
Implemented by: SubagentStopService (application layer).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.ports.driver_ports.pre_tool_use_port import HookDecision


@dataclass(frozen=True)
class SubagentStopContext:
    """Input context for subagent-stop validation.

    Attributes:
        execution_log_path: Absolute path to execution-log.json. Empty under
            ``mode == "atdd_pure"`` — atdd_pure produces no execution-log.
        project_id: Project identifier
        step_id: Step identifier. Empty under ``mode == "atdd_pure"`` — an
            atdd_pure dispatch is identified by ``slice_id``, not a step id.
        stop_hook_active: True if SubagentStop already fired once (second attempt).
            When True and validation fails, service allows to prevent infinite loops.
        cwd: Working directory for git commit verification. Empty string skips
            git verification (backward compatibility).
        mode: Dispatch workflow mode (``"classic"`` | ``"atdd_pure"``). The
            mode discriminant for T-C: under ``"atdd_pure"`` the SubagentStop
            validator takes a path that does NOT read an execution-log.json
            (atdd_pure is roadmap-free / execution-log-free by design).
        slice_id: Carpaccio slice identifier (e.g. ``"slice-02"``). Populated
            for atdd_pure dispatches; None for classic.
        atdd_pure_phase: The ATDD-pure phase value (A_GREEN..D_REFACTOR_COMMIT).
            Populated for atdd_pure dispatches; None for classic.
    """

    execution_log_path: str
    project_id: str
    step_id: str
    stop_hook_active: bool = False
    cwd: str = ""
    task_start_time: str = ""
    turns_used: int | None = None
    tokens_used: int | None = None
    # --- atdd_pure dispatch discriminant (T-C / F-DES-ATDD-PURE-DISPATCH-LIFECYCLE)
    mode: str = "classic"
    slice_id: str | None = None
    atdd_pure_phase: str | None = None


class SubagentStopPort(ABC):
    """Driver port: validates step completion when a subagent finishes.

    This is the application-layer interface that the hook adapter calls.
    The adapter translates Claude Code's JSON protocol into SubagentStopContext,
    calls this port, and translates HookDecision back to JSON + exit code.
    """

    @abstractmethod
    def validate(self, context: SubagentStopContext) -> HookDecision:
        """Validate step completion for a subagent.

        Args:
            context: Parsed context from the hook protocol

        Returns:
            HookDecision indicating allow or block
        """
        ...
