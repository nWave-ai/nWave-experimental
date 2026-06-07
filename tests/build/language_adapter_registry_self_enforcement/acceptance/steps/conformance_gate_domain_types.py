"""Domain types for the live-registry conformance gate (slice-03).

Mandate-12 (criterion 1): every domain noun used in the slice-03 Gherkin and the
Python ATs is expressed once here as a typed enum / NewType. Step methods and the
composition service consume these types -- never raw ``str`` where a domain enum
exists. Kept SEPARATE from slice-01's ``domain_types.py`` and slice-02's
``coverage_drift_domain_types.py`` so the slice-01 / slice-02 ATs are untouched.

slice-03 vocabulary -- the conformance gate CLI mode running over the LIVE
``nwave.lang.adapter`` registry (C2 resolve-and-probe + C3 CLI mode + C5 gate-surface
wiring, DDD-D4a). The domain nouns:

  * a *gate exit lane* -- the port-exposed exit-code contract the gate returns
    (``0`` conformant / ``1`` registered-but-unrealized gap / ``3`` indeterminate-loud);
  * the *registry source* the gate is asked to resolve-and-probe (the real live
    ``entry_points`` registry / an unresolvable registry / a frozen all-realized result);
  * a *registered-but-unrealized gap* -- a ``(plugin, capability)`` pair the gate names
    when a discovered plugin omits a required capability.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A registered language-adapter plugin id the gate names in a gap, e.g.
# "_conformance_fixture" (the inert live fixture at HEAD).
PluginId = NewType("PluginId", str)

# A registered AST-capability value the gate names in a gap, e.g. "imports_in_module".
CapabilityName = NewType("CapabilityName", str)


class ConformanceGateLane(Enum):
    """The port-exposed exit-code contract the live-registry conformance gate returns.

    CONFORMANT -- exit 0: every discovered plugin realizes every required capability.
                  Over the LIVE registry this lane is DEFERRED to slice-05a (the real
                  Python reference plugin); at HEAD the inert fixture keeps the live
                  gate on the GAP lane. Scenario 3 exercises this lane over an INJECTED
                  clean result, never over the live registry.
    GAP        -- exit 1: at least one registered-but-unrealized ``(plugin, capability)``
                  pair (a real coverage gap). The live registry hits this lane at HEAD
                  (the inert ``_conformance_fixture`` realizes 0/9).
    INDETERMINATE -- exit 3: the discovery surface is unresolvable (an entry point whose
                  target cannot be imported / probed). A DISTINCT loud signal, never a
                  silent green and never a fabricated empty discovery set (DDD-D5).
    """

    CONFORMANT = 0
    GAP = 1
    INDETERMINATE = 3


class ConformanceRegistrySource(Enum):
    """Which registry source the conformance gate is asked to resolve-and-probe.

    LIVE_REGISTRY -- the REAL ``entry_points(group="nwave.lang.adapter")`` registry,
                  resolved-and-probed end-to-end (scenario 1, via the real CLI subprocess).
    UNRESOLVABLE_REGISTRY -- an injected registry carrying an entry point whose target
                  module/class cannot be imported (scenario 2). Drives the exit-3 loud path.
    CLEAN_RESULT -- an injected frozen discovery RESULT in which every discovered plugin
                  realizes every required capability (scenario 3). Drives the exit-0 lane
                  WITHOUT claiming the live registry is conformant.
    """

    LIVE_REGISTRY = "live_registry"
    UNRESOLVABLE_REGISTRY = "unresolvable_registry"
    CLEAN_RESULT = "clean_result"
