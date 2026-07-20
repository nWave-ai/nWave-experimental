"""MergeLockPort -- driven port serializing the shared-box critical section
across concurrently-draining pile items (des-refactor-fixer-swarm slice-02).

CREATE_NEW (ADR-SWARM-001, design doc §9: "LLM reasoning lanes = cloud (scale
dynamically); green-to-green verification = serialised on the shared box.").
``RefactorDrainService.drain_batch`` acquires this lock around ONLY the
green-to-green run + merge-back for each item -- worktree creation, venv
provisioning, and agent dispatch stay OUTSIDE the lock (those lanes run
concurrently across items); only the shared-box-serial section is gated, so
the throughput ceiling is the box's serial fast+impacted run-rate, never the
agent count.

Pure interface -- no behavior to scaffold. The concrete adapter
(``des.adapters.driven.refactor.threading_merge_lock.ThreadingMergeLock``)
is a thin ``threading.Lock`` wrapper.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class MergeLockPort(ABC):
    """Driven port: mutual exclusion around the green-to-green+merge-back
    critical section shared by every concurrently-draining item."""

    @abstractmethod
    def acquire(self, item_id: str) -> None:
        """Block until the shared-box critical section is free, then hold it
        for ``item_id``. Callers MUST pair every ``acquire`` with a
        ``release`` (via ``try/finally``) -- an unreleased lock deadlocks
        every sibling lane."""
        ...

    @abstractmethod
    def release(self, item_id: str) -> None:
        """Release the critical section ``item_id`` is holding."""
        ...
