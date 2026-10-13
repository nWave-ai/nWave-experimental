"""Recorded native assertion RED versus startup refusal through the real DES port.

@contract-shape: real-io
@walking_skeleton @driving_port
Runtime witnesses refine capture/classify/_record_oracle_witness; no formal
claim extends to external reporter truthfulness or filesystem atomicity.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.common.in_process_cli import run_cli_in_process
from tests.des._helpers.host_facts import supplied_arguments
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    base_repository,
    block,
    git,
    hermetic_environment,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_an_absent_junit_report_is_broken import (
    design_facts,
)


SUPPORTS = Path(__file__).parent
ORACLE = "tests/acceptance/native_oracle.test.mjs"
REPORTER = "tests/acceptance/native_observer.mjs"
PYTHON = Path(sys.executable).absolute()
DES = Path(sys.executable).parent / "des"
MARKER = "DES-ORACLE-OBSERVATION: "
REQUEST = "Record real native assertion failures separately from setup failures"


class NativeCase(Enum):
    ASSERTION = "assertion"
    SETUP = "setup"
    REPORT = "report"


@dataclass(frozen=True)
class MeasuredOutcome:
    terminal: str
    stderr: str
    code: int
    witness: dict
    execution: dict


def require(condition: bool, what: str, how: str) -> None:
    assert condition, (
        f"WHAT: {what}; WHY: native oracle evidence must preserve assertion/setup meaning; HOW: {how}"
    )


class NativeOracleJourney:
    """Existing public fixture constructors plus the real oracle terminal and Git witness."""

    def __init__(self, workspace: Path, *, subprocess_port: bool = False):
        self.workspace = workspace
        self.root = base_repository(workspace / "root")
        self.subprocess_port = subprocess_port
        node = shutil.which("node")
        require(
            node is not None,
            "native Node tooling is unavailable",
            "provide the declared Node acceptance runtime",
        )
        self.node = str(Path(node).resolve())
        home = workspace / "home"
        home.mkdir()
        self.environment = hermetic_environment(
            {
                "PATH": os.pathsep.join(
                    dict.fromkeys(
                        [
                            str(Path(self.node).parent),
                            str(DES.parent),
                            "/usr/bin",
                            "/bin",
                        ]
                    )
                ),
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / "config"),
                "XDG_CACHE_HOME": str(home / "cache"),
                "XDG_DATA_HOME": str(home / "data"),
                "PYTHONPATH": str(ROOT / "src"),
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            },
            workspace / "claude",
        )

    def capture_native_events(self, programs: dict[str, str]) -> dict[str, list[dict]]:
        """Inspect actual runner metadata, independently of the candidate reducer."""
        probe = self.workspace / "native-event-probe"
        probe.mkdir()
        observer = probe / "events.mjs"
        observer.write_text(
            "export default async function* events(source) {\n"
            "  for await (const event of source) {\n"
            "    yield JSON.stringify(event, (key, value) => value instanceof Error "
            "? Object.fromEntries(Object.getOwnPropertyNames(value).map("
            "name => [name, value[name]])) : value) + '\\n';\n"
            "  }\n"
            "}\n"
        )
        captured = {}
        for label, body in programs.items():
            source = probe / f"{label}.test.mjs"
            source.write_text(body)
            run = subprocess.run(
                [self.node, "--test", f"--test-reporter={observer}", str(source)],
                cwd=probe,
                env=self.environment,
                text=True,
                capture_output=True,
                timeout=30,
            )
            require(
                run.returncode in {0, 1},
                f"native metadata probe could not run: {run.stderr}",
                "provide Node 24 and execute authentic node:test callbacks",
            )
            captured[label] = [json.loads(line) for line in run.stdout.splitlines()]
            require(
                bool(captured[label]),
                f"native metadata probe returned no events for {label}",
                "capture real runner payloads, not an empty unsupported analysis",
            )
            print(f"NATIVE-EVENTS {label}: {run.stdout}", flush=True)
        return captured

    def inspect_declaration_provenance(self) -> None:
        imports = "import {test,describe} from 'node:test'; import assert from 'node:assert/strict';\n"
        programs = {
            "empty": "export const moduleLoaded = true;\n",
            "top-level": imports
            + "test('native_oracle.test.mjs',()=>assert.equal(1,1));",
            "nested": imports
            + "describe('suite',()=>test('child',()=>assert.equal(1,1)));",
            "skip": imports
            + "test('skip',{skip:true},()=>assert.fail('not executed'));",
            "todo": imports + "test('todo',{todo:true},()=>{});",
            "failure": imports + "test('failure',()=>assert.equal(0,1));",
            "setup": "import './missing-native-dependency.mjs';",
        }
        captured = self.capture_native_events(programs)
        passes = {
            label: [event["data"] for event in events if event["type"] == "test:pass"]
            for label, events in captured.items()
        }
        require(
            bool(passes["empty"])
            and all("entryFile" not in data for data in passes["empty"]),
            f"no-test native wrapper provenance differs: {passes['empty']}",
            "return the changed native schema to DESIGN instead of assuming its discriminator",
        )
        for label in ("top-level", "nested"):
            genuine = [
                data
                for data in passes[label]
                if data.get("details", {}).get("type") == "test"
            ]
            require(
                bool(genuine)
                and all(isinstance(data.get("entryFile"), str) for data in genuine),
                f"declared {label} tests lack native declaration provenance: {passes[label]}",
                "preserve legitimate top-level and nested tests or return unsupported metadata to DESIGN",
            )
        require(
            any(
                data.get("details", {}).get("type") == "suite"
                for data in passes["nested"]
            ),
            f"nested suite lacks its native container tag: {passes['nested']}",
            "use the actual suite discriminator rather than names or source locations",
        )
        require(
            any(data.get("skip") for data in passes["skip"])
            and any(data.get("todo") for data in passes["todo"]),
            f"native skip/todo tags unavailable: {passes}",
            "return unsupported native metadata to DESIGN before selecting a population",
        )
        for label in ("failure", "setup"):
            require(
                any(event["type"] == "test:fail" for event in captured[label]),
                f"real {label} emitted no failure payload: {captured[label]}",
                "inspect authentic assertion and setup failure callbacks, not diagnostic prose",
            )

    def invoke(self, arguments: list[str], *, answers=None, stdin=""):
        command, body = supplied_arguments(self.root, arguments, answers, stdin)
        if not self.subprocess_port:
            return run_cli_in_process(
                command,
                cwd=self.root,
                env=self.environment,
                stdin_text=body,
                catch_all=True,
            )
        result = subprocess.run(
            [str(DES), *command],
            cwd=self.root,
            env=self.environment,
            input=body,
            text=True,
            capture_output=True,
            timeout=90,
        )
        require(
            f"package={ROOT / 'src' / 'des'}" in result.stderr,
            f"DES subprocess did not attest the lane runtime: {result.stderr}",
            "select the declared interpreter and lane PYTHONPATH",
        )
        return result.returncode, result.stdout, result.stderr

    def measure(
        self,
        case: NativeCase,
        *,
        body: str | None = None,
        reporter: str | None = None,
        argv: list[str] | None = None,
        companion_files: dict[str, str] | None = None,
    ) -> MeasuredOutcome:
        oracle = ORACLE
        source = (
            "native_assertion_failure.test.mjs"
            if case is NativeCase.ASSERTION
            else "native_setup_failure.test.mjs"
        )
        body = body if body is not None else (SUPPORTS / source).read_text()
        reporter = (
            reporter
            if reporter is not None
            else (SUPPORTS / "native_observer.mjs").read_text()
        )
        if case is NativeCase.REPORT:
            oracle = "tests/acceptance/test_native_value.py"
            body = "def test_promised_value():\n    assert 0 == 1\n"
            argv = [
                str(PYTHON),
                "-m",
                "pytest",
                oracle,
                "-q",
                "--junitxml=actual-report.xml",
            ]
        argv = (
            argv
            if argv is not None
            else [self.node, "--test", f"--test-reporter=./{REPORTER}", oracle]
        )
        facts = design_facts([argv])
        facts["structured_output"]["manifest"].update(
            oracle=oracle, acceptance_supports=[REPORTER, *(companion_files or {})]
        )
        for args, answers, stdin in (
            (
                ["po", "--project", "--repo-root", str(self.root)],
                [accepted_values("native measurement")],
                REQUEST,
            ),
            (["design", "--repo-root", str(self.root), "--value", "1"], [facts], ""),
        ):
            code, out, err = self.invoke(args, answers=answers, stdin=stdin)
            require(
                code == 0,
                f"public fixture binding failed: {out}{err}",
                "repair the public fixture envelope before measuring",
            )
        for name, text in {
            oracle: body,
            REPORTER: reporter,
            **(companion_files or {}),
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        code, out, err = self.invoke(
            ["oracle", "--repo-root", str(self.root), "--value", "1", "--input", "-"],
            stdin=json.dumps(
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "measure the authored native oracle",
                    }
                }
            ),
        )
        print(out, end="")
        print(err, end="", file=sys.stderr)
        # The producer record is read from DES-retained actual process evidence,
        # never by re-reading the fixture body or constructing its expected output.
        records = []
        for path in (self.root / ".nwave/des/logs/native").glob("oracle-*.json"):
            try:
                payload = json.loads(path.read_text())
            except (ValueError, OSError):
                continue

            def collect(value):
                if isinstance(value, dict):
                    if "argv" in value and "stdout" in value and "stderr" in value:
                        records.append(value)
                    for child in value.values():
                        collect(child)
                elif isinstance(value, list):
                    for child in value:
                        collect(child)

            collect(payload)
        executions = [row for row in records if list(row["argv"]) == argv]
        require(
            bool(executions),
            f"DES lost actual native execution for {argv}",
            "retain argv, exit, completion and both channels before refusal",
        )
        execution = executions[-1]
        require(
            execution.get("incomplete") is False,
            f"native process did not complete: {execution}",
            "retain measured completion rather than trusting a printed record",
        )
        require(
            execution.get("cwd") == str(self.root),
            f"native execution ran outside its declared target: {execution}",
            "execute the vector from the bound target checkout",
        )
        histories = []
        for ref in git(
            self.root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
        ).splitlines():
            message = git(self.root, "show", "-s", "--format=%B", ref)
            subject, _, payload = message.partition("\n\n")
            if subject == "nwave witness: oracle":
                histories.extend(json.loads(payload))
        require(
            bool(histories),
            f"DES emitted an outcome but retained no bound witness: {out}{err}",
            "append the executed witness before returning a refusal without completing the refused turn",
        )
        require(
            len(histories) == 1,
            f"one invocation produced {len(histories)} witness entries: {histories}",
            "append exactly once for this isolated one-invocation population",
        )
        witness = histories[0]
        require(
            all(
                witness.get(key)
                for key in ("revision", "design_sections", "acceptance_tree")
            ),
            f"unbound retained witness: {witness}",
            "retain the selected revision, DESIGN identity and acceptance tree",
        )
        rows = witness["oracles"]
        require(
            [row["oracle"] for row in rows] == [oracle],
            f"witness population differs from selected oracle {oracle}: {rows}",
            "bind exactly the selected oracle population",
        )
        require(
            rows[0]["exit"] == execution["exit"],
            f"witness exit differs from actual invocation: {rows[0]} versus {execution}",
            "retain the same captured invocation in the witness",
        )
        require(
            f"verdict={rows[0]['verdict']}" in block(out, err).get("ORACLE-RED", ""),
            f"terminal disagrees with bound witness: {out}{err}",
            "render the measured verdict without reclassifying exit status",
        )
        if code != 0:
            refs = git(
                self.root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns"
            ).splitlines()
            require(
                not any(ref.endswith("/oracle") for ref in refs),
                f"refused oracle was marked completed: {refs}",
                "retain its witness without completing its unsuccessful turn",
            )
        print(f"RETAINED-WITNESS: verdict={rows[0]['verdict']}")
        return MeasuredOutcome(out, err, code, rows[0], execution)

    def protects(self, case: NativeCase) -> None:
        result = self.measure(case)
        self.assert_outcome(result, case)

    def assert_outcome(self, result: MeasuredOutcome, case: NativeCase) -> None:
        expected = "red" if case is not NativeCase.SETUP else "broken"
        row = result.witness
        require(
            row["verdict"] == expected,
            f"expected {expected}, retained {row}",
            "classify completed assertion evidence as RED and positively observed setup as broken",
        )
        require(
            f"verdict={expected}"
            in block(result.terminal, result.stderr).get("ORACLE-RED", ""),
            f"terminal disagrees with retained {expected}: {result.terminal}{result.stderr}",
            "project the same measured verdict to the terminal",
        )
        require(
            row["exit"] == 1,
            f"same-exit control did not exit 1: {row}",
            "retain the actual native process exit",
        )
        if case is not NativeCase.REPORT:
            terminal = [
                line
                for line in result.execution["stdout"].splitlines()
                if line.startswith(MARKER)
            ]
            require(
                len(terminal) == 1,
                f"completed native record population is {terminal}",
                "emit exactly one terminal record after native events finish",
            )
            counts = json.loads(terminal[0][len(MARKER) :])
            expected_counts = {
                "version": 1,
                "observed": int(case is NativeCase.ASSERTION),
                "assertions_failed": int(case is NativeCase.ASSERTION),
                "setup_failed": int(case is NativeCase.SETUP),
            }
            require(
                counts == expected_counts,
                f"actual native counts {counts}, expected {expected_counts}",
                "derive counts from real assertion/setup callbacks",
            )
            require(
                not list(self.root.rglob("*.xml")),
                "native target unexpectedly required a report",
                "measure native evidence without JUnit instrumentation",
            )
        else:
            require(
                (self.root / "actual-report.xml").is_file(),
                "actual report-backed assertion report is missing",
                "preserve fresh native runner report capture",
            )

    @staticmethod
    def walking_skeleton(workspace: Path, *, report_completion: bool = False) -> None:
        """Report completed journey evaluations, never inner target assertions."""
        failures = []
        observed = 0
        setup_failed = 0
        try:
            for case in NativeCase:
                journey = NativeOracleJourney(
                    workspace / case.value, subprocess_port=True
                )
                try:
                    journey.protects(case)
                except AssertionError as error:
                    failures.append(str(error))
                observed += 1
        except Exception:
            setup_failed += 1
            raise
        finally:
            if report_completion:
                print(
                    MARKER
                    + json.dumps(
                        {
                            "version": 1,
                            "observed": observed,
                            "assertions_failed": len(failures),
                            "setup_failed": setup_failed,
                        }
                    ),
                    flush=True,
                )
        require(
            not failures,
            " | ".join(failures),
            "implement the declared neutral observation and witness-before-refusal chain",
        )


def test_native_assertion_red_is_distinct_from_setup_and_preserves_report_red(tmp_path):
    NativeOracleJourney.walking_skeleton(tmp_path)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="native-oracle-") as directory:
        NativeOracleJourney.walking_skeleton(Path(directory), report_completion=True)
