"""Robustness PBT-density gate CLI -- slice-01 + slice-02 + slice-03.

Spine-gate sibling of ``carpaccio_slice_gate.py`` / ``at_review_verdict.py``.
Hosted in ``scripts/cli/`` because the gate has no DES-runtime coupling
(feature-delta H1): it parses YAML, walks a staged AT-scope directory, and
exits 0/1/2.

Slice-01 (walking skeleton): parse the DISTILL-projected
``unbounded-domains.yaml`` (a projection of the DESIGN component manifest),
assert each declared ``unbounded-input-domains[].id`` has a
``# domain: <id>``-tagged ``@given`` in the staged AT scope, exit 0/1/2.

Slice-02 (empty-declaration guard + DECISION D1 provenance check): widen
exit-1 semantics with three diagnostic sub-classes carried on stdout, all
sharing exit code 1:

* ``RobustnessDeclarationMissing`` -- the projection YAML parses but carries
  no ``unbounded-input-domains`` block while the staged AT scope has at
  least one acceptance test. Closes the silent-stale-pass pattern:
  "no declaration" is a refusal, never a vacuous pass.

* ``RobustnessExplicitEmptyAccepted`` (exit 0) -- the projection explicitly
  declares ``unbounded-input-domains: []`` AND carries the M-schema's
  ``unbounded-input-domains-empty-rationale`` one-line rationale. The
  legitimate "no unbounded domains" claim per the M schema ``oneOf`` branch;
  the gate accepts and emits the discriminating diagnostic token rather
  than falling through the slice-01 coverage-walk happy path.

* ``RobustnessProvenanceViolation`` -- the projection carries an entry with
  ``declared-at: distill`` for an id absent from the staged
  ``--component-manifest`` (DECISION D1: DISTILL projects, never authors).

Slice-03 (genuineness layers 1+3 + adversarial-AST robustness probe): walk
the AT-scope Python files via ``ast`` and reject shallow-by-AST PBTs:

* ``RobustnessPBTShallow`` (exit 1) -- a ``@given(...)`` decorator whose
  strategy expression is a literal ``st.just(...)`` (layer 1), OR whose
  body's only assertion is a tautology (``x == x``, ``True``, ``len(x) ==
  len(x)``) (layer 3), reached either directly at the @given/assert site
  or via a SINGLE-HOP module-local helper return (B5 evasion closure).
  Multi-hop / cross-module indirection is NAMED RESIDUE.

* ``RobustnessAdvisoryUnclassified`` (exit 0, advisory-only) -- an
  adversarial test-file AST shape the gate's own parser cannot classify
  (canonical V4 case: ``@pytest.mark.parametrize("x", _helper())`` with the
  value list reached through a helper Call). The gate emits a deterministic
  advisory verdict WITHOUT CRASHING (R6 gate-self-dogfood: the gate's own
  parser is the SUT here).

Exit codes (mirroring sibling gate CLIs):
    0 = PASS         -- every declared domain has @given coverage / explicit empty + rationale / advisory-only adversarial AST
    1 = CHECK_FAILED -- a declared domain lacks coverage / declaration missing / provenance violation / shallow PBT
    2 = MALFORMED    -- declaration YAML unparseable / schema-invalid

Later slices extend the surface (slice-04 layer 2 mutmut-delta, slice-05
wiring).
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import yaml

from des.adapters.driven.runner.runner_registry import (
    GLOBAL_REGISTRY,
    seed_runner_registry,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.ports.test_runner_port import RunnerAdapter
from des.ports.test_runner_port import resolve as resolve_runner


_EXIT_PASS = 0
_EXIT_CHECK_FAILED = 1
_EXIT_MALFORMED = 2
# Slice-04 R5 three-state: exit 3 (UNAVAILABLE) holds the feature out of
# ``ready`` when mutmut cannot answer truthfully -- neither pass nor fail.
# Distinct from CHECK_FAILED (exit 1) because the gate does NOT have evidence
# of a shallow PBT; it has evidence the layer-2 dependency cannot be trusted.
_EXIT_UNAVAILABLE = 3

# Slice-02 diagnostic tokens (DISTILL contract: emitted on stdout so AT
# assertions on ``completed.stdout`` discriminate the three exit-1
# sub-classes). Token strings are part of the contract -- do NOT abbreviate,
# rename, or i18n.
_TOKEN_DECLARATION_MISSING = "RobustnessDeclarationMissing"
_TOKEN_EXPLICIT_EMPTY_ACCEPTED = "RobustnessExplicitEmptyAccepted"
_TOKEN_PROVENANCE_VIOLATION = "RobustnessProvenanceViolation"
# Slice-05 wiring: the slice-01 coverage-miss path now emits this token on
# stdout so downstream wiring (verdict producer + SubagentStop hook chain)
# can disambiguate the refusal shape and forward the discriminating
# diagnostic to operators. Before slice-05 the coverage-miss path was
# tokenless (relying on a human-readable summary); the wiring slice needs
# the token surface for the producer/hook-chain diagnostic contracts.
_TOKEN_COVERAGE_MISS = "RobustnessCoverageMiss"

# Slice-03 diagnostic tokens. Same on-stdout contract -- the AT
# discriminates exit-1 sub-classes via these tokens.
_TOKEN_PBT_SHALLOW = "RobustnessPBTShallow"
_TOKEN_ADVISORY_UNCLASSIFIED = "RobustnessAdvisoryUnclassified"

# Slice-04 diagnostic tokens (layer-2 mutmut-delta proxy, R5 three-state).
# ``RobustnessPBTNotFalsifiable`` (exit 1) -- the declared sut symbol kills
# zero mutants while the positive control was killed; the PBT cannot tell a
# broken SUT from a correct one. ``RobustnessLayer2Unavailable`` (exit 3) --
# mutmut cannot answer truthfully (report malformed / empty / partial /
# positive control failed); neither pass nor fail, holds the feature out of
# ready.
_TOKEN_PBT_NOT_FALSIFIABLE = "RobustnessPBTNotFalsifiable"
_TOKEN_LAYER2_UNAVAILABLE = "RobustnessLayer2Unavailable"

# Slice-04 mutmut-report JSON schema field names (gate-internal v1 contract,
# documented in tests/.../fixtures/mutmut/README.md). The CLI consumes ONLY
# what the R5 three-state logic requires; the gate is NOT a general mutmut
# report consumer.
_MUTMUT_RAN_FIELD = "mutmut_ran"
_POSITIVE_CONTROL_FIELD = "positive_control"
_POSITIVE_CONTROL_KILLED_FIELD = "killed"
_MUTANTS_FIELD = "mutants"
_MUTANT_KILLED_FIELD = "killed"
_SUT_FIELD = "sut"

_DECLARED_AT_DISTILL = "distill"
_EMPTY_RATIONALE_FIELD = "unbounded-input-domains-empty-rationale"
_UNBOUNDED_DOMAINS_FIELD = "unbounded-input-domains"

# Slice-03 genuineness-layer constants. The Hypothesis strategy attribute
# the layer-1 walker treats as trivial-by-AST -- ``hypothesis.strategies.just``
# always yields the single carried example. Sampled_from / narrow integers
# remain slice-04 / NAMED RESIDUE for slice-03.
_TRIVIAL_STRATEGY_ATTR = "just"
# The Hypothesis decorator name whose strategy expressions the layer-1
# walker probes.
_GIVEN_DECORATOR_NAME = "given"
# The pytest decorator name whose value-list source the adversarial-AST
# walker probes. V4 case: indirect source via helper Call.
_PARAMETRIZE_DECORATOR_NAME = "parametrize"


def _parse_declaration_document(declaration_path: Path) -> dict[str, object]:
    """Parse the projection YAML and return the full top-level document.

    Slice-02 widens slice-01's narrow ``list[dict]`` return to the full
    top-level mapping so callers can introspect the declaration shape
    (block absent, explicitly empty + rationale, populated). Slice-01's
    schema-shape semantics (absent block, empty list, missing id, wrong
    types) move into the slice-02 declaration-state classifier below.
    """
    text = declaration_path.read_text(encoding="utf-8")
    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"unparseable declaration YAML: {exc}") from exc
    return dict(document)


def _at_scope_has_acceptance_tests(at_scope_dir: Path) -> bool:
    """True iff the staged AT scope holds at least one acceptance test file.

    The empty-declaration guard (AT1) only fires when the slice has any AT.
    A repo-wide ``rglob('*.py')`` walk is sufficient -- the staged AT scope
    is a per-scenario tmp directory carrying only the scenario's fixture
    test files.
    """
    return any(at_scope_dir.rglob("*.py"))


def _covered_domain_ids(at_scope_dir: Path) -> set[str]:
    """Return the set of domain ids tagged by a ``# domain: <id>`` comment.

    Slice-01 walking-skeleton: presence-check only. Walks every ``*.py`` file
    under ``at_scope_dir`` and collects each ``# domain: <id>`` marker.
    Strategy non-triviality + assertion-reaches-SUT are slice-03's job;
    kill-rate is slice-04's; this slice only verifies the tag is present.
    """
    covered: set[str] = set()
    for path in at_scope_dir.rglob("*.py"):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("# domain:"):
                continue
            marker = stripped[len("# domain:") :].strip()
            if marker:
                covered.add(marker)
    return covered


def _maybe_route_through_registered_density_adapter(
    at_scope_dir: Path,
) -> set[str] | None:
    """Route through a REGISTERED ``robustness_density`` facet; else ``None``.

    unified-language-adapter-registry slice-01 (ADR-ULAR-001 prefactoring, C7):
    sprout-and-fall-through seam mirroring ``run_contract_gate.py``'s
    ``_maybe_route_through_cargo`` shape -- seed the registry, RESOLVE the
    target's runner (by lockfile inspection of the staged AT scope), and look
    up a ``RobustnessDensityPort`` facet under the resolved TOOL-NAME (never
    ``target_language``, DDD-U5). Returns the facet's covered-domain-id set
    when one is registered; ``None`` when no facet is registered for the
    resolved tool-name (the case for EVERY target until a later slice's plugin
    registers one), so the caller falls through to the EXISTING
    ``_covered_domain_ids`` glob+scan body UNCHANGED. This file imported no
    runner-resolution mechanism before this seam -- this is 1 NEW call site of
    the EXISTING ``resolve()`` function, not a new resolution component.
    """
    seed_runner_registry()
    resolution = resolve_runner(at_scope_dir, None)
    if not isinstance(resolution, RunnerAdapter):
        return None
    facet = GLOBAL_REGISTRY.lookup_robustness_density(resolution.name)
    if facet is None:
        return None
    return facet.covered_domain_ids(at_scope_dir)


def _build_helper_return_index(module: ast.Module) -> dict[str, ast.expr]:
    """Index module-local helper functions to their single ``return`` expr.

    Slice-03 B5 resolver: the gate's genuineness layers follow ONE hop of
    module-local indirection. A helper qualifies when it is a top-level
    ``def <name>(...)`` whose body ends in a single ``return <expr>``; the
    returned expression is what layers 1+3 classify. Helpers without a
    return (or with multiple branches) are NOT followed -- multi-hop /
    cross-module / branch-divergent indirection is NAMED RESIDUE.
    """
    index: dict[str, ast.expr] = {}
    for node in module.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if not node.body:
            continue
        last = node.body[-1]
        if isinstance(last, ast.Return) and last.value is not None:
            index[node.name] = last.value
    return index


def _resolve_one_hop(expr: ast.expr, helper_index: dict[str, ast.expr]) -> ast.expr:
    """Resolve a single hop of module-local helper indirection if applicable.

    If ``expr`` is a Call to a bare Name matching a module-local helper in
    ``helper_index``, return the helper's return expression; otherwise return
    ``expr`` unchanged. Slice-03 B5: ONE hop only. Multi-hop / cross-module
    is NAMED RESIDUE.
    """
    if (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id in helper_index
    ):
        return helper_index[expr.func.id]
    return expr


def _is_trivial_strategy(expr: ast.expr) -> bool:
    """Layer-1 classifier: does ``expr`` evaluate to ``st.just(...)``?

    A trivial Hypothesis strategy yields a single carried example -- the PBT
    explores a one-element space. The canonical AST shape is
    ``Attribute(value=Name('st'), attr='just')`` invoked as a Call. Any
    other strategy (``st.text()``, ``st.integers()``, ``st.lists(...)``) is
    treated as genuine in slice-03; narrowing to suspect bounds is slice-04
    (layer 2 mutmut-delta) / NAMED RESIDUE.
    """
    if not isinstance(expr, ast.Call):
        return False
    func = expr.func
    return isinstance(func, ast.Attribute) and func.attr == _TRIVIAL_STRATEGY_ATTR


def _is_tautology(expr: ast.expr) -> bool:
    """Layer-3 classifier: is ``expr`` a tautological assertion expression?

    Recognised tautologies:
      * ``True`` (Constant)
      * ``x == x`` (Compare with Eq operator and structurally-identical operands)
      * ``len(x) == len(x)`` (Compare of two identical Call expressions)

    Symmetric Compare shapes (``x is x``, ``not (x != x)``) extend the
    family; slice-03 covers the canonical ``x == x`` flavor the design
    explicitly names. Other always-true expressions are NAMED RESIDUE.
    """
    if isinstance(expr, ast.Constant) and expr.value is True:
        return True
    if (
        isinstance(expr, ast.Compare)
        and len(expr.ops) == 1
        and isinstance(expr.ops[0], ast.Eq)
        and len(expr.comparators) == 1
    ):
        left_dump = ast.dump(expr.left)
        right_dump = ast.dump(expr.comparators[0])
        if left_dump == right_dump:
            return True
    return False


def _given_strategy_expressions(decorator: ast.expr) -> list[ast.expr]:
    """Return the strategy expressions carried by a ``@given(...)`` decorator.

    Slice-03 layer-1 supports positional and keyword args. The decorator
    must be a Call whose function is the bare Name ``given`` (Hypothesis
    convention used by the slice-01 fixture templates).
    """
    if not isinstance(decorator, ast.Call):
        return []
    if not (
        isinstance(decorator.func, ast.Name)
        and decorator.func.id == _GIVEN_DECORATOR_NAME
    ):
        return []
    strategies: list[ast.expr] = list(decorator.args)
    strategies.extend(kw.value for kw in decorator.keywords if kw.value is not None)
    return strategies


def _function_assert_expressions(func: ast.FunctionDef) -> list[ast.expr]:
    """Collect every ``assert <expr>`` test-expression in a function body.

    Layer 3 classifies a function as tautology-only when EVERY assert in its
    body has a tautological test expression (resolved one helper hop). A
    function with at least one genuine assert escapes the layer-3 verdict.
    """
    asserts: list[ast.expr] = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            asserts.append(node.test)
    return asserts


def _parametrize_value_source_is_indirect_call(decorator: ast.expr) -> bool:
    """V4 adversarial-AST shape: ``@pytest.mark.parametrize(name, _helper())``.

    The advisory-only branch the gate cannot classify (open vs finite cases).
    The decorator must be a Call to a parametrize Attribute / Name; the
    SECOND positional arg (the value source) must itself be a Call -- the
    indirect helper invocation. Direct list / tuple literals are NOT
    indirect and remain out of slice-03's advisory scope.
    """
    if not isinstance(decorator, ast.Call):
        return False
    func = decorator.func
    is_parametrize = (
        isinstance(func, ast.Attribute) and func.attr == _PARAMETRIZE_DECORATOR_NAME
    ) or (isinstance(func, ast.Name) and func.id == _PARAMETRIZE_DECORATOR_NAME)
    if not is_parametrize:
        return False
    if len(decorator.args) < 2:
        return False
    value_source = decorator.args[1]
    return isinstance(value_source, ast.Call)


def _scan_genuineness(at_scope_dir: Path) -> tuple[list[str], list[str]]:
    """Walk AT-scope ``*.py`` files and classify shallow / advisory findings.

    Returns ``(shallow_findings, advisory_findings)`` where each entry is a
    human-surface description of one finding. The gate's own parser is the
    SUT (R6 dogfood) -- on an ``ast.parse`` failure the file is skipped
    (deterministic verdict: the per-file probe completes without crashing).

    Layer 1 (trivial strategy): a ``@given`` whose strategy expression is
    ``st.just(...)`` directly or via single-hop helper.
    Layer 3 (tautology assert): a ``@given``-decorated function whose every
    assert test expression is a tautology (direct or via single-hop helper).
    Advisory: ``@pytest.mark.parametrize(name, _helper())`` -- V4 indirect
    source the gate cannot classify.
    """
    shallow: list[str] = []
    advisory: list[str] = []
    for path in sorted(at_scope_dir.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            module = ast.parse(source, filename=str(path))
        except (SyntaxError, OSError, UnicodeDecodeError):
            # R6 gate-self-dogfood: an unparseable file is the adversarial
            # input; survive it as advisory rather than crashing the gate.
            advisory.append(f"{path.name}: source could not be AST-parsed")
            continue
        helper_index = _build_helper_return_index(module)
        for node in ast.walk(module):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                strategies = _given_strategy_expressions(decorator)
                for strategy in strategies:
                    resolved = _resolve_one_hop(strategy, helper_index)
                    if _is_trivial_strategy(resolved):
                        shallow.append(
                            f"{path.name}::{node.name}: trivial @given strategy"
                        )
                if _parametrize_value_source_is_indirect_call(decorator):
                    advisory.append(
                        f"{path.name}::{node.name}: indirect parametrize source "
                        "the gate AST cannot classify"
                    )
            has_given = any(
                _given_strategy_expressions(decorator)
                for decorator in node.decorator_list
            )
            if has_given:
                asserts = _function_assert_expressions(node)
                if asserts and all(
                    _is_tautology(_resolve_one_hop(test, helper_index))
                    for test in asserts
                ):
                    shallow.append(
                        f"{path.name}::{node.name}: tautology-only @given assertion"
                    )
    return shallow, advisory


def _manifest_declared_domain_ids(manifest_path: Path) -> set[str]:
    """Return the set of domain ids declared in the DESIGN component manifest.

    The provenance back-reference set for the DECISION D1 check (AT3). A
    distill-authored projection entry MUST find its id here, otherwise the
    gate refuses with ``RobustnessProvenanceViolation`` -- DISTILL projects,
    never authors.
    """
    text = manifest_path.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    entries = document.get(_UNBOUNDED_DOMAINS_FIELD) or []
    return {str(entry["id"]) for entry in entries}


def _classify_mutmut_report(
    report_path: Path, declared_suts: list[str]
) -> tuple[int, str | None]:
    """Classify a fixture mutmut report against the declared sut symbols.

    Implements the slice-04 R5 three-state classifier against the gate-internal
    v1 schema (see ``tests/.../fixtures/mutmut/README.md``). Returns a tuple of
    ``(exit_code, token)`` where ``token`` is the diagnostic token to print on
    stdout (or ``None`` when the layer-2 verdict is silently positive).

    Classification order matches the architect spec:

      1. JSON unparseable                  -> exit 3 / Layer2Unavailable
      2. ``mutmut_ran == false``           -> exit 3 / Layer2Unavailable
      3. ``mutants`` is empty              -> exit 3 / Layer2Unavailable
      4. declared sut absent from mutants  -> exit 3 / Layer2Unavailable
      5. ``positive_control.killed`` false -> exit 3 / Layer2Unavailable
      6. ``mutants[sut].killed == 0``      -> exit 1 / PBTNotFalsifiable
      7. ``mutants[sut].killed > 0``       -> exit 0 / (silent)

    The check ordering is deliberate: the positive-control veto fires AFTER
    the sut-presence check so a partial-missing-sut classifies as
    ``REPORT_PARTIAL_MISSING`` (the more specific cell) rather than being
    masked by an upstream positive-control failure. The two failure cells
    nevertheless share the same external observable (exit 3 + token), so the
    order is internal-detail only.
    """
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    if not isinstance(report, dict):
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    if report.get(_MUTMUT_RAN_FIELD) is not True:
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    mutants = report.get(_MUTANTS_FIELD) or {}
    if not mutants:
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    missing_suts = [sut for sut in declared_suts if sut not in mutants]
    if missing_suts:
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    positive_control = report.get(_POSITIVE_CONTROL_FIELD) or {}
    if positive_control.get(_POSITIVE_CONTROL_KILLED_FIELD) is not True:
        return _EXIT_UNAVAILABLE, _TOKEN_LAYER2_UNAVAILABLE
    zero_kill_suts = [
        sut
        for sut in declared_suts
        if int(mutants[sut].get(_MUTANT_KILLED_FIELD, 0)) == 0
    ]
    if zero_kill_suts:
        return _EXIT_CHECK_FAILED, _TOKEN_PBT_NOT_FALSIFIABLE
    return _EXIT_PASS, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_robustness_density",
        description=(
            "Robustness PBT-density gate (slice-01 walking skeleton + "
            "slice-02 empty-declaration guard / DECISION D1 provenance "
            "check). Asserts each declared unbounded-input-domain id has "
            "a # domain:-tagged @given in the staged AT scope; refuses a "
            "silently-missing declaration; accepts an explicit empty + "
            "rationale claim; rejects a distill-authored id missing from "
            "the DESIGN component manifest."
        ),
    )
    parser.add_argument(
        "--declaration",
        required=True,
        help="Path to the unbounded-domains.yaml projection file.",
    )
    parser.add_argument(
        "--at-scope",
        required=True,
        help="Directory of staged AT-scope test files to grep for # domain: tags.",
    )
    parser.add_argument(
        "--component-manifest",
        required=False,
        default=None,
        help=(
            "Optional path to the DESIGN component manifest. Required for "
            "the DECISION D1 provenance check on declared-at: distill entries."
        ),
    )
    parser.add_argument(
        "--mutmut-report",
        required=False,
        default=None,
        help=(
            "Optional path to a fixture mutmut report JSON. When provided, "
            "the gate runs the slice-04 layer-2 mutmut-delta proxy (R5 "
            "three-state classifier) against each declared unbounded-input-"
            "domain's sut symbol. Per the M2 architect mandate this must be "
            "a committed fixture path; the gate never invokes live mutmut."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the robustness density gate; return the verdict exit code."""
    args = _build_parser().parse_args(argv)
    declaration_path = Path(args.declaration)
    at_scope_dir = Path(args.at_scope)
    component_manifest_path = (
        Path(args.component_manifest) if args.component_manifest else None
    )
    mutmut_report_path = Path(args.mutmut_report) if args.mutmut_report else None

    try:
        document = _parse_declaration_document(declaration_path)
    except ValueError:
        print_human_summary(
            Verdict.FAIL,
            f"robustness density declaration at {declaration_path} is malformed",
        )
        return _EXIT_MALFORMED

    # Slice-02 AT1: silently-missing block + ATs in scope -> refusal.
    if _UNBOUNDED_DOMAINS_FIELD not in document:
        if _at_scope_has_acceptance_tests(at_scope_dir):
            print(_TOKEN_DECLARATION_MISSING)
            print_human_summary(
                Verdict.FAIL,
                f"robustness density declaration at {declaration_path} omits "
                f"the {_UNBOUNDED_DOMAINS_FIELD} block while acceptance tests "
                "exist in scope -- absence is not a pass",
            )
            return _EXIT_CHECK_FAILED

    declared_entries = list(document.get(_UNBOUNDED_DOMAINS_FIELD) or [])

    # Slice-02 AT2: explicit empty + one-line rationale -> legitimate claim.
    if not declared_entries and _EMPTY_RATIONALE_FIELD in document:
        print(_TOKEN_EXPLICIT_EMPTY_ACCEPTED)
        print_human_summary(
            Verdict.PASS,
            "robustness density accepts explicit empty declaration with "
            f"rationale: {document[_EMPTY_RATIONALE_FIELD]!r}",
        )
        return _EXIT_PASS

    # Slice-02 AT3: DECISION D1 provenance check for declared-at: distill.
    if component_manifest_path is not None:
        manifest_ids = _manifest_declared_domain_ids(component_manifest_path)
        distill_orphans = sorted(
            str(entry["id"])
            for entry in declared_entries
            if entry.get("declared-at") == _DECLARED_AT_DISTILL
            and str(entry["id"]) not in manifest_ids
        )
        if distill_orphans:
            print(_TOKEN_PROVENANCE_VIOLATION)
            print_human_summary(
                Verdict.FAIL,
                "robustness density refuses distill-authored domain(s) absent "
                f"from the design component manifest: {distill_orphans}",
            )
            return _EXIT_CHECK_FAILED

    covered = _maybe_route_through_registered_density_adapter(at_scope_dir)
    if covered is None:
        covered = _covered_domain_ids(at_scope_dir)
    declared_ids = {str(entry["id"]) for entry in declared_entries}
    missing = declared_ids - covered
    if missing:
        print(_TOKEN_COVERAGE_MISS)
        print_human_summary(
            Verdict.FAIL,
            f"robustness density check failed: {len(missing)} declared "
            f"unbounded-input-domain(s) lack @given coverage: {sorted(missing)}",
        )
        return _EXIT_CHECK_FAILED

    # Slice-03: genuineness layers 1+3 + adversarial-AST robustness probe.
    # Walk the AT-scope file AST; reject shallow @given strategies / tautology
    # asserts (B5 single-hop helper resolved) and emit a deterministic
    # advisory verdict for V4 indirect-parametrize sources without crashing.
    shallow_findings, advisory_findings = _scan_genuineness(at_scope_dir)
    if shallow_findings:
        print(_TOKEN_PBT_SHALLOW)
        print_human_summary(
            Verdict.FAIL,
            "robustness density refuses shallow property-based test(s): "
            f"{shallow_findings}",
        )
        return _EXIT_CHECK_FAILED
    if advisory_findings:
        print(_TOKEN_ADVISORY_UNCLASSIFIED)
        print_human_summary(
            Verdict.DEGRADED,
            f"robustness density verified: {len(declared_ids)} declared "
            "unbounded-input-domain(s) have @given coverage; "
            f"{len(advisory_findings)} adversarial-AST finding(s) recorded "
            f"as advisory-only: {advisory_findings}",
        )
        return _EXIT_PASS

    # Slice-04: layer-2 mutmut-delta proxy (R5 three-state). Fires only when
    # ``--mutmut-report`` is provided; reads the fixture JSON and classifies
    # against each declared entry's ``sut:`` symbol. Exit 1 +
    # ``RobustnessPBTNotFalsifiable`` when the PBT kills zero mutants with a
    # trustworthy run; exit 3 + ``RobustnessLayer2Unavailable`` when mutmut
    # cannot answer truthfully (R5 unavailable cells); silent exit 0 when
    # the layer-2 verdict is positive (KILL_RATE_POSITIVE).
    if mutmut_report_path is not None:
        declared_suts = [str(entry[_SUT_FIELD]) for entry in declared_entries]
        exit_code, token = _classify_mutmut_report(mutmut_report_path, declared_suts)
        if token is not None:
            print(token)
        if exit_code == _EXIT_UNAVAILABLE:
            print_human_summary(
                Verdict.DEGRADED,
                f"robustness density layer-2 unavailable: fixture mutmut "
                f"report at {mutmut_report_path} cannot answer truthfully -- "
                "feature held out of ready (neither pass nor fail)",
            )
            return _EXIT_UNAVAILABLE
        if exit_code == _EXIT_CHECK_FAILED:
            print_human_summary(
                Verdict.FAIL,
                "robustness density refuses property-based test(s) whose "
                "declared sut symbol(s) kill zero mutants while the positive "
                f"control was killed: {declared_suts}",
            )
            return _EXIT_CHECK_FAILED

    print_human_summary(
        Verdict.PASS,
        f"robustness density verified: {len(declared_ids)} declared "
        "unbounded-input-domain(s) have @given coverage",
    )
    return _EXIT_PASS


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
