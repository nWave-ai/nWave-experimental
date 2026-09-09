"""NullProbe — the test/opt-out FreshnessProbe adapter (§1.5).

Returns state ``A`` (PROCEED) unconditionally. Used by:

* tests that need a probe with no filesystem dependencies;
* the ``NWAVE_FRESHNESS=skip`` opt-out path inside
  :mod:`des.runtime.freshness`, where the probe must short-circuit before any
  manifest is read.
"""

from __future__ import annotations

from des.ports.driven_ports.freshness_port import FreshnessVerdict


class NullProbe:
    """Stub FreshnessProbe — always PROCEEDS with state ``A``."""

    def probe(self) -> FreshnessVerdict:
        return FreshnessVerdict(state="A", reason="null-probe")


__all__ = ["NullProbe"]
