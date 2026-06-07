"""GOLDEN FIXTURE (frozen matched-coverage snapshot) -- slice-02 precision corpus.

language-adapter-registry-self-enforcement, slice-02 (DISTILL, per-slice JIT). This is
NOT the live ``nwave.lang.adapter`` registry; it is the PRECISION-half (clean) corpus
for the catalog coverage-drift cross-check (C4 / ``detect_catalog_coverage_drift``). It
is a FROZEN ``(declared_coverage, discovered_coverage)`` pair in which the declared
language set EQUALS the discovered ``target_language`` set AND every discovered covered
port is inside the catalog -- so the gate clears it, proving the cross-check does NOT
over-fire (the precision half / fail-closed bar).

Mirrors the slice-01 ``clean_all_realized_snapshot.py`` shape (a frozen clean corpus):

  * ``declared_languages == discovered_languages`` (no language-coverage drift), and
  * ``covered_ports`` is a subset of ``catalog_ports`` (no out-of-catalog port).
  The cross-check finds zero drifts -> CONFORMANT.

The clean snapshot is the frozen-clean complement of the declared-over-discovered
snapshot: the recall fixture proves the gate CAN bite, this proves the gate does NOT
bite a matched coverage pair (precision). A coverage-drift gate that flagged this clean
snapshot would be a false-positive that blocks a commit -- the fail-closed bar this
fixture guards. The slice-11 Tier-M meta-gate convention requires every shipped gate to
carry BOTH a ``violation_*``/drift fixture and a ``clean_*``/matched fixture.
"""

from __future__ import annotations


# Declared coverage == discovered coverage -> no language-coverage drift.
MATCHED_DECLARED_LANGUAGES: frozenset[str] = frozenset({"alpha_lang", "beta_lang"})
MATCHED_DISCOVERED_LANGUAGES: frozenset[str] = frozenset({"alpha_lang", "beta_lang"})

# Every discovered covered port is inside the catalog -> no out-of-catalog port.
MATCHED_CATALOG_PORTS: frozenset[str] = frozenset(
    {"alpha_port", "beta_port", "gamma_port"}
)
MATCHED_COVERED_PORTS: frozenset[str] = frozenset({"alpha_port", "beta_port"})
