"""GOLDEN FIXTURE (frozen declared-over-discovered snapshot) -- slice-02 recall corpus.

language-adapter-registry-self-enforcement, slice-02 (DISTILL, per-slice JIT). This
is NOT the live ``nwave.lang.adapter`` registry; it is the RECALL-half corpus for the
catalog coverage-drift cross-check (C4 / ``detect_catalog_coverage_drift``). It is a
FROZEN ``(declared_coverage, discovered_coverage)`` pair that PERMANENTLY carries a
drift: the catalog DECLARES a language the registry does NOT provide (over-declaration).
So the gate's recall scenario stays RED-against-the-scaffold while the cross-check is a
scaffold and GREEN forever once the cross-check exists (the live substrate is never
consulted; this fixture is never reconciled -- it is the perpetual witness that the
coverage-drift gate CAN bite).

Mirrors the slice-01 ``violation_unrealized_pair_snapshot.py`` shape (a frozen recall
corpus), generalized from the per-plugin x capability axis to the per-catalog
language-coverage axis:

  * ``declared_languages`` declares two languages. The registry discovers only ONE of
    them (``ghost_discovered_lang``) -- it OMITS ``ghost_declared_only_lang``. That
    omission is the planted declared-over-discovered drift the cross-check MUST flag and
    name.
  * The covered-port set is a subset of the catalog ports here, so the ONLY drift in
    this corpus is the language-coverage drift (keeping the recall witness single-cause).

The values are deliberately bogus (``ghost_*``) so the recall fixture can never
accidentally coincide with a real language id / port id and drift into a false negative
when the real catalog evolves. A coverage-drift gate that cannot detect this planted
over-declaration is itself testing-theater -- the disease it exists to prevent one level
down.
"""

from __future__ import annotations


# The catalog's hand-authored declared coverage (the ``supported-languages`` set).
# Declares TWO languages; the registry provides only the first.
PLANTED_DECLARED_LANGUAGES: frozenset[str] = frozenset(
    {"ghost_discovered_lang", "ghost_declared_only_lang"}
)

# The registered plugins' discovered ``target_language`` set (LIGHT discovery). Provides
# only ``ghost_discovered_lang`` -- it OMITS ``ghost_declared_only_lang``, the planted
# over-declaration drift.
PLANTED_DISCOVERED_LANGUAGES: frozenset[str] = frozenset({"ghost_discovered_lang"})

# The catalog's declared port set; the discovered covered ports are a subset, so the
# port axis contributes NO drift in this recall corpus (single-cause: language drift).
PLANTED_CATALOG_PORTS: frozenset[str] = frozenset({"ghost_port_a", "ghost_port_b"})
PLANTED_COVERED_PORTS: frozenset[str] = frozenset({"ghost_port_a"})

# The exact drifted language token the gate MUST name (recall assertion).
PLANTED_DRIFTED_LANGUAGE: str = "ghost_declared_only_lang"
