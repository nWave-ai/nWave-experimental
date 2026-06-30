"""Typed domain vocabulary for the f-coherence-and-attestation slice-03 ATs (gate-G).

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-03
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the slice-03 scenarios
range over the §17 GateVerdict set and the divergence kinds, not over decorator
proliferation.

slice-03 REUSES the slice-01 LOCKED token enums (the cross-tier Published Language
is the SAME SSOT, ``ADR-LA-001`` §2/§5a) -- gate-G CONSUMES the ``CodeFactPort``
substrate (``query.adr-section`` over the prose ``[REF] Code-Design`` + ``query.
atoms-in-file`` over the AT module), it does NOT fork it (C2). This module ADDS
only the slice-03-specific scenario vocabulary (the design↔AT coherence cases, the
§17 verdict set, the gate-G observable).

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# REUSE the slice-01 LOCKED token vocabulary -- one SSOT for the cross-tier
# Published Language (do NOT re-author the locked tokens here).
from .domain_types_coherence_codefact import (  # noqa: F401  (re-exported vocabulary)
    LOCKED_CAPABILITY_IDS,
    CapabilityId,
)


# ---------------------------------------------------------------------------
# §17 GateVerdict -- the FIVE verdicts (ADR-GV-001), CONSUMED unchanged. No
# sixth (C6). The AT-side mirror of `des.domain.gate_outcome.GateVerdict`; the
# wire tokens are byte-identical to the production enum's `.value`s. gate-G maps
# onto these existing five (gate-G bijection PASS / row-or-signature divergence
# FAIL / suspected-unconfirmable-drift UNVERIFIED / manifest-or-adapter-absent
# INDETERMINATE).
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """The §17 uniform-failure-machine verdict set (ADR-GV-001, 5 verdicts)."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The LOCKED §17 verdict-token set -- gate-G must return ONE of these, never a
# sixth (C6). The slice-03 ATs assert the returned verdict is in this set.
LOCKED_GATE_VERDICTS: frozenset[str] = frozenset(v.value for v in GateVerdict)


# ---------------------------------------------------------------------------
# slice-03 scenario vocabulary -- design↔AT coherence cases + the divergence
# kinds + the contract-input shape (prose vs absent).
# ---------------------------------------------------------------------------


class CoherenceCase(Enum):
    """Whether the design `[REF] Code-Design` example-table and the AT scenarios
    are in bijection, or a confirmable divergence is present.

    BIJECTIVE      -- every ExampleTableRow maps to a covering scenario AND every
                      scenario maps to a row (the happy case -> gate-G PASS).
    DROPPED_ROW    -- the design declares a row (e.g. the empty-dataset row of
                      `f-export-csv`, domain example 4) with NO covering AT
                      scenario -> the ExampleTableRow->Scenario bijection is
                      broken -> gate-G FAIL.
    SIGNATURE_MISMATCH -- the AT references a signature the design never declared
                      (or the design declares a signature the AT contradicts) ->
                      a confirmable mechanical divergence -> gate-G FAIL.
    SUSPECTED_UNCONFIRMABLE -- the prose `[REF] Code-Design` example-table is
                      present but too LOOSE to mechanically align rows to AT
                      scenarios at the row level: the rows carry vague/placeholder
                      identifiers (no D3 manifest pins them, OB-G) so the
                      row-level diff can CONFIRM neither a clean bijection (no
                      PASS) NOR a concrete dropped-row/signature divergence (no
                      FAIL) -> gate-G surfaces the North-Star cap LOUD as
                      UNVERIFIED. CONTENT-DISTINCT from BIJECTIVE (whose rows align
                      1:1) and from DROPPED_ROW/SIGNATURE_MISMATCH (whose
                      divergence is concrete and confirmable).
    """

    BIJECTIVE = "bijective"
    DROPPED_ROW = "dropped-row"
    SIGNATURE_MISMATCH = "signature-mismatch"
    SUSPECTED_UNCONFIRMABLE = "suspected-unconfirmable"


class ContractInput(Enum):
    """The shape of the design contract gate-G diffs the AT-AST against (OB-G).

    PROSE_REF_CODE_DESIGN -- the prose `## Wave: DESIGN / [REF] Code-Design`
                             block present in the feature-delta (read via
                             `query.adr-section`). THE NORMAL CASE: OB-G RESOLVED
                             to DEFER the D3 `code-design.manifest.yaml`, so
                             gate-G diffs the PROSE contract. When a divergence is
                             suspected but NOT machine-confirmable to a row-level
                             bijection (no D3 manifest), gate-G is North-Star
                             capped -> UNVERIFIED (LOUD), never a false PASS, never
                             a hard FAIL.
    D3_MANIFEST -- a `code-design.manifest.yaml` (D3) -- DEFERRED (OB-G); not
                   present in this feature. Reserved vocabulary for when D3 lands.
    ADAPTER_ABSENT -- the CodeFactPort AstAdapter cannot run / the target language
                      is unsupported -> the mechanism could not run -> gate-G
                      degrades LOUD to INDETERMINATE.
    """

    PROSE_REF_CODE_DESIGN = "prose-ref-code-design"
    D3_MANIFEST = "d3-manifest"
    ADAPTER_ABSENT = "adapter-absent"


@dataclass(frozen=True)
class GateGObservable:
    """The observable slice of a gate-G run the slice-03 ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the §17 GateVerdict
    token + the diagnostic (the divergence the mechanical diff names) + whether
    the North-Star cap was surfaced LOUD. NEVER an internal gate-G field.

    ``verdict``        -- the §17 GateVerdict token returned by gate-G (one of the
                          LOCKED five; gate-G ran).
    ``diagnostic``     -- the human-readable divergence the mechanical diff names
                          (e.g. "ExampleTableRow 'empty-dataset' has no covering
                          scenario") -- non-empty on FAIL; the LOUD-cap reason on
                          UNVERIFIED.
    ``cap_surfaced``   -- the North-Star cap was surfaced LOUD in the envelope
                          (True on the suspected-but-unconfirmable UNVERIFIED case).
    ``ran``            -- the gate-G mechanism actually ran (False on the
                          adapter-absent INDETERMINATE degrade -- the Then names
                          the missing/un-runnable mechanism).
    """

    verdict: str | None
    diagnostic: str | None
    cap_surfaced: bool
    ran: bool
