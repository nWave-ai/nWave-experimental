"""M2 technical-call-smell rule (ADR-TEST-002 slice-08, Mandate 2).

slice-08 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port: *a pytest-bdd step
function MUST NOT issue a TECHNICAL call in its body* — an HTTP client call
(``requests.*`` / ``httpx.*``) or a DB call (``db.execute`` / ``cursor.execute``
/ ``session.execute``), including a technical call that drives an assertion
(``assert client.get(url).status_code == 200``). Only domain-language delegation
belongs in a step body (Mandate 2 three-abstraction-layer model: step methods
delegate to a domain service; transport + cursor live inside the service). A step
that reaches for a transport or a cursor is the Mystery-Guest / Eager-Test smell
family (research C1) — the scenario stops speaking the domain.

This is the MECHANIZABLE half of M2 only — the call-shape DENYLIST. The
ubiquitous-language SEMANTIC judgment ("does the step speak the domain?") stays
Tier-J agent-audit and is OUT of scope here.

A step function's call sites are STRUCTURAL facts the adapter supplies (via
``functions_with_decorator`` + ``calls_in_function``, which returns the dotted
callee of each call site). The denylist keys on the dotted callee shape. A bare
attribute read with NO call (e.g. ``assert response.status_code == 201`` with
``response`` already in hand) carries no call site and is outside this rule's
dotted-callee mechanism (slice-08 [REF] residue — would need an
attribute-read-in-assert capability the port does not yet expose; flagged, NOT
falsely registered).

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names the abstract capabilities only; the parser walk is the adapter's
job. The step decorator names and the denylisted technical-callee shapes are
domain constants, not parser concepts.

``detect`` runs the denylist cross-check. The capabilities it consumes
(``functions_with_decorator``, ``calls_in_function``) are realized by the
production ``PythonAstAdapter`` (slice-01 + slice-03), so no capability is added
by this slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import FunctionInfo, TestSuiteAstAdapter


# The step decorators that mark a pytest-bdd step body. A technical call inside
# any of these is the smell M2 flags. Domain constants — not a parser API.
STEP_DECORATORS: frozenset[str] = frozenset({"given", "when", "then", "step"})

# The technical-callee shapes a step body must never issue (the DENYLIST).
#
#   * HTTP client calls — a dotted callee whose base module is an HTTP client
#     (``requests.get`` / ``requests.post`` / ``httpx.get`` / ``httpx.post`` …):
#     matched by the base prefix so every verb is caught without enumerating it.
#   * DB calls — a cursor/connection/session ``.execute`` (``db.execute`` /
#     ``cursor.execute`` / ``session.execute``): matched by the exact dotted
#     callee.
#
# Domain constants (the call-shape denylist), kept in lock-step with the
# acceptance vocabulary's ``TechnicalCallKind``.
HTTP_CLIENT_PREFIXES: frozenset[str] = frozenset({"requests", "httpx"})
DB_EXECUTE_CALLEES: frozenset[str] = frozenset(
    {"db.execute", "cursor.execute", "session.execute"}
)

# The breach-kind name the verdict reports (the port-exposed ``Violation.kind``
# string). Kept in lock-step with the acceptance vocabulary's
# ``TechnicalCallBreachKind``.
TECHNICAL_CALL_IN_STEP_BODY = "technical_call_in_step_body"


@dataclass(frozen=True)
class Violation:
    """A flagged M2 technical-call-smell breach (port-exposed observable).

    ``function`` — the offending step function's name.
    ``callee``   — the technical dotted callee the step issues (e.g.
                   ``"requests.post"`` or ``"db.execute"``).
    ``kind``     — ``"technical_call_in_step_body"``: a step body issued a
                   denylisted technical call where only domain delegation belongs.
    ``lineno``   — the 1-based source line of the offending call site.
    """

    function: str
    callee: str
    kind: str
    lineno: int


@dataclass(frozen=True)
class TechnicalCallSmellVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == clean suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.FUNCTIONS_WITH_DECORATOR,
    Capability.CALLS_IN_FUNCTION,
)
def detect(
    source: str,
    *,
    adapter: TestSuiteAstAdapter,
    filename: str = "<test>",
) -> TechnicalCallSmellVerdict:
    """Scan one test-suite source for M2 technical-call-smell violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``): find every
    pytest-bdd step function, then flag any call site in its body whose dotted
    callee is a denylisted technical call — an HTTP client call
    (``requests.*`` / ``httpx.*``) or a DB call (``db.execute`` /
    ``cursor.execute`` / ``session.execute``), including a technical call nested
    inside an assertion. A step that delegates only to domain services yields no
    violation. Returns a ``TechnicalCallSmellVerdict`` naming each offending step
    + the technical callee it issues. Language-agnostic: the rule never touches
    ``ast``.
    """
    tree = adapter.parse(source, filename)
    step_functions = adapter.functions_with_decorator(tree, STEP_DECORATORS)
    violations = tuple(
        breach
        for function in step_functions
        for breach in _breaches_of(adapter, tree, function)
    )
    return TechnicalCallSmellVerdict(violations=violations)


def _breaches_of(
    adapter: TestSuiteAstAdapter, tree: object, function: FunctionInfo
) -> tuple[Violation, ...]:
    """Every M2 technical-call breach a single step body carries.

    Each call site whose dotted callee is a denylisted technical call (an HTTP
    client call, or a DB ``.execute``), including one nested inside an assertion,
    becomes one breach naming the offending step + the technical callee it issues.
    """
    return tuple(
        Violation(
            function=function.name,
            callee=call.callee,
            kind=TECHNICAL_CALL_IN_STEP_BODY,
            lineno=call.lineno,
        )
        for call in adapter.calls_in_function(tree, function)
        if _is_technical_callee(call.callee)
    )


def _is_technical_callee(callee: str) -> bool:
    """True iff ``callee`` is a denylisted technical call shape.

    An HTTP client call is any dotted callee whose base module is an HTTP client
    (``requests.get`` → base ``requests``); a DB call is an exact cursor/session
    ``.execute`` callee. A bare domain method (``order_service.place`` /
    ``the_gate.judge``) is neither and is clean.
    """
    base = callee.split(".", 1)[0]
    return base in HTTP_CLIENT_PREFIXES or callee in DB_EXECUTE_CALLEES
