"""ThreadingMergeLock -- MergeLockPort implementation via ``threading.Lock``.

CREATE_NEW (des-refactor-fixer-swarm slice-02). The production default:
a real, process-local mutual-exclusion lock around each item's
green-to-green+merge-back critical section. One ``des refactor`` process ==
one shared box == one lock; a future multi-process/multi-box driver would
need a file-lock or distributed-lock adapter behind the SAME port, not a
port-shape change.
"""

from __future__ import annotations

import threading

from des.ports.driven_ports.merge_lock_port import MergeLockPort


class ThreadingMergeLock(MergeLockPort):
    """Real adapter -- one process-local ``threading.Lock``."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def acquire(self, item_id: str) -> None:
        self._lock.acquire()

    def release(self, item_id: str) -> None:
        self._lock.release()
