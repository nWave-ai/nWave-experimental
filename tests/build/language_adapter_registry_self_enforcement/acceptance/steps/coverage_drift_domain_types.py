"""Domain types for the catalog coverage-drift cross-check (slice-02).

Mandate-12 (criterion 1): every domain noun used in the slice-02 Gherkin and the
Python ATs is expressed once here as a typed enum / NewType. Step methods and the
composition service consume these types -- never raw ``str`` where a domain enum
exists. Kept SEPARATE from slice-01's ``domain_types.py`` so the slice-01 ATs that
import ``ConformanceOutcome`` are untouched.

slice-02 vocabulary -- the catalog coverage-drift cross-check (C4). The domain nouns:

  * a *coverage declaration* -- the catalog's hand-authored ``supported-languages``
    set + declared ``ports`` set;
  * a *discovered coverage* -- the registered plugins' ``target_language`` set + their
    covered-port set (LIGHT discovery: ``target_language``/``port_coverage`` keys only,
    NOT the capability resolve-and-probe of slice-03);
  * a *drift verdict* (flagged vs conformant) -- the port-exposed observable;
  * the *kind* of corpus the gate is asked to classify (frozen declared-over-discovered
    drift vs frozen matched coverage vs the real live catalog read).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


# A declared/discovered language id the gate names in a drift violation, e.g.
# "ghost_declared_only_lang" (frozen corpus) or "typescript" (the live catalog).
LanguageId = NewType("LanguageId", str)

# A catalog/covered port id the gate names in an out-of-catalog drift violation.
PortId = NewType("PortId", str)


class CoverageDriftCorpus(Enum):
    """Which corpus the catalog coverage-drift cross-check is asked to classify.

    DECLARED_OVER_DISCOVERED_SNAPSHOT -- a frozen ``(declared, discovered)`` pair in
                        which the catalog declares a language the registry does not
                        provide. The gate MUST flag it and name the drifted language
                        (the recall half).
    MATCHED_COVERAGE_SNAPSHOT -- a frozen ``(declared, discovered)`` pair in which the
                        declared language set equals the discovered set and every
                        covered port is inside the catalog. The gate MUST NOT flag it
                        (the frozen precision half / fail-closed bar).
    LIVE_CATALOG -- the real ``language-adapter-ports.yaml`` declared coverage cross-
                        checked against a LIGHT live ``target_language`` discovery. The
                        gate MUST report the real HEAD drift (catalog over-declares
                        python/typescript/go vs the single inert registered fixture);
                        this is the witness that flips RED->GREEN exactly on C4's
                        cross-check implementation (the precision-live half).
    """

    DECLARED_OVER_DISCOVERED_SNAPSHOT = "declared_over_discovered_snapshot"
    MATCHED_COVERAGE_SNAPSHOT = "matched_coverage_snapshot"
    LIVE_CATALOG = "live_catalog"


class CoverageDriftOutcome(Enum):
    """The port-exposed verdict the catalog coverage-drift cross-check returns.

    FLAGGED    -- declared coverage drifts from discovered coverage (a declared-vs-
                  discovered language mismatch and/or an out-of-catalog covered port).
    CONFORMANT -- declared coverage matches discovered coverage and no covered port
                  falls outside the catalog; no drift.
    """

    FLAGGED = "flagged"
    CONFORMANT = "conformant"
