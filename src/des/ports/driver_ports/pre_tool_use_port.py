"""PreToolUsePort - driver port for validating Agent tool invocations.

Abstract interface defining how the Claude Code hook adapter communicates
with the application layer for pre-tool-use validation.

Called by: ClaudeCodeHookAdapter when PreToolUse hook fires for Agent tool.
Implemented by: PreToolUseService (application layer).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PreToolUseInput:
    """Input data for pre-tool-use validation.

    Attributes:
        prompt: Full Agent tool prompt text
        subagent_type: Type of subagent being created
        wave_entering: True iff this dispatch is the wave-ENTERING dispatch
            (slice-07c F3 NORMATIVO). Computed by the HOOK ADAPTER from the
            anchor-owned ``entry_pending`` flag on the wave-active floor
            (``WaveActivationService.peek_entry``) -- deterministic,
            never derived from prompt wording (AD-66 closed).
    """

    prompt: str
    subagent_type: str = ""
    wave_entering: bool = False


@dataclass(frozen=True)
class HookDecision:
    """Decision result from a hook validation.

    Shared by both PreToolUsePort and SubagentStopPort.

    Attributes:
        action: "allow" or "block"
        reason: Block reason (None when allowed)
        exit_code: 0=allow, 2=block
        recovery_suggestions: Actionable steps to fix block (empty when allowed)
        warning: Non-blocking advisory to surface LOUD on an allow decision
            (GDP-6 -- degrade-LOUD, never silent-wrong). ``None`` on every
            ordinary allow (byte-identical to before this field existed); set
            ONLY when the gate consciously chose not to veto something it
            noticed (e.g. an INFERRED wave floor past its own TTL). The
            adapter renders it via ``permissionDecisionReason`` on the SAME
            "allow" decision -- it never changes ``exit_code``.
    """

    action: str  # "allow" | "block"
    reason: str | None = None
    exit_code: int = 0
    recovery_suggestions: list[str] = field(default_factory=list)
    warning: str | None = None

    @staticmethod
    def allow(warning: str | None = None) -> HookDecision:
        """Create an allow decision, optionally carrying a LOUD advisory."""
        return HookDecision(action="allow", exit_code=0, warning=warning)

    @staticmethod
    def block(
        reason: str, recovery_suggestions: list[str] | None = None
    ) -> HookDecision:
        """Create a block decision with reason."""
        return HookDecision(
            action="block",
            reason=reason,
            exit_code=2,
            recovery_suggestions=recovery_suggestions or [],
        )


class PreToolUsePort(ABC):
    """Driver port: validates Agent tool invocations before execution.

    This is the application-layer interface that the hook adapter calls.
    The adapter translates Claude Code's JSON protocol into PreToolUseInput,
    calls this port, and translates HookDecision back to JSON + exit code.
    """

    @abstractmethod
    def validate(self, input_data: PreToolUseInput) -> HookDecision:
        """Validate an Agent tool invocation.

        Args:
            input_data: Parsed input from the hook protocol

        Returns:
            HookDecision indicating allow or block
        """
        ...
