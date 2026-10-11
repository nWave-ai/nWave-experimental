"""Real node:test producer output through the public DES consumer.

@contract-shape: real-io @adapter-integration
Noise preservation projects directly to the same captured stdout and bound
verdict as the subprocess skeleton; the CLI entry is in-process, not mocked.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import pytest
from hypothesis import Phase, example, given, seed, settings
from hypothesis import strategies as st

from tests.des.acceptance.steps_for_the_orchestrator.test_native_assertion_failure_is_measured_red import (
    MARKER,
    ORACLE,
    PYTHON,
    REPORTER,
    ROOT,
    NativeCase,
    NativeOracleJourney,
    require,
)


class PopulationBranch(Enum):
    EMPTY = "empty"
    PASSED = "passed"
    ASSERTION_FAILED = "assertion-failed"
    SETUP_FAILED = "setup-failed"


@dataclass(frozen=True)
class NativePopulation:
    """Independent authored semantic cases, not predicted callback metadata.

    Bounds below limit exploration only. Repeated and file-like names deliberately
    carry no observation semantics. Each completed test contains a real assertion.
    """

    branch: PopulationBranch
    left_passes: int = 0
    left_failures: int = 0
    right_passes: int = 0
    right_failures: int = 0
    skipped: int = 0
    todo: int = 0
    empty_suites: int = 0
    wrapper_files: int = 0
    depth: int = 0
    name: str = "native_oracle.test.mjs"

    def completed_source(self, passes: int, failures: int) -> str:
        message = json.dumps(
            "WHAT: promised value differs; WHY: native observation must be real; HOW: deliver the value"
        )
        name = json.dumps(self.name)
        return "\n".join(
            [f"await test({name},()=>assert.equal(1,1,{message}));"] * passes
            + [f"await test({name},()=>assert.equal(0,1,{message}));"] * failures
        )

    def source(self, completed: str, *, setup: bool, decorated: bool) -> str:
        body = completed
        if decorated:
            name = json.dumps(self.name)
            body += "\n" + "\n".join(
                [f"test({name},{{skip:true}},()=>assert.fail('must not execute'));"]
                * self.skipped
                + [f"test({name},{{todo:true}},()=>{{}});"] * self.todo
                + [f"describe({name},()=>{{}});"] * self.empty_suites
            )
            for _ in range(self.depth):
                body = f"await describe({name},async()=>{{\n{body}\n}});"
        if setup:
            body += "\nawait test('runtime setup',()=>{throw new Error('setup unavailable');});"
        return (
            "import {test,describe} from 'node:test'; import assert from 'node:assert/strict';\n"
            "console.log('NATIVE-DIAGNOSTIC: runner reached authored module');\n"
            + body
            + "\n"
        )


@st.composite
def native_populations(draw, branch: PopulationBranch):
    # The finite branch is selected by native parametrization BEFORE generation.
    # Shrinking can remove observations/containers but cannot switch that branch.
    passes = branch in {
        PopulationBranch.PASSED,
        PopulationBranch.ASSERTION_FAILED,
        PopulationBranch.SETUP_FAILED,
    }
    failures = branch in {
        PopulationBranch.ASSERTION_FAILED,
        PopulationBranch.SETUP_FAILED,
    }
    fields = {
        "left_passes": draw(
            st.integers(min_value=int(branch is PopulationBranch.PASSED), max_value=8)
        )
        if passes
        else 0,
        "left_failures": draw(
            st.integers(
                min_value=int(branch is PopulationBranch.ASSERTION_FAILED), max_value=8
            )
        )
        if failures
        else 0,
        "right_passes": draw(st.integers(min_value=0, max_value=8)) if passes else 0,
        "right_failures": draw(st.integers(min_value=0, max_value=8))
        if failures
        else 0,
        "skipped": draw(st.integers(min_value=0, max_value=8)),
        "todo": draw(st.integers(min_value=0, max_value=8)),
        "empty_suites": draw(st.integers(min_value=0, max_value=8)),
        "wrapper_files": draw(st.integers(min_value=0, max_value=8)),
        "depth": draw(st.integers(min_value=0, max_value=3)),
    }
    names_used = any(value for name, value in fields.items() if name != "wrapper_files")
    name = (
        draw(
            st.one_of(
                st.just("native_oracle.test.mjs"),
                st.text(
                    alphabet=st.characters(blacklist_categories=("Cs",)), max_size=64
                ),
            )
        )
        if names_used
        else "native_oracle.test.mjs"
    )
    return NativePopulation(branch, **fields, name=name)


class NativeProtocolContract:
    def __init__(self, workspace: Path):
        self.workspace = workspace

    def observes(
        self, case: NativeCase, transformation: str = "", exit_status: int | None = None
    ):
        journey = NativeOracleJourney(self.workspace)
        argv = None
        if transformation or exit_status is not None:
            # The selected target-native bridge relays ACTUAL native callbacks.
            # Only negative protocol controls mutate the completed wire output.
            bridge = (
                'import {spawnSync} from "node:child_process";'
                'const r=spawnSync(process.execPath,["--test",'
                f'"--test-reporter=./{REPORTER}","{ORACLE}"],{{encoding:"utf8"}});'
                "let output=r.stdout;"
                + transformation
                + "process.stdout.write(output);process.stderr.write(r.stderr);"
                f"process.exit({exit_status if exit_status is not None else 'r.status'});"
            )
            argv = [journey.node, "--input-type=module", "-e", bridge]
        return journey, journey.measure(case, argv=argv)

    def preserves_actual_assertion(self, exit_status: int):
        _, result = self.observes(NativeCase.ASSERTION, exit_status=exit_status)
        expected = "red" if exit_status else "indeterminate"
        require(
            result.witness["verdict"] == expected,
            f"actual assertion with exit {exit_status} retained {result.witness}",
            "use zero/nonzero completion semantics, never pytest-specific numeric meanings",
        )

    def refuses_invalid_evidence(self, replacement: str):
        transformation = (
            "output=output.replace(/DES-ORACLE-OBSERVATION: [^\\n]*/,"
            + json.dumps(replacement)
            + ");"
        )
        _, result = self.observes(NativeCase.ASSERTION, transformation)
        require(
            result.witness["verdict"] == "indeterminate",
            f"invalid terminal observation was promoted: {result.witness}",
            "strictly decode one compatible complete record and retain the unavailable reason",
        )
        require(
            result.witness["axis"] != "exit-status-only",
            f"invalid protocol silently fell back to exit-only: {result.witness}",
            "surface native-observation-invalid provenance instead of guessing assertion meaning",
        )
        require(
            bool(result.terminal + result.stderr),
            "unavailable protocol lost its diagnostic",
            "explain WHAT is unavailable, WHY and HOW to repair the producing recipe",
        )

    def distinguishes_missing_tooling(self):
        journey = NativeOracleJourney(self.workspace)
        result = journey.measure(
            NativeCase.SETUP,
            argv=[
                journey.node,
                "--test",
                "--test-reporter=./missing-reporter.mjs",
                ORACLE,
            ],
        )
        require(
            result.witness["verdict"] not in {"red", "green"},
            f"missing native test tooling became an outcome: {result.witness}",
            "retain startup failure without inventing an assertion observation",
        )
        require(
            MARKER not in result.execution["stdout"],
            f"incapable reporter produced a terminal observation: {result.execution}",
            "derive observations only after actual native runner completion",
        )

    def preserves_wire_equivalence(self):
        transformation = (
            "output=output.replace(/DES-ORACLE-OBSERVATION: ([^\\n]*)/,(_,wire)=>{"
            "const record=JSON.parse(wire);return 'DES-ORACLE-OBSERVATION: '+JSON.stringify("
            "Object.fromEntries(Object.entries(record).reverse()),null,0).replace(/:/g,': ');});"
        )
        _, result = self.observes(NativeCase.ASSERTION, transformation)
        require(
            result.witness["verdict"] == "red",
            f"equivalent actual producer wire lost assertion RED: {result.witness}",
            "decode semantic fields independently of JSON key order and insignificant whitespace",
        )

    def refuses_source_disagreement(self):
        journey = NativeOracleJourney(self.workspace)
        bridge = (
            "import {spawnSync} from 'node:child_process';import {writeFileSync} from 'node:fs';"
            f"const actual=spawnSync(process.execPath,['--test','--test-reporter=./{REPORTER}','{ORACLE}'],{{encoding:'utf8'}});"
            "writeFileSync('tests/acceptance/test_report_control.py',"
            '"def test_observed_pass():\\n    assert 1 == 1\\n");'
            f"const report=spawnSync({json.dumps(str(PYTHON))},['-m','pytest','tests/acceptance/test_report_control.py','-q','--junitxml=actual-report.xml'],{{encoding:'utf8'}});"
            "if(report.status!==0){process.stderr.write(report.stderr+report.stdout);process.exit(3);}"
            "process.stdout.write(actual.stdout);process.stderr.write(actual.stderr);process.exit(actual.status);"
        )
        result = journey.measure(
            NativeCase.ASSERTION,
            argv=[
                journey.node,
                "--input-type=module",
                "-e",
                bridge,
                "--",
                "--junitxml=actual-report.xml",
            ],
        )
        require(
            result.witness["verdict"] == "indeterminate",
            f"actual native failure and fresh actual passing report disagreed but became {result.witness}",
            "reconcile both real observation sources and retain conflict as unavailable",
        )

    def refuses_missing_assertion_record(self):
        _, result = self.observes(
            NativeCase.ASSERTION,
            "output=output.replace(/DES-ORACLE-OBSERVATION: [^\\n]*\\n?/,'AssertionError: diagnostic only\\n');",
        )
        require(
            result.witness["verdict"] not in {"red", "green"},
            f"human prose without observation became {result.witness}",
            "never infer assertion meaning from exception names or process exit",
        )

    def preserves_noise(self, case: str, count: int, noise: str):
        semantic = NativeCase.ASSERTION if case == "assertion" else NativeCase.SETUP
        lines = [
            'import test from "node:test";',
            'import assert from "node:assert/strict";',
        ]
        for index in range(count):
            lines.append(f'test("actual observation {index}",()=>assert.equal(0,1));')
        if case != "assertion":
            lines.append(
                'test("runtime setup fails after observations",()=>{throw new Error("setup unavailable");});'
            )
        body = "\n".join(lines)
        # Noise originates in the real target program. Never rewrite the candidate reporter.
        verdicts = []
        for label, diagnostics in (("clean", ""), ("noisy", noise)):
            journey = NativeOracleJourney(self.workspace / label)
            noisy_body = "console.log(" + json.dumps(diagnostics) + ");\n" + body
            result = journey.measure(semantic, body=noisy_body)
            records = [
                line
                for line in result.execution["stdout"].splitlines()
                if line.startswith(MARKER)
            ]
            require(
                len(records) == 1,
                f"native terminal record population differs: {records}",
                "emit exactly one completed native record",
            )
            counts = json.loads(records[0][len(MARKER) :])
            require(
                counts
                == {
                    "version": 1,
                    "observed": count,
                    "assertions_failed": count,
                    "setup_failed": int(case != "assertion"),
                },
                f"native events did not preserve generated case/count: {counts}",
                "map completed actual assertion and setup callbacks, ignoring diagnostics",
            )
            verdicts.append(result.witness["verdict"])
        require(
            verdicts[0] == verdicts[1],
            f"noise changed verdict {verdicts}",
            "ignore diagnostic noise outside the terminal observation",
        )
        expected = "red" if case == "assertion" else "broken"
        require(
            all(verdict == expected for verdict in verdicts),
            f"independently selected {case} retained clean/noisy verdicts {verdicts}",
            "preserve actual assertion/setup meaning, not two equally wrong classifications",
        )

    def preserves_population(self, population: NativePopulation) -> None:
        """Public refinement of observation::fold and _oracle_verdict.

        WrapperCounted is killed by empty/decorated counts; PassLost, FailureLost
        and SetupPromoted by independently authored controls. Four native runs
        cover zero/additive concatenation and container insertion in one law.
        """
        left = population.completed_source(
            population.left_passes, population.left_failures
        )
        right = population.completed_source(
            population.right_passes, population.right_failures
        )
        has_setup = population.branch is PopulationBranch.SETUP_FAILED
        measurements = {}
        for label, body, passed, failed, setup, decorated in (
            (
                "left",
                left,
                population.left_passes,
                population.left_failures,
                False,
                False,
            ),
            (
                "right",
                right,
                population.right_passes,
                population.right_failures,
                has_setup,
                False,
            ),
            (
                "joined",
                left + "\n" + right,
                population.left_passes + population.right_passes,
                population.left_failures + population.right_failures,
                has_setup,
                False,
            ),
            (
                "containers",
                left + "\n" + right,
                population.left_passes + population.right_passes,
                population.left_failures + population.right_failures,
                has_setup,
                True,
            ),
        ):
            journey = NativeOracleJourney(self.workspace / label)
            companions = {
                f"tests/acceptance/wrapper-{index}.test.mjs": "export const moduleLoaded = true;\n"
                for index in range(population.wrapper_files if decorated else 0)
            }
            result = journey.measure(
                NativeCase.ASSERTION,
                body=population.source(body, setup=setup, decorated=decorated),
                argv=[
                    journey.node,
                    "--test",
                    f"--test-reporter=./{REPORTER}",
                    ORACLE,
                    *companions,
                ],
                companion_files=companions,
            )
            records = [
                line
                for line in result.execution["stdout"].splitlines()
                if line.startswith(MARKER)
            ]
            expected = {
                "version": 1,
                "observed": passed + failed,
                "assertions_failed": failed,
                "setup_failed": int(setup),
            }
            require(
                len(records) == 1
                and result.execution["stdout"].endswith(records[0] + "\n"),
                f"{label} terminal population/order differs: {records}",
                "emit one terminal record only after all native diagnostics/events finish",
            )
            actual = json.loads(records[0][len(MARKER) :])
            verdict = (
                "broken"
                if setup
                else "red"
                if failed
                else "green"
                if passed
                else "indeterminate"
            )
            require(
                actual == expected,
                f"{population.branch.value}/{label}: authored {expected}, actual {actual}; case={population}",
                "exclude synthetic containers and preserve additive completed assertion/setup counts",
            )
            require(
                result.witness["verdict"] == verdict
                and result.execution["exit"] == int(bool(failed or setup)),
                f"{label}: authored {verdict}, actual {result.witness}; case={population}",
                "preserve genuine pass/fail outcomes with setup precedence and no outcome for the empty identity",
            )
            require(
                "NATIVE-DIAGNOSTIC: runner reached authored module"
                in result.execution["stdout"],
                f"{label} lost authentic diagnostic forwarding: {result.execution}",
                "forward native stdout while keeping diagnostics outside the observation population",
            )
            require(
                not list(journey.root.rglob("*.xml")),
                f"{label} unexpectedly produced XML",
                "measure native completed callbacks without requiring JUnit",
            )
            measurements[label] = (actual, result.witness["verdict"])
        require(
            measurements["joined"] == measurements["containers"],
            f"container insertion changed native counts/verdict: {measurements}",
            "give non-observing wrappers/suites/skip/todo the zero contribution",
        )
        for field in ("observed", "assertions_failed", "setup_failed"):
            require(
                measurements["joined"][0][field]
                == sum(measurements[arm][0][field] for arm in ("left", "right")),
                f"concatenation lost population conservation for {field}: {measurements}",
                "add the two independently observed completed populations without double-counting containers",
            )


@pytest.mark.parametrize(
    "exit_status",
    [0, 1, 2, 127],
    ids=[
        "contradictory-success",
        "native-failure",
        "non-pytest-failure",
        "foreign-nonzero-convention",
    ],
)
def test_actual_native_assertion_meaning_is_independent_of_numeric_exit_conventions(
    tmp_path, exit_status
):
    NativeProtocolContract(tmp_path).preserves_actual_assertion(exit_status)


INVALID_RECORDS = {
    "unknown-version": MARKER
    + '{"version":2,"observed":1,"assertions_failed":1,"setup_failed":0}',
    "boolean-count": MARKER
    + '{"version":1,"observed":true,"assertions_failed":1,"setup_failed":0}',
    "negative-count": MARKER
    + '{"version":1,"observed":-1,"assertions_failed":0,"setup_failed":0}',
    "incoherent-count": MARKER
    + '{"version":1,"observed":0,"assertions_failed":1,"setup_failed":0}',
    "duplicate-key": MARKER
    + '{"version":1,"version":1,"observed":1,"assertions_failed":1,"setup_failed":0}',
    "truncated": MARKER + '{"version":1',
    "duplicate-record": (
        MARKER + '{"version":1,"observed":1,"assertions_failed":1,"setup_failed":0}\n'
    )
    * 2,
    "extra-field": MARKER
    + '{"version":1,"observed":1,"assertions_failed":1,"setup_failed":0,"extra":1}',
}


@pytest.mark.parametrize(
    "replacement", list(INVALID_RECORDS.values()), ids=list(INVALID_RECORDS)
)
def test_incompatible_native_protocol_is_unavailable_not_an_assertion(
    tmp_path, replacement
):
    NativeProtocolContract(tmp_path).refuses_invalid_evidence(replacement)


def test_missing_native_tooling_cannot_masquerade_as_observed_assertion(tmp_path):
    NativeProtocolContract(tmp_path).distinguishes_missing_tooling()


def test_equivalent_actual_native_wire_preserves_assertion_meaning(tmp_path):
    NativeProtocolContract(tmp_path).preserves_wire_equivalence()


def test_native_and_fresh_actual_report_disagreement_is_unavailable(tmp_path):
    NativeProtocolContract(tmp_path).refuses_source_disagreement()


def test_human_assertion_prose_without_completed_record_is_unmeasured(tmp_path):
    NativeProtocolContract(tmp_path).refuses_missing_assertion_record()


@seed(42)
@settings(max_examples=20, deadline=None)
@example(case="setup", count=1, noise="AssertionError: misleading human prose λ🌊")
@example(case="assertion", count=1, noise="AssertionError: misleading human prose λ🌊")
@given(
    case=st.sampled_from(["assertion", "setup"]),
    count=st.integers(min_value=1, max_value=16),
    noise=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)), max_size=2048
    ).filter(lambda text: MARKER not in text),
)
def test_diagnostic_noise_preserves_actual_native_observation_and_retained_verdict(
    case, count, noise
):
    with tempfile.TemporaryDirectory(prefix="native-protocol-") as directory:
        NativeProtocolContract(Path(directory)).preserves_noise(case, count, noise)


def test_native_declaration_provenance_preserves_top_level_and_nested_tests(tmp_path):
    NativeOracleJourney(tmp_path).inspect_declaration_provenance()


@pytest.mark.parametrize(
    "branch", list(PopulationBranch), ids=lambda branch: branch.value
)
@seed(42)
@settings(
    max_examples=6,
    deadline=None,
    print_blob=True,
    report_multiple_bugs=False,
    phases=(Phase.generate, Phase.shrink),
)
@given(data=st.data())
def test_non_observing_containers_preserve_native_population_and_public_verdict(
    branch, data
):
    # Four constructive alternatives x six samples = the declared initial
    # 24-case budget. Finite controls live in ObservationJourney, not @example
    # decorators which would prevent the failing branch's generation/shrinking.
    # Generation and shrinking remain real-port observations. Exclude the
    # separate explanatory rerun phase; it is not another declared law.
    population = data.draw(native_populations(branch), label=branch.value)
    with tempfile.TemporaryDirectory(prefix="native-population-") as directory:
        NativeProtocolContract(Path(directory)).preserves_population(population)


class OrdinaryImports(ast.NodeVisitor):
    """Runtime import statements, not incidental AST layout or prose.

    TYPE_CHECKING-only imports are not executed. Lazy/dynamic resolution is
    outside ordinary imports; when found in the governed domain, it is reported
    unsupported rather than silently counted as an empty dependency population.
    """

    def __init__(self):
        self.imports = []
        self.dynamic = []

    def visit_Import(self, node):
        self.imports.extend((alias.name, 0, ()) for alias in node.names)

    def visit_ImportFrom(self, node):
        self.imports.append(
            (node.module or "", node.level, tuple(alias.name for alias in node.names))
        )

    def visit_If(self, node):
        type_only = (
            isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
        ) or (
            isinstance(node.test, ast.Attribute) and node.test.attr == "TYPE_CHECKING"
        )
        for child in (
            node.orelse if type_only else [node.test, *node.body, *node.orelse]
        ):
            self.visit(child)

    def visit_Call(self, node):
        if (isinstance(node.func, ast.Name) and node.func.id == "__import__") or (
            isinstance(node.func, ast.Attribute) and node.func.attr == "import_module"
        ):
            self.dynamic.append(node.lineno)
        self.generic_visit(node)


class NeutralDependencyContract:
    """Resolve the entire ordinary project closure; stdlib is a trusted boundary."""

    def __init__(self, root: Path):
        self.root = root
        self.visited = set()
        self.dependencies = set()

    def local(self, name: str) -> Path | None:
        for base in (self.root / "src", self.root):
            path = base.joinpath(*name.split("."))
            if path.with_suffix(".py").is_file():
                return path.with_suffix(".py")
            if (path / "__init__.py").is_file():
                return path / "__init__.py"
        return None

    def require_stdlib(self, name: str) -> None:
        top = name.split(".", maxsplit=1)[0]
        require(
            top in sys.stdlib_module_names,
            f"neutral domain imports non-standard dependency {name}",
            "keep target-tool, application/adapter/CLI and test dependencies outside the neutral domain",
        )
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError, ModuleNotFoundError) as error:
            raise AssertionError(
                f"WHAT: unresolved dependency {name}: {error}; WHY: unsupported resolution is not absence; HOW: expose an ordinary resolvable dependency"
            ) from error
        require(
            spec is not None,
            f"dependency {name} could not be resolved",
            "resolve the actual module instead of passing an empty unsupported import analysis",
        )
        require(
            spec.origin in {"built-in", "frozen"}
            or (
                spec.origin is not None
                and "site-packages" not in Path(spec.origin).parts
                and Path(spec.origin).is_relative_to(Path(sys.base_prefix))
            ),
            f"standard-library name {name} resolves outside the interpreter: {spec.origin}",
            "remove target/project shadowing of the standard-library dependency",
        )

    def inspect(self, name: str) -> None:
        if name in self.visited:
            return
        source = self.local(name)
        if source is None:
            self.require_stdlib(name)
            return
        allowed = name in {"des", "des.domain"} or name.startswith("des.domain.")
        require(
            allowed,
            f"neutral domain reaches forbidden project owner {name}: {source}",
            "restore domain-only ownership with standard-library dependencies",
        )
        self.visited.add(name)
        package = name if source.name == "__init__.py" else name.rpartition(".")[0]
        imports = OrdinaryImports()
        imports.visit(ast.parse(source.read_text(), filename=str(source)))
        if name not in {"des", "des.domain"}:
            require(
                not imports.dynamic,
                f"unsupported dynamic imports in {source}:{imports.dynamic}",
                "make the neutral dependency ordinary/resolvable or return the analysis gap to DESIGN",
            )
        for module, level, members in imports.imports:
            try:
                resolved = (
                    importlib.util.resolve_name("." * level + module, package)
                    if level
                    else module
                )
            except (ImportError, ValueError) as error:
                raise AssertionError(
                    f"WHAT: unresolved relative dependency in {source}: {error}; WHY: no supported closure was measured; HOW: declare a resolvable import"
                ) from error
            require(
                bool(resolved),
                f"import in {source} has no resolvable module",
                "declare the module before claiming the neutral dependency closure",
            )
            self.dependencies.add(resolved)
            self.inspect(resolved)
            for member in members:
                child = f"{resolved}.{member}"
                if member != "*" and self.local(child) is not None:
                    self.dependencies.add(child)
                    self.inspect(child)
        parts = name.split(".")
        for length in range(1, len(parts)):
            self.inspect(".".join(parts[:length]))

    def protects(self) -> None:
        self.inspect("des.domain.oracle_observation")
        require(
            "des.domain.oracle_observation" in self.visited and bool(self.dependencies),
            f"decoder dependency population was never inspected: {self.visited}",
            "read the decoder and every reachable ordinary project module before claiming absence",
        )
        runtime = set((self.root / "src/des").rglob("*.py"))
        require(
            bool(runtime),
            "DES runtime source population is absent",
            "inspect the actual candidate runtime rather than an empty directory",
        )
        for source in runtime:
            imports = OrdinaryImports()
            imports.visit(ast.parse(source.read_text(), filename=str(source)))
            for module, _, members in imports.imports:
                require(
                    module.split(".")[0] != "tests"
                    and "native_observer" not in module.split(".")
                    and "native_observer" not in members,
                    f"DES runtime imports candidate reporter/test support in {source}: {module}/{members}",
                    "leave target-native producer interpretation outside DES runtime",
                )
            # Literal dynamic imports are dependencies too, not ordinary prose.
            for node in ast.walk(ast.parse(source.read_text())):
                if (
                    isinstance(node, ast.Call)
                    and node.args
                    and (
                        (
                            isinstance(node.func, ast.Name)
                            and node.func.id == "__import__"
                        )
                        or (
                            isinstance(node.func, ast.Attribute)
                            and node.func.attr == "import_module"
                        )
                    )
                ):
                    argument = node.args[0]
                    if isinstance(argument, ast.Constant) and isinstance(
                        argument.value, str
                    ):
                        require(
                            not argument.value.startswith("tests.")
                            and "native_observer" not in argument.value,
                            f"runtime dynamically imports candidate support in {source}: {argument.value}",
                            "keep the candidate reporter loaded only by the target-native runner",
                        )


def test_neutral_decoder_dependency_closure_excludes_target_reporters_and_runtime_layers():
    NeutralDependencyContract(ROOT).protects()


@pytest.mark.parametrize(
    "dependency",
    [
        "des.application.forbidden",
        "foreign_native_tool",
        "missing_module",
        "json.missing_native_module",
    ],
    ids=[
        "transitive-runtime-layer",
        "target-tool-package",
        "unresolved-module",
        "unresolved-stdlib-member",
    ],
)
def test_unresolvable_or_forbidden_dependency_cannot_be_an_empty_architecture_pass(
    tmp_path, dependency
):
    assert_dependency_analysis_refuses(tmp_path, dependency)


def assert_dependency_analysis_refuses(workspace: Path, dependency: str) -> None:
    # This negative population exercises the checker, not a substitute product.
    sources = {
        "src/des/__init__.py": "",
        "src/des/domain/__init__.py": "",
        "src/des/domain/oracle_observation.py": "from . import future_member\n",
        "src/des/domain/future_member.py": f"import {dependency}\n",
        "src/des/application/__init__.py": "",
        "src/des/application/forbidden.py": "import json\n",
    }
    for name, text in sources.items():
        path = workspace / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    try:
        NeutralDependencyContract(workspace).protects()
    except AssertionError as error:
        require(
            "WHAT:" in str(error)
            and ("dependency" in str(error) or "forbidden" in str(error)),
            f"dependency refusal was not attributable: {error}",
            "report the inspected forbidden/unresolved dependency rather than an incidental fixture failure",
        )
        return
    require(
        False,
        f"unsupported/forbidden dependency {dependency} was accepted as empty",
        "refuse an incapable analysis distinctly from the actual standard-library-only closure",
    )
