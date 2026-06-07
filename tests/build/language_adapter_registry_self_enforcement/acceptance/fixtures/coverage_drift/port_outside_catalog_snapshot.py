"""GOLDEN FIXTURE (frozen port-outside-catalog snapshot) -- slice-02 recall corpus (axis b).

language-adapter-registry-self-enforcement, slice-02 (DISTILL, per-slice JIT). This is
NOT the live ``nwave.lang.adapter`` registry; it is the RECALL-half corpus for the
SECOND drift axis of the catalog coverage-drift cross-check (C4 /
``detect_catalog_coverage_drift``): a discovered covered port that falls OUTSIDE the
catalog's declared ports (``PORT_OUTSIDE_CATALOG_BREACH``). It is a FROZEN
``(declared, discovered)`` pair that PERMANENTLY carries an out-of-catalog port, so the
gate's port-axis recall scenario stays RED-against-the-scaffold while the cross-check is
a scaffold and GREEN forever once the cross-check exists (the live substrate is never
consulted; this fixture is never reconciled -- it is the perpetual witness that the
PORT axis CAN bite, distinct from the language-set axis).

Single-cause golden-fixture hygiene (mirroring the slice-02 language-axis recall
fixture): the ONLY drift cause in this corpus is the out-of-catalog port. The declared
language set EQUALS the discovered language set (so axis (a) -- the language symmetric-
difference -- contributes NO drift here). That isolation is what makes this AT a true
positive witness for axis (b): a cross-check that implements ONLY the language axis and
ignores the port axis MUST leave this scenario RED, exposing the dead port contract.

  * ``declared_languages == discovered_languages`` -> axis (a) silent.
  * ``covered_ports`` includes ``ghost_uncatalogued_port`` which is NOT in
    ``catalog_ports`` -> the planted out-of-catalog-port drift the cross-check MUST flag
    and name with ``kind == PORT_OUTSIDE_CATALOG_BREACH``.

The values are deliberately bogus (``ghost_*``) so the recall fixture can never
accidentally coincide with a real language id / port id and drift into a false negative
when the real catalog evolves. A coverage-drift gate that cannot detect this planted
out-of-catalog port is itself testing-theater -- the disease it exists to prevent one
level down.
"""

from __future__ import annotations


# Declared coverage == discovered coverage -> the language axis (a) is SILENT here, so
# the only drift cause is the out-of-catalog port (single-cause isolation).
PORT_DRIFT_DECLARED_LANGUAGES: frozenset[str] = frozenset({"ghost_matched_lang"})
PORT_DRIFT_DISCOVERED_LANGUAGES: frozenset[str] = frozenset({"ghost_matched_lang"})

# The catalog declares two ports; the discovered covered set includes a THIRD port
# (``ghost_uncatalogued_port``) that is NOT in the catalog -- the planted out-of-catalog
# drift. ``ghost_catalog_port_a`` is the in-snapshot control proving the gate flags ONLY
# the genuine out-of-catalog port, not every covered port.
PORT_DRIFT_CATALOG_PORTS: frozenset[str] = frozenset(
    {"ghost_catalog_port_a", "ghost_catalog_port_b"}
)
PORT_DRIFT_COVERED_PORTS: frozenset[str] = frozenset(
    {"ghost_catalog_port_a", "ghost_uncatalogued_port"}
)

# The exact out-of-catalog port the gate MUST name (recall assertion, axis b).
PLANTED_OUT_OF_CATALOG_PORT: str = "ghost_uncatalogued_port"
