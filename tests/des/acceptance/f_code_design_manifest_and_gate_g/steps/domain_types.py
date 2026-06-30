"""Typed domain vocabulary for the f-code-design-manifest-and-gate-g ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
across all four slices names is expressed once here as a typed enum / frozen
dataclass, so the composition methods consume typed parameters (no raw ``str``
where an enum exists). The DSL emerges from these typed concepts -- the scenarios
range over the §17 ``GateVerdict`` set + the coherence cases + the wiring
surfaces, not over decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13). The §17
``GateVerdict`` enum here is the AT-side MIRROR of
``des.domain.gate_outcome.GateVerdict``; the wire tokens are byte-identical to the
production enum's ``.value``s (verified live at HEAD:
``pass / fail / not_applicable / unverified / indeterminate``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# §17 GateVerdict -- the FIVE verdicts (ADR-GV-001), CONSUMED unchanged. No
# sixth (C6 / AT-A3 / DDD-7). gate-G maps onto these existing five: manifest
# bijection -> PASS; confirmable divergence (dropped row / undeclared scenario)
# -> FAIL; untagged-or-loose-or-prose -> UNVERIFIED; unsupported language ->
# INDETERMINATE; no contract -> NOT_APPLICABLE.
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """The §17 uniform-failure-machine verdict set (ADR-GV-001, 5 verdicts)."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The LOCKED §17 verdict-token set -- gate-G must return ONE of these, never a
# sixth. The ATs assert the returned verdict is in this set before the equality.
LOCKED_GATE_VERDICTS: frozenset[str] = frozenset(v.value for v in GateVerdict)


# ---------------------------------------------------------------------------
# Coherence cases -- the design↔AT bijection shapes gate-G adjudicates over a
# manifest-backed contract. Drives slices 01/02/03.
# ---------------------------------------------------------------------------


class CoherenceCase(Enum):
    """The design (manifest ``example-tables:`` ``row-id``) ↔ AT (``@row:`` tag)
    relationship, per the row-level bijection gate-G computes against a MANIFEST.

    BIJECTIVE          -- every manifest ``row-id`` has exactly one covering AT
                          scenario carrying a matching ``@row:`` tag, and vice
                          versa -> deterministic gate-G PASS (CT-1). The manifest
                          makes this CONFIRMABLE (no UNVERIFIED cap).
    DROPPED_ROW        -- a manifest ``example-tables:`` row has NO covering AT
                          scenario (a dropped row) -> deterministic gate-G FAIL,
                          diagnostic naming the dropped ``row-id`` (CT-2). Confirmable
                          BECAUSE the manifest's stable ``row-id`` is the join key.
    UNDECLARED_SCENARIO -- an AT scenario's ``@row:`` tag references a ``row-id``
                          the manifest never declares -> deterministic gate-G FAIL,
                          diagnostic naming the undeclared ``row-id`` (CT-3).
    EMPTY_BIJECTIVE    -- the manifest declares ZERO example-table rows and the AT
                          module declares ZERO covering scenarios -> a vacuous-but-
                          confirmable bijection -> gate-G PASS (the C3 ZERO case for
                          the example-tables iterative surface).
    UNTAGGED_SCENARIO  -- a manifest is present and ≥1 AT scenario carries NO
                          ``@row:`` tag (or a malformed one). gate-G CANNOT confirm
                          the bijection for that scenario -> gate-G UNVERIFIED,
                          diagnostic NAMING the untagged scenario; never a silent
                          ignore, never a fabricated PASS (CT-10b / DDD-4 -- the
                          no-silent-pass case).
    """

    BIJECTIVE = "bijective"
    EMPTY_BIJECTIVE = "empty-bijective"
    DROPPED_ROW = "dropped-row"
    UNDECLARED_SCENARIO = "undeclared-scenario"
    UNTAGGED_SCENARIO = "untagged-scenario"


# Wire-token (kebab-lowercase) -> typed CoherenceCase, for the parametrized
# divergence step (one scenario shape ranges over the confirmable-FAIL kinds).
CONFIRMABLE_DIVERGENCE_BY_TOKEN: dict[str, CoherenceCase] = {
    "dropped-row": CoherenceCase.DROPPED_ROW,
    "undeclared-scenario": CoherenceCase.UNDECLARED_SCENARIO,
}


# ---------------------------------------------------------------------------
# Contract-input shape -- which design source gate-G reads, and the
# AT-module-language probe (drives slice-03 generalization + INDETERMINATE).
# ---------------------------------------------------------------------------


class ContractInput(Enum):
    """The shape of the design contract gate-G diffs the AT module against (DDD-3).

    MANIFEST          -- a ``code-design.manifest.yaml`` carrying ``example-tables:``
                         with stable ``row-id``s present -> deterministic PASS/FAIL,
                         NO UNVERIFIED cap (the D3 closure).
    PROSE_FALLBACK    -- no manifest, but the prose ``## Wave: DESIGN / [REF]
                         Code-Design`` block present, with LOOSE rows disjoint from
                         the AT tags -> EXISTING prose path + EXISTING North-Star
                         UNVERIFIED cap (CT-7, no regression).
    PROSE_GENERAL_WORDING_BIJECTIVE -- no manifest; the prose ``[REF] Code-Design``
                         block declares rows that ARE covered, one-to-one, by
                         acceptance scenarios written in GENERAL wording (NOT the
                         feature-specific "Operator exports the X case" form the
                         hardcoded ``_SCENARIO_LINE`` regex once required). gate-G
                         must RECOGNIZE the general-wording scenarios (via the
                         generalized ``@row`` reader that REPLACES ``_SCENARIO_LINE``
                         on the prose path) and return PASS -- the mechanical witness
                         that the single-feature regex is GONE (slice-03's thesis:
                         a GENERAL coherence gate, not a single-feature probe).
    NEITHER           -- neither manifest nor prose -> NOT_APPLICABLE (CT-7).
    UNSUPPORTED_LANGUAGE -- the AT module is in a language the ``CodeFactPort``
                         AstAdapter cannot parse (e.g. ``.exs``) -> the mechanism
                         could not run -> INDETERMINATE (CT-6).
    """

    MANIFEST = "manifest"
    PROSE_FALLBACK = "prose-fallback"
    PROSE_GENERAL_WORDING_BIJECTIVE = "prose-general-wording-bijective"
    NEITHER = "neither"
    UNSUPPORTED_LANGUAGE = "unsupported-language"


class ManifestHealth(Enum):
    """The DESIGN-OUT manifest-validation outcome (drives slice-01 + CT-4).

    SCHEMA_VALID_GROUNDED -- schema-valid AND every ``sut: path::symbol`` is
                             grep-findable in its cited file -> validator exit 0.
    STALE_SYMBOL          -- a ``sut:`` symbol (in ``example-tables[]`` /
                             ``signatures[]`` / the absorbed ``component-manifest:``)
                             is NOT grep-findable -> validator exit ≠ 0 (CT-4,
                             the WIDENED sut-key iteration, review MEDIUM-1).
    SCHEMA_INVALID        -- the manifest violates the schema (e.g. a row missing
                             its ``row-id``) -> validator exit ≠ 0 (CT-4).
    """

    SCHEMA_VALID_GROUNDED = "schema-valid-grounded"
    STALE_SYMBOL = "stale-symbol"
    SCHEMA_INVALID = "schema-invalid"


# ---------------------------------------------------------------------------
# Wiring surfaces -- the catalog/registry/gate-stack membership the slice-04
# ATs witness (AT-A1-now). Each enum member names a shipped artifact.
# ---------------------------------------------------------------------------


class WiringSurface(Enum):
    """A shipped wiring artifact the ``gate-design-at-coherence`` gate must appear in.

    REGISTRY    -- ``src/des/cli/__main__.py:_REGISTRY`` SubcommandRow, witnessed
                   via the REAL ``des`` dispatcher recognizing the subcommand (CT-8).
    CATALOG     -- ``nWave/gates/_catalog.yaml`` mirror entry (CT-8).
    GATE_STACK  -- the LIVE distill gate-out stack the spine resolves through
                   ``wave_gate_stack_dispatch.resolve_stack("distill","gate-out")``,
                   reading the canonical registry ``nWave/waves/distill.yaml`` (the
                   SOLE gate-stack source, ADR-FLOW-006 D6 -- NOT the dormant
                   ``atdd_pure.yaml`` flavor block, which the spine never resolves).
                   The feature-delta "wave_gate_stacks.distill.gate-out (flavor)"
                   wording predates the f-wave slice-06 registry MOVE (CT-9).
    """

    REGISTRY = "registry"
    CATALOG = "catalog"
    GATE_STACK = "gate-stack"


# The wired subcommand id this feature ships (DDD-5). The join key the wiring ATs
# look for across the three surfaces.
GATE_SUBCOMMAND_ID = "gate-design-at-coherence"


@dataclass(frozen=True)
class GateGObservable:
    """The observable slice of a gate-G run the ATs assert on (Mandate-8 universe).

    Port-exposed names only -- the §17 ``GateVerdict`` token + the diagnostic the
    mechanical diff names + whether the North-Star cap was surfaced + whether the
    mechanism ran. NEVER an internal gate-G field.
    """

    verdict: str | None
    diagnostic: str | None
    cap_surfaced: bool
    ran: bool


@dataclass(frozen=True)
class ValidationObservable:
    """The observable slice of a manifest-validation run (CT-4).

    ``exit_code`` is the validator process exit code (0 = schema-valid + grounded;
    ≠ 0 = stale symbol / schema-invalid). ``message`` is the stderr diagnostic
    (non-empty on a non-zero exit, naming the stale symbol / schema error).
    """

    exit_code: int | None
    message: str | None
