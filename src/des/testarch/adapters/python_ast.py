"""The reference Python stdlib-``ast`` adapter (ADR-TEST-002 D-C).

This is the ONLY testarch module permitted to ``import ast`` — the rule layer
dispatches through the ``TestSuiteAstAdapter`` port and never names a parser API
(genericità, ADR-TEST-002 D-A). The dormant
``scripts/hooks/check_driving_port_boundary.py`` IS this adapter's logic;
slice-01 recasts it behind the port.

The opaque tree handle returned by ``parse`` is an ``ast.Module``; callers
treat it as opaque and only ever pass it back into adapter methods. Likewise the
``FunctionInfo.node_ref`` returned here is the underlying ``ast.FunctionDef`` —
an adapter-private handle the caller never inspects.

slice-03 (M8 universe-bound assertion gate) ADDS three capability realizations —
``calls_in_function``, ``keyword_arg_names``, ``layer_of_file`` — each a pure
query over the opaque ``ast`` tree. The slice-01 surface (``parse``,
``functions_with_decorator``, ``imports_in_function``) is preserved verbatim.

slice-04 (M9/9-v2 PBT-layer-mode gate) ADDS one capability realization —
``imports_in_module`` — a pure query over the opaque ``ast`` tree that reports
every module-level import. The slice-01/03 surface is preserved verbatim.

slice-05 (CM-I seam-tag-honesty gate) ADDS two capability realizations —
``marker_decorators`` (the pytest tags a test function carries) and
``spawn_shape_in_body`` (whether the body spawns a real subprocess, drives an
in-process ``main(argv)``, or neither). Both are RED scaffolds here (created by
DISTILL, implemented by DELIVER). The slice-01/03/04 surface is preserved
verbatim.

slice-09 (P3 composition-root gate) ADDS one capability realization —
``assignments_constructing_type`` — a pure query over the opaque ``ast`` tree that
reports every ``name = Type(...)`` construction in a step body whose constructed
type is in a requested set. The slice-01/03/04/05 surface is preserved verbatim.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

from des.testarch.ports import (
    CallInfo,
    ConstructInfo,
    FailureModeCoverage,
    FunctionInfo,
    ImportInfo,
    Layer,
    SpawnShape,
    StepShapeCorpus,
    SymbolInfo,
)


if TYPE_CHECKING:
    from collections.abc import Iterable


# The dotted callee names that signal a genuine real-subprocess spawn (slice-05
# CM-I ``spawn_shape_in_body``). The ``subprocess.`` prefix is matched as well as
# the bare callee so a ``from subprocess import run`` alias is still recognized.
_REAL_SUBPROCESS_CALLEES: frozenset[str] = frozenset(
    {
        "subprocess.run",
        "subprocess.Popen",
        "subprocess.check_output",
        "subprocess.call",
        "run",
        "Popen",
        "check_output",
    }
)

# The pytest-bdd step-definition decorator base names (sustainable-test-suite slice-09
# ``step_shapes_in_module``). A function decorated with one of these is a step definition
# whose step-text literal (the decorator's first string argument) is the near-duplicate-step
# similarity signal the existing-base ratio counts.
_STEP_DECORATOR_NAMES: frozenset[str] = frozenset({"given", "when", "then"})

# A trailing numeric token of a normalized step-text key (sustainable-test-suite slice-09).
# Stripping the trailing index collapses the per-variant suffix ("... variant 0" / "...
# variant 1") so the two variants of one near-duplicate cluster share a normalized shape.
_TRAILING_INDEX_RE = re.compile(r"\s+\d+$")

# Collapse every run of whitespace to a single space (step-text normalization).
_WHITESPACE_RUN_RE = re.compile(r"\s+")

# The in-process CLI-entry callee name a ``main(argv)`` body drives (slice-05
# CM-I). A ``main`` / ``*.main`` callee with no real-subprocess spawn is the
# IN_PROCESS_MAIN shape — the very shape that is dishonest under a subprocess tag.
_MAIN_CALLEE = "main"

# Component-manifest shape the slice-07 M11 coverage half reads. A manifest
# declares a list of failure modes under a ``failure_modes:`` key; each entry
# names a mode as a ``- id: <value>`` list item. The adapter extracts the ids
# with a stdlib line-scan (no third-party YAML dependency — the DES-bundle
# stdlib-only contract, ADR-PLAT-001 + ARCH "the only runtime dependency is
# Python") and matches each id against the named tests in scope; the rule layer
# never sees the parse.
_FAILURE_MODES_HEADER = "failure_modes:"
# Matches a ``- id: <value>`` list entry (optional surrounding quotes), capturing
# the bare mode id. Indentation is permissive; the entry must be a ``-`` item.
_MODE_ID_ENTRY = re.compile(r"^\s*-\s*id:\s*[\"']?([A-Za-z0-9_./-]+)[\"']?\s*$")


# Path-segment → structural layer convention (first match wins). Pure-string,
# git-free, language-agnostic — the adapter classifies a file by its directory
# segments, never by repository state.
_SEGMENT_TO_LAYER: dict[str, Layer] = {
    "unit": Layer.UNIT,
    "acceptance": Layer.IN_MEMORY_ACCEPTANCE,
    "integration": Layer.INTEGRATION,
    "wiring_e2e": Layer.WIRING_E2E,
    "wiring": Layer.WIRING_E2E,
    "e2e": Layer.E2E,
}


class PythonAstAdapter:
    """``TestSuiteAstAdapter`` implementation over Python stdlib ``ast``."""

    def parse(self, source: str, filename: str) -> object:
        """Parse ``source`` into an ``ast.Module`` (opaque to callers)."""
        return ast.parse(source, filename=filename)

    def functions_with_decorator(
        self, tree: object, decorator_names: frozenset[str]
    ) -> list[FunctionInfo]:
        """Return every top-level function decorated with one of ``decorator_names``.

        Decorator matching resolves the base callable name, so ``@when``,
        ``@when("...")`` (a ``Call``) and ``@module.when`` (an ``Attribute``)
        all match the name ``when``.
        """
        module = self._as_module(tree)
        found: list[FunctionInfo] = []
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if self._has_matching_decorator(node, decorator_names):
                found.append(
                    FunctionInfo(name=node.name, lineno=node.lineno, node_ref=node)
                )
        return found

    def functions_in_module(self, tree: object) -> list[FunctionInfo]:
        """Return every function/method defined in ``tree`` (slice-02 CodeFact).

        Walks the whole module for ``ast.FunctionDef`` / ``ast.AsyncFunctionDef``
        nodes — at any nesting depth, so a class method is reported as well as a
        top-level function — and reports each as a ``FunctionInfo`` (name + 1-based
        line + the ``ast`` node as the opaque handle). The unfiltered "every
        function" surface the ``AstAdapter`` consumes for atoms / call-site walks.
        """
        module = self._as_module(tree)
        return [
            FunctionInfo(name=node.name, lineno=node.lineno, node_ref=node)
            for node in ast.walk(module)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

    def imports_in_function(self, tree: object, fn: FunctionInfo) -> list[ImportInfo]:
        """Return every import statement inside ``fn``'s body.

        Both ``import x`` and ``from x import y`` forms are reported, using the
        dotted source module as ``ImportInfo.module``. ``tree`` is unused here —
        ``fn.node_ref`` already anchors the function subtree.
        """
        function_node = fn.node_ref
        if not isinstance(function_node, ast.AST):
            raise TypeError("FunctionInfo.node_ref must be an ast.AST handle")
        return self._imports_from_nodes(ast.walk(function_node))

    def imports_in_module(self, tree: object) -> list[ImportInfo]:
        """Return every module-level import statement (slice-04 M9/9-v2).

        Reads the module body for ``ast.Import`` / ``ast.ImportFrom`` nodes and
        reports each as an ``ImportInfo`` (dotted source module + 1-based line),
        so the M9 rule can spot a ``hypothesis`` / ``RuleBasedStateMachine``
        import in a layer-3+ test file. Both ``import x`` and ``from x import y``
        forms are reported, using the dotted source module as
        ``ImportInfo.module``. Only top-level statements are read (module body),
        not nested imports inside function bodies.
        """
        return self._imports_from_nodes(self._as_module(tree).body)

    def calls_in_function(self, tree: object, fn: FunctionInfo) -> list[CallInfo]:
        """Return every call site inside ``fn``'s body (slice-03 M8).

        The dotted callee name is resolved for ``Name`` callees (``foo()`` →
        ``foo``) and ``Attribute`` callees (``board.append()`` → ``board.append``);
        an unresolvable callee yields the empty string. ``tree`` is unused — the
        function subtree is anchored by ``fn.node_ref``. The ``Call`` node is
        carried back as the opaque ``CallInfo.node_ref`` so a follow-up
        ``keyword_arg_names`` query can read its keyword arguments.
        """
        return [
            CallInfo(
                callee=self._callee_name(node.func),
                lineno=node.lineno,
                node_ref=node,
            )
            for node in self._calls_in(fn)
        ]

    def keyword_arg_names(self, call: CallInfo, kw: str) -> list[str]:
        """Return the literal names passed in ``call``'s ``kw`` keyword (slice-03 M8).

        Reads the ``kw`` keyword argument of the call and returns the string-literal
        names inside a set/list/tuple literal (e.g. ``universe={"a", "_b"}`` →
        ``["a", "_b"]``). A non-literal or absent argument yields the empty list —
        an undecidable universe is treated as out of audit scope by the rule.
        """
        call_node = call.node_ref
        if not isinstance(call_node, ast.Call):
            raise TypeError("CallInfo.node_ref must be an ast.Call handle")
        for keyword in call_node.keywords:
            if keyword.arg == kw:
                return self._literal_names(keyword.value)
        return []

    def layer_of_file(self, path: str) -> Layer:
        """Classify ``path`` into a structural ``Layer`` (slice-03 M8).

        Pure path-segment convention (git-free, language-agnostic): the first
        recognized directory segment fixes the layer. ``unit`` → UNIT;
        ``acceptance`` → IN_MEMORY_ACCEPTANCE; ``integration`` → INTEGRATION;
        ``e2e`` → E2E; ``wiring``/``wiring_e2e`` → WIRING_E2E. A path naming none of
        these is ``UNKNOWN`` (the fail-safe).
        """
        segments = path.replace("\\", "/").split("/")
        for segment in segments:
            layer = _SEGMENT_TO_LAYER.get(segment)
            if layer is not None:
                return layer
        return Layer.UNKNOWN

    def marker_decorators(self, tree: object, fn: FunctionInfo) -> list[str]:
        """Return the pytest marker names on ``fn`` (slice-05 CM-I).

        Walks ``fn``'s decorator list and reports each ``@pytest.mark.<name>`` as
        ``<name>`` (the test's CLAIM about what it spawns). A bare ``@something``
        decorator that is not a ``pytest.mark.*`` attribute is not a marker and
        is not reported. ``tree`` is unused — ``fn.node_ref`` anchors the
        function subtree.
        """
        function_node = fn.node_ref
        if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise TypeError("FunctionInfo.node_ref must be a function-def handle")
        return [
            name
            for decorator in function_node.decorator_list
            if (name := self._marker_name(decorator))
        ]

    def spawn_shape_in_body(self, tree: object, fn: FunctionInfo) -> SpawnShape:
        """Return the spawn shape of ``fn``'s body (slice-05 CM-I).

        ``REAL_SUBPROCESS`` if the body calls ``subprocess.run`` /
        ``subprocess.Popen`` / ``subprocess.check_output`` (a genuine spawn);
        else ``IN_PROCESS_MAIN`` if the body calls an in-process ``main(...)``
        entry (a ``main`` / ``*.main`` callee); else ``NONE``. ``tree`` is
        unused — ``fn.node_ref`` anchors the function subtree.
        """
        callees = self._callees_in_function(fn)
        if any(callee in _REAL_SUBPROCESS_CALLEES for callee in callees):
            return SpawnShape.REAL_SUBPROCESS
        if any(self._is_main_callee(callee) for callee in callees):
            return SpawnShape.IN_PROCESS_MAIN
        return SpawnShape.NONE

    def failure_mode_coverage(
        self, manifest_source: str, test_names: frozenset[str]
    ) -> FailureModeCoverage:
        """Cross-check a manifest's failure modes against named tests (slice-07 M11).

        Scans ``manifest_source`` for its ``failure_modes:`` list and reports every
        declared mode ``id`` that no name in ``test_names`` mentions. Matching is
        structural-by-name: a mode is covered iff its id is a substring of some test
        name (the slice-07 learning hypothesis — a failure mode maps to its covering
        test by name, no judgment). A manifest with no ``failure_modes`` declares
        nothing to cover, so nothing is uncovered.
        """
        declared = self._declared_failure_modes(manifest_source)
        uncovered = tuple(
            mode_id
            for mode_id in declared
            if not any(mode_id in test_name for test_name in test_names)
        )
        return FailureModeCoverage(uncovered=uncovered)

    def step_shapes_in_module(self, tree: object) -> StepShapeCorpus:
        """Census the step-shape corpus of a test module (sustainable-test-suite slice-09).

        Finds every pytest-bdd step definition (a function decorated ``@given`` / ``@when``
        / ``@then``), normalizes each one's step-text literal into a similarity key (lower-
        case, whitespace-collapsed, trailing per-variant index stripped), groups by that key,
        and reports ``total_step_definitions`` + the number of groups holding more than one
        step (each a collapsible near-duplicate cluster). A module with no step definitions
        reports a zero census — never a crash.
        """
        module = self._as_module(tree)
        keys: list[str] = [
            self._normalize_step_text(text)
            for node in ast.walk(module)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and (text := self._step_text_of(node)) is not None
        ]
        groups: dict[str, int] = {}
        for key in keys:
            groups[key] = groups.get(key, 0) + 1
        near_duplicate_groups = sum(1 for count in groups.values() if count > 1)
        return StepShapeCorpus(
            near_duplicate_groups=near_duplicate_groups,
            total_step_definitions=len(keys),
        )

    @classmethod
    def _step_text_of(cls, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """The step-text literal of a pytest-bdd step definition, else None.

        A step definition is decorated with ``@given`` / ``@when`` / ``@then`` (bare,
        called with a string, or attribute-accessed). The step text is the first string
        argument of the decorator call (``@given("a maintainer ...")``); a bare decorator
        with no call has no step text and yields the empty string (still a step definition).
        A function decorated with none of the step decorators is not a step definition.
        """
        for decorator in node.decorator_list:
            base = cls._decorator_base_name(decorator)
            if base not in _STEP_DECORATOR_NAMES:
                continue
            if isinstance(decorator, ast.Call) and decorator.args:
                first = decorator.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    return first.value
            return ""
        return None

    @staticmethod
    def _normalize_step_text(text: str) -> str:
        """Normalize a step-text literal into a near-duplicate similarity key.

        Lowercase, collapse internal whitespace to single spaces, strip a single trailing
        numeric index (the per-variant suffix), so the two variants of one near-duplicate
        cluster ("... variant 0" / "... variant 1") share a normalized key.
        """
        collapsed = _WHITESPACE_RUN_RE.sub(" ", text.strip().lower())
        return _TRAILING_INDEX_RE.sub("", collapsed)

    def module_level_symbols_in_module(self, tree: object) -> list[SymbolInfo]:
        """Return every module-level ``def``/``class`` symbol (WS-9b, similar-
        responsibility slice-01).

        Reads only ``tree``'s TOP-LEVEL body (``ast.Module.body``) — a nested
        ``def``/``class`` (a method, a closure) is skipped, distinguishing this
        from the unfiltered ``functions_in_module`` walk (which reports every
        function at any nesting depth). ``arity`` is a function's positional +
        keyword-only parameter count (``*args``/``**kwargs`` excluded — those are
        variadic, not a fixed arity); a class always reports arity 0.
        """
        module = self._as_module(tree)
        symbols: list[SymbolInfo] = []
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(
                    SymbolInfo(
                        name=node.name,
                        lineno=node.lineno,
                        kind="function",
                        arity=self._arity_of(node.args),
                    )
                )
            elif isinstance(node, ast.ClassDef):
                symbols.append(
                    SymbolInfo(
                        name=node.name, lineno=node.lineno, kind="class", arity=0
                    )
                )
        return symbols

    def module_level_assignment_targets_in_module(self, tree: object) -> list[str]:
        """Return every module-level simple-assignment target name (CodeFact
        atoms, F-fix-delta-grounding-incapacity-is-indeterminate slice-02).

        Reads only ``tree``'s TOP-LEVEL body (``ast.Module.body``) for
        ``ast.Assign`` statements with a SINGLE ``ast.Name`` target --
        ``LIMIT = 5`` reports ``"LIMIT"``; a tuple/attribute/subscript
        target, an augmented/annotated assignment, or a nested (function-
        body) assignment is skipped. Companion to
        ``module_level_symbols_in_module`` (functions/classes) -- the
        ``AstAdapter``'s atoms surface reads this so a Reuse-Analysis
        citation of a module-level constant grounds too.
        """
        module = self._as_module(tree)
        return [
            target
            for node in module.body
            if isinstance(node, ast.Assign)
            and (target := self._single_name_target(node.targets)) is not None
        ]

    @staticmethod
    def _arity_of(args: ast.arguments) -> int:
        """A function's fixed parameter count: positional + keyword-only.

        ``*args``/``**kwargs`` are variadic (no fixed count) and excluded.
        """
        return len(args.posonlyargs) + len(args.args) + len(args.kwonlyargs)

    def assignments_constructing_type(
        self, tree: object, fn: FunctionInfo, type_names: frozenset[str]
    ) -> list[ConstructInfo]:
        """Return every ``name = Type(...)`` construction in ``fn`` (slice-09 P3).

        Walks ``fn``'s body for ``ast.Assign`` statements whose value is a call
        whose callee name is in ``type_names`` (``service = OrderService(...)`` →
        ``ConstructInfo(constructed="OrderService", target="service", ...)``). A
        plain function call (``app = build_application()``) has a callee outside
        ``type_names`` and is skipped; so is a construction of a type not in the
        requested set (``money = Money(150)``). Only single-target name assignments
        are reported (the hand-wiring shape). ``tree`` is unused — ``fn.node_ref``
        anchors the function subtree.
        """
        function_node = fn.node_ref
        if not isinstance(function_node, ast.AST):
            raise TypeError("FunctionInfo.node_ref must be an ast.AST handle")
        constructions: list[ConstructInfo] = []
        for node in ast.walk(function_node):
            if not isinstance(node, ast.Assign):
                continue
            construction = self._construction_of(node, type_names)
            if construction is not None:
                constructions.append(construction)
        return constructions

    def _construction_of(
        self, node: ast.Assign, type_names: frozenset[str]
    ) -> ConstructInfo | None:
        """The ``ConstructInfo`` of a single ``name = Type(...)`` assignment, or None.

        Reports only a single-target name assignment whose value is a call whose
        callee name is in ``type_names``; any other assignment shape (tuple target,
        non-call value, callee outside the set) yields None.
        """
        target = self._single_name_target(node.targets)
        if target is None or not isinstance(node.value, ast.Call):
            return None
        constructed = self._callee_name(node.value.func)
        if constructed not in type_names:
            return None
        return ConstructInfo(constructed=constructed, target=target, lineno=node.lineno)

    @staticmethod
    def _single_name_target(targets: list[ast.expr]) -> str | None:
        """The bound variable name of a single-target name assignment, else None."""
        if len(targets) != 1:
            return None
        target = targets[0]
        return target.id if isinstance(target, ast.Name) else None

    @staticmethod
    def _declared_failure_modes(manifest_source: str) -> list[str]:
        """The ordered ``failure_modes`` entry ids declared in a component manifest.

        A stdlib line-scan (no third-party YAML dependency — DES-bundle stdlib-only
        contract): once the ``failure_modes:`` header is seen, every following
        indented ``- id: <value>`` list entry contributes its id. A list item is
        always indented under its key, so a manifest's other top-level keys (which
        are never ``- id:`` list items) cannot be mistaken for failure modes. A
        manifest with no ``failure_modes`` header declares nothing — the adapter
        degrades to "nothing declared" rather than crashing on a malformed manifest.
        """
        modes: list[str] = []
        in_section = False
        for raw_line in manifest_source.splitlines():
            line = raw_line.rstrip()
            if not line or line.lstrip().startswith("#"):
                continue
            if line == _FAILURE_MODES_HEADER:
                in_section = True
                continue
            match = _MODE_ID_ENTRY.match(line) if in_section else None
            if match is not None:
                modes.append(match.group(1))
        return modes

    @staticmethod
    def _marker_name(decorator: ast.expr) -> str:
        """The ``<name>`` of a ``@pytest.mark.<name>`` decorator, else ``""``.

        Both the bare attribute (``@pytest.mark.wiring_e2e``) and the parametrized
        call (``@pytest.mark.parametrize(...)``) forms resolve to ``<name>``. A
        decorator that is not anchored at ``mark`` (a plain ``@given`` or
        ``@module.helper``) is not a pytest marker and yields ``""``.
        """
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and isinstance(
            target.value, ast.Attribute
        ):
            return target.attr if target.value.attr == "mark" else ""
        return ""

    def _callees_in_function(self, fn: FunctionInfo) -> list[str]:
        """The dotted callee name of every call site inside ``fn``'s body."""
        return [self._callee_name(call.func) for call in self._calls_in(fn)]

    @staticmethod
    def _calls_in(fn: FunctionInfo) -> list[ast.Call]:
        """Every ``ast.Call`` node inside ``fn``'s body (shared call-site walk)."""
        function_node = fn.node_ref
        if not isinstance(function_node, ast.AST):
            raise TypeError("FunctionInfo.node_ref must be an ast.AST handle")
        return [node for node in ast.walk(function_node) if isinstance(node, ast.Call)]

    @staticmethod
    def _is_main_callee(callee: str) -> bool:
        """True iff ``callee`` is a ``main`` / ``*.main`` in-process CLI entry."""
        return callee == _MAIN_CALLEE or callee.endswith(f".{_MAIN_CALLEE}")

    @staticmethod
    def _callee_name(func: ast.expr) -> str:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            base = PythonAstAdapter._callee_name(func.value)
            return f"{base}.{func.attr}" if base else func.attr
        return ""

    @staticmethod
    def _literal_names(value: ast.expr) -> list[str]:
        if not isinstance(value, (ast.Set, ast.List, ast.Tuple)):
            return []
        return [
            element.value
            for element in value.elts
            if isinstance(element, ast.Constant) and isinstance(element.value, str)
        ]

    @staticmethod
    def _as_module(tree: object) -> ast.Module:
        if not isinstance(tree, ast.Module):
            raise TypeError("PythonAstAdapter expects an ast.Module tree handle")
        return tree

    @staticmethod
    def _imports_from_nodes(nodes: Iterable[ast.AST]) -> list[ImportInfo]:
        """Collect ``ImportInfo`` from every ``ast.Import`` / ``ast.ImportFrom``.

        ``import x`` reports one entry per alias (dotted name); ``from x import y``
        reports the dotted source module ``x`` once (a ``from`` with no module —
        a bare relative import — is skipped). Shared by ``imports_in_function``
        (recursive walk) and ``imports_in_module`` (top-level body only); the
        caller supplies the node sequence so the traversal scope stays its choice.
        """
        imports: list[ImportInfo] = []
        for node in nodes:
            if isinstance(node, ast.Import):
                imports.extend(
                    ImportInfo(module=alias.name, lineno=node.lineno)
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(ImportInfo(module=node.module, lineno=node.lineno))
        return imports

    def _has_matching_decorator(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, names: frozenset[str]
    ) -> bool:
        return any(
            self._decorator_base_name(decorator) in names
            for decorator in node.decorator_list
        )

    @staticmethod
    def _decorator_base_name(decorator: ast.expr) -> str:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            return target.attr
        return ""
