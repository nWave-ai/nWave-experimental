"""Domain types for the wire-p0-gates-at-feature-end acceptance suite.

Mandate-12 criterion 1 (ATDD SSOT via Types + Services + DSL): the closed set
of P0 gate names the Gherkin names is expressed once here as a typed enum --
no raw ``str`` where a domain enum exists. The Then step template does a
single typed-dict lookup, never an ``if``-ladder, and a Gherkin phrase outside
the closed set raises ``KeyError`` at collection/run time rather than
silently asserting against an arbitrary substring.

CONTRACT SOURCE: the SSOT for "which gate produced this refusal" is the
substring each gate's own CLI names in its refusal diagnostic --
``verify_fresh_clone.py`` / ``verify_execution_reach.py`` /
``verify_doc_coherence.py`` -- surfaced verbatim through
``run_feature_end_cycle``'s ``CycleRefusal.error`` once the leg is wired
(``feature_end_cycle_service.py``, evolution-plan P0.1/P0.4/P0.5).
"""

from __future__ import annotations

from enum import Enum


class GateName(str, Enum):
    """The three P0 evidence-by-execution gates this feature wires in."""

    FRESH_CLONE = "fresh-clone"
    EXECUTION_REACH = "execution-reach"
    DOC_COHERENCE = "doc-coherence"


# Phrase -> typed-value lookup (Mandate-12 criterion 3): the Gherkin literal
# ("fresh-clone" / "execution-reach" / "doc-coherence") maps to the SAME typed
# enum whose ``.value`` is asserted as a substring of the refusal diagnostic.
GATE_NAME_BY_PHRASE: dict[str, GateName] = {g.value: g for g in GateName}
