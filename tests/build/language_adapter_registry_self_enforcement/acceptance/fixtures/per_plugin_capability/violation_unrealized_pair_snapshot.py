"""GOLDEN FIXTURE (frozen unrealized-pair snapshot) — slice-01 recall corpus.

language-adapter-registry-self-enforcement, slice-01 (DISTILL, per-slice JIT;
DDD-D3a plugin-axis ruling). This is NOT the live ``nwave.lang.adapter`` registry;
it is the RECALL-half corpus for the generalized per-plugin x per-capability
conformance detector (C1). It is a FROZEN snapshot that PERMANENTLY carries a
registered-but-unrealized ``(plugin, capability)`` pair, so the gate's recall
scenario stays RED-against-the-detector while the detector is a scaffold and GREEN
forever once the detector exists (the live substrate is never consulted; this
fixture is never cleaned — it is the perpetual witness that the 2-D gate CAN bite).

Mirrors the slice-12 ``violation_drifted_snapshot.py`` shape, generalized from the
1-D (caps x one adapter) form to the 2-D (plugin x capability) cross-product:

  * The realized map declares two plugins. ``ghost_plugin`` realizes only ONE of
    the two required capabilities — it OMITS ``ghost_capability``. That omission is
    the planted ``(plugin, capability)`` drift the 2-D detector MUST flag and name.
  * ``well_formed_plugin`` realizes BOTH required capabilities — it is the in-snapshot
    control proving the detector flags ONLY the genuine gap, not every plugin.

The values are deliberately bogus (``ghost_*``) so the recall fixture can never
accidentally coincide with a real ``Capability.value`` / registered plugin id and
drift into a false negative when the real vocabulary evolves. A 2-D gate that
cannot detect this planted pair is itself testing-theater — the disease it exists
to prevent one level down.
"""

from __future__ import annotations


# The registered-capability obligation set the detector cross-products against
# (the per-plugin obligation). Two members; the planted gap is the second one
# being absent from ``ghost_plugin``'s realized surface.
PLANTED_REQUIRED_CAPABILITIES: frozenset[str] = frozenset(
    {"ghost_capability_realized", "ghost_capability"}
)

# The frozen per-plugin realized-capability surface:
#   ``plugin_id`` -> the capability-method names that plugin realizes.
# ``ghost_plugin`` realizes only the first required capability (it OMITS
# ``ghost_capability``) — the planted unrealized pair. ``well_formed_plugin``
# realizes BOTH — the in-snapshot control.
PLANTED_REALIZED_BY_PLUGIN: dict[str, frozenset[str]] = {
    "ghost_plugin": frozenset({"ghost_capability_realized"}),
    "well_formed_plugin": frozenset({"ghost_capability_realized", "ghost_capability"}),
}

# The exact ``(plugin_id, capability)`` pair the gate MUST name (recall assertion).
PLANTED_UNREALIZED_PLUGIN_ID: str = "ghost_plugin"
PLANTED_UNREALIZED_CAPABILITY: str = "ghost_capability"
