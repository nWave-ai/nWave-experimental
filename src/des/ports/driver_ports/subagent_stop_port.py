"""SubagentStopPort - driver port for validating step completion.

Abstract interface defining how the Claude Code hook adapter communicates
with the application layer for subagent-stop validation.

Called by: ClaudeCodeHookAdapter when SubagentStop hook fires.
Implemented by: SubagentStopService (application layer).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.ports.driver_ports.pre_tool_use_port import HookDecision


class SubagentStopReturnKind(Enum):
    """The only supported SubagentStop return shapes."""

    ATDD_PURE = "atdd_pure"
    WAVE_ONLY = "wave_only"


@dataclass(frozen=True)
class SubagentStopContext:
    """Input context for subagent-stop validation.

    Attributes:
        project_id: Project identifier
        return_kind: Typed discriminator for the closed return set:
            ``ATDD_PURE`` or ``WAVE_ONLY``.
        cwd: Working directory used by the applicable return path.
        turns_used: Optional observed turn count for an atdd_pure return.
        tokens_used: Optional observed token count for an atdd_pure return.
        slice_id: Carpaccio slice identifier (e.g. ``"slice-02"``). Populated
            for an ``ATDD_PURE`` return.
        atdd_pure_phase: The ATDD-pure phase value (A_GREEN..D_REFACTOR_COMMIT).
            Populated for an ``ATDD_PURE`` return.
        subagent_type: The returning agent's subagent_type (e.g. "nw-product-owner").
            The owner identity the cross-wave floor auto-close gates on: the
            wave-active floor closes on a terminal gate-OUT PASS ONLY when this
            returning agent is the ACTIVE wave's OWNER (WAVE_OWNERS[subagent_type]
            == active wave). Empty when the return is not a wave-owner dispatch.
    """

    project_id: str
    return_kind: SubagentStopReturnKind
    cwd: str = ""
    turns_used: int | None = None
    tokens_used: int | None = None
    slice_id: str | None = None
    atdd_pure_phase: str | None = None
    subagent_type: str = ""


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
