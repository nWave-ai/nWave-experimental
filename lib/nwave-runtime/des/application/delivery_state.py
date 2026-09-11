"""Read the owned state as a projection, and derive the canonical next step.

ADR-SSOT-002 Section 4b names this step by PROPERTY: «Reading the owned state as
a projection -- takes the repository root, returns the exact Request, the ordered
values, what each already carries.»  It is the step an orchestrator invokes after
every terminal, and the base every other step is read against.

WHAT IT MAY OBSERVE, and nothing beyond it.  The two owned facts are the
persisted handover at `.nwave/des/handover.json` and the turn records under
`refs/nwave/turns`.  Section 4b forbids a new persisted field for anything
derivable, so this module derives and adds none: `design` is `authority is not
None` in the handover the software itself wrote, and `oracle` and `craft` are
the existence of that value's turn ref.  The diagnostic turn LOGS are not read
here -- Section 4b: «No step may read one to decide anything» -- and the path
they live at is deliberately not spelled, because a trunk guard measures that
only their writer names it, and a module naming a substrate is a module that
could reach it.

WHY THE NEXT STEP IS DERIVED AND NOT DECIDED.  The canonical order is DATA: it
is written in the ADR and every step reports it.  This module computes the first
position in that order the state does not already hold, and returns its exact
invocation form.  It executes nothing, and the orchestrator may ignore it
entirely -- splitting the work, going upstream to a durable authority, or
stopping.

WHY A MEASUREMENT THAT DID NOT RESOLVE IS ITS OWN STATE.  A Git that never
answered has not said a turn record is absent.  Reporting absence there would
send the orchestrator to re-pay a turn whose record is on disk, so the third
state reaches the aggregate as `None` and the caller degrades LOUD (GDP-6,
GDP-8 arity corollary) rather than printing a plausible projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_observation import observe_text
from des.application.handover import Blocked, stored_handover
from des.domain.turn_record_ref import CRAFT_TURN, ORACLE_TURN, TURN_REF_ROOT, turn_ref


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from des.adapters.driven.git.git_observation import GitObservation


#: What a record can be. THREE states, not two, because two readers of the same
#: ref asked different questions and could disagree: this projection asked
#: whether the ref EXISTS while the runner asked whether its tree EQUALS the
#: current owned tree. Between them lay every state where recorded bytes moved,
#: and there `des state` printed `oracle=recorded` and named `des craft` while
#: `des craft` refused -- the projection naming a step that refuses in the very
#: state it names it from (ADR-DES-003 §5). One predicate now, and the third
#: state is SHOWN rather than folded into either neighbour.
#: A verification record reads by these SAME three states, and MOVED is the one
#: an upstream correction produces: the candidate is still on disk, the graph it
#: was measured against is not. Naming `des integrate` there would send an
#: orchestrator to bless evidence collected before the correction.
ABSENT, RECORDED, MOVED = "absent", "recorded", "bytes moved"


@dataclass(frozen=True, slots=True)
class ValueState:
    """One value of the persisted graph, and what it already carries."""

    position: int
    observation: str
    dependencies: tuple[str, ...]
    design_bound: bool
    oracle: str
    craft: str

    @property
    def oracle_recorded(self) -> bool:
        return self.oracle == RECORDED

    @property
    def craft_recorded(self) -> bool:
        return self.craft == RECORDED


@dataclass(frozen=True, slots=True)
class DeliveryState:
    """The whole projection: the exact Request and its ordered values.

    `request is None` is the state of a root nothing has been decomposed in.  It
    is a state the projection READS, never an error: the canonical next step
    there is the Product Owner, and saying so is the whole point of the step.
    """

    request: str | None
    values: tuple[ValueState, ...]
    candidate: str | None = None
    candidate_record: str = ABSENT


def _turn_refs(root: Path, observe: Callable[..., GitObservation]) -> set[str] | None:
    """Every existing turn ref, in ONE observation, or `None` if Git did not answer.

    One call rather than one per value and role: the namespace is small, and a
    projection that spends 2N subprocesses to answer a read is a projection an
    orchestrator stops invoking.
    """
    observed = observe(root, "for-each-ref", "--format=%(refname)", TURN_REF_ROOT)
    if observed.returncode:
        return None
    return {line.strip() for line in observed.stdout.splitlines() if line.strip()}


def read_state(
    root: Path, observe: Callable[..., GitObservation] = observe_text
) -> DeliveryState | Blocked:
    """The projection, or the software refusal that says why it is not readable."""
    stored = stored_handover(root)
    if isinstance(stored, Blocked):
        return stored
    if stored is None:
        return DeliveryState(None, ())
    refs = _turn_refs(root, observe)
    if refs is None:
        return Blocked(
            "TurnRecordsUnobservable",
            "the turn-record namespace could not be read, so what each value "
            "already carries is unknown and no next step can be derived from it",
            f"run `git -C {root} for-each-ref {TURN_REF_ROOT}` and read what it "
            "refuses, then invoke this step again",
        )
    # ONE predicate, the runner's, imported here rather than re-implemented:
    # §5 measured the contradiction between this projection asking whether a ref
    # exists and the runner asking whether its tree still matches. Nothing is
    # composed by importing it -- the projection buys no turn and enacts nothing.
    from des.application.delivery_continuation import DeliveryContinuationRunner

    runner = DeliveryContinuationRunner()
    values = []
    for position, value in enumerate(stored.values, start=1):
        facts = (
            None
            if value.authority is None
            else runner.derive_authority(root, value.authority)
        )
        usable = facts is not None and not hasattr(facts, "disposition")
        values.append(
            ValueState(
                position,
                value.observation,
                value.dependencies,
                value.authority is not None,
                _record(
                    turn_ref(stored.request, value.observation, ORACLE_TURN) in refs,
                    usable and runner.oracle_turn_complete(root, stored, value, facts),
                ),
                _record(
                    turn_ref(stored.request, value.observation, CRAFT_TURN) in refs,
                    usable and runner.craft_turn_complete(root, stored, value, facts),
                ),
            )
        )
    verified = runner.verification_record(root, stored)
    return DeliveryState(
        stored.request,
        tuple(values),
        None if verified is None else verified.candidate,
        _record(
            verified is not None,
            verified is not None and verified.covers_current_upstream,
        ),
    )


def _record(exists: bool, current: bool) -> str:
    """The three states a record can be in, never collapsed to two."""
    if not exists:
        return ABSENT
    return RECORDED if current else MOVED


def canonical_next(state: DeliveryState, root: Path) -> str:
    """The first step in the canonical order the state does not already hold.

    Returned in its EXACT invocation form -- the command and the minimum inputs
    that step requires -- because Section 4b asks for the form that would invoke
    the step, never a description of it.
    """
    if state.request is None:
        return (
            f"des po --repo-root {root} -- one Request on stdin, decomposed into "
            "its ordered observable values"
        )
    # VALUE BY VALUE, not phase by phase.  The handover's values are already in
    # canonical topological order, so the first one that is not complete is the
    # first work the order owes, and its own three facts are checked in the
    # order the steps produce them.  Sweeping design across every value first
    # would name a step for value 2 while value 1 has no oracle, which is
    # neither what the runner's loop does nor what an orchestrator delivering
    # one value at a time would read as next.
    for value in state.values:
        if not value.design_bound:
            return f"des design --repo-root {root} --value {value.position}"
        if not value.oracle_recorded:
            return f"des oracle --repo-root {root} --value {value.position}"
        if not value.craft_recorded:
            return f"des craft --repo-root {root} --value {value.position}"
    if state.candidate is not None and state.candidate_record == RECORDED:
        return f"des integrate --repo-root {root} --candidate {state.candidate}"
    return f"des verify --repo-root {root}"
