"""M11 integration-sad-path rule (ADR-TEST-002 slice-07).

slice-07 (created by DISTILL, implemented by DELIVER). The RULE,
language-agnostic, over the ``TestSuiteAstAdapter`` port. It enforces TWO halves
of Mandate 11 (SKILL.md :300-307 — *integration sad paths stay example-based*):

  * **no-PBT-in-layer-3+-sad-path** — a property-based-test construct (a
    ``@given``-decorated test, or a ``hypothesis.stateful`` /
    ``RuleBasedStateMachine`` import) appearing in a sad-path test file at
    layer-3-or-deeper is a violation. At layers 3+ each generated example is
    real-I/O-heavy (100ms-seconds); sad paths there must be ENUMERATED
    example-by-example, never PBT-GENERATED (Mandate 11 rationale). This half is
    the recast of the dormant ``check_robustness_density.py`` ``RobustnessPBTShallow``
    layer logic — lifted behind the port, no longer a standalone CLI.
  * **failure-mode-coverage** — every ``failure_modes`` entry declared in a
    component manifest MUST have at least one matching named test (a failure mode
    declared but never tested is a coverage gap). Mandate 11: *every failure mode
    enumerated … gets at least one named sad-path test*.

A test file's layer is a STRUCTURAL fact (directory + marker convention — the
adapter supplies it via ``layer_of_file``). The PBT-forbidden layers are the
layers 3+ the adapter can actually emit: ``INTEGRATION`` / ``WIRING_E2E`` /
``E2E``. Drift-guard (feature-delta F-TESTARCH-FS-ACCEPTANCE-UNREACHABLE): the
adapter's ``_SEGMENT_TO_LAYER`` maps ``acceptance`` → ``IN_MEMORY_ACCEPTANCE``
(layer 2) and NEVER emits ``Layer.FS_ACCEPTANCE``; this rule therefore does NOT
reference ``fs_acceptance`` — a value the adapter cannot produce would make the
half unreachable-by-construction.

HARD genericità constraint (ADR-TEST-002 D-A): this module does NOT ``import
ast``. It names abstract capabilities only; the parser walk is the adapter's job.
The PBT decorator names, the stateful-module prefix, and the breach-kind strings
are domain constants, not parser concepts.

The failure-mode-coverage half consumes the ``failure_mode_coverage``
capability. Per ADR-TEST-002 D-C (Reading-B), that capability is a non-AST
adapter helper — it reads a component manifest (YAML), not an AST tree — and is
deliberately NOT transcribed into the capability registry as adapter-covered:
the registry conformance check is method-name-only / value-range-blind, so a
falsely-registered capability would be a silent residue (feature-delta
drift-guard). ``@requires_capabilities`` below names only the AST capabilities
the adapter produces; ``failure_mode_coverage`` is the manifest helper, not an
AST-registry entry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.testarch.capabilities import Capability, requires_capabilities


if TYPE_CHECKING:
    from des.testarch.ports import Layer, TestSuiteAstAdapter


# The PBT decorator that designates a property-based test, and the stateful-PBT
# module the ``RuleBasedStateMachine`` base is reached through. Domain constants —
# not a parser API. Kept in lock-step with the M9 rule's vocabulary so the two
# layer-discipline gates agree on what "a PBT construct" is.
GIVEN_DECORATORS: frozenset[str] = frozenset({"given"})
HYPOTHESIS_STATEFUL_MODULE = "hypothesis.stateful"
STATE_MACHINE_BASE = "RuleBasedStateMachine"

# The layers Mandate 11 forbids PBT sad-paths at — the layers-3+ the adapter can
# ACTUALLY emit (drift-guard: ``fs_acceptance`` is deliberately absent because
# the adapter never produces ``Layer.FS_ACCEPTANCE``; ``acceptance`` segments map
# to ``IN_MEMORY_ACCEPTANCE``, layer 2). Layers 1-2 (unit / in-memory acceptance)
# are PBT's home and out of scope.
PBT_FORBIDDEN_LAYERS: frozenset[str] = frozenset({"integration", "wiring_e2e", "e2e"})

# The breach-kind names the verdict reports (the port-exposed ``Violation.kind``
# strings). Domain constants — kept in lock-step with the acceptance vocabulary's
# ``SadPathBreachKind`` enum values.
PBT_IN_LAYER3_SAD_PATH_BREACH = "pbt_in_layer3_sad_path"
UNCOVERED_FAILURE_MODE_BREACH = "uncovered_failure_mode"


@dataclass(frozen=True)
class Violation:
    """A flagged Mandate-11 integration-sad-path breach (port-exposed observable).

    ``offender`` — the offending construct's name: the ``@given`` test function
                   name / the ``RuleBasedStateMachine`` symbol (PBT half), or the
                   uncovered ``failure_modes`` entry id (coverage half).
    ``kind``     — ``"pbt_in_layer3_sad_path"`` or ``"uncovered_failure_mode"``.
    ``detail``   — the port-exposed contextual fact: the layer string a stranded
                   PBT construct sits at, or the manifest component a failure mode
                   was declared on (empty when not applicable).
    ``lineno``   — the 1-based source line of the offending construct, or 0 for a
                   manifest-declared failure mode with no source line.
    """

    offender: str
    kind: str
    detail: str
    lineno: int


@dataclass(frozen=True)
class SadPathPbtVerdict:
    """The rule's port-exposed result.

    ``violations`` — every flagged breach (empty == compliant). Covers both the
                     PBT-in-layer-3+ half and the failure-mode-coverage half.
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
) -> SadPathPbtVerdict:
    """Scan one layer-3+ sad-path test-suite source for Mandate-11 violations.

    The no-PBT-in-layer-3+ half: classify the file's layer via the adapter; if at
    a PBT-forbidden layer (3+ the adapter can emit — integration/wiring_e2e/e2e),
    flag every ``@given``-decorated test and any ``hypothesis.stateful`` /
    ``RuleBasedStateMachine`` module-level import. A file at layers 1-2 carrying
    PBT is compliant (the precision half). Language-agnostic: the rule never
    touches ``ast``.

    The failure-mode-coverage half is reached through the separate
    ``detect_failure_mode_coverage`` entry, which consumes the
    ``failure_mode_coverage`` capability (the non-AST manifest helper).
    """
    if not _layer_forbids_pbt(adapter.layer_of_file(path)):
        return SadPathPbtVerdict(violations=())
    layer = adapter.layer_of_file(path).value
    tree = adapter.parse(source, filename)
    violations = (
        *_given_breaches(adapter, tree, layer),
        *_stateful_import_breaches(adapter, tree, layer),
    )
    return SadPathPbtVerdict(violations=violations)


def _given_breaches(
    adapter: TestSuiteAstAdapter, tree: object, layer: str
) -> tuple[Violation, ...]:
    """Every ``@given``-decorated sad-path test in a PBT-forbidden file.

    At a layer-3+ file each generated example is real-I/O-heavy, so a generative
    property test where only enumerated example sad paths belong is a breach.
    """
    return tuple(
        Violation(
            offender=function.name,
            kind=PBT_IN_LAYER3_SAD_PATH_BREACH,
            detail=layer,
            lineno=function.lineno,
        )
        for function in adapter.functions_with_decorator(tree, GIVEN_DECORATORS)
    )


def _stateful_import_breaches(
    adapter: TestSuiteAstAdapter, tree: object, layer: str
) -> tuple[Violation, ...]:
    """Every stateful-PBT import in a PBT-forbidden file.

    The structural signal is a module-level import of ``hypothesis.stateful`` (the
    module the ``RuleBasedStateMachine`` base lives in). A bare ``hypothesis`` /
    ``hypothesis.strategies`` import is NOT a stateful import.
    """
    return tuple(
        Violation(
            offender=STATE_MACHINE_BASE,
            kind=PBT_IN_LAYER3_SAD_PATH_BREACH,
            detail=layer,
            lineno=imported.lineno,
        )
        for imported in adapter.imports_in_module(tree)
        if _is_stateful_import(imported.module)
    )


def detect_failure_mode_coverage(
    manifest_source: str,
    *,
    adapter: TestSuiteAstAdapter,
    test_sources: dict[str, str],
    manifest_filename: str = "<manifest>",
) -> SadPathPbtVerdict:
    """Cross-check every ``failure_modes`` entry against a matching named test.

    The coverage half of Mandate 11: each ``failure_modes`` entry declared in a
    component manifest MUST have at least one test whose name matches the entry
    (a failure mode declared but never tested is a coverage gap). A declared mode
    with no covering named test is flagged ``uncovered_failure_mode``.

    This half consumes the ``failure_mode_coverage`` capability — reading a
    component manifest's declared failure modes and matching them against the
    named tests in ``test_sources``. Per ADR-TEST-002 D-C (Reading-B) that
    capability is a non-AST adapter helper (it reads a YAML manifest, not an AST
    tree), so it is NOT transcribed into the capability registry as
    adapter-covered (drift-guard: the registry conformance check is
    method-name-only, so a falsely-registered capability would be a silent
    residue).
    """
    coverage = adapter.failure_mode_coverage(manifest_source, frozenset(test_sources))
    violations = tuple(
        Violation(
            offender=mode_id,
            kind=UNCOVERED_FAILURE_MODE_BREACH,
            detail=manifest_filename,
            lineno=0,
        )
        for mode_id in coverage.uncovered
    )
    return SadPathPbtVerdict(violations=violations)


def _layer_forbids_pbt(layer: Layer) -> bool:
    """True iff ``layer`` is one of the Mandate-11 PBT-forbidden layers (3+).

    Only the adapter-producible layers-3+ are forbidden (drift-guard:
    ``fs_acceptance`` excluded — the adapter never emits ``Layer.FS_ACCEPTANCE``).
    """
    return layer.value in PBT_FORBIDDEN_LAYERS


def _is_stateful_import(module: str) -> bool:
    """True iff ``module`` is the stateful-PBT module or sits beneath it."""
    return module == HYPOTHESIS_STATEFUL_MODULE or module.startswith(
        f"{HYPOTHESIS_STATEFUL_MODULE}."
    )
