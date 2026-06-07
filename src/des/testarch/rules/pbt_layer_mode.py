"""M9/9-v2 PBT-layer-mode rule (ADR-TEST-002 slice-04).

slice-04 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port: *a property-based-test
construct (a ``@given``-decorated test, or a ``RuleBasedStateMachine`` import /
subclass) MUST NOT appear in a test file at layer-3-or-deeper* (Mandate 9: PBT
machinery is the default ONLY at layers 1-2 — unit + in-memory acceptance; at
layers 3+ — subprocess/FS acceptance, integration, walking-skeleton, E2E — only
example-based tests belong, sad paths enumerated not generated; SKILL.md
:259-266 + :303-310).

Two violation classes the gate flags:

  * **given-at-layer-3plus** — a ``@given``-decorated test function in a
    layer-3+ file. The generative input space belongs at layers 1-2 where each
    example is ~10ms; at layer 3+ each example is real-I/O-heavy (100ms-seconds),
    so PBT runtime cost is incompatible with the layer (Mandate 9 rationale).
  * **state-machine-at-layer-3plus** — a layer-3+ file that imports a
    ``RuleBasedStateMachine`` (or the ``hypothesis.stateful`` API it comes from).
    Stateful PBT exploration belongs at the in-memory tier (Tier B, Mandate 10),
    never against a real adapter.

A test file's layer is a STRUCTURAL fact (directory + marker convention — the
adapter supplies it via ``layer_of_file``). The audited layers are the
adapter-producible 3+ layers (``INTEGRATION`` / ``WIRING_E2E`` / ``E2E``); a file
at layers 1-2 (``UNIT`` / ``IN_MEMORY_ACCEPTANCE``) carrying PBT is COMPLIANT and
the gate must NOT flag it (the precision half).

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names abstract capabilities only; the parser walk is the adapter's job.
The PBT decorator names, the stateful-base name, and the hypothesis-module prefix
are domain constants, not parser concepts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import Layer, TestSuiteAstAdapter


# The PBT decorator that designates a property-based test, the stateful-PBT base
# class name, and the import prefix the stateful base is reached through. Domain
# constants — not a parser API.
GIVEN_DECORATORS: frozenset[str] = frozenset({"given"})
STATE_MACHINE_BASE = "RuleBasedStateMachine"
HYPOTHESIS_MODULE_PREFIX = "hypothesis"

# The stateful-PBT module the ``RuleBasedStateMachine`` base is reached through.
# A module-level import of this module (or a submodule of it) at a layer-3+ file
# is the structural state-machine-PBT signal. Keyed precisely — a bare
# ``hypothesis`` / ``hypothesis.strategies`` import (the plain-@given corpus) is
# NOT a stateful import and must not be mistaken for one.
HYPOTHESIS_STATEFUL_MODULE = f"{HYPOTHESIS_MODULE_PREFIX}.stateful"

# The breach-kind names the verdict reports (the port-exposed ``Violation.kind``
# strings). Domain constants — kept in lock-step with the acceptance vocabulary's
# ``PbtBreachKind`` enum values.
GIVEN_AT_LAYER_BREACH = "given_at_layer_3plus"
STATE_MACHINE_AT_LAYER_BREACH = "state_machine_at_layer_3plus"

# The adapter-producible layers Mandate 9 forbids PBT at (integration,
# walking-skeleton, E2E). Layers 1-2 (unit / in-memory acceptance) are PBT's home
# and are out of scope — a PBT construct there is compliant.
PBT_FORBIDDEN_LAYERS: frozenset[str] = frozenset({"integration", "wiring_e2e", "e2e"})


@dataclass(frozen=True)
class Violation:
    """A flagged Mandate-9 PBT-layer-mode breach (port-exposed observable).

    ``construct`` — the offending PBT construct's name: the ``@given`` test
                    function name, or the ``RuleBasedStateMachine`` symbol.
    ``kind``      — ``"given_at_layer_3plus"`` (a ``@given`` test) or
                    ``"state_machine_at_layer_3plus"`` (a stateful-PBT import).
    ``layer``     — the structural layer the offending file sits at (the
                    port-exposed ``Layer.value`` string).
    ``lineno``    — the 1-based source line of the offending construct.
    """

    construct: str
    kind: str
    layer: str
    lineno: int


@dataclass(frozen=True)
class PbtLayerModeVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == compliant suite).
    ``flagged``    — True iff at least one breach was found (the recall signal).
    """

    violations: tuple[Violation, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.violations)


@requires_capabilities(
    Capability.LAYER_OF_FILE,
    Capability.FUNCTIONS_WITH_DECORATOR,
    Capability.IMPORTS_IN_MODULE,
)
def detect(
    source: str,
    *,
    adapter: TestSuiteAstAdapter,
    path: str,
    filename: str = "<test>",
) -> PbtLayerModeVerdict:
    """Scan one test-suite source for Mandate-9 PBT-layer-mode violations.

    Dispatches through ``adapter`` (a ``TestSuiteAstAdapter``): classifies the
    file's layer; if at a PBT-forbidden layer (3+), flags (a) every
    ``@given``-decorated test and (b) any ``RuleBasedStateMachine`` /
    ``hypothesis``-stateful module-level import. A file at layers 1-2 carrying
    PBT is compliant and yields no violation. Returns a ``PbtLayerModeVerdict``
    naming each offending construct + breach kind + layer.
    Language-agnostic: the rule never touches ``ast``.
    """
    if not _layer_forbids_pbt(adapter.layer_of_file(path)):
        return PbtLayerModeVerdict(violations=())
    layer = adapter.layer_of_file(path).value
    tree = adapter.parse(source, filename)
    violations = (
        *_given_breaches(adapter, tree, layer),
        *_state_machine_breaches(adapter, tree, layer),
    )
    return PbtLayerModeVerdict(violations=violations)


def _given_breaches(
    adapter: TestSuiteAstAdapter, tree: object, layer: str
) -> tuple[Violation, ...]:
    """Every ``@given``-decorated test in a PBT-forbidden file (breach #1)."""
    return tuple(
        Violation(
            construct=function.name,
            kind=GIVEN_AT_LAYER_BREACH,
            layer=layer,
            lineno=function.lineno,
        )
        for function in adapter.functions_with_decorator(tree, GIVEN_DECORATORS)
    )


def _state_machine_breaches(
    adapter: TestSuiteAstAdapter, tree: object, layer: str
) -> tuple[Violation, ...]:
    """Every stateful-PBT import in a PBT-forbidden file (breach #2).

    The structural signal is a module-level import of ``hypothesis.stateful``
    (the module the ``RuleBasedStateMachine`` base lives in). A bare
    ``hypothesis`` / ``hypothesis.strategies`` import is NOT a stateful import.
    """
    return tuple(
        Violation(
            construct=STATE_MACHINE_BASE,
            kind=STATE_MACHINE_AT_LAYER_BREACH,
            layer=layer,
            lineno=imported.lineno,
        )
        for imported in adapter.imports_in_module(tree)
        if _is_stateful_import(imported.module)
    )


def _layer_forbids_pbt(layer: Layer) -> bool:
    """True iff ``layer`` is one of the Mandate-9 PBT-forbidden layers (3+)."""
    return layer.value in PBT_FORBIDDEN_LAYERS


def _is_stateful_import(module: str) -> bool:
    """True iff ``module`` is the stateful-PBT module or sits beneath it."""
    return module == HYPOTHESIS_STATEFUL_MODULE or module.startswith(
        f"{HYPOTHESIS_STATEFUL_MODULE}."
    )
