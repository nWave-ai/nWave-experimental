"""Domain types: the `_inline_restatement` clause scopes to gate-stack *enumeration*.

algebra-projections-enforced slice-04 — ADR-003 (REROUTE_DESIGN #2, DD-A6). The
narrowing witnesses pin the NARROWED behaviour of `_inline_restatement`
(`src/des/cli/verify_wave_contract_coherence.py:155-171`): a *structured gate-stack
enumeration* in prose FAILs (the drift ADR-FLOW-006 D8 cure-I exists to veto), while
a `des <gate-id>` command *invocation* and the `roadmap` artifact *noun* PASS (the
false positives ADR-003 D1 removes).

These witnesses complement (do NOT replace) the 5 existing slice-04 coverage ATs:
those prove the firing-surface hook covers distill/deliver + the real migrated
prose loci clear; these prove the clause those loci must clear distinguishes
enumeration from mention. The driving port is the SAME shipped gate
(`des verify-wave-contract-coherence`); the prose is synthetic (tmp_path) for the
enumeration/invocation discriminators and the REAL discuss locus for the byte-stable
preservation guard.

Every Gherkin domain noun is a typed enum here (Mandate-12 criterion 1); step bodies
consume the typed value (no raw ``str`` where an enum exists, no control flow).
"""

from __future__ import annotations

from enum import Enum


__all__ = [
    "INLINE_PROSE_BY_PHRASE",
    "NARROWING_VERDICT_BY_PHRASE",
    "CoherenceVerdict",
    "InlineProseShape",
]


# -- the §17 GateVerdict closed token set the coherence gate emits ----------------
# Reused verbatim (SSOT: src/des/domain/gate_outcome.GateVerdict). The narrowing
# witnesses assert on `fail` (a restated gate-stack enumeration is drift) and `pass`
# (a command invocation / artifact noun is legitimate operational prose).
class CoherenceVerdict(str, Enum):
    """The closed verdict token the ``verify-wave-contract-coherence`` gate returns."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


class InlineProseShape(str, Enum):
    """A prose presentation that exercises the narrowed inline-restatement clause.

    Each shape carries a valid ``gates-ref``/``outputs-ref`` pointer pair (so the
    pointer-presence check PASSes and the gate REACHES the inline-restatement clause
    — the clause under test), and differs only in the body the clause scans.
    """

    # A markdown list of >=2 bare catalog gate_ids presented AS a gate stack — the
    # re-enumeration of `gate_stack` ADR-003 D1 says STILL FAILs. (synthetic, tmp_path)
    GATE_STACK_ENUMERATION = "a restated gate-stack enumeration in the prose"
    # `des <gate-id>` invocations + the `roadmap.json` artifact noun, zero
    # enumeration — the legitimate operational prose ADR-003 D1 says now PASSes.
    # (synthetic, tmp_path)
    COMMAND_INVOCATION_AND_ARTIFACT_NOUN = (
        "command invocations and the roadmap.json artifact noun, with no enumeration"
    )
    # The real migrated DISCUSS skill prose exactly as the repo carries it — the
    # only currently-migrated wave; its PASS verdict must stay byte-stable across the
    # narrowing (ADR-003 D2). (the REAL repo locus, not synthetic)
    PRISTINE_DISCUSS = "the discuss wave prose exactly as the repository carries it"


# -- the body each synthetic shape presents to the gate --------------------------
# The bodies below are the literal prose the gate scans. The pointer pair is shared;
# the body discriminates enumeration (FAIL) from mention (PASS). These are DATA, not
# logic — the composition writes them to tmp_path and drives the real gate over them.
_POINTERS = "<!-- gates-ref: discuss -->\n<!-- outputs-ref: discuss -->\n"

_ENUMERATION_BODY = (
    _POINTERS
    + "# The discuss gate stack\n\n"
    + "The gate stack this wave runs, in order, is:\n\n"
    + "- carpaccio-slice-gate\n"
    + "- run-contract-gate\n"
    + "- commit-slice\n"
)

_INVOCATION_BODY = (
    _POINTERS
    + "# Operational prose\n\n"
    + "Run des verify-integrity to validate the audit log, then des init-log to "
    + "start the phase log.\n"
    + "The classic-mode plan file roadmap.json carries the per-slice phases.\n"
)

# Synthetic-prose body per shape (the PRISTINE_DISCUSS shape reads the REAL repo
# locus instead — the composition special-cases it, NOT a synthetic body).
SYNTHETIC_BODY_BY_SHAPE: dict[InlineProseShape, str] = {
    InlineProseShape.GATE_STACK_ENUMERATION: _ENUMERATION_BODY,
    InlineProseShape.COMMAND_INVOCATION_AND_ARTIFACT_NOUN: _INVOCATION_BODY,
}


# -- Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3) --------------
INLINE_PROSE_BY_PHRASE: dict[str, InlineProseShape] = {
    shape.value: shape for shape in InlineProseShape
}

NARROWING_VERDICT_BY_PHRASE: dict[str, CoherenceVerdict] = {
    "is rejected as a gate-stack restatement": CoherenceVerdict.FAIL,
    "clears the coherence check": CoherenceVerdict.PASS,
}
