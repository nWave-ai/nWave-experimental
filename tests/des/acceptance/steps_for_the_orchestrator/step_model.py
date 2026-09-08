"""The reference model: what each step SHOULD print and cost, from any state.

ADR-DES-003 §12 asks for one executable falsifier instead of a checklist a
reviewer must remember: a small pure model that says what each command answers,
and one property that throws generated sequences at the real commands and checks
they agree.

WHAT THIS IS, AND WHAT IT IS NOT. It is the design's own tables -- §2.4's
preconditions, L1's cost rule, §3's grammar, §4's refusal classes and
`canonical_next` -- turned into code. Production reads NONE of it. A
disagreement between this model and the CLI is a RED, never a second truth: the
model is the denotation the other observations derive from, and a slice that
changes a step without changing the model goes red before it reaches a review.

WHY IT IS TEST-SIDE. A model the production code consulted would stop being an
independent statement of the design and become a second implementation of it,
agreeing with the first by construction. The whole value is that the two are
written apart and compared.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


#: Every step of the canonical order, plus the two that stand outside it.
STEPS = (
    "state",
    "po",
    "design",
    "oracle",
    "craft",
    "verify",
    "integrate",
    "project",
)


@dataclass(frozen=True)
class ValueState:
    """What one value of the graph already carries."""

    observation: str
    design_bound: bool = False
    oracle_recorded: bool = False
    craft_recorded: bool = False


@dataclass(frozen=True)
class ModelState:
    """The owned state as the design defines it: a graph and a verified candidate."""

    request: str | None = None
    values: tuple[ValueState, ...] = ()
    candidate: str | None = None
    integrated: bool = False


@dataclass(frozen=True)
class ModelTerminal:
    """What one invocation answers: the outcome, its rows, its cost, its NEXT count.

    `facts` are the LABELS the block must carry. They are asserted because a
    terminal that drops a fact the software measured is exactly what §4b
    forbids, and because without them a mutation that stops printing `RECORDED`
    or `ORACLE-RED` leaves the surface agreeing with a model that never looked.
    """

    outcome: str
    what: str | None = None
    turns_bought: int = 0
    next_count: int = 1
    facts: frozenset[str] = field(default_factory=frozenset)


#: The refusal each unmet `ensures` of §2.4 is named by, keyed on the step that
#: would meet it. `canonical_next` answers WHICH is owed; this says how the
#: refusal spells it.
OWED_BY_STEP = {
    "design": "DesignUnbound",
    "oracle": "OracleUnrecorded",
    "craft": "CraftUnrecorded",
}

#: §4 class B: the state does not admit the step. Exactly ONE lawful move, so
#: exactly one `NEXT` (G7).
SEQUENCE_REFUSALS = frozenset(
    {
        "HandoverAbsent",
        "ValueOutOfRange",
        "DesignUnbound",
        "OracleUnrecorded",
        "CraftUnrecorded",
        "CandidateUnverified",
        "AlreadyIntegrated",
    }
)


def orchestrator_row(terminal: ModelTerminal) -> str | None:
    """What the `ORCHESTRATOR` line must say, or `None` when there must be none.

    G5: derived from primitive rows, and ABSENT on `Success`, where the move
    available now IS `NEXT`. The three states are the ones the terminals were
    measured wrong on twice: no turn bought, a turn bought whose words did not
    survive the boundary, and a turn whose answer is there to read.
    """
    if terminal.outcome == "Success":
        return None
    if terminal.turns_bought == 0:
        return "no role turn ran"
    if terminal.what == MALFORMED:
        return "did not survive the provider boundary"
    return "below"


def canonical_next(state: ModelState) -> str:
    """The first `ensures` of §2.4 not yet true, in the order the steps produce them.

    §2.4 states the same function answers two questions: the `NEXT` of
    `des state`, and the HOW of a sequence refusal. So a step never names, as
    HOW or NEXT, a step that would refuse in the state it names it from.
    """
    if state.request is None:
        return "po"
    for value in state.values:
        if not value.design_bound:
            return "design"
        if not value.oracle_recorded:
            return "oracle"
        if not value.craft_recorded:
            return "craft"
    return "integrate" if state.candidate is not None else "verify"


#: The refusals a REJECTING role produces, by step. §4 class F: the step returns
#: what the role said, one name per (role, outcome), never a software judgement.
REJECTED_BY = {
    "po": "ProductOwnerRejected",
    "rewrite": "ProductOwnerRejected",
    "design": "DesignRejected",
    "oracle": "AcceptanceDesignRejected",
    "craft": "CraftRejected",
    "verify": "ImplementationReviewRejected",
}

#: What a paid turn whose envelope the boundary cannot read answers: §4 class E,
#: `Indeterminate`, one turn bought and no diagnostic.
MALFORMED = "ModelEnvelopeUnavailable"


def _refuse(what: str, turns: int = 0) -> ModelTerminal:
    return ModelTerminal(
        "Refusal" if what in SEQUENCE_REFUSALS else "Indeterminate",
        what,
        turns_bought=turns,
        next_count=1 if what in SEQUENCE_REFUSALS else 2,
    )


def _role_refusal(name: str, answer: str) -> ModelTerminal:
    """The terminal a non-accepting turn leaves: bought, and forwarded as its own.

    §4 separates the two by CLASS, and so does the disposition. Class F is the
    role's own answer, forwarded: a `rejected` turn is a `Refusal`, because the
    role said no about something it understood. Class E is the envelope the
    boundary could not read: `Indeterminate`, because the world did not say no,
    it did not answer -- and the turn is bought either way.
    """
    # TWO at least, not three: the canonical move is dropped when it IS this
    # step, so a rejecting `design --value 1` leaves its own form after the HOW
    # and the projection. A terminal never prints one invocation twice.
    if answer == "malformed":
        return ModelTerminal("Indeterminate", MALFORMED, turns_bought=1, next_count=2)
    return ModelTerminal("Refusal", REJECTED_BY[name], turns_bought=1, next_count=2)


def step(
    state: ModelState,
    name: str,
    value: int | None = None,
    answer: str = "accepted",
    same_candidate: bool = False,
) -> tuple[ModelState, ModelTerminal]:
    """One invocation: the state after, and the terminal it printed.

    `answer` is what the provider said -- `accepted`, `rejected` or `malformed`
    -- because the cost rule and the grammar both depend on it: a rejected turn
    is bought and carries a diagnostic; a malformed one is bought and carries
    none, which is the incident §3's G6 exists for.
    """
    if name in ("state", "project"):
        # Pure reads (§2, L3): they commute with everything and cost nothing.
        if name == "project" and state.request is None:
            return state, _refuse("HandoverAbsent")
        return state, ModelTerminal("Success")

    if name in ("po", "rewrite"):
        stored = "R" if name == "po" else "R2"
        if state.request == stored:
            return state, ModelTerminal("Success")  # L1: the same Request twice
        if answer != "accepted":
            return state, _role_refusal(name, answer)
        if state.request is None:
            # A FRESH graph, whether or not one closed before it: `po` after an
            # integration is how the next Request starts, and it inherits
            # nothing from the one that closed.
            return (
                ModelState(request=stored, values=(ValueState("v1"), ValueState("v2"))),
                ModelTerminal("Success", turns_bought=1),
            )
        # §7: a Request that DIFFERS rewrites. The fake answers with the first
        # stored observation verbatim plus one new, so the split is one KEPT,
        # one ARCHIVED and one NEW -- measured by byte identity, never guessed.
        # The verified candidate does not survive a graph that changed under it.
        kept = state.values[0]
        return (
            replace(
                state,
                request=stored,
                values=(kept, ValueState("v3")),
                candidate=None,
            ),
            ModelTerminal(
                "Success",
                turns_bought=1,
                next_count=2,
                facts=frozenset({"KEPT", "ARCHIVED", "NEW"}),
            ),
        )

    if state.request is None:
        # INTEGRATION RELEASES THE GRAPH. Everything downstream of it is then
        # answered `HandoverAbsent`, because there is no Request left to owe
        # anything -- the terminal says so in as many words and sends the reader
        # to `des po`. The one exception is re-integrating the SAME candidate,
        # which is answered by what it is: already the destination.
        if name == "integrate" and state.integrated and same_candidate:
            return state, _refuse("AlreadyIntegrated")
        return state, _refuse("HandoverAbsent")

    if name in ("design", "oracle", "craft"):
        assert value is not None
        if not 1 <= value <= len(state.values):
            return state, _refuse("ValueOutOfRange")
        target = state.values[value - 1]
        if name == "design":
            if target.design_bound:
                # L1: bound and no finding is free, and says so.
                return state, ModelTerminal("Success", facts=frozenset({"RECORDED"}))
            if answer != "accepted":
                return state, _role_refusal(name, answer)
            return _with(state, value, design_bound=True), ModelTerminal(
                "Success",
                turns_bought=1,
                facts=frozenset({"ORACLE", "TARGETS", "ALGEBRA"}),
            )
        if name == "oracle":
            if not target.design_bound:
                return state, _refuse("DesignUnbound")
            if target.oracle_recorded:
                return state, ModelTerminal("Success", facts=frozenset({"RECORDED"}))
            if answer != "accepted":
                return state, _role_refusal(name, answer)
            # Authored and MEASURED red, one turn: §5 retires the pre-craft judge.
            return _with(state, value, oracle_recorded=True), ModelTerminal(
                "Success", turns_bought=1, facts=frozenset({"ORACLE-RED"})
            )
        if not target.design_bound:
            return state, _refuse("DesignUnbound")
        if not target.oracle_recorded:
            return state, _refuse("OracleUnrecorded")
        if target.craft_recorded:
            return state, ModelTerminal("Success", facts=frozenset({"RECORDED"}))
        if answer != "accepted":
            return state, _role_refusal(name, answer)
        return _with(state, value, craft_recorded=True), ModelTerminal(
            "Success", turns_bought=1, facts=frozenset({"TARGETS"})
        )

    if name == "verify":
        # §2.4 says the preconditions of `verify` ARE the canonical order run to
        # the end: the candidate covers every value, so every value owes its
        # three facts. Written as a second pass over the values, this model
        # checked design and oracle and forgot craft, and named `DesignUnbound`
        # where the surface truthfully named `CraftUnrecorded` -- a model that
        # disagreed with its own `canonical_next`. Derived from that one
        # function, the two cannot drift apart again.
        owed = canonical_next(state)
        if owed in OWED_BY_STEP:
            return state, _refuse(OWED_BY_STEP[owed])
        if state.candidate is not None:
            return state, ModelTerminal(
                "Success", facts=frozenset({"CANDIDATE", "RECORDED"})
            )
        if answer != "accepted":
            # A refusing review is bought; the examiner behind it never is. The
            # radius is measured BEFORE either, so it survives the refusal.
            return state, replace(
                _role_refusal(name, answer), facts=frozenset({"RADIUS"})
            )
        # The whole-diff review and the source-blind judgement: two turns.
        return replace(state, candidate="c"), ModelTerminal(
            "Success", turns_bought=2, facts=frozenset({"CANDIDATE", "RADIUS"})
        )

    if name == "integrate":
        if state.candidate is None:
            return state, _refuse("CandidateUnverified")
        # The graph is RELEASED, not merely marked: nothing is owed for this
        # Request any more, so the projection shows none and every later step
        # says so. `integrated` survives only to tell a re-integration of the
        # same candidate apart from a Request that never existed.
        return replace(state, request=None, values=(), integrated=True), ModelTerminal(
            "Success", facts=frozenset({"INTEGRATED", "CLEANUP"})
        )

    raise AssertionError(f"the model does not know the step {name!r}")


def _with(state: ModelState, position: int, **changes) -> ModelState:
    values = list(state.values)
    values[position - 1] = replace(values[position - 1], **changes)
    return replace(state, values=tuple(values))
