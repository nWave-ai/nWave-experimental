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

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_observation import observe_text
from des.application.handover import Blocked, HandoverValue, stored_handover
from des.domain.turn_record_ref import CRAFT_TURN, ORACLE_TURN, TURN_REF_ROOT, turn_ref
from des.ports.driven_ports.task_invocation_port import DesignFacts


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

#: The fourth state, shown only where the selected acceptance facts cannot be
#: derived (a legacy partial selection, or one made over another DESIGN): the
#: record may exist, but nothing can say what it was measured against.
UNCERTAIN = "uncertain"

#: Human-page labels of one evidence record or one selected revision.
CURRENT, HISTORICAL = "current", "historical"

_SELECTION_UNCERTAIN = frozenset(
    {"SelectedRevisionIncomplete", "SelectedRevisionRealignmentNeeded"}
)
_EVIDENCE_NAME = re.compile(r"([0-9a-f]{40,64})-([0-9a-f]{64})-.*\.json")


@dataclass(frozen=True, slots=True)
class SelectionView:
    """What one value's selected revision is, and where it came from."""

    source: str
    oracle: str
    supports: tuple[str, ...]
    verification: tuple[tuple[str, ...], ...] | None
    oracle_verification_index: int | None
    label: str
    what: str | None = None
    how: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRow:
    """One retained native observation, measured over one candidate."""

    locator: str
    sha256: str
    candidate: str
    label: str


@dataclass(frozen=True, slots=True)
class ValueState:
    """One value of the persisted graph, and what it already carries."""

    position: int
    observation: str
    dependencies: tuple[str, ...]
    design_bound: bool
    oracle: str
    craft: str
    selection: SelectionView | None = None
    # Internal routing fact: the oracle's own bytes/authority still match even
    # when a recorded craft moved the production bytes it judges.
    oracle_witness_current: bool = False

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
    evidence: tuple[EvidenceRow, ...] = ()


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
        # ONE reader of the selected revision, the same every step asks.
        facts = (
            None
            if value.authority is None
            else runner.selected_authority(root, stored, position)
        )
        usable = facts is not None and not hasattr(facts, "disposition")
        failure = getattr(facts, "failure", None)
        uncertain = (failure is not None and failure.what in _SELECTION_UNCERTAIN) or (
            usable and runner.cited_design_sections(root, stored, value) is None
        )
        oracle_ref = turn_ref(stored.request, value.observation, ORACLE_TURN)
        craft_ref = turn_ref(stored.request, value.observation, CRAFT_TURN)
        craft_current = usable and runner.craft_turn_complete(
            root, stored, value, facts
        )
        oracle_witness_current = usable and runner.oracle_turn_complete(
            root, stored, value, facts
        )
        # The oracle record is a fact about the acceptance bytes and the
        # selected revision identity alone: production target bytes are the
        # crafter's to move and carry no oracle-authorship claim (design
        # authority: docs/feature/atomic-selected-acceptance, section-granular
        # currentness).  It is therefore never coupled to `craft_current`.
        oracle_current = oracle_witness_current
        values.append(
            ValueState(
                position,
                value.observation,
                value.dependencies,
                value.authority is not None,
                _record(
                    oracle_ref in refs,
                    oracle_current,
                    uncertain,
                ),
                _record(
                    craft_ref in refs,
                    craft_current,
                    uncertain,
                ),
                _selection_view(
                    value,
                    uncertain,
                    None if failure is None else failure.what,
                    None if failure is None else failure.how,
                ),
                oracle_witness_current,
            )
        )
    verified = runner.verification_record(root, stored)
    current = verified is not None and verified.covers_current_upstream
    return DeliveryState(
        stored.request,
        tuple(values),
        None if verified is None else verified.candidate,
        _record(verified is not None, current),
        _evidence_rows(
            root,
            verified.candidate
            if current and _measured_on_current_code(root, runner, verified.candidate)
            else None,
        ),
    )


def _measured_on_current_code(root: Path, runner: object, candidate: str) -> bool:
    """A record is proof now only while its candidate sits on the code as it stands.

    The candidate is parented on the base it was measured over; a later commit
    moves that base, so the kept record is historical, not current. Only the
    evidence label reads this; the canonical NEXT keeps the record predicate.
    """
    if runner.destination_is(root, candidate):
        return True
    base = runner.candidate_base(root, candidate)
    head = runner._head(root)
    return isinstance(base, str) and isinstance(head, str) and base == head


def _selection_view(
    value: HandoverValue, uncertain: bool, what: str | None, how: str | None
) -> SelectionView | None:
    """The selected tuple with its source, or ``None`` when nothing is derivable."""
    if value.acceptance_oracle is not None:
        complete = value.acceptance_verification is not None
        return SelectionView(
            "DISTILL schema_version 2"
            if complete
            else "DISTILL schema_version 1 (incomplete)",
            value.acceptance_oracle,
            value.acceptance_supports,
            value.acceptance_verification,
            value.acceptance_oracle_verification_index,
            UNCERTAIN if uncertain else CURRENT,
            what,
            how,
        )
    if isinstance(value.authority, DesignFacts):
        facts = value.authority
        return SelectionView(
            "DESIGN",
            facts.oracle,
            facts.acceptance_supports,
            facts.verification,
            facts.oracle_verification_index,
            CURRENT,
        )
    return None


def _evidence_rows(
    root: Path, current_candidate: str | None
) -> tuple[EvidenceRow, ...]:
    """Every retained native observation, labelled by what it was measured over.

    Read from the evidence files themselves, which are never rewritten or
    deleted, so no second cache exists.  ``current`` is only the observation of
    the candidate a current verify record covers; every other kept file is
    ``historical``; one whose bytes no longer match the digest in its name is
    ``uncertain``.
    """
    directory = root / ".nwave" / "des" / "logs" / "native"
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return ()
    rows = []
    for path in paths:
        named = _EVIDENCE_NAME.fullmatch(path.name)
        if named is None:
            continue
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = ""
        label = (
            UNCERTAIN
            if digest != named.group(2)
            else CURRENT
            if named.group(1) == current_candidate
            else HISTORICAL
        )
        rows.append(
            EvidenceRow(
                path.relative_to(root).as_posix(), named.group(2), named.group(1), label
            )
        )
    return tuple(rows)


def _record(exists: bool, current: bool, uncertain: bool = False) -> str:
    """The states a record can be in, never collapsed."""
    if uncertain:
        return UNCERTAIN
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
            f"des po --repo-root {root} (--project | --epic ID | --feature ID | --slice FEATURE_ID SLICE_ID) -- one Request on stdin, decomposed into "
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
        if value.selection is not None and value.selection.label == UNCERTAIN:
            return f"des distill --repo-root {root} --replace-current --input -"
        if not value.oracle_recorded:
            # A moved craft makes its prior oracle historical for the state
            # projection.  If that oracle's own bytes and authority are still
            # current, `des craft` can execute it on the moved workspace and
            # settle the record without buying either authoring turn.  A moved
            # oracle of its own is different: return it to its author first.
            if value.craft == MOVED and value.oracle_witness_current:
                return f"des craft --repo-root {root} --value {value.position}"
            return f"des oracle --repo-root {root} --value {value.position}"
        if not value.craft_recorded:
            return f"des craft --repo-root {root} --value {value.position}"
    if state.candidate is not None and state.candidate_record == RECORDED:
        return f"des integrate --repo-root {root} --candidate {state.candidate}"
    return f"des verify --repo-root {root}"
