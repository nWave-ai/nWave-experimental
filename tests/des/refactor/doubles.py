"""Test doubles -- des-refactor-fixer-swarm slice-02 concurrency observability.

CREATE_NEW (feature-delta Test Reuse & Consolidation Analysis). No existing
double models ``MergeLockPort``/``AgentInvocationPort``/``EnvProvisionPort``
with the deterministic-ordering-observability + fault-injection slice-02's
ATs need (the ports themselves are net-new, or -- for ``AgentInvocationPort``
-- need a controllable-concurrency variant slice-01's real
``ShellAgentInvocationAdapter`` cannot provide on its own).

Three doubles:

* ``RecordingMergeLock`` -- wraps a REAL ``threading.Lock`` with an
  append-only event log, so an AT asserts the critical section was NEVER
  held by two items at once via a DETERMINISTIC invariant (mutual exclusion
  enforced by the underlying real lock, witnessed by the log's own
  high-water mark) rather than a timing-dependent race the test would have
  to get lucky to observe.
* ``BarrierGatedAgentInvocationPort`` -- wraps a REAL delegate adapter but
  forces every lane's ``invoke()`` call to rendezvous at a
  ``threading.Barrier`` before any of them proceeds -- deterministic PROOF
  that N reasoning lanes were in-flight simultaneously (the barrier
  physically cannot release until N=parties calls have all arrived; a
  serialized caller would deadlock at the timeout instead of a flaky
  overlap that sometimes doesn't happen).
* ``FakeEnvProvisionPort`` -- the driven-external/non-deterministic port
  class defaults to a fake with output capture (Architecture of Reference,
  `nw-distill-port-treatment-policy`): writes a per-worktree marker instead
  of paying a real (slow) ``uv sync`` per concurrent item, and records every
  provisioned path so an AT asserts isolation (no two items share a path)
  without the real provisioning cost.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from des.ports.driven_ports.agent_invocation_port import (
    AgentInvocationPort,
    AgentInvocationResult,
)
from des.ports.driven_ports.env_provision_port import EnvProvisionPort
from des.ports.driven_ports.merge_lock_port import MergeLockPort


@dataclass(frozen=True)
class LockEvent:
    """One acquire/release event in the merge-lock's observable timeline.

    ``open_sections_after`` is the count of held-but-not-yet-released
    sections immediately after this event -- the witness a correctly
    serialized batch keeps at exactly 0 or 1, never 2+.
    """

    item_id: str
    kind: str  # "acquire" | "release"
    open_sections_after: int


class RecordingMergeLock(MergeLockPort):
    """Real mutual exclusion (``threading.Lock``) + an append-only witness
    log an AT reads to assert the critical section was never held by two
    items at once."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._log_guard = threading.Lock()
        self._open_count = 0
        self.events: list[LockEvent] = []

    def acquire(self, item_id: str) -> None:
        self._lock.acquire()
        with self._log_guard:
            self._open_count += 1
            self.events.append(LockEvent(item_id, "acquire", self._open_count))

    def release(self, item_id: str) -> None:
        with self._log_guard:
            self._open_count -= 1
            self.events.append(LockEvent(item_id, "release", self._open_count))
        self._lock.release()

    def max_concurrent_holders(self) -> int:
        """The high-water mark of simultaneously-open critical sections --
        must be exactly 1 for a correctly serialized batch (the observable
        the never-overlap AT asserts on)."""
        return max((event.open_sections_after for event in self.events), default=0)

    def acquire_release_counts_balance(self) -> bool:
        """Conservation witness: every acquire has a matching release (a
        leaked/missing lock cycle would deadlock or falsely free a sibling
        lane -- the PARTITION closure obligation for this event log)."""
        acquires = sum(1 for event in self.events if event.kind == "acquire")
        releases = sum(1 for event in self.events if event.kind == "release")
        return acquires == releases


class BarrierGatedAgentInvocationPort(AgentInvocationPort):
    """Wraps a REAL delegate adapter; every ``invoke()`` rendezvous at a
    ``threading.Barrier`` shared across ``parties`` lanes before any of them
    proceeds -- deterministic proof that N reasoning lanes were in-flight at
    once (the barrier cannot release early; a serialized caller times out
    instead of silently passing)."""

    def __init__(self, delegate: AgentInvocationPort, parties: int) -> None:
        self._delegate = delegate
        self._barrier = threading.Barrier(parties)
        self._log_guard = threading.Lock()
        self.rendezvoused_worktree_names: list[str] = []

    def probe(self, agent_cmd: str) -> bool:
        return self._delegate.probe(agent_cmd)

    def invoke(
        self, agent_cmd: str, prompt_path: Path, worktree_path: Path
    ) -> AgentInvocationResult:
        with self._log_guard:
            self.rendezvoused_worktree_names.append(worktree_path.name)
        self._barrier.wait(timeout=10)
        return self._delegate.invoke(agent_cmd, prompt_path, worktree_path)


@dataclass
class FakeEnvProvisionPort(EnvProvisionPort):
    """Driven-external fake (Architecture of Reference default): writes a
    distinguishing marker instead of a real ``uv sync``; records every
    provisioned path for the isolation oracle."""

    provisioned_paths: list[Path] = field(default_factory=list)

    def probe(self) -> bool:
        return True

    def provision(self, worktree_path: Path) -> Path:
        venv = worktree_path / ".venv"
        venv.mkdir(parents=True, exist_ok=True)
        (venv / "provisioned-for.marker").write_text(
            worktree_path.name, encoding="utf-8"
        )
        self.provisioned_paths.append(worktree_path)
        return venv / "bin" / "python"
