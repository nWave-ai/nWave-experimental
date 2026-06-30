"""Self-attest verdict classifier -- a machine YES never authorizes (ADR-CA-001 D1).

The dual-source self-attest layer (D9 / flow-v2-design §R, Invariant 1
"asymmetric authority", Invariant 2 "no silent pass"). It reads a dual-source
verdict record carrying a mechanical-gate verdict, an LLM-reviewer verdict, a
reference to the mechanical evidence, and a watchdog/timeout signal, and
classifies the record onto the §17 ``GateVerdict`` SSOT (ADR-GV-001, FIVE
verdicts -- CONSUMED unchanged, no sixth, C6):

  * mechanical evidence present AND the two sources AGREE -> PASS
    (a mechanical control found no objection -- never a bare-LLM green)
  * an LLM say-so with NO mechanical evidence -> UNVERIFIED
    (a NO floor -- the bare-LLM YES never authorizes, Invariant 1)
  * the mechanical and LLM sources DISAGREE -> INDETERMINATE
  * the watchdog fired before the mechanical leg set its verdict ->
    INDETERMINATE (the mechanism could not run -- degrade LOUD)

A PASS means "a mechanical control found no objection", NEVER an authorizing GO.
UNVERIFIED and INDETERMINATE are honest NO-floors. Only a human GO advances the
flow (Invariant 1).

EXTEND-not-fork (ADR-CA-001 D1 / OB-ATTEST): the signed verdict record reuses the
ONE keyless content-seal -- ``at_review_signing.canonical_signed_json`` over an
additive signed-field set (``VERDICT_SIGNED_FIELDS``). There is NO second signing
scheme, NO HMAC (removed 2026-06-11), NO key. The seal is PROJECTED by the spine
over the record, never self-signed by the producing agent -- this module builds
the CLASSIFIER, the projection is the spine's concern (A4, not asserted here).

Pure domain -- no I/O, no dependency on ports or adapters. stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass

from .at_review_signing import SIGNED_FIELDS, canonical_signed_json
from .gate_outcome import GateVerdict


# ADR-CA-001 D1: the additive signed-field set for the general verdict record,
# layered onto the AT-review ``SIGNED_FIELDS`` -- the same ONE canonicalizer
# (``canonical_signed_json``) seals it. The fields the classifier decides on are
# appended to the inherited seven; no field is renamed, no second scheme.
VERDICT_SIGNED_FIELDS: tuple[str, ...] = (
    *SIGNED_FIELDS,
    "mechanical_verdict",
    "llm_verdict",
    "mechanical_evidence_ref",
    "watchdog_timed_out",
)

# Discriminating cause fragments (Invariant 2 -- the degrade names what failed).
# The three are mutually exclusive (none a substring of another's reason) so the
# two INDETERMINATE causes (divergence vs watchdog) are never conflated.
_REASON_GROUNDED = "mechanical control found no objection -- both sources agree"
_REASON_NO_EVIDENCE = (
    "no mechanical evidence reference -- a bare reviewer say-so does not "
    "authorize (UNVERIFIED, a NO floor)"
)
_REASON_DISAGREE = (
    "the mechanical and reviewer sources disagree -- two sources that disagree "
    "cannot ground a verdict (INDETERMINATE)"
)
_REASON_WATCHDOG = (
    "the watchdog timed out before the mechanical leg completed -- the "
    "mechanism could not run (INDETERMINATE, degrade LOUD)"
)


@dataclass(frozen=True)
class SelfAttestVerdict:
    """The classified self-attest outcome: a §17 GateVerdict + a cause-naming reason.

    Frozen: a classification is an observation, never mutated after construction.
    ``verdict`` is the §17 ``GateVerdict`` (one of the LOCKED five, no sixth);
    ``reason`` names WHY a machine YES did not authorize / why it degraded.
    """

    verdict: GateVerdict
    reason: str


def canonical_verdict_seal(record: dict[str, object]) -> bytes:
    """Seal a general verdict record via the ONE keyless content-seal.

    ADR-CA-001 D1: reuses ``at_review_signing.canonical_signed_json`` over the
    additive ``VERDICT_SIGNED_FIELDS`` -- one canonicalizer, an additive field
    set, never a second signing scheme, never HMAC, never a key. The seal is
    projected by the spine over the record, never self-signed here.
    """
    return canonical_signed_json(record, VERDICT_SIGNED_FIELDS)


def classify(
    mechanical_verdict: str | None,
    llm_verdict: str | None,
    mechanical_evidence_ref: str | None,
    watchdog_timed_out: bool,
) -> SelfAttestVerdict:
    """Classify a dual-source verdict record onto the §17 GateVerdict SSOT.

    The order is deterministic so each case is reached unambiguously:

      1. watchdog fired           -> INDETERMINATE (the mechanism could not run)
      2. both sources DISAGREE    -> INDETERMINATE (two sources that disagree)
      3. no mechanical evidence   -> UNVERIFIED   (bare-LLM, a NO floor)
      4. evidence + sources agree -> PASS         (a control found no objection)

    A machine YES never authorizes: a bare-LLM PASS floors to UNVERIFIED, a
    divergence / watchdog degrades LOUD to INDETERMINATE, each with a DISTINCT
    cause-naming reason. Only a mechanically-grounded agreement yields PASS, and
    even that PASS means "no objection found", never an authorizing GO.
    """
    if watchdog_timed_out:
        return SelfAttestVerdict(GateVerdict.INDETERMINATE, _REASON_WATCHDOG)

    if _sources_disagree(mechanical_verdict, llm_verdict):
        return SelfAttestVerdict(GateVerdict.INDETERMINATE, _REASON_DISAGREE)

    if _carries_no_mechanical_evidence(mechanical_verdict, mechanical_evidence_ref):
        return SelfAttestVerdict(GateVerdict.UNVERIFIED, _REASON_NO_EVIDENCE)

    return SelfAttestVerdict(_grounded_verdict(mechanical_verdict), _REASON_GROUNDED)


def _sources_disagree(mechanical_verdict: str | None, llm_verdict: str | None) -> bool:
    """True when both sources produced a verdict and they differ."""
    if mechanical_verdict is None or llm_verdict is None:
        return False
    return mechanical_verdict != llm_verdict


def _carries_no_mechanical_evidence(
    mechanical_verdict: str | None, mechanical_evidence_ref: str | None
) -> bool:
    """True when no mechanical leg grounds the verdict (bare reviewer say-so)."""
    if mechanical_verdict is None:
        return True
    return not mechanical_evidence_ref


def _grounded_verdict(mechanical_verdict: str | None) -> GateVerdict:
    """The mechanically-grounded verdict that stands once a control found no objection."""
    if mechanical_verdict is None:
        return GateVerdict.PASS
    return GateVerdict(mechanical_verdict)


__all__ = [
    "VERDICT_SIGNED_FIELDS",
    "SelfAttestVerdict",
    "canonical_verdict_seal",
    "classify",
]
