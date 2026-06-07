"""Domain types for the language-adapter-registry-self-enforcement suite (slice-01).

Mandate-12 (criterion 1): every domain noun used in the Gherkin and the Python ATs
is expressed once here as a typed enum / NewType / dataclass. Step methods and the
composition service consume these types — never raw ``str`` where a domain enum
exists.

slice-01 vocabulary — the generalized per-plugin x per-capability conformance gate
(the walking-skeleton vertical; DDD-D3a). The domain nouns:

  * a *realized-capability map* — a ``{plugin_id: realized_capability_method_names}``
    surface the gate cross-products against the registered-capability obligation set;
  * a *conformance verdict* (flagged vs conformant) — the port-exposed observable;
  * the *kind* of corpus (frozen unrealized-pair vs frozen all-realized vs the
    injected reference-adapter surface) the gate is asked to classify.

The slice-01 self-AT closes the loop in the recall/precision golden-fixture shape
(DDD-D3a, mirroring slice-12): ``detect(unrealized-pair) == flagged`` AND
``detect(all-realized) == conformant`` AND ``detect(injected PythonAstAdapter
surface) == conformant``.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# --- domain nouns ----------------------------------------------------------

# A registered language-adapter plugin id the gate names in a violation, e.g.
# "ghost_plugin" (frozen corpus) or "python" (the injected reference adapter).
PluginId = NewType("PluginId", str)

# A registered AST-capability value the gate names in a violation, e.g.
# "imports_in_module".
CapabilityName = NewType("CapabilityName", str)


class ConformanceCorpus(Enum):
    """Which corpus the per-plugin x per-capability gate is asked to classify.

    UNREALIZED_PAIR_SNAPSHOT — a frozen ``{plugin_id: realized_map}`` carrying a
                        registered-but-unrealized ``(plugin, capability)`` pair. The
                        gate MUST flag it and name the pair (the recall half).
    ALL_REALIZED_SNAPSHOT — a frozen ``{plugin_id: realized_map}`` in which every
                        plugin realizes every required capability. The gate MUST NOT
                        flag it (the frozen precision half / fail-closed bar).
    INJECTED_REFERENCE_ADAPTER — the real ``PythonAstAdapter`` method-surface
                        injected as a single-element realized map (the de-facto
                        reference adapter, DDD-D3a). The gate MUST report CONFORMANT;
                        this is the witness that flips RED->GREEN exactly on C1's
                        2-D detector implementation (the precision-live half).
    """

    UNREALIZED_PAIR_SNAPSHOT = "unrealized_pair_snapshot"
    ALL_REALIZED_SNAPSHOT = "all_realized_snapshot"
    INJECTED_REFERENCE_ADAPTER = "injected_reference_adapter"


class ConformanceOutcome(Enum):
    """The port-exposed verdict the per-plugin x per-capability gate returns.

    FLAGGED    — at least one ``(plugin, capability)`` pair is registered-but-
                 unrealized (a real coverage gap).
    CONFORMANT — every plugin realizes every registered capability; no gap.
    """

    FLAGGED = "flagged"
    CONFORMANT = "conformant"
