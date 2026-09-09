"""What every step prints on its `NEXT` lines, computed the same way once.

ADR-SSOT-002 Section 4b: `NEXT` is «the canonical next step, or steps, each with
its exact invocation form -- the command and the minimum inputs that step
requires.  Not a description of the step: the form that would invoke it.»

WHY THERE IS NO PER-STEP TABLE.  The canonical order is DATA, and the state
projection already derives the first position that order does not hold.  So the
next step AFTER any successful step is exactly what `des state` would say, read
from the two owned facts rather than from a literal each step carries -- a table
would be a second spelling of the order and would drift the moment a step's own
effect changed what the state holds.

WHY A REFUSAL NAMES SEVERAL AND CHOOSES NONE.  Section 4b: «A Refusal names
every move that is available and chooses between none of them: choosing would
mean reading the diagnostic, which is exactly what this module refuses to do.»
So a refusing step prints its own re-invocation form, the projection, and
nothing that ranks them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.application.delivery_state import canonical_next, read_state
from des.application.handover import Blocked


if TYPE_CHECKING:
    from pathlib import Path


def projection(root: Path) -> str:
    """The read-only step every other terminal can fall back to."""
    return f"des state --repo-root {root}"


def after_step(root: Path) -> str:
    """The canonical next step, read from the owned state this step just moved.

    A projection that cannot be read is not silently replaced by a guess: the
    orchestrator is sent to the read-only step, which says LOUD why the state
    is unreadable instead of naming a step derived from nothing.
    """
    state = read_state(root)
    if isinstance(state, Blocked):
        return projection(root)
    return canonical_next(state, root)


#: The SEQUENCE refusals (ADR-DES-003 §4 class B): the owned state does not
#: admit the step. Each has exactly ONE lawful move -- the step that produces
#: what it lacks -- so under G7 it prints one `NEXT` and signals no fork.
#: Closed and named here because the cardinality of `NEXT` is the fork signal,
#: and a fork announced where there is none teaches the orchestrator to stop
#: counting.
SEQUENCE_REFUSALS = frozenset(
    {
        "HandoverAbsent",
        "ValueOutOfRange",
        "DesignUnbound",
        "CandidateUnverified",
        "CandidateUnreadable",
        "AlreadyIntegrated",
    }
)


def moves_after_refusal(root: Path, own_form: str, what: str = "") -> tuple[str, ...]:
    """Every move available after this step refused, ranked by nothing.

    A SEQUENCE refusal gets ONE: §2.4 states that the HOW of a sequence refusal
    and the `NEXT` of `des state` are the same function of the same state, so
    the canonical step IS the whole move and the other two lines would announce
    a fork that does not exist (G7).

    Everything else gets three, derived and unranked: the canonical step the
    CURRENT state owes, this step's own re-invocation after the HOW, and the
    read-only projection. The canonical move is dropped when it IS this step, so
    a terminal never prints one invocation twice.

    `own_form` is a format string taking `root`, so a step states its own
    re-invocation shape once and this module never has to know its flags.
    """
    canonical = after_step(root)
    if what in SEQUENCE_REFUSALS:
        return (canonical,)
    own = own_form.format(root=root)
    moves = [] if canonical == own else [canonical]
    moves.append(f"{own} -- after the HOW above")
    moves.append(projection(root))
    return tuple(dict.fromkeys(moves))
