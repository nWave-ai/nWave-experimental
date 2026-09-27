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
    #: A record exists but the later first oracle write changed its acceptance
    #: bytes.  The public CRAFT step can settle it by executing that oracle.
    craft_moved: bool = False


@dataclass(frozen=True)
class ModelState:
    """The owned state as the design defines it: a graph and a verified candidate."""

    request: str | None = None
    values: tuple[ValueState, ...] = ()
    # The model fixture deliberately gives every designed value the same
    # acceptance oracle and support locators.  Verification consumes those
    # declared bytes once per path, not one oracle-turn receipt per value.
    # Keep that physical evidence separately from the per-value projection:
    # a successful oracle turn for either value writes the shared bytes.
    shared_acceptance_bytes: bool = False
    # The fixture also gives every value `product_value.py` as its sole target.
    # Native verification observes that one declared byte path, while state
    # continues to report which value recorded the craft turn.
    shared_target_bytes: bool = False
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
}

#: §4 class B: the state does not admit the step. Exactly ONE lawful move, so
#: exactly one `NEXT` (G7).
SEQUENCE_REFUSALS = frozenset(
    {
        "HandoverAbsent",
        "ValueOutOfRange",
        "DesignUnbound",
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
            # The fixture deliberately gives every value the same acceptance
            # paths.  An oracle authored after an early craft therefore moves
            # that craft's record: its bytes were built against an earlier
            # acceptance tree.  The public state reports ``bytes moved`` and
            # owes CRAFT again, so the independent model must carry that fact
            # rather than treating a role receipt as eternally current.
            with_oracle = _with(state, value, oracle_recorded=True)
            # The fake oracle's later writes are byte-identical.  Only its first
            # write can move a craft record; invalidating on every receipt would
            # model a changed file that the public surface did not observe.
            values = (
                tuple(
                    replace(
                        item,
                        craft_moved=item.craft_recorded or item.craft_moved,
                        craft_recorded=False,
                    )
                    for item in with_oracle.values
                )
                if not state.shared_acceptance_bytes
                else with_oracle.values
            )
            return replace(
                with_oracle,
                values=values,
                shared_acceptance_bytes=True,
            ), ModelTerminal("Success", turns_bought=1, facts=frozenset({"ORACLE-RED"}))
        if not target.design_bound:
            return state, _refuse("DesignUnbound")
        if target.craft_recorded:
            return state, ModelTerminal("Success", facts=frozenset({"RECORDED"}))
        # A moved record is not an absent record.  The public CRAFT step first
        # runs its tracked oracle; in this fixture the target written by the
        # earlier craft makes that vector GREEN, so it re-points the record and
        # buys no model turn.  The provider answer is deliberately irrelevant.
        if target.craft_moved and state.shared_target_bytes:
            return _with(
                state, value, craft_recorded=True, craft_moved=False
            ), ModelTerminal("Success", facts=frozenset({"WITNESS"}))
        if answer != "accepted":
            return state, _role_refusal(name, answer)
        return replace(
            _with(state, value, craft_recorded=True, craft_moved=False),
            shared_target_bytes=True,
        ), ModelTerminal("Success", turns_bought=1, facts=frozenset({"TARGETS"}))

    if name == "verify":
        if any(not value.design_bound for value in state.values):
            return state, _refuse("DesignUnbound")
        if not state.shared_acceptance_bytes:
            # Native verification first reads immutable authored acceptance
            # evidence.  In this fixture the same declared paths are shared by
            # every value, so one successful oracle write supplies those bytes
            # even while another value still projects `oracle=unrecorded`.
            return state, _refuse("AcceptanceEvidenceUnavailable")
        if not state.shared_target_bytes:
            # Authored evidence exists, so verification reaches the declared
            # native argv; without its declared target byte that execution fails
            # rather than becoming an evidence-loading refusal.  As with the
            # oracle paths, a single shared target write is what native verify
            # consumes, rather than a craft receipt for every value.
            return state, ModelTerminal(
                "Refusal", "VerificationFailed", facts=frozenset({"RADIUS"})
            )
        if state.candidate is not None:
            return state, ModelTerminal(
                "Success", facts=frozenset({"CANDIDATE", "RECORDED"})
            )
        # Native verification has no provider answer. It constructs and
        # captures one candidate with zero turns; a host separately chooses
        # whether to prepare, invoke, and record either review role.
        return replace(state, candidate="c"), ModelTerminal(
            "Success", facts=frozenset({"CANDIDATE", "RADIUS"})
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
