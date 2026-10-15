"""Successful startup is not an observed oracle outcome.

@contract-shape: real-io @driving_port
Extends the native assertion/setup feature journey through the existing public
oracle command. Capture/classify and the bound witness are observed, not mocked.
External reporter honesty and filesystem atomicity remain trust boundaries.
"""

from __future__ import annotations

import json
import sys
import tempfile
from enum import Enum
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.des.acceptance.steps_for_the_orchestrator.test_native_assertion_failure_is_measured_red import (
    MARKER,
    ORACLE,
    PYTHON,
    REPORTER,
    NativeCase,
    NativeOracleJourney,
)


class ObservationCase(Enum):
    ABSENT = "skipped-without-record"
    ZERO = "skipped-with-current-reporter"
    REPORT = "fresh-zero-test-report"
    PASSED = "completed-passing-assertion"
    NO_TEST = "successful-file-with-no-declared-test"
    EMPTY_SUITE = "empty-suite-without-observation"
    TODO = "todo-without-observation"
    NESTED_PASSED = "nested-completed-passing-assertion"
    ASSERTION = "genuine-failing-assertion-without-junit"
    NESTED_ASSERTION = "nested-failure-without-aggregate-double-count"
    SETUP = "missing-native-dependency"
    SETUP_AFTER_PASS = "runtime-setup-failure-after-completed-pass"


def require(condition: bool, what: str, how: str) -> None:
    assert condition, (
        f"WHAT: {what}; WHY: exit0 alone cannot establish an observed oracle "
        f"outcome; HOW: {how}"
    )


class ObservationJourney:
    def __init__(self, workspace: Path, *, subprocess_port: bool = False):
        self.native = NativeOracleJourney(workspace, subprocess_port=subprocess_port)

    def protects(self, case: ObservationCase) -> None:
        native = self.native
        if case in {ObservationCase.ASSERTION, ObservationCase.SETUP}:
            native.protects(
                NativeCase.ASSERTION
                if case is ObservationCase.ASSERTION
                else NativeCase.SETUP
            )
            return
        if case is ObservationCase.NESTED_ASSERTION:
            result = native.measure(
                NativeCase.ASSERTION,
                body=(
                    "import {test,describe} from 'node:test'; import assert from 'node:assert/strict';\n"
                    "describe('container',()=>describe('nested',()=>test('value',()=>assert.equal(0,1))));\n"
                ),
            )
            native.assert_outcome(result, NativeCase.ASSERTION)
            return
        if case is ObservationCase.SETUP_AFTER_PASS:
            result = native.measure(
                NativeCase.SETUP,
                body=(
                    "import test from 'node:test'; import assert from 'node:assert/strict';\n"
                    "await test('completed value',()=>assert.equal(1,1));\n"
                    "await test('runtime setup',()=>{throw new Error('setup unavailable');});\n"
                ),
            )
            require(
                result.witness["verdict"] == "broken" and result.execution["exit"] == 1,
                f"setup after pass was promoted: {result.witness}",
                "preserve setup precedence even after genuine completed observations",
            )
            records = [
                line
                for line in result.execution["stdout"].splitlines()
                if line.startswith(MARKER)
            ]
            require(
                len(records) == 1
                and json.loads(records[0][len(MARKER) :])
                == {
                    "version": 1,
                    "observed": 1,
                    "assertions_failed": 0,
                    "setup_failed": 1,
                },
                f"setup after completed pass lost native counts: {records}",
                "count the completed assertion and authentic runtime failure separately",
            )
            require(
                not list(native.root.rglob("*.xml")),
                "setup control unexpectedly produced XML",
                "retain native setup evidence without requiring JUnit",
            )
            return
        body = (
            "import test from 'node:test';\n"
            "import assert from 'node:assert/strict';\n"
            "test('promised observation', {skip: true}, () => assert.equal(0, 1));\n"
        )
        argv = [native.node, "--test", f"--test-reporter=./{REPORTER}", ORACLE]
        if case is ObservationCase.ABSENT:
            argv = [native.node, "--test", "--test-reporter=tap", ORACLE]
        if case is ObservationCase.NO_TEST:
            body = "export const moduleLoaded = true;\n"
        if case is ObservationCase.EMPTY_SUITE:
            body = "import {describe} from 'node:test'; describe('empty container',()=>{});\n"
        if case is ObservationCase.TODO:
            body = "import test from 'node:test'; test('pending observation',{todo:true},()=>{});\n"
        if case in {ObservationCase.PASSED, ObservationCase.NESTED_PASSED}:
            body = (
                "import test from 'node:test';\n"
                "import assert from 'node:assert/strict';\n"
                "test('promised observation', () => assert.equal(1, 1));\n"
            )
            if case is ObservationCase.NESTED_PASSED:
                body = (
                    "import {test,describe} from 'node:test'; import assert from 'node:assert/strict';\n"
                    "describe('container',()=>test('native_oracle.test.mjs',()=>assert.equal(1,1)));\n"
                )
        if case is ObservationCase.REPORT:
            # Genuine empty discovery, not test-authored XML. Only the actual
            # no-tests exit is mapped to zero; missing tooling stays nonzero.
            body = (
                "import {mkdirSync} from 'node:fs';\n"
                "import {spawnSync} from 'node:child_process';\n"
                "mkdirSync('empty-discovery', {recursive: true});\n"
                f"const run = spawnSync({json.dumps(str(PYTHON))}, "
                "['-m', 'pytest', 'empty-discovery', '-q', "
                "'--junitxml=actual-report.xml'], {encoding: 'utf8'});\n"
                "process.stdout.write(run.stdout ?? '');\n"
                "process.stderr.write(run.stderr ?? '');\n"
                "process.stdout.write('EMPTY-DISCOVERY-EXIT: ' + run.status + '\\n');\n"
                "process.exit(run.status === 5 ? 0 : (run.status ?? 127));\n"
            )
            argv = [native.node, ORACLE, "--junitxml=actual-report.xml"]
        result = native.measure(NativeCase.ASSERTION, body=body, argv=argv)
        row = result.witness
        require(
            row["exit"] == 0 and result.execution["exit"] == 0,
            f"{case.value} did not actually exit0: {row}",
            "execute the declared native recipe and retain its actual exit",
        )
        records = [
            line
            for line in result.execution["stdout"].splitlines()
            if line.startswith(MARKER)
        ]
        if case is ObservationCase.ABSENT:
            require(
                not records
                and "# skipped 1" in result.execution["stdout"]
                and "# pass 0" in result.execution["stdout"],
                f"skipped native body did not produce empty TAP evidence: {result.execution}",
                "execute the skipped Node assertion with the real TAP reporter",
            )
        elif case is ObservationCase.REPORT:
            require(
                not records and "EMPTY-DISCOVERY-EXIT: 5" in result.execution["stdout"],
                f"bridge did not observe genuine empty discovery: {result.execution}",
                "map only pytest's measured no-tests exit5 to bridge exit0",
            )
            require(
                row["counts"] == [0, 0, 0]
                and str(row["axis"]).startswith("junit-report")
                and row["completed"] is True
                and "--junitxml=actual-report.xml" in row["argv"],
                f"retained fresh empty-discovery report observation is wrong: {row}",
                "retain the completed explicit-report invocation's genuine zero-test/zero-error/zero-failure JUnit observation",
            )
            require(
                not (native.root / "actual-report.xml").exists(),
                "empty-discovery reporting created a report in the host workspace",
                "generate the fresh report only in the isolated checkout and retain its observed counts before cleanup",
            )
        else:
            require(
                len(records) == 1,
                f"terminal record population differs: {records}",
                "use the current native reporter after real runner events",
            )
            counts = json.loads(records[0][len(MARKER) :])
            require(
                counts
                == {
                    "version": 1,
                    "observed": int(
                        case in {ObservationCase.PASSED, ObservationCase.NESTED_PASSED}
                    ),
                    "assertions_failed": 0,
                    "setup_failed": 0,
                },
                f"{case.value}: actual current reporter counts differ: {counts}",
                "count genuine top-level/nested assertions, never file wrappers, suites or skip/todo callbacks",
            )
        if case is not ObservationCase.REPORT:
            require(
                not list(native.root.rglob("*.xml")),
                "native target unexpectedly produced a JUnit report",
                "observe native completion without requiring optional reports",
            )
        expected = (
            "green"
            if case in {ObservationCase.PASSED, ObservationCase.NESTED_PASSED}
            else "indeterminate"
        )
        require(
            row["verdict"] == expected,
            f"{case.value}: expected {expected}, DES retained {row}",
            "require positive completed observations for GREEN; retain empty execution as indeterminate",
        )
        if expected != "green":
            axis = (
                "junit-report-no-observation"
                if case is ObservationCase.REPORT
                else "native-observation-no-observation"
            )
            require(
                row["axis"] == axis,
                f"{case.value}: expected no-observation provenance {axis}, retained {row}",
                "retain the source-specific empty-observation axis before refusal",
            )
            require(
                result.code != 0
                and "OracleRedUnobservable" in result.terminal + result.stderr,
                f"empty execution lacked explicit refusal: {result.terminal}{result.stderr}",
                "refuse the unobserved outcome after retaining its bound witness",
            )

    @staticmethod
    def complete(workspace: Path) -> None:
        failures = []
        observed = 0
        setup_failed = 0
        try:
            for case in ObservationCase:
                journey = ObservationJourney(
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
            "correct the candidate native reporter population without losing genuine pass/fail or setup controls",
        )


@pytest.mark.parametrize(
    "case",
    [ObservationCase.ABSENT, ObservationCase.REPORT],
    ids=lambda case: case.value,
)
def test_successful_empty_execution_is_not_an_oracle_outcome(tmp_path, case):
    ObservationJourney(tmp_path).protects(case)


@pytest.mark.parametrize(
    "case",
    [
        case
        for case in ObservationCase
        if case not in {ObservationCase.ABSENT, ObservationCase.REPORT}
    ],
    ids=lambda case: case.value,
)
def test_actual_native_zero_observation_reaches_des_consumer(tmp_path, case):
    ObservationJourney(tmp_path).protects(case)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="observation-outcome-") as directory:
        ObservationJourney.complete(Path(directory))
