"""M1 driving-port-boundary rule (ADR-TEST-002 slice-01 walking skeleton).

slice-01 (created by DISTILL, implemented by DELIVER). The RULE, language-agnostic, over
the ``TestSuiteAstAdapter`` port: *a ``@when``-decorated step function MUST NOT
import a driven adapter* (``des.adapters.driven.*``). Adapter imports belong in
fixtures (``conftest.py``), not in ``@when`` steps — they collapse the test
through a driven port instead of the driving port (Mandate 1).

This recasts the dormant ``scripts/hooks/check_driving_port_boundary.py`` behind
the port. The dormant gate's known-violation corpus and clean corpus are the
golden fixtures the slice-01 self-AT asserts against (ADR-TEST-002 D-E).

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names the abstract capabilities only; the parser walk is the adapter's
job. The driven-adapter prefix is a domain constant, not a parser concept.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import TestSuiteAstAdapter


# The step decorator that marks a driving-port action, and the import prefix a
# driving-port action must never reach for. Domain constants — not parser API.
WHEN_DECORATORS: frozenset[str] = frozenset({"when"})
DRIVEN_ADAPTER_PREFIX = "des.adapters.driven"


@dataclass(frozen=True)
class Violation:
    """A flagged driving-port-boundary breach (port-exposed observable).

    ``function`` — the offending ``@when`` step function name.
    ``module``   — the driven-adapter module it illegally imports.
    ``lineno``   — the 1-based source line of the offending import.
    """

    function: str
    module: str
    lineno: int


@dataclass(frozen=True)
class BoundaryVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == clean suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.FUNCTIONS_WITH_DECORATOR, Capability.IMPORTS_IN_FUNCTION
)
def detect(
    source: str, *, adapter: TestSuiteAstAdapter, filename: str = "<test>"
) -> BoundaryVerdict:
    """Scan one test-suite source for M1 driving-port-boundary violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``) — finds every
    ``@when`` step function, then flags any ``des.adapters.driven.*`` import in
    its body. Returns a ``BoundaryVerdict`` naming each offending function +
    module. Language-agnostic: the rule never touches ``ast``.
    """
    tree = adapter.parse(source, filename)
    when_functions = adapter.functions_with_decorator(tree, WHEN_DECORATORS)
    violations = tuple(
        Violation(
            function=function.name,
            module=imported.module,
            lineno=imported.lineno,
        )
        for function in when_functions
        for imported in adapter.imports_in_function(tree, function)
        if _is_driven_adapter(imported.module)
    )
    return BoundaryVerdict(violations=violations)


def _is_driven_adapter(module: str) -> bool:
    """True iff ``module`` is the driven-adapter prefix or sits beneath it."""
    return module == DRIVEN_ADAPTER_PREFIX or module.startswith(
        f"{DRIVEN_ADAPTER_PREFIX}."
    )
