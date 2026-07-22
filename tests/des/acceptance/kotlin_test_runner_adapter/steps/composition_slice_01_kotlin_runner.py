"""Composition root for kotlin-test-runner-adapter slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
production slice-01 SUTs imported + invoked in a CHILD interpreter. The SUTs are
the net-new production seams the feature ships (mirroring go-test-runner-adapter
+ the pytest/cargo AT-discovery facet pair):

  1. the Kotlin run-facet ``run_kotlin_scope`` (kotlin_runner.py) -- resolves the
     target's ``gradlew`` via the shared resolve_tool scale, shells the declared
     ``gradlew test`` command over a real subprocess, and maps the exit code to
     PASS / FAIL / INDETERMINATE.
  2. the Kotlin AT-discovery facet ``discover_kotlin_ats`` (kotlin_runner.py) --
     discovers @Test-annotated ``fun`` identities a Kotlin regression file
     carries, mirroring ``discover_pytest_ats`` / ``discover_cargo_ats``.
  3. the routing registry ``resolve`` (test_runner_port.py) -- the
     build.gradle.kts / build.gradle -> gradle-test row this feature adds
     directly (a small routing-table addition, LIVE-GREEN at HEAD, unlike 1/2
     which are RED until DELIVER ships kotlin_runner.py).

WHY a child interpreter (not a thin in-process call): at HEAD ``kotlin_runner``
does not exist (Tsunami: kotlin_runner.py absent). Importing it in THIS process
would raise ModuleNotFoundError at COLLECTION -> a BROKEN test, not active-RED.
Running the import in a child ``python -c`` makes the absent module a CAPTURED
observable (child rc != 0, no marker) that each Then turns into a SEMANTIC
AssertionError. Same pattern as go-test-runner-adapter.

ZERO ``des.adapters.*`` import in THIS process: the SUT is only ever imported in
the CHILD interpreter, never here.

FAKE-gradlew determinism (AC-1/2/3 -- explicit fixture approach, mirrors go): the
exit-semantics ATs do NOT require a real Gradle/JDK toolchain (absent in CI). The
fixture plants a REAL chmod+x ``gradlew`` script on a controlled child PATH that
emits a controlled exit code:
  - GREEN -> exit 0 (all pass)                  -> PASS verdict.
  - RED   -> emit test output, then exit 1      -> FAIL verdict (propagated, NOT
             swallowed into INDETERMINATE).
The run-facet resolves this fake gradlew via the shared ``resolve_tool`` scale
(PATH rung) and shells it exactly like a real gradlew.

AC-3 (gradlew-unresolvable) drives ``run_kotlin_scope`` over a fixture where
``gradlew`` is absent everywhere (PATH scrubbed to an empty dir, known-locations
real-but-empty) and asserts the LOUD INDETERMINATE via ``resolve_tool``'s named
remediation.

AC-4/AC-5 (AT-discovery) drive ``discover_kotlin_ats`` over a REAL ``.kt``
regression file planted on disk -- a two-@Test fixture (GREEN) and a zero-@Test
fixture (the malformed-file RED partner).

AC-6 (routing) drives the PRODUCTION ``resolve()`` over a REAL target carrying
only a ``build.gradle.kts`` manifest -- this row is authored by THIS feature
directly (not gated behind kotlin_runner.py), so it is LIVE-GREEN at HEAD.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``kotlin_runner`` is
absent, so AC-1..5's child import fails (rc != 0, no marker) and each Then fires
a semantic AssertionError. AC-6 is unaffected (resolve() does not import
kotlin_runner). GREEN once DELIVER ships kotlin_runner.py. No @skip, no
collection / import error in THIS process.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_kotlin_runner import GradleExitScenario, RunnerVerdict


# The production seam the child interpreter imports + invokes (the SUT). Absent
# at HEAD -> the child import raises ModuleNotFoundError THERE (captured
# rc/stderr), never an import error in this test process.
_KOTLIN_RUNNER_MODULE = "des.adapters.driven.runner.kotlin_runner"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The token TestRunnerPort.resolve returns for a build.gradle.kts target
# (test_runner_port.py -- the row this feature adds directly).
_GRADLE_TOKEN = "gradle-test"

# The fake-gradlew binary name the run-facet resolves + shells.
_GRADLEW_NAME = "gradlew"

# The declared feature-scoped test_command tokens passed to the run-facet as the
# per-runner "scope" (NOT a node-id list). The leading token is the binary the
# run-facet resolves; the rest is the subcommand shelled as-is -- the adapter
# does NOT choose the subcommand (the feature declares it, mirroring go D5).
_DECLARED_COMMAND = (_GRADLEW_NAME, "test")

# A Kotlin regression file declaring TWO @Test functions (AC-4's GREEN fixture).
_TWO_AT_KOTLIN_SOURCE = """\
package fixture

import org.junit.jupiter.api.Test

class FixtureRegressionTest {

    @Test
    fun additionIsCommutative() {
        assert(1 + 2 == 2 + 1)
    }

    @Test
    fun subtractionIsNotCommutative() {
        assert(5 - 2 != 2 - 5)
    }

    fun helperNotATest() {
        // not @Test-annotated -- must NOT be discovered
    }
}
"""

_TWO_AT_KOTLIN_EXPECTED_IDS = (
    "additionIsCommutative",
    "subtractionIsNotCommutative",
)

# A Kotlin regression file declaring ZERO @Test functions (AC-5's RED partner --
# the malformed-file fixture, mirroring discover_pytest_ats / discover_cargo_ats'
# zero-tests-found degrade-LOUD row).
_ZERO_AT_KOTLIN_SOURCE = """\
package fixture

class FixtureRegressionTestEmpty {

    fun helperNotATest() {
        // no @Test annotations anywhere in this file
    }
}
"""


@dataclass
class KotlinRunnerComposition:
    """Drives the REAL slice-01 SUTs over a controlled filesystem + FAKE gradlew."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the target tree the run-facet runs gradlew in
    _target_root: Path | None = field(default=None)
    # the controlled child env: PATH carrying (or scrubbed of) the fake gradlew,
    # HOME under the fixture, and the known_locations passed to resolve_tool
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # which exit behaviour the planted fake gradlew exhibits (None = absent)
    _exit_scenario: GradleExitScenario | None = field(default=None)
    # the regression file AC-4/AC-5 discover_kotlin_ats reads
    _regression_file: Path | None = field(default=None)
    # child-interpreter probe results (shared by run-facet + AT-discovery probes)
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-gradlew fixtures) --------------------

    def given_target_with_fake_gradlew(self, scenario: GradleExitScenario) -> None:
        """Plant a REAL chmod+x fake ``gradlew`` exhibiting ``scenario``'s exit code.

        Used by AC-1 (GREEN -> PASS), AC-2 (RED -> FAIL). Mirrors
        go_test_runner_adapter's ``given_target_with_fake_go``.
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        (target / "build.gradle.kts").write_text(
            'plugins { kotlin("jvm") version "1.9.0" }\n', encoding="utf-8"
        )
        self._target_root = target
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_gradlew(path_bin / _GRADLEW_NAME, scenario)
        # the fake gradlew is on PATH (resolve_tool PATH rung); known_locations empty
        self._child_path = str(path_bin)
        self._known_locations = []
        self._exit_scenario = scenario

    def given_target_with_gradlew_absent_everywhere(self) -> None:
        """Fixture for AC-3 (gradlew-unresolvable).

        A real Kotlin/Gradle target tree, but ``gradlew`` exists NOWHERE: PATH is
        an empty dir AND the known_locations dirs are real-but-empty. The
        run-facet's resolve_tool scale exhausts -> the run-facet must degrade
        LOUD to INDETERMINATE naming the remediation (NOT a silent pass, NOT a
        FAIL). Mirrors go's ``given_target_with_go_absent_everywhere``.
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        (target / "build.gradle.kts").write_text(
            'plugins { kotlin("jvm") version "1.9.0" }\n', encoding="utf-8"
        )
        self._target_root = target
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        empty_known = root / "empty-known"
        empty_known.mkdir(parents=True, exist_ok=True)
        self._child_path = str(empty_path)
        self._known_locations = [str(empty_known)]
        self._exit_scenario = None

    def given_kotlin_regression_file_with_two_tests(self) -> None:
        """Plant a REAL ``.kt`` file declaring two @Test functions (AC-4)."""
        root = self._ensure_root()
        self._regression_file = root / "FixtureRegressionTest.kt"
        self._regression_file.write_text(_TWO_AT_KOTLIN_SOURCE, encoding="utf-8")

    def given_kotlin_regression_file_with_zero_tests(self) -> None:
        """Plant a REAL ``.kt`` file declaring zero @Test functions (AC-5)."""
        root = self._ensure_root()
        self._regression_file = root / "FixtureRegressionTestEmpty.kt"
        self._regression_file.write_text(_ZERO_AT_KOTLIN_SOURCE, encoding="utf-8")

    def given_target_with_only_build_gradle_kts(self) -> None:
        """Plant a REAL target carrying ONLY a ``build.gradle.kts`` manifest (AC-6)."""
        root = self._ensure_root()
        target = root / "gradle-only-target"
        target.mkdir(parents=True, exist_ok=True)
        (target / "build.gradle.kts").write_text(
            'plugins { kotlin("jvm") version "1.9.0" }\n', encoding="utf-8"
        )
        self._target_root = target

    # ---- when (drive the REAL SUTs in a child interpreter) ------------------

    def when_the_run_facet_runs_the_command(self) -> None:
        """Invoke the REAL ``run_kotlin_scope`` over the fixture in a child.

        Mirrors go's ``when_the_run_facet_runs_the_command``. The child imports
        kotlin_runner + the port, builds a ``RunnerAdapter(name="gradle-test")``,
        and calls ``run_kotlin_scope(adapter, target_root, declared_command)``.
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(_DECLARED_COMMAND)!r}\n"
            f"runner_mod = importlib.import_module({_KOTLIN_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_GRADLE_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = runner_mod.run_kotlin_scope(\n"
            "        adapter, pathlib.Path(target_root), command)\n"
            "except unavailable as exc:\n"
            "    print('VERDICT:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('VERDICT:' + ('PASS' if verdict.passed else 'FAIL'))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(
            program, path=self._child_path
        )

    def when_the_at_discovery_facet_discovers_ats(self) -> None:
        """Invoke the REAL ``discover_kotlin_ats`` over the regression file.

        Mirrors ``discover_pytest_ats`` / ``discover_cargo_ats``'s driving
        pattern: the child imports kotlin_runner + the port, builds a
        ``RunnerAdapter(name="gradle-test")``, and calls
        ``discover_kotlin_ats(adapter, target_root, regression_test_file)``.
        """
        program = (
            "import importlib, pathlib\n"
            f"regression_file = {str(self._regression_file)!r}\n"
            f"runner_mod = importlib.import_module({_KOTLIN_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_GRADLE_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    result = runner_mod.discover_kotlin_ats(\n"
            "        adapter, pathlib.Path('.'), pathlib.Path(regression_file))\n"
            "except unavailable as exc:\n"
            "    print('DISCOVERY:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('DISCOVERY:AT_IDS:' + ','.join(result.at_ids))\n"
            "    print('DISCOVERY:HASH:' + result.content_hash)\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    def when_the_target_runner_is_resolved(self) -> None:
        """Invoke the REAL production ``resolve()`` over the AC-6 fixture.

        Unlike the run-facet / AT-discovery probes, this drives ONLY the
        routing registry (test_runner_port.resolve) -- it never imports
        kotlin_runner, so it is LIVE-GREEN at HEAD (the resolve() row is
        authored by THIS feature directly).
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            "result = port.resolve(pathlib.Path(target_root))\n"
            "if isinstance(result, port.RunnerAdapter):\n"
            "    print('RESOLVED:' + result.name)\n"
            "else:\n"
            "    print('UNRECOGNIZED:' + str(result.reason))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the SUT OUTCOME -- the port-exposed observable) ----

    def then_the_verdict_is(self, expected: RunnerVerdict) -> None:
        """The run-facet mapped the gradlew exit code to ``expected`` verdict.

        Used by AC-1 (PASS), AC-2 (FAIL), and AC-3 (INDETERMINATE
        gradlew-unresolvable). Mirrors go's ``then_the_verdict_is``.

        Active-RED at HEAD: kotlin_runner is absent, the child import fails
        (rc != 0, no ``VERDICT:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the Kotlin run-facet must run the declared command and map the "
            f"exit code to the {expected.name} verdict; at HEAD "
            f"{_KOTLIN_RUNNER_MODULE} is absent so the child probe could not "
            f"produce a verdict. {self._probe_observed()}"
        )
        marker = self._probe_out.split("VERDICT:", 1)[1].strip().splitlines()[0]
        observed = marker.split(":", 1)[0]  # PASS | FAIL | INDETERMINATE
        assert observed == expected.name, (
            f"the Kotlin run-facet mapped the {self._exit_scenario} fixture to "
            f"the WRONG verdict: expected {expected.name}, got {observed!r} "
            f"(marker={marker!r}). exit 0 -> PASS, non-zero-with-tests -> FAIL "
            f"(propagated, NOT indeterminate), gradlew-absent -> INDETERMINATE. "
            f"{self._probe_observed()}"
        )

    def then_the_indeterminate_names_the_remediation(self) -> None:
        """The gradlew-unresolvable INDETERMINATE carries an actionable remediation.

        Used by AC-3. Mirrors go's
        ``then_the_indeterminate_names_the_remediation``.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:``
        marker -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:INDETERMINATE:" in self._probe_out, (
            "an unresolvable gradlew (absent after the full discovery scale) "
            "must yield a LOUD INDETERMINATE naming the remediation (never a "
            f"silent degrade, never a FAIL); at HEAD {_KOTLIN_RUNNER_MODULE} is "
            f"absent so the child probe could not produce it. "
            f"{self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("VERDICT:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        lowered = reason.lower()
        assert any(token in lowered for token in ("install", "gradle", "gradlew")), (
            "the INDETERMINATE reason must NAME an actionable install path "
            "(e.g. 'install gradlew' / 'gradle wrapper') so the operator can "
            f"act -- not a bare failure; got {reason!r}. "
            f"{self._probe_observed()}"
        )

    def then_the_discovered_at_ids_match(self, expected_ids: tuple[str, ...]) -> None:
        """The AT-discovery facet discovered exactly the declared @Test identities.

        Used by AC-4. Mirrors ``discover_pytest_ats`` / ``discover_cargo_ats``'s
        AT-identity observable.

        Active-RED at HEAD: kotlin_runner is absent, the child import fails
        (rc != 0, no ``DISCOVERY:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "DISCOVERY:AT_IDS:" in self._probe_out, (
            f"the Kotlin AT-discovery facet must discover the @Test identities "
            f"a regression file carries; at HEAD {_KOTLIN_RUNNER_MODULE} is "
            f"absent so the child probe could not produce a discovery result. "
            f"{self._probe_observed()}"
        )
        line = next(
            ln
            for ln in self._probe_out.splitlines()
            if ln.startswith("DISCOVERY:AT_IDS:")
        )
        observed_ids = tuple(
            token for token in line.split("DISCOVERY:AT_IDS:", 1)[1].split(",") if token
        )
        assert set(observed_ids) == set(expected_ids), (
            "the Kotlin AT-discovery facet must discover EXACTLY the "
            f"@Test-annotated functions declared in the regression file: "
            f"expected {sorted(expected_ids)}, got {sorted(observed_ids)}. "
            f"{self._probe_observed()}"
        )

    def then_the_discovery_carries_a_content_seal(self) -> None:
        """The AT-discovery result carries a sha256 seal over the file's raw bytes.

        Used by AC-4. The content_hash must equal sha256 of the EXACT bytes on
        disk (no read-time-of-check/read-time-of-use gap), mirroring
        ``discover_pytest_ats`` / ``discover_cargo_ats``.
        """
        import hashlib

        assert self._regression_file is not None, "no regression file was planted"
        expected_hash = hashlib.sha256(self._regression_file.read_bytes()).hexdigest()
        assert self._probe_rc == 0 and "DISCOVERY:HASH:" in self._probe_out, (
            "the Kotlin AT-discovery facet must return a content_hash seal; at "
            f"HEAD {_KOTLIN_RUNNER_MODULE} is absent so no seal was produced. "
            f"{self._probe_observed()}"
        )
        line = next(
            ln
            for ln in self._probe_out.splitlines()
            if ln.startswith("DISCOVERY:HASH:")
        )
        observed_hash = line.split("DISCOVERY:HASH:", 1)[1].strip()
        assert observed_hash == expected_hash, (
            "the Kotlin AT-discovery facet's content_hash must be the sha256 "
            f"of the regression file's raw bytes: expected {expected_hash!r}, "
            f"got {observed_hash!r}. {self._probe_observed()}"
        )

    def then_the_discovery_degrades_loud_naming_the_malformed_file(self) -> None:
        """discover_kotlin_ats degrades LOUD when zero @Test functions are found.

        Used by AC-5 -- the malformed-file partner of AC-4, mirroring
        ``discover_pytest_ats`` / ``discover_cargo_ats``'s zero-tests-found
        degrade-LOUD row (never a silently-empty discovery).
        """
        assert self._probe_rc == 0 and "DISCOVERY:INDETERMINATE:" in self._probe_out, (
            "a Kotlin regression file with ZERO @Test functions must degrade "
            "LOUD (RunnerAdapterUnavailable), never a silently-empty discovery; "
            f"at HEAD {_KOTLIN_RUNNER_MODULE} is absent so the child probe "
            f"could not produce it. {self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("DISCOVERY:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        assert (
            str(self._regression_file) in reason
            or "0" in reason
            or "zero" in reason.lower()
        ), (
            "the degrade-LOUD reason must name the malformed regression file "
            f"or the zero-@Test condition; got {reason!r}. "
            f"{self._probe_observed()}"
        )

    def then_the_resolved_runner_is(self, expected_runner: str) -> None:
        """The production resolve() registry routes the target to ``expected_runner``.

        Used by AC-6. This is LIVE-GREEN at HEAD -- resolve() never imports
        kotlin_runner, so the AC-6 routing row this feature adds directly is
        exercised end-to-end through the REAL production registry immediately.
        """
        assert self._probe_rc == 0 and "RESOLVED:" in self._probe_out, (
            f"a target carrying only build.gradle.kts must resolve the "
            f"{expected_runner!r} runner via the production registry, not "
            f"degrade unrecognized. {self._probe_observed()}"
        )
        observed = self._probe_out.split("RESOLVED:", 1)[1].strip().splitlines()[0]
        assert observed == expected_runner, (
            f"the build.gradle.kts routing row must resolve {expected_runner!r}, "
            f"got {observed!r}. {self._probe_observed()}"
        )

    # ---- real-fixture helpers ------------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-kotlin-runner-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_gradlew(target: Path, scenario: GradleExitScenario) -> Path:
        """Write a REAL chmod+x fake ``gradlew`` exhibiting ``scenario``'s exit code.

        A POSIX shell script (the run-facet shells it like a real gradlew). It
        does NOT interpret its argv -- the fixture controls the exit code
        deterministically, independent of a real Gradle/JDK toolchain. Mirrors
        go_test_runner_adapter's ``_plant_fake_go`` (minus the argv-record file,
        not needed by this feature's ACs).
        """
        exit_code = {GradleExitScenario.GREEN: 0, GradleExitScenario.RED: 1}[scenario]
        summary = {
            GradleExitScenario.GREEN: "echo 'BUILD SUCCESSFUL'",
            GradleExitScenario.RED: (
                "echo 'FixtureRegressionTest > additionIsCommutative FAILED'\n"
                "echo 'BUILD FAILED'"
            ),
        }[scenario]
        script = f"#!/bin/sh\n{summary}\nexit {exit_code}\n"
        target.write_text(script, encoding="utf-8")
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    # ---- driving-port invocation (Layer 3 subprocess) ------------------------

    def _run_python_c(
        self, program: str, path: str | None = None
    ) -> tuple[int, str, str]:
        """Run a one-shot ``python -c`` probe in a child interpreter.

        HERMETIC env when ``path`` is given (the run-facet probes): PATH is set
        to ONLY the fixture's controlled dir (so the run-facet resolves the FAKE
        gradlew, never an ambient host gradlew/gradle, and the
        gradlew-absent fixture genuinely finds nothing). HOME is the fixture's
        tmp home. When ``path`` is None (the AT-discovery + routing probes,
        which never shell a binary) the ambient PATH is left untouched.
        ``src`` is prepended to PYTHONPATH so the in-tree ``des`` package is
        importable.
        """
        env = dict(os.environ)
        if path is not None:
            env["PATH"] = path
            env["HOME"] = self._child_home
        root = _repo_root()
        src = str(root / "src")
        existing = env.get("PYTHONPATH", "")
        prepend = src + os.pathsep + str(root)
        env["PYTHONPATH"] = prepend + os.pathsep + existing if existing else prepend
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        return completed.returncode, completed.stdout, completed.stderr

    # ---- diagnostics -----------------------------------------------------

    def _probe_observed(self) -> str:
        return (
            f"probe_rc={self._probe_rc!r}; "
            f"exit_scenario={self._exit_scenario!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"regression_file={str(self._regression_file)!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/kotlin_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=kotlin_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]


__all__ = [
    "_TWO_AT_KOTLIN_EXPECTED_IDS",
    "KotlinRunnerComposition",
]
