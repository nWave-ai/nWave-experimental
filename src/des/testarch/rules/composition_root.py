"""P3 composition-root rule (ADR-TEST-002 slice-09, Pillar 3).

slice-09 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port: *a step function MUST
build the system-under-test through a production composition-root entry call, NOT
by hand-wiring its collaborator object graph inline*. A step body that constructs
one or more SUT-collaborator types directly (``repo = InMemoryRepo();
svc = OrderService(repo, FakeClock(), ...)``) is hand-wiring the application — it
duplicates the production wiring, drifts from it, and tests an object graph the
user never runs (Pillar 3: "app as in production"; the SUT is built via the
production composition root, only external/non-deterministic ports are faked).
A step that reaches a single composition-root entry (``app = build_application()``
/ ``compose_root()``) and drives the SUT through it is clean.

This is the MECHANIZABLE Pillar — P3 (composition-root) — only. P1
(domain-language) and P2 (chained-narrative) stay Tier-J agent-audit and are OUT
of scope here: they are semantic judgments the AST cannot decide. P3 is
structural — the construction of a known collaborator type vs a call to a known
composition-root entry is a fact the adapter supplies.

The mechanism: a step body's COLLABORATOR-CONSTRUCTING assignments are structural
facts the adapter reports (via ``assignments_constructing_type`` — every
``name = SomeType(...)`` whose constructed type is in a known SUT-collaborator
set), and its CALL sites are reported via ``calls_in_function`` (used to spot the
presence/absence of a composition-root entry call). The rule flags a step that
hand-wires (constructs ≥1 collaborator type) where no composition-root entry call
is present; a step whose only SUT construction is a composition-root entry call is
clean.

The collaborator-type set and the composition-root entry names are DOMAIN
constants (the wiring vocabulary), not parser concepts — kept in lock-step with
the acceptance vocabulary.

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names the abstract capabilities only; the parser walk is the adapter's
job.

``detect`` runs the hand-wired-vs-composition-root cross-check. The capability
``calls_in_function`` is realized by the production ``PythonAstAdapter``
(slice-03); ``assignments_constructing_type`` is an enum-registered capability
(``capabilities.py``: ``ASSIGNMENTS_CONSTRUCTING_TYPE``) realized on
``PythonAstAdapter`` with the ``ConstructInfo`` plain-data type in ``ports.py``. NO
new capability is added by this slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import FunctionInfo, TestSuiteAstAdapter


# The step decorators that mark a pytest-bdd step body. Hand-wiring inside any of
# these is the P3 breach the gate flags. Domain constants — not a parser API.
STEP_DECORATORS: frozenset[str] = frozenset({"given", "when", "then", "step"})

# The SUT-collaborator types a step body must NOT construct inline. A step that
# instantiates any of these is hand-wiring the application's object graph instead
# of reaching the production composition root. Domain constants (the wiring
# vocabulary), kept in lock-step with the acceptance vocabulary's
# ``CompositionConstructKind``. These stand for the collaborators a real feature's
# composition root would assemble (a repository, a clock, an application service);
# the gate reads the CONSTRUCTED-TYPE name, not behaviour.
SUT_COLLABORATOR_TYPES: frozenset[str] = frozenset(
    {"InMemoryRepo", "FakeClock", "OrderService"}
)

# The composition-root entry names a clean step calls to build the SUT in
# production wiring. A step whose SUT construction is a call to one of these — and
# which constructs no collaborator type inline — is clean. Domain constants.
COMPOSITION_ROOT_ENTRIES: frozenset[str] = frozenset(
    {"build_application", "compose_root"}
)

# The breach-kind name the verdict reports (the port-exposed ``Violation.kind``
# string). Kept in lock-step with the acceptance vocabulary's
# ``CompositionBreachKind``.
HAND_WIRED_SUT_IN_STEP_BODY = "hand_wired_sut_in_step_body"


@dataclass(frozen=True)
class Violation:
    """A flagged P3 composition-root breach (port-exposed observable).

    ``function``    — the offending step function's name.
    ``constructed`` — a SUT-collaborator type the step hand-wires inline (e.g.
                      ``"OrderService"``).
    ``kind``        — ``"hand_wired_sut_in_step_body"``: a step body assembled the
                      SUT's collaborator graph by hand where a composition-root
                      entry call belongs.
    ``lineno``      — the 1-based source line of the offending construction.
    """

    function: str
    constructed: str
    kind: str
    lineno: int


@dataclass(frozen=True)
class CompositionRootVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == clean step suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.FUNCTIONS_WITH_DECORATOR,
    Capability.CALLS_IN_FUNCTION,
    Capability.ASSIGNMENTS_CONSTRUCTING_TYPE,
)
def detect(
    source: str,
    *,
    adapter: TestSuiteAstAdapter,
    filename: str = "<test>",
) -> CompositionRootVerdict:
    """Scan one step-suite source for P3 composition-root violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``): find every
    pytest-bdd step function, then flag any step that constructs a known
    SUT-collaborator type inline (``assignments_constructing_type``) where no
    production composition-root entry call (``calls_in_function``) is present in
    the same body. A step whose only SUT construction is a composition-root entry
    call yields no violation. Returns a ``CompositionRootVerdict`` naming each
    offending step + the collaborator type it hand-wires. Language-agnostic: the
    rule never touches ``ast``.

    """
    tree = adapter.parse(source, filename)
    step_functions = adapter.functions_with_decorator(tree, STEP_DECORATORS)
    violations = tuple(
        breach
        for function in step_functions
        for breach in _breaches_of(adapter, tree, function)
    )
    return CompositionRootVerdict(violations=violations)


def _breaches_of(
    adapter: TestSuiteAstAdapter, tree: object, function: FunctionInfo
) -> tuple[Violation, ...]:
    """Every P3 hand-wired-SUT breach a single step body carries.

    A step body breaches P3 when it constructs ≥1 known SUT-collaborator type
    inline AND no production composition-root entry call is present in the body —
    each such inline construction becomes one breach naming the offending step +
    the collaborator type it hand-wires. A body whose only SUT construction is a
    composition-root entry call (or which constructs no collaborator at all)
    carries no breach.
    """
    constructions = adapter.assignments_constructing_type(
        tree, function, SUT_COLLABORATOR_TYPES
    )
    if not constructions or _has_composition_root_entry(adapter, tree, function):
        return ()
    return tuple(
        Violation(
            function=function.name,
            constructed=construction.constructed,
            kind=HAND_WIRED_SUT_IN_STEP_BODY,
            lineno=construction.lineno,
        )
        for construction in constructions
    )


def _has_composition_root_entry(
    adapter: TestSuiteAstAdapter, tree: object, function: FunctionInfo
) -> bool:
    """True iff ``function``'s body calls a production composition-root entry.

    A step that reaches ``build_application()`` / ``compose_root()`` builds the
    SUT through the production composition root — so even an inline construction in
    the same body is not the hand-wiring breach P3 flags.
    """
    return any(
        call.callee in COMPOSITION_ROOT_ENTRIES
        for call in adapter.calls_in_function(tree, function)
    )
