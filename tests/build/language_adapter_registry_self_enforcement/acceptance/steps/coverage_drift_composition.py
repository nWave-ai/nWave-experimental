"""Composition-root service for the catalog coverage-drift cross-check (slice-02).

Provenance: feature ``language-adapter-registry-self-enforcement``, slice-02 (DISTILL,
per-slice JIT). The catalog coverage-drift cross-check (C4): the catalog's hand-authored
declared coverage (``supported-languages`` + ``ports``) is cross-checked against the
DISCOVERED plugins' actual coverage (the registered plugins' ``target_language`` set +
their covered-port set). Hand-drift -> RED (ARCH_TECH_DEBT.md:61 "remember to maintain
the catalog" becomes mechanical).

Mandate-12 (criteria 2+3): the coverage-drift business logic lives in the production
rule ``des.testarch.rules.registry_conformance.detect_catalog_coverage_drift`` (the
single source of truth -- RED scaffold until A_GREEN); this service is the thin
composition root that drives the cross-check over the three corpora and projects its
port-exposed verdict onto the acceptance vocabulary. Step bodies invoke this service and
never inline logic.

Three corpora (the recall/precision golden-fixture shape, mirroring slice-01):

  * RECALL -- the FROZEN declared-over-discovered snapshot
    (``fixtures/coverage_drift/declared_over_discovered_snapshot.py``) that permanently
    carries a declared-but-undiscovered language. FLAGGED forever once the cross-check
    exists -- proves the coverage-drift gate CAN bite.
  * PRECISION (frozen) -- the FROZEN matched-coverage snapshot
    (``fixtures/coverage_drift/matched_coverage_snapshot.py``) in which declared coverage
    equals discovered coverage and no covered port falls outside the catalog. CONFORMANT
    -- the fail-closed bar.
  * PRECISION-LIVE -- the real ``nWave/data/language-adapter-ports.yaml`` declared
    coverage cross-checked against a LIGHT live ``target_language``/``port_coverage``-key
    discovery over ``entry_points(group="nwave.lang.adapter")``. At HEAD the catalog
    declares ``{python, typescript, go}`` while the only registered plugin's
    ``target_language`` is ``{_conformance_fixture}`` -- a REAL declared-vs-discovered
    drift. The cross-check MUST report FLAGGED. RED NOW (the cross-check is a scaffold),
    GREEN EXACTLY when A_GREEN implements C4. THIS is the falsifiable flip -- reverting
    C4 re-REDs it.

LIGHT discovery (the slice-02 composition-root read): each registered plugin's
``target_language`` (single attribute) + ``port_coverage`` dict keys ONLY. NOT the C2
capability resolve-and-probe-method-surface (that is slice-03). Reading the catalog YAML
via ``yaml.safe_load`` is the composition root's I/O concern; the pure rule sees only
plain-data frozensets.

Driving port: the pure ``detect_catalog_coverage_drift`` entrypoint
(``des.testarch.rules.registry_conformance``). The rule cross-checks the supplied
frozensets as plain data; the live ``entry_points`` + catalog read live here at the
composition root (DDD-D6).

Honest tagging: an in-process introspection of the testarch substrate + a light registry
read -- @component (auto-``unit`` under ``tests/build/``), NEVER @wiring_e2e/@subprocess.

RED scaffold (Mandate-7 / ADR-025): the driven ``detect_catalog_coverage_drift`` function
raises ``AssertionError`` (the RED token -- NOT NotImplementedError, NOT ImportError)
until A_GREEN implements it.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

import yaml

from des.testarch.rules.registry_conformance import (
    CoverageDriftVerdict,
    detect_catalog_coverage_drift,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.coverage_drift.declared_over_discovered_snapshot import (
    PLANTED_CATALOG_PORTS,
    PLANTED_COVERED_PORTS,
    PLANTED_DECLARED_LANGUAGES,
    PLANTED_DISCOVERED_LANGUAGES,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.coverage_drift.matched_coverage_snapshot import (
    MATCHED_CATALOG_PORTS,
    MATCHED_COVERED_PORTS,
    MATCHED_DECLARED_LANGUAGES,
    MATCHED_DISCOVERED_LANGUAGES,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.fixtures.coverage_drift.port_outside_catalog_snapshot import (
    PORT_DRIFT_CATALOG_PORTS,
    PORT_DRIFT_COVERED_PORTS,
    PORT_DRIFT_DECLARED_LANGUAGES,
    PORT_DRIFT_DISCOVERED_LANGUAGES,
)
from tests.build.language_adapter_registry_self_enforcement.acceptance.steps.coverage_drift_domain_types import (
    CoverageDriftOutcome,
)


# The live catalog the precision-live corpus reads (the real hand-authored SSOT).
_REPO_ROOT = Path(__file__).resolve().parents[5]
_LIVE_CATALOG_PATH = _REPO_ROOT / "nWave" / "data" / "language-adapter-ports.yaml"
_ENTRY_POINT_GROUP = "nwave.lang.adapter"


class CatalogCoverageDriftService:
    """Drives the catalog coverage-drift cross-check (C4) over three corpora.

    Recall corpus = the frozen declared-over-discovered snapshot; frozen precision
    corpus = the frozen matched-coverage snapshot; precision-live corpus = the real
    catalog YAML declared coverage vs a light live ``target_language`` discovery.
    """

    # --- RECALL (frozen declared-over-discovered snapshot -- flagged forever) -

    def drift_of_declared_over_discovered_snapshot(self) -> CoverageDriftVerdict:
        """Drive the cross-check against the frozen declared-over-discovered snapshot."""
        return detect_catalog_coverage_drift(
            PLANTED_DECLARED_LANGUAGES,
            PLANTED_DISCOVERED_LANGUAGES,
            PLANTED_CATALOG_PORTS,
            PLANTED_COVERED_PORTS,
        )

    # --- PRECISION (frozen matched-coverage snapshot -- clean complement) -----

    def drift_of_matched_coverage_snapshot(self) -> CoverageDriftVerdict:
        """Drive the cross-check against the frozen matched-coverage snapshot."""
        return detect_catalog_coverage_drift(
            MATCHED_DECLARED_LANGUAGES,
            MATCHED_DISCOVERED_LANGUAGES,
            MATCHED_CATALOG_PORTS,
            MATCHED_COVERED_PORTS,
        )

    # --- RECALL axis (b) (frozen port-outside-catalog snapshot -- flagged) -----

    def drift_of_port_outside_catalog_snapshot(self) -> CoverageDriftVerdict:
        """Drive the cross-check against the frozen port-outside-catalog snapshot.

        Single-cause axis-(b) corpus: the declared language set equals the discovered
        set (axis (a) silent), so the ONLY drift is a discovered covered port outside
        the catalog (``PORT_OUTSIDE_CATALOG_BREACH``). Witnesses that a cross-check
        implementing only the language symmetric-difference leaves the port axis as dead
        contract -- this scenario must stay RED for such an impl.
        """
        return detect_catalog_coverage_drift(
            PORT_DRIFT_DECLARED_LANGUAGES,
            PORT_DRIFT_DISCOVERED_LANGUAGES,
            PORT_DRIFT_CATALOG_PORTS,
            PORT_DRIFT_COVERED_PORTS,
        )

    # --- PRECISION-LIVE (real catalog vs light live discovery) ----------------

    def drift_of_live_catalog(self) -> CoverageDriftVerdict:
        """Drive the cross-check against the real catalog vs a light live discovery.

        The declared coverage is read live from ``language-adapter-ports.yaml``; the
        discovered coverage is the LIGHT ``target_language``/``port_coverage``-key read
        over the registered ``nwave.lang.adapter`` plugins (NOT the C2 resolve-and-probe
        of slice-03). At HEAD this is a real declared-vs-discovered drift.
        """
        declared_languages, catalog_ports = self._live_declared_coverage()
        discovered_languages, covered_ports = self._live_discovered_coverage()
        return detect_catalog_coverage_drift(
            declared_languages, discovered_languages, catalog_ports, covered_ports
        )

    # --- live-surface readers (READ, never transcribe) ------------------------

    @staticmethod
    def _live_declared_coverage() -> tuple[frozenset[str], frozenset[str]]:
        """The catalog's declared ``supported-languages`` + ``port-id`` sets, read live."""
        document = yaml.safe_load(_LIVE_CATALOG_PATH.read_text(encoding="utf-8"))
        declared = frozenset(document.get("supported-languages") or [])
        ports = frozenset(
            entry.get("port-id")
            for entry in (document.get("ports") or [])
            if isinstance(entry, dict) and entry.get("port-id")
        )
        return declared, ports

    @staticmethod
    def _live_discovered_coverage() -> tuple[frozenset[str], frozenset[str]]:
        """The registered plugins' ``target_language`` + covered-port sets (LIGHT read)."""
        languages: set[str] = set()
        covered_ports: set[str] = set()
        for endpoint in entry_points(group=_ENTRY_POINT_GROUP):
            plugin = endpoint.load()
            instance = plugin() if isinstance(plugin, type) else plugin
            target_language = getattr(instance, "target_language", None)
            if callable(target_language):
                target_language = target_language()
            if target_language is not None:
                languages.add(target_language)
            port_coverage = getattr(instance, "port_coverage", None)
            if callable(port_coverage):
                port_coverage = port_coverage()
            if isinstance(port_coverage, dict):
                covered_ports.update(port_coverage.keys())
        return frozenset(languages), frozenset(covered_ports)

    # --- verdict -> outcome projection ----------------------------------------

    @staticmethod
    def outcome_of(verdict: CoverageDriftVerdict) -> CoverageDriftOutcome:
        """Project the coverage-drift verdict onto the port-exposed outcome enum."""
        return (
            CoverageDriftOutcome.FLAGGED
            if verdict.flagged
            else CoverageDriftOutcome.CONFORMANT
        )


def build_service() -> CatalogCoverageDriftService:
    """Composition-root entry -- the production object graph for the slice-02 AT."""
    return CatalogCoverageDriftService()
