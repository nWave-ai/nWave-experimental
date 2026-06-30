"""Typed domain vocabulary for the f-coherence-and-attestation slice-04 ATs.

The self-attest verdict layer (D9 / ADR-CA-001 D1): the classifier that makes a
machine YES never authorize -- a bare-LLM PASS with no mechanical evidence is
UNVERIFIED (a NO floor, Invariant 1); two sources that disagree are INDETERMINATE.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-04
Gherkin names is expressed once here as a typed enum / frozen dataclass, so the
composition methods consume typed parameters (no raw ``str`` where an enum
exists). The DSL emerges from these typed concepts -- the slice-04 scenarios
range over the §17 GateVerdict set and the dual-source attestation cases, not
over decorator proliferation.

slice-04 REUSES the §17 GateVerdict set (the cross-tier-LOCKED 5-verdict SSOT,
ADR-GV-001 -- CONSUMED unchanged, no sixth, C6). gate-G (slice-03) and the
runner port (slice-05) are mechanical-evidence SOURCES the self-attest layer
reads; this slice CONSUMES the §17 verdict set, it does NOT extend it.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through composition-root driving ports (Mandate-13).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# ---------------------------------------------------------------------------
# §17 GateVerdict -- the FIVE verdicts (ADR-GV-001), CONSUMED unchanged. No
# sixth (C6). The AT-side mirror of `des.domain.gate_outcome.GateVerdict`; the
# wire tokens are byte-identical to the production enum's `.value`s. The
# self-attest classifier maps every attestation case onto these existing five
# (mechanically-grounded PASS / bare-LLM UNVERIFIED / dual-source-divergence
# INDETERMINATE / watchdog-timeout INDETERMINATE).
# ---------------------------------------------------------------------------


class GateVerdict(Enum):
    """The §17 uniform-failure-machine verdict set (ADR-GV-001, 5 verdicts)."""

    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    UNVERIFIED = "unverified"
    INDETERMINATE = "indeterminate"


# The LOCKED §17 verdict-token set -- the self-attest classifier must return ONE
# of these, never a sixth (C6). The slice-04 ATs assert the verdict is in this set.
LOCKED_GATE_VERDICTS: frozenset[str] = frozenset(v.value for v in GateVerdict)


# ---------------------------------------------------------------------------
# slice-04 scenario vocabulary -- the dual-source attestation cases.
# ---------------------------------------------------------------------------


class AttestationCase(Enum):
    """The four dual-source attestation cases the self-attest classifier decides.

    Each case builds a CONTENT-DISTINCT verdict record (the
    {mechanical_verdict, llm_verdict, mechanical_evidence_ref, watchdog} fields
    of ADR-CA-001 D1 differ per case) so a deterministic classifier maps each
    distinct record to its distinct verdict.

    MECHANICAL_EVIDENCE_AGREE -- the record carries a mechanical-evidence
                      reference AND the mechanical source and the LLM source
                      AGREE (mechanical_verdict == llm_verdict) -> the verdict is
                      mechanically grounded -> classified PASS (a control found no
                      objection). [AT-12]
    BARE_LLM_NO_EVIDENCE -- the record carries an LLM say-so but NO mechanical
                      evidence (mechanical_verdict is None / mechanical_evidence_ref
                      absent) -> the bare-LLM YES never authorizes -> classified
                      UNVERIFIED (a NO floor, Invariant 1). [AT-13]
    DUAL_SOURCE_DIVERGENCE -- the mechanical source and the LLM source DISAGREE
                      (mechanical_verdict != llm_verdict, both present) -> two
                      sources that disagree -> classified INDETERMINATE. [AT-14]
    WATCHDOG_TIMEOUT -- the mechanical leg did not complete within the watchdog
                      window (the mechanism could not run; mechanical_verdict
                      never set) -> classified INDETERMINATE (degrade LOUD -- the
                      mechanism could not run). [AT-15]
    """

    MECHANICAL_EVIDENCE_AGREE = "mechanical-evidence-agree"
    BARE_LLM_NO_EVIDENCE = "bare-llm-no-evidence"
    DUAL_SOURCE_DIVERGENCE = "dual-source-divergence"
    WATCHDOG_TIMEOUT = "watchdog-timeout"


@dataclass(frozen=True)
class VerdictRecord:
    """The dual-source verdict record the self-attest classifier reads (ADR-CA-001 D1).

    The field NAMES are the contract (the crafter owns types/internals). This
    AT-side frozen mirror lets each AttestationCase build a CONTENT-DISTINCT
    on-the-wire record so a deterministic classifier returns a distinct verdict
    per case.

    ``mechanical_verdict``     -- the mechanical-gate result (gate-G / runner /
                                  chain) as a §17 verdict token; ``None`` means no
                                  mechanical leg ran (bare-LLM detection, or the
                                  watchdog fired before it was set).
    ``llm_verdict``            -- the LLM-reviewer's verdict token, if any;
                                  ``None`` if no LLM leg produced one.
    ``mechanical_evidence_ref``-- a stable reference to the mechanical result (a
                                  CodeFactResult content hash / gate-G digest /
                                  runner exit record id) -- NOT a file path;
                                  ``None`` means the record carries no mechanical
                                  evidence (the "carries mechanical evidence"
                                  presence test).
    ``watchdog_timed_out``     -- the watchdog/timeout signal (ADR-CA-001 D1 "+ a
                                  watchdog/timeout signal"): True iff the mechanical
                                  leg did not complete within the watchdog window.
                                  DESIGN-CONTRACT ASSUMPTION (flagged to DELIVER):
                                  the ADR names a watchdog/timeout signal but does
                                  NOT pin its field name; this AT models it as a
                                  bool. DELIVER MUST wire whatever real signal shape
                                  it ships into the classifier's watchdog branch.
    """

    mechanical_verdict: str | None
    llm_verdict: str | None
    mechanical_evidence_ref: str | None
    watchdog_timed_out: bool = False


@dataclass(frozen=True)
class AttestObservable:
    """The observable slice of a self-attest classification the slice-04 ATs assert on.

    Port-exposed names only (Mandate-8 universe discipline): the classified §17
    GateVerdict token + the reason the classifier names (why it floored to a NO /
    degraded LOUD). NEVER an internal classifier field.

    ``verdict``  -- the §17 GateVerdict token the classifier returned (one of the
                    LOCKED five; the classifier ran).
    ``reason``   -- the human-readable reason the classifier names (e.g. "no
                    mechanical evidence reference -- bare-LLM say-so", "mechanical
                    and LLM sources disagree", "watchdog timed out") -- non-empty
                    on every NO-floor / degrade case.
    """

    verdict: str | None
    reason: str | None
