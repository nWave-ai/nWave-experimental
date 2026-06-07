"""FreshnessProbe driven port (DDD-7).

Driven port for the runtime freshness check. The composition root
(``des.cli/__init__.py``) instantiates a concrete adapter and asks for one
:class:`FreshnessVerdict`; the adapter encapsulates how the verdict is reached
(reading ``_install_manifest.json``, recomputing the tree-hash, etc.).

Hexagonal placement: this port lives alongside the other driven ports
(``filesystem_port``, ``audit_log_writer``, ...). Domain/application code does
NOT import the gate; the gate is a CLI-time concern wired at
``des.cli/__init__.py``.

Reference: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md §1.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


# The four-state truth table verdict labels (§1.3). DEGRADED is the sentinel
# for "manifest absent or malformed" — REFUSE. STALE is the #58 `*.py`-content
# drift (degrade-loud). CONFIG_DRIFT is the SYS-4 / AD-27 config-asset content
# drift — a shipped `lib/nWave/` config asset diverged from its install snapshot
# (degrade-loud on the hook path), distinct from the `*.py` STALE state.
FreshnessStateLabel = Literal["A", "B", "C", "D", "STALE", "CONFIG_DRIFT", "DEGRADED"]


@dataclass(frozen=True)
class FreshnessVerdict:
    """Verdict returned by a FreshnessProbe.

    Carries the state label (§1.3), a human-readable reason, and the optional
    installed/source facts used for diagnostics on REFUSE. Slice-01 ships the
    minimum subset that satisfies AT-01-A and AT-01-B: ``state`` and
    ``reason``. Slice-02/03 will extend with ``installed`` and ``source``.
    """

    state: FreshnessStateLabel
    reason: str


class FreshnessProbe(Protocol):
    """Driven port — produces a FreshnessVerdict for the current process."""

    def probe(self) -> FreshnessVerdict: ...


__all__ = [
    "FreshnessProbe",
    "FreshnessStateLabel",
    "FreshnessVerdict",
]
