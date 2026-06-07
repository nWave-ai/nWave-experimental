"""GOLDEN FIXTURE (frozen all-realized discovery result) -- slice-03 precision-clean corpus.

language-adapter-registry-self-enforcement, slice-03 (DISTILL, per-slice JIT). This is
NOT the live ``nwave.lang.adapter`` registry; it is a FROZEN discovery RESULT in which
EVERY discovered plugin realizes EVERY required capability. The conformance gate over
this clean result returns exit 0 (CONFORMANT).

This corpus exercises the gate's exit-0 lane WITHOUT claiming the LIVE registry is
conformant: the precision-live-CONFORMANT flip over the REAL registry is EXPLICITLY
DEFERRED to slice-05a (the real Python reference plugin). At HEAD the live registry holds
only the inert ``_conformance_fixture`` (realizes 0/9) and the gate correctly stays on the
GAP lane (exit 1) over it -- see scenario 1. This frozen clean result is the fail-closed
precision complement: it pins that the gate maps a no-violation verdict to exit 0, so a
buggy gate that always reported a gap would fail this scenario.

The realized surface is a frozen ``{plugin_id: realized_capability_method_names}`` mapping
(the C2 resolve-and-probe RESULT shape, the same shape the pure 2-D detector consumes). The
required-capability obligation set is read live from the registry (the SSOT) so the clean
result is always exactly aligned to the current contract -- a clean result that realizes
the LIVE obligation set can never drift into a false RED when a capability is added.
"""

from __future__ import annotations

from des.testarch.capabilities import build_registry


# The reference plugin id for the frozen clean result. NOT a registered
# ``nwave.lang.adapter`` plugin id -- a frozen-injected discovery RESULT (the live-registry
# read is the GAP/INDETERMINATE concern of scenarios 1+2).
CLEAN_PLUGIN_ID = "reference_clean_plugin"


def clean_realized_by_plugin() -> dict[str, frozenset[str]]:
    """A frozen discovery result in which the one plugin realizes every required capability.

    The realized surface equals the live required-capability obligation set, so the gate's
    cross-check finds zero registered-but-unrealized pairs -> CONFORMANT (exit 0).
    """
    required = frozenset(
        capability.value for capability in build_registry().required_capabilities()
    )
    return {CLEAN_PLUGIN_ID: required}
