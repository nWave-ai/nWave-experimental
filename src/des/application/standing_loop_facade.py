"""The sole operator-facing driving facade for standing-loop control."""

from __future__ import annotations

import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from des.application.loop_runner import (
    IdempotencyConflict,
    LoopControlService,
    LoopRunner,
)


if TYPE_CHECKING:
    from des.ports.standing_loop_ports import (
        StandingLoopControlPort,
        StandingLoopTickPort,
    )


@dataclass(frozen=True)
class StandingLoopInspection:
    outcome: str
    context_mode: str
    limits: dict[str, int]
    started: bool = False


@dataclass(frozen=True)
class LoopDiagnostic:
    code: str
    what: str
    why: str
    how: str


@dataclass(frozen=True)
class LoopRefusal:
    status: str
    diagnostic: LoopDiagnostic


class StandingLoopFacade:
    """Delegates operator control and occurrence execution to their ports.

    It never claims an occurrence, creates an attestation, touches a ledger, or
    invokes a scheduler.  Both manual and scheduler drivers normalize an
    occurrence and call the same ``StandingLoopTickPort.execute_tick`` boundary.
    """

    def __init__(
        self,
        control: StandingLoopControlPort | None = None,
        tick_port: StandingLoopTickPort | None = None,
    ) -> None:
        self._control = control or LoopControlService()
        self._tick_port = tick_port or LoopRunner()

    def inspect(self, work: Any) -> StandingLoopInspection:
        return StandingLoopInspection(
            outcome=work.outcome,
            context_mode=work.context_mode,
            limits={
                "max_tokens_per_tick": work.max_tokens_per_tick,
                "max_wall_seconds": work.max_wall_seconds,
                "max_agent_concurrency": work.max_agent_concurrency,
                "max_box_concurrency": work.max_box_concurrency,
            },
        )

    def arm(self, work: Any, *, idempotency_key: str) -> Any:
        if any(
            limit <= 0
            for limit in (
                work.max_tokens_per_tick,
                work.max_wall_seconds,
                work.max_agent_concurrency,
                work.max_box_concurrency,
            )
        ):
            return LoopRefusal(
                status="refused",
                diagnostic=LoopDiagnostic(
                    code="INVALID_LIMIT",
                    what="A standing-loop resource limit is not positive.",
                    why=(
                        "A zero or negative limit cannot authorise a bounded "
                        "continued-work occurrence."
                    ),
                    how=(
                        "Supply a positive token, wall-time, agent, and box "
                        "limit before arming the loop."
                    ),
                ),
            )
        if work.context_mode == "native_chat":
            return LoopRefusal(
                status="refused",
                diagnostic=LoopDiagnostic(
                    code="CONTEXT_CONTINUITY_UNPROVED",
                    what="Native-chat continuity has not been proved.",
                    why=(
                        "Proof-shaped caller input cannot prove a fresh, challenge-bound "
                        "resume of the original host conversation."
                    ),
                    how=(
                        "Use reconstructed context until the host adapter has issued and "
                        "verified a fresh project-bound continuity receipt."
                    ),
                ),
            )
        try:
            return self._control.arm(work, idempotency_key=idempotency_key)
        except IdempotencyConflict:
            return LoopRefusal(
                status="refused",
                diagnostic=LoopDiagnostic(
                    code="IDEMPOTENCY_CONFLICT",
                    what="This idempotency key was already used for a different arm request.",
                    why="An authority key must preserve the original bounded request.",
                    how="Reuse the original request or choose a new idempotency key.",
                ),
            )

    def list(self, project_root: Any) -> tuple[Any, ...]:
        return self._control.list(project_root)

    def offer_for_session_start(
        self, project_root: Any
    ) -> StandingLoopInspection | None:
        """Return the armed project's bounded opportunity without executing it."""
        records = self._control.list(project_root)
        armed = next(
            (
                record
                for record in records
                if record.desired_state == "ARMED" and record.due_at <= time.time()
            ),
            None,
        )
        if armed is None:
            return None
        return StandingLoopInspection(
            outcome=armed.outcome,
            context_mode="reconstructed",
            limits=dict(armed.limits),
        )

    def execute_for_session_start(
        self, project_root: Any
    ) -> tuple[StandingLoopInspection, Any] | None:
        """Execute one due record through the canonical tick boundary."""
        records = self._control.list(project_root)
        attested_occurrences = {
            payload.get("occurrence_key")
            for payload in self._control.attestation_payloads(project_root)
        }

        def has_attestation(record: Any) -> bool:
            return f"codex-session-start:{record.loop_id}" in attested_occurrences

        fresh_due = next(
            (
                record
                for record in records
                if record.due_at <= time.time()
                and record.desired_state == "ARMED"
                and not has_attestation(record)
            ),
            None,
        )
        terminal_replay = next(
            (
                record
                for record in records
                if record.due_at <= time.time()
                and record.desired_state == "STOPPED"
                and has_attestation(record)
            ),
            None,
        )
        armed = (
            fresh_due
            or terminal_replay
            or next(
                (
                    record
                    for record in records
                    if record.due_at <= time.time() and has_attestation(record)
                ),
                None,
            )
        )
        if armed is None:
            return None
        inspection = StandingLoopInspection(
            outcome=armed.outcome,
            context_mode="reconstructed",
            limits=dict(armed.limits),
        )
        occurrence = SimpleNamespace(
            loop_id=armed.loop_id,
            idempotency_key=f"codex-session-start:{armed.loop_id}",
        )
        return inspection, self.manual_tick(project_root, occurrence)

    def manual_tick(self, project_root: Any, occurrence: Any) -> Any:
        inputs = self._control.execution_inputs(project_root, occurrence)
        return self._tick_port.execute_tick(
            occurrence,
            inputs.context_capsule,
            inputs.budget,
            inputs.isolation,
        )

    def recover(
        self,
        project_root: Any,
        *,
        apply: bool = False,
        idempotency_key: str = "recover-plan",
    ) -> Any:
        return self._control.recover(
            project_root, apply=apply, idempotency_key=idempotency_key
        )

    def stop(
        self, project_root: Any, handle: Any, *, idempotency_key: str = "direct-stop"
    ) -> Any:
        return self._control.stop(project_root, handle, idempotency_key=idempotency_key)


__all__ = [
    "LoopDiagnostic",
    "LoopRefusal",
    "StandingLoopFacade",
    "StandingLoopInspection",
]
