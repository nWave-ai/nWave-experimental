"""Vendor-neutral contracts for standing-loop control and semantic ticks."""

from __future__ import annotations

from typing import Any, Protocol


class StandingLoopControlPort(Protocol):
    """Owns desired/observed loop control, never semantic occurrence execution."""

    def arm(self, work: Any, *, idempotency_key: str) -> Any: ...

    def list(self, project_root: Any) -> tuple[Any, ...]: ...

    def stop(self, project_root: Any, handle: Any) -> Any: ...

    def recover(self, project_root: Any) -> Any: ...

    def execution_inputs(self, project_root: Any, occurrence: Any) -> Any: ...


class StandingLoopTickPort(Protocol):
    """Executes exactly one normalized occurrence through the claim boundary."""

    def execute_tick(
        self,
        occurrence: Any,
        context_capsule: Any,
        budget: Any,
        isolation: Any,
    ) -> Any: ...


__all__ = ["StandingLoopControlPort", "StandingLoopTickPort"]
