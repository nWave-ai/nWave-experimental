"""CM-I seam-tag-honesty rule (ADR-TEST-001 D-8, ADR-TEST-002 slice-05).

slice-05 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port: *a test's marker tags
must match the spawn shape its body actually exhibits* (CM-I — "the test's tag
matches what the test actually spawns", ADR-TEST-001 D-5/D-8).

The dishonesty class the gate flags (the labelling half of the 7 fires —
TD-5/11/28/37/41/45/46): a test tagged ``@wiring_e2e`` / ``@subprocess`` (a CLAIM
of a real-subprocess spawn) whose body only drives a CLI ``main(argv)``
IN-PROCESS (no ``subprocess.run`` / real spawn). The shared dispatch/packaging/
exit seam is therefore never exercised, yet the tag asserts it is. A test whose
tag MATCHES its spawn shape is honest and must NOT be flagged (the precision
half): a real-subprocess body tagged ``@wiring_e2e`` is honest, and an in-process
``main(argv)`` body honestly tagged ``@component`` is honest.

A test's marker tags and its body's spawn shape are STRUCTURAL facts (the adapter
supplies them via ``marker_decorators`` and ``spawn_shape_in_body``). The CM-I
tag set is finite; the spawn shape is decidable from the call shapes in the body
(ADR-TEST-001 §Consequences: CM-I is decidable — the spawn shape is structural,
the tag set finite).

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names abstract capabilities only; the parser walk is the adapter's job.
The real-subprocess tag names and the dishonesty breach kind are domain
constants, not parser concepts.

``detect`` cross-checks each test's real-subprocess tag claim against its body's
spawn shape, consuming the adapter capabilities ``marker_decorators`` +
``spawn_shape_in_body`` (both realized on ``python_ast.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities
from des.testarch.ports import SpawnShape


if TYPE_CHECKING:
    from des.testarch.ports import FunctionInfo, TestSuiteAstAdapter


# The marker tags that CLAIM a real-subprocess spawn. A test carrying any of
# these asserts it spawns a real interpreter/process; if its body does not, the
# claim is dishonest. Domain constants (ADR-TEST-001 D-4) — not a parser API.
REAL_SUBPROCESS_TAGS: frozenset[str] = frozenset({"wiring_e2e", "subprocess"})

# The breach-kind name the verdict reports (the port-exposed ``Violation.kind``
# string). Kept in lock-step with the acceptance vocabulary's ``SeamBreachKind``.
TAG_CLAIMS_SUBPROCESS_BUT_RUNS_IN_PROCESS = "tag_claims_subprocess_but_runs_in_process"


@dataclass(frozen=True)
class Violation:
    """A flagged CM-I seam-tag-honesty breach (port-exposed observable).

    ``test``  — the offending test function's name.
    ``kind``  — ``"tag_claims_subprocess_but_runs_in_process"``: the test claims a
                real-subprocess spawn (a ``@wiring_e2e``/``@subprocess`` tag) but
                its body drives ``main(argv)`` in-process (or spawns nothing).
    ``tag``   — the dishonest CLAIM tag the test carries (e.g. ``"wiring_e2e"``).
    ``lineno``— the 1-based source line of the offending test function.
    """

    test: str
    kind: str
    tag: str
    lineno: int


@dataclass(frozen=True)
class SeamTagHonestyVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == honest suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.FUNCTIONS_WITH_DECORATOR,
    Capability.MARKER_DECORATORS,
    Capability.SPAWN_SHAPE_IN_BODY,
)
def detect(
    source: str,
    *,
    adapter: TestSuiteAstAdapter,
    filename: str = "<test>",
) -> SeamTagHonestyVerdict:
    """Scan one test-suite source for CM-I seam-tag-honesty violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``): for each test
    function, read its marker tags (the CLAIM) and its body's spawn shape (the
    ACTUAL); flag a test that carries a real-subprocess tag
    (``@wiring_e2e``/``@subprocess``) while its body does NOT spawn a real
    subprocess. A test whose tag matches its spawn shape is honest and yields no
    violation. Returns a ``SeamTagHonestyVerdict`` naming each dishonest test +
    its claim tag. Language-agnostic: the rule never touches ``ast``.
    """
    tree = adapter.parse(source, filename)
    violations = tuple(
        violation
        for test in adapter.functions_with_decorator(tree, REAL_SUBPROCESS_TAGS)
        if (violation := _breach_for(adapter, tree, test)) is not None
    )
    return SeamTagHonestyVerdict(violations=violations)


def _breach_for(
    adapter: TestSuiteAstAdapter, tree: object, test: FunctionInfo
) -> Violation | None:
    """The CM-I breach a single test carries, or ``None`` if its tag is honest.

    A test whose body genuinely spawns a real subprocess matches its claim and is
    honest. Otherwise the first real-subprocess claim tag it wears is dishonest:
    the tag asserts a spawn the body never performs.
    """
    if adapter.spawn_shape_in_body(tree, test) is SpawnShape.REAL_SUBPROCESS:
        return None
    claim_tag = _real_subprocess_claim(adapter.marker_decorators(tree, test))
    if claim_tag is None:
        return None
    return Violation(
        test=test.name,
        kind=TAG_CLAIMS_SUBPROCESS_BUT_RUNS_IN_PROCESS,
        tag=claim_tag,
        lineno=test.lineno,
    )


def _real_subprocess_claim(tags: list[str]) -> str | None:
    """The first real-subprocess claim tag among ``tags``, or ``None``."""
    return next((tag for tag in tags if tag in REAL_SUBPROCESS_TAGS), None)
