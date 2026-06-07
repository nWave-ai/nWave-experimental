"""GOLDEN FIXTURE (frozen all-realized snapshot) — slice-01 precision corpus.

language-adapter-registry-self-enforcement, slice-01 (DISTILL, per-slice JIT;
DDD-D3a plugin-axis ruling). This is NOT the live ``nwave.lang.adapter`` registry;
it is the PRECISION-half (clean) corpus for the generalized per-plugin x
per-capability conformance detector (C1). It is a FROZEN snapshot in which EVERY
plugin realizes EVERY required capability, so the gate clears it — proving the 2-D
detector does NOT over-fire (the precision half / fail-closed bar).

Mirrors the slice-12 ``clean_conformant_snapshot.py`` shape, generalized to the
2-D cross-product:

  * Two plugins, each realizing a SUPERSET of the required-capability set. The 2-D
    detector finds zero ``(plugin, capability)`` gaps → CONFORMANT.

The clean snapshot is the frozen-clean complement of the violation snapshot: the
violation fixture proves the gate CAN bite (recall), this proves the gate does NOT
bite a conformant cross-product (precision). A 2-D gate that flagged this clean
snapshot would be a false-positive that blocks a commit — the fail-closed bar this
fixture guards. The slice-11 Tier-M meta-gate convention requires every shipped gate
to carry BOTH a ``violation_*`` and a ``clean_*`` fixture.
"""

from __future__ import annotations


# The registered-capability obligation set the detector cross-products against.
CONFORMANT_REQUIRED_CAPABILITIES: frozenset[str] = frozenset(
    {"alpha_capability", "beta_capability"}
)

# The frozen per-plugin realized-capability surface: every plugin realizes a
# superset of the required set, so the 2-D detector finds zero gaps.
CONFORMANT_REALIZED_BY_PLUGIN: dict[str, frozenset[str]] = {
    "first_plugin": frozenset({"alpha_capability", "beta_capability", "extra_method"}),
    "second_plugin": frozenset({"alpha_capability", "beta_capability"}),
}
