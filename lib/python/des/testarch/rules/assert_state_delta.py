"""M8 universe-bound assertion rule (ADR-TEST-002 slice-03).

slice-03 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port: *every state-mutating
test at layers 1-2 MUST guard its mutation with an ``assert_state_delta(...)``
call, AND the ``universe=`` argument of that call MUST NOT name a private
(``_``-prefixed) observable* (Mandate 8; the rule the mandates skill specifies at
SKILL.md :370 + :206-215).

Two violation classes the gate flags:

  * **missing-assert** — a state-mutating layer-1-2 test whose body has NO
    ``assert_state_delta`` call. The universe guard is absent: the test can
    silently pass against a wired-but-broken seam (the assertion-free-test smell,
    the highest-value static smell).
  * **private-universe-leak** — a test that DOES call ``assert_state_delta`` but
    passes a ``_``-prefixed name into the ``universe=`` set. A private name
    couples the test to an internal mutation field (``BoardProjection._rows``);
    a refactor rename reds the test for no functional reason. The universe must
    name only port-exposed observables.

A test is "state-mutating" structurally: it carries the ``@mutates_state``
marker (a domain convention — the structural fact the adapter supplies via
``functions_with_decorator``). Read-only (query) tests carry no such marker and
are out of scope. Layer scope: only files at layers 1-2 (unit, in-memory
acceptance) are audited — layers 3+ may use traditional assertions (Mandate 8
carve-out).

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names abstract capabilities only; the parser walk is the adapter's job.
``ASSERT_STATE_DELTA_CALLEE`` and the private-name prefix are domain constants,
not parser concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import FunctionInfo, Layer, TestSuiteAstAdapter


# The marker that designates a state-mutating test (the structural state-mutating
# signal), the universe-guard callee the mandate requires, the keyword whose
# argument names must stay port-observable, and the prefix that marks a private
# (internal-field) name. Domain constants — not a parser API.
MUTATES_STATE_MARKER: frozenset[str] = frozenset({"mutates_state"})
ASSERT_STATE_DELTA_CALLEE = "assert_state_delta"
UNIVERSE_KEYWORD = "universe"
PRIVATE_NAME_PREFIX = "_"

# The breach-kind names the verdict reports (the port-exposed ``Violation.kind``
# strings). Domain constants — kept in lock-step with the acceptance vocabulary's
# ``BreachKind`` enum values (``missing_assert`` / ``private_universe_leak``).
MISSING_ASSERT_BREACH = "missing_assert"
PRIVATE_UNIVERSE_LEAK_BREACH = "private_universe_leak"

# The adapter-producible layers Mandate 8 audits (unit / in-memory acceptance).
# Layers 4+ may use traditional assertions and are out of scope.
AUDITED_LAYERS: frozenset[str] = frozenset({"unit", "in_memory_acceptance"})


@dataclass(frozen=True)
class Violation:
    """A flagged Mandate-8 breach (port-exposed observable).

    ``function`` — the offending state-mutating test function name.
    ``kind``     — ``"missing_assert"`` (no universe guard) or
                   ``"private_universe_leak"`` (a ``_``-prefixed universe name).
    ``detail``   — the leaked private name for a leak; the empty string for a
                   missing-assert breach.
    ``lineno``   — the 1-based source line of the offending function.
    """

    function: str
    kind: str
    detail: str
    lineno: int


@dataclass(frozen=True)
class AssertStateDeltaVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == compliant suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.FUNCTIONS_WITH_DECORATOR,
    Capability.CALLS_IN_FUNCTION,
    Capability.KEYWORD_ARG_NAMES,
    Capability.LAYER_OF_FILE,
)
def detect(
    source: str,
    *,
    adapter: TestSuiteAstAdapter,
    path: str,
    filename: str = "<test>",
) -> AssertStateDeltaVerdict:
    """Scan one test-suite source for Mandate-8 universe-guard violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``): classifies the
    file's layer; if at an audited layer (1-2), finds every ``@mutates_state``
    test, then flags (a) a missing ``assert_state_delta`` guard and (b) any
    ``_``-prefixed name in the ``universe=`` argument. Returns an
    ``AssertStateDeltaVerdict`` naming each offending function + breach kind.
    Language-agnostic: the rule never touches ``ast``.
    """
    if not _layer_is_audited(adapter.layer_of_file(path)):
        return AssertStateDeltaVerdict(violations=())
    tree = adapter.parse(source, filename)
    mutating_tests = adapter.functions_with_decorator(tree, MUTATES_STATE_MARKER)
    violations = tuple(
        breach
        for function in mutating_tests
        for breach in _breaches_of(adapter, tree, function)
    )
    return AssertStateDeltaVerdict(violations=violations)


def _breaches_of(
    adapter: TestSuiteAstAdapter, tree: object, function: FunctionInfo
) -> tuple[Violation, ...]:
    """Every Mandate-8 breach a single state-mutating test carries."""
    guard_calls = [
        call
        for call in adapter.calls_in_function(tree, function)
        if call.callee == ASSERT_STATE_DELTA_CALLEE
    ]
    if not guard_calls:
        return (
            Violation(
                function=function.name,
                kind=MISSING_ASSERT_BREACH,
                detail="",
                lineno=function.lineno,
            ),
        )
    return tuple(
        Violation(
            function=function.name,
            kind=PRIVATE_UNIVERSE_LEAK_BREACH,
            detail=name,
            lineno=function.lineno,
        )
        for call in guard_calls
        for name in adapter.keyword_arg_names(call, UNIVERSE_KEYWORD)
        if _is_private_name(name)
    )


def _layer_is_audited(layer: Layer) -> bool:
    """True iff ``layer`` is one of the Mandate-8 audited layers (1-2)."""
    return layer.value in AUDITED_LAYERS


def _is_private_name(name: str) -> bool:
    """True iff ``name`` is a private (``_``-prefixed) observable name."""
    return name.startswith(PRIVATE_NAME_PREFIX)
