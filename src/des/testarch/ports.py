"""The ``TestSuiteAstAdapter`` driven port (ADR-TEST-002 D-C).

slice-01 (created by DISTILL, implemented by DELIVER). The abstract structural contract
the rule layer dispatches through. A per-language AST adapter satisfies this
Protocol; the rule layer consumes ONLY these capabilities and never imports a
concrete parser API (genericità, ADR-TEST-002 D-A).

slice-01 needs exactly two capabilities for the M1 driving-port-boundary rule:
``functions_with_decorator`` and ``imports_in_function``. The full capability
set (D-C, 11 entries) is fleshed out in slice-02; this scaffold declares only
the two slice-01 consumes, plus the opaque-handle vocabulary every adapter
returns as plain data (never a live ``ast`` node to the caller).

slice-03 (M8 universe-bound assertion gate) ADDS the call/keyword/layer
vocabulary the rule consumes: ``CallInfo`` (a call site the adapter reports),
``Layer`` (the structural layer a test file sits at), and three new port methods
(``calls_in_function``, ``keyword_arg_names``, ``layer_of_file``). The slice-01
surface is preserved verbatim.

slice-04 (M9/9-v2 PBT-layer-mode gate) ADDS the module-level import vocabulary
the rule consumes: one new port method ``imports_in_module`` (every
module-level import, used to spot a ``hypothesis``/``RuleBasedStateMachine``
import in a layer-3+ test file). The slice-01/03 surface is preserved verbatim.

slice-05 (CM-I seam-tag-honesty gate) ADDS the tag-vs-spawn vocabulary the rule
consumes: the ``SpawnShape`` enum (what a test actually spawns — nothing, an
in-process ``main(argv)`` call, or a real subprocess) plus two new port methods
``marker_decorators`` (the pytest tags a test function carries) and
``spawn_shape_in_body`` (the structural spawn shape of a test's body). The CM-I
rule cross-checks a test's CLAIMED spawn (its ``@wiring_e2e``/``@subprocess``
tags) against its ACTUAL spawn shape. The slice-01/03/04 surface is preserved
verbatim.

slice-09 (P3 composition-root gate) ADDS the construction vocabulary the rule
consumes: the ``ConstructInfo`` plain-data type (a ``name = Type(...)``
construction the adapter reports) plus one new port method
``assignments_constructing_type`` (every assignment in a step body that
constructs one of a named SUT-collaborator type set). The P3 rule cross-checks a
step body's collaborator-constructing assignments against the presence/absence of
a composition-root entry call. cap 10 (``ASSIGNMENTS_CONSTRUCTING_TYPE``)
pre-exists in the capability enum + cap-table; slice-09 realizes it on the
adapter. The slice-01/03/04/05 surface is preserved verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class SpawnShape(Enum):
    """What a test's body actually spawns (slice-05 CM-I) — a structural fact.

    The CM-I rule reads this and cross-checks it against the test's CLAIM (its
    marker decorators). A test that CLAIMS a real subprocess (``@wiring_e2e`` /
    ``@subprocess``) but whose body is ``IN_PROCESS_MAIN`` is dishonest; a test
    that genuinely ``REAL_SUBPROCESS``-spawns and carries the real-subprocess
    tags is honest.

    NONE             — the body neither calls an in-process ``main(argv)`` entry
                       nor spawns a real subprocess (e.g. a pure unit assertion).
    IN_PROCESS_MAIN  — the body drives a CLI in-process: a ``main(argv)`` /
                       ``main([...])`` call (typically under ``redirect_stdout``),
                       with NO real subprocess spawn.
    REAL_SUBPROCESS  — the body spawns a real interpreter/process: a
                       ``subprocess.run`` / ``subprocess.Popen`` /
                       ``subprocess.check_output`` call (the genuine
                       ``@wiring_e2e`` shape).
    """

    NONE = "none"
    IN_PROCESS_MAIN = "in_process_main"
    REAL_SUBPROCESS = "real_subprocess"


class Layer(Enum):
    """The structural layer a test file sits at (from directory + marker convention).

    Mandate 8 audits layers 1-3 (``UNIT`` / ``IN_MEMORY_ACCEPTANCE`` /
    ``FS_ACCEPTANCE``); layers 4+ (``INTEGRATION`` / ``WIRING_E2E`` / ``E2E``) may
    use traditional assertions and are out of scope for the universe guard.
    ``UNKNOWN`` is the fail-safe for a path the adapter cannot classify.
    """

    UNIT = "unit"
    IN_MEMORY_ACCEPTANCE = "in_memory_acceptance"
    FS_ACCEPTANCE = "fs_acceptance"
    INTEGRATION = "integration"
    WIRING_E2E = "wiring_e2e"
    E2E = "e2e"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CallInfo:
    """A plain-data description of a call site found inside a function.

    ``callee`` is the dotted callee name (e.g. ``assert_state_delta`` or
    ``board.append_event``); ``lineno`` is the 1-based source line. The opaque
    ``node_ref`` is an adapter-private handle the adapter uses to answer
    follow-up queries (e.g. ``keyword_arg_names`` on this call); callers treat it
    as an opaque token and never inspect it.
    """

    callee: str
    lineno: int
    node_ref: object


@dataclass(frozen=True)
class ImportInfo:
    """A plain-data description of an import statement found inside a function.

    ``module`` is the dotted source module (e.g. ``des.adapters.driven.x``);
    ``lineno`` is the 1-based source line. No live parser node is exposed.
    """

    module: str
    lineno: int


@dataclass(frozen=True)
class FailureModeCoverage:
    """A plain-data cross-check of a component manifest against named tests (slice-07).

    ``uncovered`` is the tuple of declared ``failure_modes`` entry ids for which no
    test name in scope matched (empty == every declared mode is covered). The M11
    coverage half reads only this — the manifest parse + name-match lives entirely
    in the per-language adapter (genericità, ADR-TEST-002 D-A). Matching is
    structural-by-name: a mode id is covered iff some named test mentions it.
    """

    uncovered: tuple[str, ...]


@dataclass(frozen=True)
class ConstructInfo:
    """A plain-data description of a ``name = Type(...)`` construction (slice-09).

    Reports an assignment in a step body that constructs a (requested) type:
    ``constructed`` is the constructed type's callee name (e.g. ``OrderService``
    for ``service = OrderService(repo, clock)``); ``target`` is the assigned
    variable name (e.g. ``service``); ``lineno`` is the 1-based source line. The
    P3 composition-root rule reads these to spot a step that hand-wires a SUT
    collaborator inline. A plain function call (``app = build_application()``) is
    NOT a type construction and is never reported here.
    """

    constructed: str
    target: str
    lineno: int


@dataclass(frozen=True)
class StepShapeCorpus:
    """A plain-data step-shape census of a test module (sustainable-test-suite slice-09).

    ``total_step_definitions`` is the count of pytest-bdd step definitions
    (``@given`` / ``@when`` / ``@then`` functions) in the module;
    ``near_duplicate_groups`` is the number of step-shape groups that contain MORE than one
    step definition sharing a normalized body shape (each such group is one collapsible
    near-duplicate cluster). A module with every step distinct has
    ``near_duplicate_groups == 0``. The existing-base near-duplicate-step ratio is
    ``near_duplicate_groups / total_step_definitions``; the rule layer reads only this
    plain-data census — the normalization + grouping is the per-language adapter's concern
    (genericità, ADR-TEST-002 D-A).
    """

    near_duplicate_groups: int
    total_step_definitions: int


@dataclass(frozen=True)
class SymbolInfo:
    """A plain-data description of a MODULE-LEVEL ``def``/``class`` symbol
    (WS-9b, ``codefact-similar-responsibility`` slice-01).

    ``name`` is the symbol's bare identifier; ``lineno`` its 1-based
    definition line; ``kind`` is ``"function"`` or ``"class"``; ``arity`` is
    the symbol's parameter count (a function's positional+keyword-only
    parameter count; a class reports 0 — module-level symbols only, nested
    defs/methods are NOT reported). The ``AstAdapter``'s
    similar-responsibility fingerprint reads ``name`` (token-split) +
    ``arity`` (tie-break) from this plain-data shape — no live ``ast`` node
    is exposed.
    """

    name: str
    lineno: int
    kind: str
    arity: int


@dataclass(frozen=True)
class FunctionInfo:
    """A plain-data description of a function definition in a parsed tree.

    ``name`` is the function name; ``lineno`` its 1-based definition line.
    The opaque ``node_ref`` is an adapter-private handle the adapter uses to
    answer follow-up queries (e.g. ``imports_in_function``); callers treat it
    as an opaque token and never inspect it.
    """

    name: str
    lineno: int
    node_ref: object


class TestSuiteAstAdapter(Protocol):
    """Per-language AST adapter the rule layer dispatches through.

    Each method is a pure query over an opaque parsed-tree handle, returning
    plain data. Python's reference implementation is
    ``des.testarch.adapters.python_ast.PythonAstAdapter``.
    """

    def parse(self, source: str, filename: str) -> object:
        """Parse ``source`` into an opaque tree handle (never inspected by callers)."""
        ...

    def functions_with_decorator(
        self, tree: object, decorator_names: frozenset[str]
    ) -> list[FunctionInfo]:
        """Return every function decorated with one of ``decorator_names``."""
        ...

    def functions_in_module(self, tree: object) -> list[FunctionInfo]:
        """Return every function/method defined in ``tree`` (slice-02 CodeFact).

        The structural enumeration the ``AstAdapter`` (``approx`` tier) consumes to
        compute atoms / call-sites over a real tree without a second parser. Every
        ``def`` / ``async def`` at any nesting depth is reported as a
        ``FunctionInfo`` (name + 1-based line + opaque ``node_ref``), so a class
        method is reported as well as a top-level function. Decorator filtering is
        NOT applied — this is the unfiltered "every function" surface, distinct from
        ``functions_with_decorator``.
        """
        ...

    def imports_in_function(self, tree: object, fn: FunctionInfo) -> list[ImportInfo]:
        """Return every import statement inside ``fn``'s body."""
        ...

    def imports_in_module(self, tree: object) -> list[ImportInfo]:
        """Return every module-level import statement (slice-04 M9/9-v2).

        Both ``import x`` and ``from x import y`` forms are reported, using the
        dotted source module as ``ImportInfo.module``. The M9 rule reads these to
        spot a ``hypothesis`` / ``RuleBasedStateMachine`` import in a layer-3+
        test file (where only example-based tests belong).
        """
        ...

    def calls_in_function(self, tree: object, fn: FunctionInfo) -> list[CallInfo]:
        """Return every call site inside ``fn``'s body (dotted callee + handle)."""
        ...

    def keyword_arg_names(self, call: CallInfo, kw: str) -> list[str]:
        """Return the names passed inside the ``kw`` keyword arg of ``call``.

        For ``assert_state_delta(..., universe={"a", "_b"})`` and ``kw="universe"``
        this returns ``["a", "_b"]`` — the observable names the test declares it
        tracks. String/set/list literals are read; non-literal expressions yield
        no names (the rule treats an undecidable universe as out of audit scope).
        """
        ...

    def layer_of_file(self, path: str) -> Layer:
        """Classify ``path`` into a structural ``Layer`` (directory + marker)."""
        ...

    def marker_decorators(self, tree: object, fn: FunctionInfo) -> list[str]:
        """Return the pytest marker names a test function carries (slice-05 CM-I).

        Reads ``@pytest.mark.<name>`` decorators on ``fn`` and reports each
        ``<name>`` (e.g. ``["wiring_e2e", "subprocess"]``). The CM-I rule reads
        these as the test's CLAIM about what it spawns. A bare ``@something``
        decorator that is not a ``pytest.mark.*`` attribute is not a marker and
        is not reported.
        """
        ...

    def spawn_shape_in_body(self, tree: object, fn: FunctionInfo) -> SpawnShape:
        """Return the structural spawn shape of ``fn``'s body (slice-05 CM-I).

        ``REAL_SUBPROCESS`` if the body calls ``subprocess.run`` /
        ``subprocess.Popen`` / ``subprocess.check_output`` (a genuine spawn);
        else ``IN_PROCESS_MAIN`` if the body calls an in-process ``main(...)``
        entry (a ``main`` / ``*.main`` callee); else ``NONE``. The CM-I rule
        cross-checks this ACTUAL shape against the test's CLAIMED tags.
        """
        ...

    def failure_mode_coverage(
        self, manifest_source: str, test_names: frozenset[str]
    ) -> FailureModeCoverage:
        """Cross-check a component manifest's failure modes against named tests (slice-07 M11).

        Reads ``manifest_source`` (a component manifest declaring a ``failure_modes``
        list of entries with ``id`` keys) and reports every declared mode id that no
        name in ``test_names`` covers. A mode id is covered iff some test name mentions
        it (structural-by-name match — the learning hypothesis of slice-07). The M11
        coverage rule consumes only the resulting ``FailureModeCoverage``; the manifest
        parse + the name match are the adapter's per-language concern.
        """
        ...

    def step_shapes_in_module(self, tree: object) -> StepShapeCorpus:
        """Census the step-shape corpus of a test module (sustainable-test-suite slice-09).

        Counts the pytest-bdd step definitions (``@given`` / ``@when`` / ``@then``
        functions) in ``tree``, groups them by normalized body shape, and reports
        ``total_step_definitions`` + the number of groups holding MORE than one step
        (``near_duplicate_groups`` — each a collapsible near-duplicate cluster). The
        normalization is structural (the sequence of statement/call shapes in the body),
        so two step defs that perform the same body shape group together regardless of
        their step-text literal. A module with no step definitions reports a zero census.
        """
        ...

    def assignments_constructing_type(
        self, tree: object, fn: FunctionInfo, type_names: frozenset[str]
    ) -> list[ConstructInfo]:
        """Return every ``name = Type(...)`` construction in ``fn`` (slice-09 P3).

        Walks ``fn``'s body for assignment statements whose right-hand side
        constructs a type named in ``type_names`` — reporting the constructed type
        name, the assigned variable name, and the 1-based line as ``ConstructInfo``.
        Only a constructor call whose callee name is in ``type_names`` is reported;
        a plain function call (``app = build_application()``) or a construction of a
        type outside ``type_names`` (a value object like ``money = Money(150)``)
        yields nothing. The P3 composition-root rule reads these to spot a step that
        hand-wires a SUT collaborator inline where a composition-root entry call
        belongs.
        """
        ...

    def module_level_symbols_in_module(self, tree: object) -> list[SymbolInfo]:
        """Return every MODULE-LEVEL ``def``/``class`` symbol in ``tree``
        (WS-9b, ``codefact-similar-responsibility`` slice-01).

        Reads only ``tree``'s top-level body — a nested ``def``/``class``
        (a method, a closure) is NOT reported, distinguishing this from the
        unfiltered ``functions_in_module`` walk. Each symbol reports its
        ``name`` / 1-based ``lineno`` / ``kind`` (``"function"`` or
        ``"class"``) / ``arity`` (a function's parameter count; 0 for a
        class) as plain data — the ``AstAdapter``'s similar-responsibility
        fingerprint consumes this directly, no live ``ast`` node exposed.
        """
        ...
