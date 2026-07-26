"""Acceptance composition root for the slice-04 standing-loop control surface."""

from __future__ import annotations

from typing import Any

from .domain_types_slice_04_standing_loop import ContinuedWork, ManualOccurrence


class StandingLoopComposition:
    """Drive one future facade; never construct or substitute a LoopRunner."""

    @staticmethod
    def _facade() -> Any:
        try:
            from des.application.standing_loop_facade import StandingLoopFacade
        except ModuleNotFoundError as exc:
            if exc.name != "des.application.standing_loop_facade":
                raise
            raise AssertionError(
                "WHAT: slice-04 has no StandingLoopFacade. "
                "WHY: an operator cannot inspect, arm, tick, recover, or stop "
                "continued work through one control surface. "
                "HOW: implement StandingLoopFacade over StandingLoopControlPort and "
                "StandingLoopTickPort, reusing LoopRunner behind the tick port."
            ) from None
        return StandingLoopFacade()

    def inspect(self, work: ContinuedWork) -> Any:
        return self._facade().inspect(work)

    def arm(self, work: ContinuedWork, *, idempotency_key: str) -> Any:
        return self._facade().arm(work, idempotency_key=idempotency_key)

    def list(self, project_root: object) -> Any:
        return self._facade().list(project_root)

    def tick(self, project_root: object, occurrence: ManualOccurrence) -> Any:
        return self._facade().manual_tick(project_root, occurrence)

    def recover(self, project_root: object) -> Any:
        return self._facade().recover(project_root)

    def stop(self, project_root: object, handle: object) -> Any:
        return self._facade().stop(project_root, handle)
