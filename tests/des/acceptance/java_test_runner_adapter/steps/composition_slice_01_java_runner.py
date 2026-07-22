"""Composition root for java-test-runner-adapter slice-01 ATs.

TWO driving surfaces, Mandate-13 driving-port-only (Layer 3 subprocess): the
REAL production slice-01 SUT imported + invoked in a CHILD interpreter. The SUT
is the pair of net-new production seams the feature ships in ONE module
(mirrors ``cargo_runner.py``'s run+discover pair):

  the Java run-facet ``run_java_scope`` (java_runner.py) -- mirrors
  ``run_go_scope``/``run_cargo_scope``: resolves the target's ``mvn`` via the
  shared resolve_tool scale, shells the declared ``mvn test`` command over a
  real subprocess at ``cwd=target_root``, and maps the exit code to PASS /
  FAIL / INDETERMINATE.

  the Java AT-discovery facet ``discover_java_ats`` (java_runner.py) --
  mirrors ``discover_pytest_ats``/``discover_cargo_ats``: scans a regression
  file's raw bytes for ``@Test``-attributed method names and returns them
  alongside a sha256 content seal.

WHY a child interpreter (not a thin in-process call): at HEAD ``java_runner``
does not exist (Tsunami: java_runner.py absent). Importing it in THIS process
would raise ModuleNotFoundError at COLLECTION -> a BROKEN test, not
active-RED. Running the import in a child ``python -c`` makes the absent
module a CAPTURED observable (child rc != 0, no ``VERDICT:``/``DISCOVERY:``
marker) that each Then turns into a SEMANTIC AssertionError. Same pattern as
go_test_runner_adapter's harness.

ZERO ``des.adapters.*`` import in THIS process: the SUT is only ever imported
in the CHILD interpreter, never here.

FAKE-mvn determinism (AC-1/2/4 -- explicit fixture approach): the
exit-semantics + declared-command-shelled ATs do NOT require a real
Maven/JDK toolchain (absent in CI). The fixture plants a REAL chmod+x ``mvn``
script on a controlled child PATH that emits a controlled exit code + output
AND records its argv + cwd to a record file:
  - GREEN -> exit 0 (all pass)                  -> PASS verdict.
  - RED   -> emit test output, then exit 1      -> FAIL verdict (propagated,
             NOT swallowed into INDETERMINATE).
The run-facet resolves this fake mvn via the shared ``resolve_tool`` scale
(PATH rung) and shells it exactly like a real mvn -- so the exit-semantics +
the declared-subcommand-at-cwd contract are exercised end-to-end through the
REAL run-facet, deterministically, in CI.

JAVA-vs-cargo: ``mvn test`` exits 0 even with NO test files (like
``go test``) -- there is NO cargo-style exit-4 NO_MATCH empty-scope. So the
planted fake has only GREEN (0) and RED (non-zero) behaviours; there is NO
"mvn ran no tests -> INDETERMINATE" path. INDETERMINATE is reached ONLY by
AC-3's mvn-absent fixture.

AC-3 (mvn-unresolvable) drives ``run_java_scope`` over a fixture where ``mvn``
is absent everywhere (PATH scrubbed to an empty dir, known-locations
real-but-empty) and asserts the LOUD INDETERMINATE via ``resolve_tool``'s
named remediation.

AC-5/6 (AT-discovery) drive ``discover_java_ats`` over a REAL, controlled Java
regression file -- a bare ``@Test`` method plus a ``@Test`` +
``@DisplayName``-annotated method (AC-5, the discovered-identities + real
content-hash contract) and a Java file with ZERO ``@Test`` methods (AC-6, the
degrade-LOUD refusal, mirrors ``discover_cargo_ats``'s zero-#[test] row).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``java_runner`` is
absent, so the child import fails (rc != 0, no marker) and each Then fires a
semantic AssertionError. GREEN once DELIVER ships java_runner.py. No @skip,
no collection / import error in THIS process.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_java_runner import MavenExitScenario, RunnerVerdict


# The production seam the child interpreter imports + invokes (the SUT). Absent at
# HEAD -> the child import raises ModuleNotFoundError THERE (captured rc/stderr),
# never an import error in this test process.
_JAVA_RUNNER_MODULE = "des.adapters.driven.runner.java_runner"
_RUNNER_REGISTRY_MODULE = "des.adapters.driven.runner.runner_registry"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The token TestRunnerPort.resolve returns for a pom.xml target
# (test_runner_port.py -- ``_RegistryRow(filename="pom.xml", runner="maven-test")``).
_MAVEN_TOKEN = "maven-test"

# The fake-mvn binary name the run-facet resolves + shells. Literally "mvn" so
# the planted fake satisfies resolve_tool("mvn", ...) on the PATH rung exactly
# as a real mvn would.
_MVN_NAME = "mvn"

# The declared feature-scoped test_command tokens passed to the run-facet as
# the per-runner "scope" (NOT a node-id list). The leading "mvn" is the binary
# the run-facet resolves; the rest ("test") is the subcommand shelled as-is --
# the adapter does NOT choose the subcommand (the feature declares it, AC-4).
_DECLARED_COMMAND = (_MVN_NAME, "test")

# The argv tail the fake mvn must record + the run-facet must shell as-is
# (AC-4): everything after the resolved binary.
_DECLARED_SUBCOMMAND = _DECLARED_COMMAND[1:]

# The two fixture Java regression-file sources (AC-5/6). Self-contained,
# ephemeral -- never the shared polyglot-pilot fixture -- so the discovery
# contract is pinned independent of the pilot's own evolution.
_TWO_TEST_METHODS_SOURCE = """package pilot;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

class SignupFixture {

    @Test
    void userSignsUpAndIsRegistered() throws Exception {
        // fixture body irrelevant to discovery
    }

    @Test
    @DisplayName("Duplicate signup is rejected")
    void duplicateSignupIsRejected() throws Exception {
        // fixture body irrelevant to discovery
    }
}
"""

_ZERO_TEST_METHODS_SOURCE = """package pilot;

public class NotATestFixture {

    public int add(int a, int b) {
        return a + b;
    }
}
"""


@dataclass
class JavaRunnerComposition:
    """Drives the REAL slice-01 SUT over a controlled filesystem + FAKE mvn."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the target tree the run-facet runs mvn in (cwd)
    _target_root: Path | None = field(default=None)
    # the file the fake mvn records its argv + cwd into (AC-4 observable)
    _record_path: Path | None = field(default=None)
    # the controlled child env: PATH carrying (or scrubbed of) the fake mvn,
    # HOME under the fixture
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # which exit behaviour the planted fake mvn exhibits (None = mvn absent)
    _exit_scenario: MavenExitScenario | None = field(default=None)
    _mvn_planted: bool = field(default=False)
    # child-interpreter probe results (run facet)
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")
    # the regression file discover_java_ats reads (AC-5/6)
    _regression_file: Path | None = field(default=None)

    # ---- given (REAL filesystem + FAKE-mvn fixtures) -------------------------

    def given_target_with_fake_mvn(self, scenario: MavenExitScenario) -> None:
        """Plant a REAL chmod+x fake ``mvn`` exhibiting ``scenario``'s exit code.

        Used by AC-1 (GREEN -> PASS), AC-2 (RED -> FAIL), AC-4 (records argv/cwd).
        The fake mvn is a real shell script on a controlled PATH that the
        run-facet resolves via the shared resolve_tool PATH rung and shells
        like any mvn. This is the explicit FAKE-mvn determinism approach: the
        exit-semantics are exercised end-to-end through the REAL run-facet
        WITHOUT a real Maven/JDK toolchain (absent in CI). The fake ALSO
        records its argv + cwd to a record file so AC-4 can assert the
        declared subcommand was shelled as-is at cwd=target_root.
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        # a real pom.xml so the target is a genuine Maven tree the run-facet runs in
        (target / "pom.xml").write_text(
            "<project><modelVersion>4.0.0</modelVersion></project>\n",
            encoding="utf-8",
        )
        self._target_root = target
        self._record_path = root / "mvn-argv-record.txt"
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_mvn(path_bin / _MVN_NAME, scenario, self._record_path)
        # the fake mvn is on PATH (resolve_tool PATH rung); known_locations empty
        self._child_path = str(path_bin)
        self._known_locations = []
        self._exit_scenario = scenario
        self._mvn_planted = True

    def given_target_with_mvn_absent_everywhere(self) -> None:
        """Fixture for AC-3 (mvn-unresolvable).

        A real Maven target tree, but mvn exists NOWHERE: PATH is an empty dir
        AND the known_locations dirs are real-but-empty. The run-facet's
        resolve_tool scale exhausts -> the run-facet must degrade LOUD to
        INDETERMINATE naming the remediation (NOT a silent pass, NOT a FAIL).
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        (target / "pom.xml").write_text(
            "<project><modelVersion>4.0.0</modelVersion></project>\n",
            encoding="utf-8",
        )
        self._target_root = target
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        empty_known = root / "empty-known"
        empty_known.mkdir(parents=True, exist_ok=True)
        self._child_path = str(empty_path)
        self._known_locations = [str(empty_known)]
        self._exit_scenario = None
        self._mvn_planted = False

    def given_regression_file_with_two_test_methods(self) -> None:
        """Plant a REAL Java regression file (AC-5): a bare ``@Test`` method
        plus a ``@Test`` + ``@DisplayName``-annotated method, mirroring
        ``discover_cargo_ats``'s two-function fixture.
        """
        root = self._ensure_root()
        self._regression_file = root / "SignupFixture.java"
        self._regression_file.write_text(_TWO_TEST_METHODS_SOURCE, encoding="utf-8")

    def given_regression_file_with_zero_test_methods(self) -> None:
        """Plant a REAL Java regression file with ZERO ``@Test`` methods
        (AC-6, mirrors ``discover_cargo_ats``'s zero-#[test] negative row).
        """
        root = self._ensure_root()
        self._regression_file = root / "NotATestFixture.java"
        self._regression_file.write_text(_ZERO_TEST_METHODS_SOURCE, encoding="utf-8")

    # ---- when (drive the REAL SUT in a child interpreter) -------------------

    def when_the_run_facet_runs_the_command(self) -> None:
        """Invoke the REAL ``run_java_scope`` over the fixture in a child.

        Drives the run-facet end-to-end: the child imports java_runner + the
        port, builds a ``RunnerAdapter(name="maven-test")``, and calls
        ``run_java_scope(adapter, target_root, declared_command)``. The
        run-facet resolves the (fake or absent) mvn via resolve_tool, shells
        the declared command at cwd=target_root, and maps the exit code to a
        verdict. The child prints a machine-readable marker:
          - ``VERDICT:PASS`` / ``VERDICT:FAIL`` from a returned
            ``RunVerdict(passed=...)``,
          - ``VERDICT:INDETERMINATE:<reason>`` when the run-facet raises
            ``RunnerAdapterUnavailable`` (the degrade-LOUD channel) -- carried
            DISTINCTLY from FAIL.
        At HEAD java_runner is absent -> the child import raises
        ModuleNotFoundError (rc != 0, no marker), captured here as the
        observable.
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(_DECLARED_COMMAND)!r}\n"
            f"runner_mod = importlib.import_module({_JAVA_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_MAVEN_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = runner_mod.run_java_scope(\n"
            "        adapter, pathlib.Path(target_root), command)\n"
            "except unavailable as exc:\n"
            "    print('VERDICT:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('VERDICT:' + ('PASS' if verdict.passed else 'FAIL'))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    def when_the_at_discovery_facet_discovers_the_ats(self) -> None:
        """Invoke the REAL ``discover_java_ats`` over the fixture in a child.

        Drives the AT-discovery facet end-to-end: the child imports
        java_runner + the port, builds a ``RunnerAdapter(name="maven-test")``,
        and calls ``discover_java_ats(adapter, target_root, regression_file)``
        directly (mirrors the run-facet probe's direct-function-call shape --
        the SUT is the concrete facet, not the registry dispatch). The child
        prints a machine-readable marker:
          - ``DISCOVERY:OK:<at_id>,<at_id>,...|<content_hash>`` on success,
          - ``DISCOVERY:REFUSED:<reason>`` when the facet raises
            ``RunnerAdapterUnavailable`` (the degrade-LOUD channel).
        At HEAD java_runner is absent -> the child import raises
        ModuleNotFoundError (rc != 0, no marker), captured here as the
        observable.
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {(str(self._target_root) if self._target_root else '')!r}\n"
            f"regression_file = {str(self._regression_file)!r}\n"
            f"runner_mod = importlib.import_module({_JAVA_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_MAVEN_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    result = runner_mod.discover_java_ats(\n"
            "        adapter, pathlib.Path(target_root), pathlib.Path(regression_file))\n"
            "except unavailable as exc:\n"
            "    print('DISCOVERY:REFUSED:' + str(exc))\n"
            "else:\n"
            "    print('DISCOVERY:OK:' + ','.join(result.at_ids) + '|' + result.content_hash)\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the run-facet OUTCOME -- the port-exposed observable) -

    def then_the_verdict_is(self, expected: RunnerVerdict) -> None:
        """The run-facet mapped the mvn exit code to ``expected`` verdict.

        Used by AC-1 (PASS), AC-2 (FAIL), and AC-3 (INDETERMINATE
        mvn-unresolvable). Asserts the child reported the exact verdict
        marker. The FAIL vs INDETERMINATE distinction is load-bearing: a
        legit mvn RED must be FAIL (propagated), an mvn-absent must be
        INDETERMINATE -- never the other way, never a silent pass.

        Active-RED at HEAD: java_runner is absent, the child import fails
        (rc != 0, no ``VERDICT:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the java run-facet must run the declared command and map the exit "
            f"code to the {expected.name} verdict; at HEAD {_JAVA_RUNNER_MODULE} "
            f"is absent so the child probe could not produce a verdict. "
            f"{self._probe_observed()}"
        )
        marker = self._probe_out.split("VERDICT:", 1)[1].strip().splitlines()[0]
        observed = marker.split(":", 1)[0]  # PASS | FAIL | INDETERMINATE
        assert observed == expected.name, (
            f"the java run-facet mapped the {self._exit_scenario} fixture to the "
            f"WRONG verdict: expected {expected.name}, got {observed!r} "
            f"(marker={marker!r}). The exit-semantics require: exit 0 -> PASS, "
            f"non-zero-with-tests -> FAIL (propagated, NOT indeterminate), "
            f"mvn-absent -> INDETERMINATE. (Unlike cargo there is NO exit-4 "
            f"empty-scope row for mvn.) {self._probe_observed()}"
        )

    def then_the_indeterminate_names_the_remediation(self) -> None:
        """The mvn-unresolvable INDETERMINATE carries an actionable remediation.

        Used by AC-3. Asserts the INDETERMINATE reason NAMES an install path
        (``mvn`` / ``install`` / ``maven``) -- the LOUD degrade resolve_tool's
        named remediation flows through, never a bare/silent failure.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:``
        marker -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:INDETERMINATE:" in self._probe_out, (
            "an unresolvable mvn (absent after the full discovery scale) must "
            "yield a LOUD INDETERMINATE naming the remediation (never a silent "
            f"degrade, never a FAIL); at HEAD {_JAVA_RUNNER_MODULE} is absent so "
            f"the child probe could not produce it. {self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("VERDICT:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        lowered = reason.lower()
        assert any(token in lowered for token in ("install", "mvn", "maven")), (
            "the INDETERMINATE reason must NAME an actionable install path (e.g. "
            "'install mvn' / 'maven.apache.org') so the operator can act -- not a "
            f"bare failure; got {reason!r}. {self._probe_observed()}"
        )

    def then_the_declared_subcommand_was_shelled(self) -> None:
        """The fake mvn recorded the declared subcommand as-is (AC-4).

        The run-facet must shell the feature's declared command tokens AFTER
        the resolved binary VERBATIM -- the adapter does NOT choose the
        subcommand (the feature declares ``mvn test``, mirroring cargo D5).
        Reads the record file the fake mvn wrote its argv into and asserts
        the tail equals the declared subcommand.

        Active-RED at HEAD: java_runner is absent, the fake mvn was never
        shelled, the record file is absent / the child probe failed -> this
        AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the java run-facet must shell the fake mvn (which records its "
            f"argv) and return a verdict; at HEAD {_JAVA_RUNNER_MODULE} is "
            f"absent so the fake mvn was never invoked. {self._probe_observed()}"
        )
        recorded = self._read_record()
        assert recorded is not None, (
            "the fake mvn must have been SHELLED by the run-facet (so it "
            "recorded its argv); the record file is absent -- the run-facet "
            f"did not invoke the resolved mvn. {self._probe_observed()}"
        )
        observed_argv = recorded["argv"][1:]  # drop argv[0] (the binary path)
        assert tuple(observed_argv) == _DECLARED_SUBCOMMAND, (
            "the java run-facet must shell the feature's declared subcommand "
            f"AS-IS (the adapter does NOT choose it): expected "
            f"{list(_DECLARED_SUBCOMMAND)}, the fake mvn was invoked with "
            f"{observed_argv!r}. {self._probe_observed()}"
        )

    def then_the_cwd_was_the_target_root(self) -> None:
        """The fake mvn recorded a cwd equal to the target root (AC-4).

        The run-facet must shell the declared command at ``cwd=target_root``
        (so ``mvn test`` resolves the target's own pom.xml). Reads the cwd
        the fake mvn recorded and asserts it is the target root.

        Active-RED at HEAD: java_runner is absent, the fake mvn was never
        shelled, the record file is absent -> this AssertionError fires.
        """
        recorded = self._read_record()
        assert recorded is not None, (
            "the fake mvn must have been SHELLED by the run-facet (so it "
            "recorded its cwd); the record file is absent -- the run-facet "
            f"did not invoke the resolved mvn. {self._probe_observed()}"
        )
        observed_cwd = Path(recorded["cwd"]).resolve()
        expected_cwd = Path(str(self._target_root)).resolve()
        assert observed_cwd == expected_cwd, (
            "the java run-facet must shell the declared command at "
            f"cwd=target_root (so 'mvn test' resolves the target's pom.xml): "
            f"expected {str(expected_cwd)!r}, the fake mvn ran in "
            f"{str(observed_cwd)!r}. {self._probe_observed()}"
        )

    def then_the_discovered_at_ids_are(self, expected_ids: frozenset[str]) -> None:
        """The AT-discovery facet discovered EXACTLY ``expected_ids`` (AC-5).

        Active-RED at HEAD: java_runner is absent -> no ``DISCOVERY:OK:``
        marker -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "DISCOVERY:OK:" in self._probe_out, (
            "the java AT-discovery facet must discover the regression file's "
            f"@Test methods; at HEAD {_JAVA_RUNNER_MODULE} is absent so the "
            f"child probe could not produce a discovery. {self._probe_observed()}"
        )
        payload = self._probe_out.split("DISCOVERY:OK:", 1)[1].strip().splitlines()[0]
        ids_part = payload.split("|", 1)[0]
        observed_ids = frozenset(i for i in ids_part.split(",") if i)
        assert observed_ids == expected_ids, (
            f"expected the discovered AT identities to be exactly "
            f"{sorted(expected_ids)!r}, got {sorted(observed_ids)!r} "
            f"(payload={payload!r}). {self._probe_observed()}"
        )

    def then_the_content_hash_seals_the_real_bytes(self) -> None:
        """The AT-discovery facet's content_hash is sha256 over the file's
        REAL raw bytes (AC-5, mirrors discover_pytest_ats/discover_cargo_ats).

        Active-RED at HEAD: no ``DISCOVERY:OK:`` marker -> this
        AssertionError fires.
        """
        assert self._probe_rc == 0 and "DISCOVERY:OK:" in self._probe_out, (
            "the java AT-discovery facet must return a content_hash seal; at "
            f"HEAD {_JAVA_RUNNER_MODULE} is absent so the child probe could "
            f"not produce one. {self._probe_observed()}"
        )
        payload = self._probe_out.split("DISCOVERY:OK:", 1)[1].strip().splitlines()[0]
        observed_hash = payload.split("|", 1)[1] if "|" in payload else ""
        assert self._regression_file is not None
        expected_hash = hashlib.sha256(self._regression_file.read_bytes()).hexdigest()
        assert observed_hash == expected_hash, (
            "the content_hash must be sha256 over the REAL regression file "
            f"raw bytes -- expected {expected_hash!r}, got {observed_hash!r} "
            f"(payload={payload!r}). {self._probe_observed()}"
        )

    def then_the_discovery_is_refused_naming_zero(self) -> None:
        """A zero-@Test regression file must degrade LOUD, never a silent
        empty discovery (AC-6, mirrors discover_cargo_ats's zero-#[test] row).

        Active-RED at HEAD: no ``DISCOVERY:REFUSED:`` marker -> this
        AssertionError fires.
        """
        assert self._probe_rc == 0 and "DISCOVERY:REFUSED:" in self._probe_out, (
            "a Java regression file with ZERO @Test methods must be refused "
            "LOUD by the AT-discovery facet (RunnerAdapterUnavailable), never "
            f"a silent empty discovery; at HEAD {_JAVA_RUNNER_MODULE} is "
            f"absent so the child probe could not produce the refusal. "
            f"{self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("DISCOVERY:REFUSED:", 1)[1].strip().splitlines()[0]
        )
        lowered = reason.lower()
        assert "zero" in lowered or "malformed" in lowered, (
            "the refusal reason must NAME the zero-test/malformed condition "
            f"-- got {reason!r}. {self._probe_observed()}"
        )

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-java-runner-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_mvn(
        target: Path,
        scenario: MavenExitScenario,
        record_path: Path,
    ) -> Path:
        """Write a REAL chmod+x fake ``mvn`` exhibiting ``scenario``'s exit code.

        A POSIX shell script (the run-facet shells it like a real mvn). The
        script:
          1. RECORDS its argv + cwd to ``record_path`` as two lines:
               ARGV<TAB>arg0<TAB>arg1<TAB>...
               CWD<TAB><working-directory>
             (so AC-4 can assert the declared subcommand was shelled as-is at
             cwd=target_root -- the declared-command-shelled observable).
          2. emits maven-shaped output and exits with the scenario's code:
               - GREEN -> emit a BUILD SUCCESS summary, exit 0.
               - RED   -> emit a BUILD FAILURE summary (tests EXECUTED), exit 1.

        It does NOT interpret its argv (the declared subcommand) to choose an
        outcome -- the fixture controls the exit code deterministically,
        independent of a real Maven/JDK toolchain. (Unlike cargo there is no
        exit-4 row: ``mvn test`` exits 0 even with no tests, so empty-scope
        is OUT-OF-SCOPE.)
        """
        exit_code = {MavenExitScenario.GREEN: 0, MavenExitScenario.RED: 1}[scenario]
        summary = {
            MavenExitScenario.GREEN: "echo '[INFO] BUILD SUCCESS'",
            MavenExitScenario.RED: (
                "echo '[ERROR] Tests run: 1, Failures: 1'\necho '[INFO] BUILD FAILURE'"
            ),
        }[scenario]
        # Record argv (tab-separated) + cwd, then emit the summary + exit. ``$@``
        # carries the subcommand args the run-facet shelled; ``$0`` is the binary
        # path. ``printf %s`` keeps each arg on the ARGV line; PWD is the cwd.
        record = str(record_path)
        script = (
            "#!/bin/sh\n"
            f'{{ printf \'ARGV\'; for a in "$0" "$@"; do printf \'\\t%s\' "$a"; '
            f"done; printf '\\n'; printf 'CWD\\t%s\\n' \"$PWD\"; }} > {record!r}\n"
            f"{summary}\n"
            f"exit {exit_code}\n"
        )
        target.write_text(script, encoding="utf-8")
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    def _read_record(self) -> dict[str, object] | None:
        """Read the argv + cwd the fake mvn recorded (AC-4), or None if absent.

        Returns ``{"argv": [arg0, arg1, ...], "cwd": "<dir>"}`` parsed from the
        tab-separated record file, or ``None`` when the fake mvn was never
        shelled (the file does not exist -- e.g. at HEAD where the run-facet
        is absent).
        """
        if self._record_path is None or not self._record_path.is_file():
            return None
        argv: list[str] = []
        cwd = ""
        for line in self._record_path.read_text(encoding="utf-8").splitlines():
            fields = line.split("\t")
            if fields[0] == "ARGV":
                argv = fields[1:]
            elif fields[0] == "CWD" and len(fields) > 1:
                cwd = fields[1]
        return {"argv": argv, "cwd": cwd}

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_python_c(self, program: str) -> tuple[int, str, str]:
        """Run a one-shot ``python -c`` probe in a child interpreter.

        HERMETIC env: PATH is set to ONLY the fixture's controlled dir (so the
        run-facet resolves the FAKE mvn, never an ambient host mvn, and the
        mvn-absent fixture genuinely finds nothing). HOME is the fixture's tmp
        home and the Maven env (MAVEN_HOME/M2_HOME/JAVA_HOME) is neutralised so
        a known-location / Maven toolchain dir can never leak a real mvn.
        ``src`` is prepended to PYTHONPATH so the in-tree ``des`` package is
        importable.
        """
        env = dict(os.environ)
        env["PATH"] = self._child_path
        env["HOME"] = self._child_home
        # neutralise the Maven/JDK env so a real host mvn can never leak into
        # resolution (mirrors go_test_runner_adapter's GOROOT/GOPATH/GOBIN pop).
        for var in ("MAVEN_HOME", "M2_HOME", "JAVA_HOME"):
            env.pop(var, None)
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

    # ---- diagnostics --------------------------------------------------------

    def _probe_observed(self) -> str:
        return (
            f"probe_rc={self._probe_rc!r}; "
            f"exit_scenario={self._exit_scenario!r}; "
            f"mvn_planted={self._mvn_planted!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"regression_file={str(self._regression_file)!r}; "
            f"record_present={self._record_path.is_file() if self._record_path else False!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/java_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=java_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
