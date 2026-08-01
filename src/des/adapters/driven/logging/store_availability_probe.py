"""StoreAvailabilityProbe -- the Earned Trust canary probe (DD-14, principle 13).

RED scaffold authored by DISTILL (unified-event-store slice-02). DELIVER
wires the real canary write/flock/read/delete against
`.nwave/telemetry/` (via `des.domain.telemetry_paths`) and classifies the
induced fault (missing directory / permission-denied / not-a-directory /
ENOSPC) into a `StoreProbeFailed(fault=..., path=..., message=...)` naming
WHAT failed, WHY it matters, and HOW to fix it -- never a bare traceback,
never a silent `ProbeResult(ok=False, ...)` (Probeable's own contract
forbids an ok=False return; failure is ALWAYS an exception).

`UnifiedEventStoreAdapter.probe()` DELEGATES to this class (peer-review
MEDIUM finding, closed -- feature-delta.md [REF] Driven Ports + Adapters):
this is the ONLY place canary write/flock/read/delete logic may live: a
second inline copy inside the adapter would violate witness-independence
(GDP-8) -- two checks sharing one implementation are one check wearing two
names, not two differently-lensed checks.
"""

from __future__ import annotations

import errno
import fcntl
import uuid
from typing import TYPE_CHECKING

from des.domain.telemetry_paths import telemetry_root
from des.ports.driven_ports.probeable_port import ProbeResult, StoreProbeFailed


if TYPE_CHECKING:
    from pathlib import Path


class StoreAvailabilityProbe:
    """RED scaffold -- DELIVER slice-02 wires the real canary round-trip.

    Fault-injection contract DELIVER must satisfy (feature-delta.md Runtime
    Contract Matrix + the slice-02 expectation charter, EXP-unified-event-
    store-1):

    * missing directory  -> `StoreProbeFailed(fault="missing-directory", ...)`
    * permission denied  -> `StoreProbeFailed(fault="permission-denied", ...)`
    * path not a directory -> `StoreProbeFailed(fault="not-a-directory", ...)`
    * ENOSPC (injected `OSError(errno.ENOSPC, ...)` at the write seam, since a
      real full disk cannot be induced portably with Python + filesystem
      alone) -> `StoreProbeFailed(fault="enospc", ...)`
    * healthy substrate -> `ProbeResult(ok=True, ...)`, and the canary
      write/flock/read/delete leaves NO residue under `.nwave/telemetry/`.

    Every `StoreProbeFailed.message` names the concrete path attempted (so a
    refusal can never point outside the `--repo-root` sandbox it was given)
    and is WHAT/WHY/HOW-shaped.
    """

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def probe(self) -> ProbeResult:
        root = telemetry_root(self._project_root)

        if not root.exists():
            raise StoreProbeFailed(
                fault="missing-directory",
                path=root,
                message=(
                    f"WHAT: the telemetry root {root} does not exist. "
                    "WHY: the unified event store cannot append a record "
                    "without a writable directory to hold it -- writing "
                    "anyway would silently fall back to a different "
                    "substrate than the one the operator expects. "
                    "HOW: create the directory (or fix the provisioning "
                    "step that should have) before the composition root "
                    "starts."
                ),
            )
        if not root.is_dir():
            raise StoreProbeFailed(
                fault="not-a-directory",
                path=root,
                message=(
                    f"WHAT: {root} exists but is not a directory. "
                    "WHY: the unified event store needs a directory to "
                    "hold per-family JSONL files, not a plain file at that "
                    "path. "
                    "HOW: remove or rename the file at that path so the "
                    "composition root can recreate it as a directory."
                ),
            )

        canary_path = root / f".probe-canary-{uuid.uuid4().hex}"
        try:
            with open(canary_path, "w", encoding="utf-8") as handle:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    handle.write("probe")
                    handle.flush()
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            with open(canary_path, encoding="utf-8") as handle:
                handle.read()
        except PermissionError as exc:
            self._cleanup(canary_path)
            raise StoreProbeFailed(
                fault="permission-denied",
                path=root,
                message=(
                    f"WHAT: a canary write to {root} was refused with a "
                    f"permission error ({exc}). "
                    "WHY: the unified event store needs write and execute "
                    "permission on the telemetry root to append records. "
                    "HOW: fix the directory's permissions/ownership for "
                    "the process running the composition root."
                ),
            ) from exc
        except OSError as exc:
            self._cleanup(canary_path)
            if exc.errno == errno.ENOSPC:
                raise StoreProbeFailed(
                    fault="enospc",
                    path=root,
                    message=(
                        f"WHAT: a canary write to {root} failed with "
                        f"ENOSPC ({exc}). "
                        "WHY: the unified event store cannot append a "
                        "record with no space left on the device. "
                        "HOW: free disk space (or relocate the telemetry "
                        "root) before the composition root starts."
                    ),
                ) from exc
            raise StoreProbeFailed(
                fault="other",
                path=root,
                message=(
                    f"WHAT: a canary round-trip against {root} failed "
                    f"unexpectedly ({exc}). "
                    "WHY: the unified event store cannot verify the "
                    "telemetry substrate is genuinely usable. "
                    "HOW: inspect the underlying OSError and fix the "
                    "substrate before the composition root starts."
                ),
            ) from exc
        else:
            self._cleanup(canary_path)
            return ProbeResult(ok=True, detail=f"canary round-trip OK at {root}")

    @staticmethod
    def _cleanup(canary_path: Path) -> None:
        try:
            canary_path.unlink()
        except OSError:
            pass


__all__ = ["StoreAvailabilityProbe"]
