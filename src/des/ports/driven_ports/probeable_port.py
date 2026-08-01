"""Probeable -- the Earned Trust driven-port contract (DD-14, principle 13).

A driven adapter that touches a real substrate (filesystem, network, ...)
proves its OWN usability before the composition root trusts it, rather than
discovering the substrate is broken on the first real write. `probe()` is
that proof: a canary round-trip against the adapter's real dependency,
raising `StoreProbeFailed` -- never returning a false-healthy result -- when
the substrate cannot honor its contract.

Slice-02 of unified-event-store (feature-delta.md [REF] Driven Ports +
Adapters): `UnifiedEventStoreAdapter` implements this port by DELEGATING to
`StoreAvailabilityProbe` (witness-independence, GDP-8 -- the probe is a
SEPARATE, differently-lensed check, not the same write logic invoked twice
under two names).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ProbeResult:
    """The positive outcome of a successful `Probeable.probe()` call.

    `ok` is always `True` on a `ProbeResult` -- a failed probe never
    constructs one, it raises `StoreProbeFailed` instead (GDP-6: no
    silent-wrong -- a caller cannot mistake a "probe ran" marker for a
    "probe passed" marker by reading a boolean that might be `False`).
    """

    ok: bool
    detail: str


class StoreProbeFailed(Exception):
    """Raised when a `Probeable` adapter's canary probe cannot pass.

    Carries a `fault` classification distinguishing WHICH substrate defect
    was hit (so a caller can react/report differently per class) and the
    `path` the probe was exercising, alongside a WHAT/WHY/HOW message body
    (per the assertion-message standing) -- the composition root refuses to
    start on this exception (`health.startup.refused`, DD-14), and the CLI
    surface renders the message verbatim so "reading only the terminal, you
    can tell which fault occurred without opening a single file" (the
    slice-02 expectation charter's own oracle).

    `fault` is one of: `"missing-directory"`, `"permission-denied"`,
    `"not-a-directory"`, `"enospc"`, `"other"`.
    """

    def __init__(self, fault: str, path: Path, message: str) -> None:
        self.fault = fault
        self.path = path
        super().__init__(message)


class Probeable(Protocol):
    """A driven adapter that can prove its real substrate is usable."""

    def probe(self) -> ProbeResult:
        """Prove the adapter's real substrate is genuinely usable.

        Returns `ProbeResult(ok=True, ...)` on success. Raises
        `StoreProbeFailed` -- never returns a falsy/ok=False result -- when
        the substrate cannot honor its contract.
        """
        ...


__all__ = ["ProbeResult", "Probeable", "StoreProbeFailed"]
