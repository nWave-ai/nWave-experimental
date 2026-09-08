"""Whether a mechanical checker for the algebra is reachable, and what to say.

ADR-SSOT-002 Section 1a, item 6, is a non-inferiority obligation: «Algebra-driven
design: observations, observational equality, constructors, laws and preservation
maps named before implementation.»  Naming them is the ARCHITECT's work and needs
no tool.  MECHANICALLY CHECKING them -- that the laws hold, that the preservation
maps compose -- needs Agda or TLA+, and this repository ships neither.

WHY THIS IS MEASURED AND NOT ASKED.  A stored answer to "do you want the
modelling tools" can be stale the moment the environment changes, and an
obligation attested from a stale answer is attested from nothing.  Whether the
checker is REACHABLE is a primitive observation, and a primitive observation can
be incomplete but cannot be wrong (`boundary:software-measures-model-decides`).
So the software measures, says what the measurement means for the obligation,
and decides nothing: `nw-auto` asks the human once whether to install them, and
the human installing them is what flips this measurement.

WHY IT IS SAID AT ALL.  Discord feedback, 2026-09-05: a tool absent without a
warning.  An obligation nobody could mechanically check, reported as silence,
reads as an obligation met.  Stating it is GDP-6, degrade LOUD, applied to a
non-inferiority item rather than to a gate.
"""

from __future__ import annotations

import shutil


#: The two checkers Section 6a's algebraic design authority is expressed in.
#: A closed tuple rather than a search: naming them is what makes the terminal
#: line say WHICH tool would answer, instead of "some tool is missing".
ALGEBRAIC_CHECKERS = ("agda", "tlc")


def reachable_checkers() -> tuple[str, ...]:
    """Every declared algebraic checker this environment can actually run."""
    return tuple(name for name in ALGEBRAIC_CHECKERS if shutil.which(name) is not None)


def algebra_line() -> str:
    """One terminal line stating what item 6 of Section 1a rests on here.

    Both branches are stated.  An obligation reported only when it is unmet
    teaches the reader that silence means met, and silence is exactly what the
    Discord report was about.
    """
    found = reachable_checkers()
    if found:
        # What was measured is a NAME on PATH, not a working checker. Saying
        # "can be checked mechanically" would be a claim derived from that
        # observation, and a derived claim can be wrong where the primitive one
        # cannot (GDP-8: decide on the property, never the designation). The
        # honest sentence states the reach and leaves the running to the
        # architect, who is the one who would find out.
        return (
            "ALGEBRA: " + ", ".join(found) + " on PATH, so a checker for the "
            "algebraic design obligation of ADR-SSOT-002 Section 1a item 6 is "
            "reachable; whether it runs is for the turn that uses it to find out"
        )
    return (
        "ALGEBRA: INDETERMINATE -- neither "
        + " nor ".join(ALGEBRAIC_CHECKERS)
        + " is on PATH, so the algebraic design obligation of ADR-SSOT-002 "
        "Section 1a item 6 rests on the architect's typed facts alone and is "
        "not mechanically checked; install one of them to change this"
    )
