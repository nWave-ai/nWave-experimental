"""Composition root for cpp-test-runner-adapter slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
production slice-01 SUTs imported + invoked in a CHILD interpreter. The SUTs are
the net-new production seams the feature ships (mirroring go-test-runner-adapter
+ kotlin/csharp-test-runner-adapter's AT-discovery facet pair):

  1. the C++ run-facet ``run_cpp_scope`` (cpp_runner.py) -- resolves the target's
     ``make`` via the shared resolve_tool scale, shells the declared
     ``make test`` command over a real subprocess, and maps the exit code to
     PASS / FAIL / INDETERMINATE.
  2. the C++ AT-discovery facet ``discover_cpp_ats`` (cpp_runner.py) -- discovers
     ``TEST("...")``-declared identities a C++ regression file carries, mirroring
     ``discover_kotlin_ats`` / ``discover_csharp_ats``.

WHY a child interpreter (not a thin in-process call): at HEAD ``cpp_runner`` does
not exist (Tsunami: cpp_runner.py absent). Importing it in THIS process would
raise ModuleNotFoundError at COLLECTION -> a BROKEN test, not active-RED. Running
the import in a child ``python -c`` makes the absent module a CAPTURED observable
(child rc != 0, no marker) that each Then turns into a SEMANTIC AssertionError.
Same pattern as go/kotlin/csharp-test-runner-adapter.

ZERO ``des.adapters.*`` import in THIS process: the SUT is only ever imported in
the CHILD interpreter, never here.

FAKE-make determinism (AC-1/2/3 -- explicit fixture approach, mirrors go/kotlin):
the exit-semantics ATs do NOT require a real g++/make toolchain build. The
fixture plants a REAL chmod+x ``make`` script on a controlled child PATH that
emits a controlled exit code:
  - GREEN -> exit 0 (all pass)                  -> PASS verdict.
  - RED   -> emit test output, then exit 2      -> FAIL verdict (propagated, NOT
             swallowed into INDETERMINATE).
The run-facet resolves this fake make via the shared ``resolve_tool`` scale
(PATH rung) and shells it exactly like a real make. RED exits 2 (not 1) because
that mirrors the REAL GNU make behaviour verified during this DISTILL: a failing
recipe line's own exit code is wrapped into a generic non-zero ``make`` exit
(``make: *** [Makefile:N: test] Error N``) -- the exact wrapped code is
irrelevant to the contract (any non-zero -> FAIL), so the fixture picks 2 to
prove the run-facet does NOT special-case a specific non-zero value.

AC-3 (make-unresolvable) drives ``run_cpp_scope`` over a fixture where ``make``
is absent everywhere (PATH scrubbed to an empty dir, known-locations
real-but-empty) and asserts the LOUD INDETERMINATE via ``resolve_tool``'s named
remediation.

AC-4/AC-5 (AT-discovery) drive ``discover_cpp_ats`` over REAL files already on
disk in the polyglot pilot fixture ``tests/polyglot-pilot/cpp/`` -- NO synthetic
fixture is planted:
  - AC-4 reads ``feature/feature_scenarios_test.cpp`` (a genuine two-``TEST``
    file, verified by running ``make test`` in the pilot during this DISTILL:
    "[PASS] Signup: user added to registry" / "[PASS] Signup: duplicate
    rejected").
  - AC-5 reads ``common/testkit/test_main.cpp`` (a genuine zero-``TEST`` file --
    it only calls ``testkit::run_all()``).

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``cpp_runner`` is absent,
so the child import fails (rc != 0, no marker) and each Then fires a semantic
AssertionError. GREEN once DELIVER ships cpp_runner.py. No @skip, no
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

from .domain_types_cpp_runner import MakeExitScenario, RunnerVerdict


# The production seam the child interpreter imports + invokes (the SUT). Absent
# at HEAD -> the child import raises ModuleNotFoundError THERE (captured
# rc/stderr), never an import error in this test process.
_CPP_RUNNER_MODULE = "des.adapters.driven.runner.cpp_runner"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The token this feature registers the C++ run-facet + AT-discovery facet under
# (registration only -- NO test_runner_port._REGISTRY scan row is added by this
# feature; see the feature-delta's Manifest-Detection Decision). The AT
# constructs RunnerAdapter(name=...) directly and never touches resolve().
_CPP_TOKEN = "cpp-make-test"

# The fake-make binary name the run-facet resolves + shells.
_MAKE_NAME = "make"

# The declared feature-scoped test_command tokens passed to the run-facet as the
# per-runner "scope" (NOT a node-id list). The leading "make" is the binary the
# run-facet resolves; the rest ("test",) is the subcommand shelled as-is -- the
# adapter does NOT choose the subcommand (the feature declares it, mirroring
# go/csharp D5).
_DECLARED_COMMAND = (_MAKE_NAME, "test")

# The two REAL polyglot pilot files AC-4/AC-5 read directly -- no synthetic
# discovery fixture is planted. Verified during this DISTILL: `make test` in the
# pilot exits 0, and these two source files carry exactly the TEST("...") shapes
# named below (confirmed by reading + grepping the files, not assumed).
_PILOT_ROOT = "tests/polyglot-pilot/cpp"
_TWO_TEST_PILOT_RELPATH = "feature/feature_scenarios_test.cpp"
_ZERO_TEST_PILOT_RELPATH = "common/testkit/test_main.cpp"

_TWO_TEST_EXPECTED_IDS = (
    "Signup: user added to registry",
    "Signup: duplicate rejected",
)


@dataclass
class CppRunnerComposition:
    """Drives the REAL slice-01 SUTs over a controlled filesystem + FAKE make,
    and over the REAL polyglot pilot fixture files for AT-discovery."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the target tree the run-facet runs make in
    _target_root: Path | None = field(default=None)
    # the controlled child env: PATH carrying (or scrubbed of) the fake make,
    # HOME under the fixture, and the known_locations passed to resolve_tool
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # which exit behaviour the planted fake make exhibits (None = make absent)
    _exit_scenario: MakeExitScenario | None = field(default=None)
    # the REAL regression file AC-4/AC-5 discover_cpp_ats reads
    _regression_file: Path | None = field(default=None)
    # child-interpreter probe results (shared by run-facet + AT-discovery probes)
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-make fixtures) -----------------------

    def given_target_with_fake_make(self, scenario: MakeExitScenario) -> None:
        """Plant a REAL chmod+x fake ``make`` exhibiting ``scenario``'s exit code.

        Used by AC-1 (GREEN -> PASS), AC-2 (RED -> FAIL). Mirrors
        go_test_runner_adapter's ``given_target_with_fake_go`` and
        kotlin_test_runner_adapter's ``given_target_with_fake_gradlew``.
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        # a real (minimal) Makefile so the target is a genuine C++/Make tree the
        # run-facet runs in -- not consulted for auto-detection (this feature
        # adds no _REGISTRY scan row; the AT bypasses resolve() entirely).
        (target / "Makefile").write_text(
            "test:\n\t@echo fixture make target\n", encoding="utf-8"
        )
        self._target_root = target
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_make(path_bin / _MAKE_NAME, scenario)
        # the fake make is on PATH (resolve_tool PATH rung); known_locations empty
        self._child_path = str(path_bin)
        self._known_locations = []
        self._exit_scenario = scenario

    def given_target_with_make_absent_everywhere(self) -> None:
        """Fixture for AC-3 (make-unresolvable).

        A real C++/Make target tree, but ``make`` exists NOWHERE: PATH is an
        empty dir AND the known_locations dirs are real-but-empty. The
        run-facet's resolve_tool scale exhausts -> the run-facet must degrade
        LOUD to INDETERMINATE naming the remediation (NOT a silent pass, NOT a
        FAIL). Mirrors go/kotlin's absent-everywhere fixtures.
        """
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        (target / "Makefile").write_text(
            "test:\n\t@echo fixture make target\n", encoding="utf-8"
        )
        self._target_root = target
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        empty_known = root / "empty-known"
        empty_known.mkdir(parents=True, exist_ok=True)
        self._child_path = str(empty_path)
        self._known_locations = [str(empty_known)]
        self._exit_scenario = None

    def given_real_pilot_file_with_two_tests(self) -> None:
        """Point at the REAL polyglot pilot file declaring two TEST cases (AC-4).

        No synthetic fixture is planted -- ``feature/feature_scenarios_test.cpp``
        is a genuine, already-verified-working pilot source file (confirmed by
        running ``make test`` in the pilot during this DISTILL).
        """
        self._regression_file = _repo_root() / _PILOT_ROOT / _TWO_TEST_PILOT_RELPATH
        assert self._regression_file.is_file(), (
            f"the polyglot pilot fixture file is expected to exist on disk: "
            f"{self._regression_file}"
        )

    def given_real_pilot_file_with_zero_tests(self) -> None:
        """Point at the REAL polyglot pilot file declaring zero TEST cases (AC-5).

        ``common/testkit/test_main.cpp`` is a genuine pilot source file that only
        calls ``testkit::run_all()`` -- zero TEST("...") macro invocations.
        """
        self._regression_file = _repo_root() / _PILOT_ROOT / _ZERO_TEST_PILOT_RELPATH
        assert self._regression_file.is_file(), (
            f"the polyglot pilot fixture file is expected to exist on disk: "
            f"{self._regression_file}"
        )

    # ---- when (drive the REAL SUTs in a child interpreter) ------------------

    def when_the_run_facet_runs_the_command(self) -> None:
        """Invoke the REAL ``run_cpp_scope`` over the fixture in a child.

        Mirrors go/kotlin's ``when_the_run_facet_runs_the_command``. The child
        imports cpp_runner + the port, builds a
        ``RunnerAdapter(name="cpp-make-test")``, and calls
        ``run_cpp_scope(adapter, target_root, declared_command)``.
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(_DECLARED_COMMAND)!r}\n"
            f"runner_mod = importlib.import_module({_CPP_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_CPP_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = runner_mod.run_cpp_scope(\n"
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
        """Invoke the REAL ``discover_cpp_ats`` over the regression file.

        Mirrors ``discover_kotlin_ats`` / ``discover_csharp_ats``'s driving
        pattern: the child imports cpp_runner + the port, builds a
        ``RunnerAdapter(name="cpp-make-test")``, and calls
        ``discover_cpp_ats(adapter, target_root, regression_test_file)``.
        """
        program = (
            "import importlib, pathlib\n"
            f"regression_file = {str(self._regression_file)!r}\n"
            f"runner_mod = importlib.import_module({_CPP_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_CPP_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    result = runner_mod.discover_cpp_ats(\n"
            "        adapter, pathlib.Path('.'), pathlib.Path(regression_file))\n"
            "except unavailable as exc:\n"
            "    print('DISCOVERY:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('DISCOVERY:AT_IDS:' + '\\x1f'.join(result.at_ids))\n"
            "    print('DISCOVERY:HASH:' + result.content_hash)\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the SUT OUTCOME -- the port-exposed observable) ----

    def then_the_verdict_is(self, expected: RunnerVerdict) -> None:
        """The run-facet mapped the make exit code to ``expected`` verdict.

        Used by AC-1 (PASS), AC-2 (FAIL), and AC-3 (INDETERMINATE
        make-unresolvable). Mirrors go/kotlin's ``then_the_verdict_is``.

        Active-RED at HEAD: cpp_runner is absent, the child import fails
        (rc != 0, no ``VERDICT:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the C++ run-facet must run the declared command and map the exit "
            f"code to the {expected.name} verdict; at HEAD {_CPP_RUNNER_MODULE} "
            f"is absent so the child probe could not produce a verdict. "
            f"{self._probe_observed()}"
        )
        marker = self._probe_out.split("VERDICT:", 1)[1].strip().splitlines()[0]
        observed = marker.split(":", 1)[0]  # PASS | FAIL | INDETERMINATE
        assert observed == expected.name, (
            f"the C++ run-facet mapped the {self._exit_scenario} fixture to the "
            f"WRONG verdict: expected {expected.name}, got {observed!r} "
            f"(marker={marker!r}). exit 0 -> PASS, non-zero-with-tests -> FAIL "
            f"(propagated, NOT indeterminate), make-absent -> INDETERMINATE. "
            f"(Unlike cargo there is NO exit-4 empty-scope row for make.) "
            f"{self._probe_observed()}"
        )

    def then_the_indeterminate_names_the_remediation(self) -> None:
        """The make-unresolvable INDETERMINATE carries an actionable remediation.

        Used by AC-3. Mirrors go/kotlin's
        ``then_the_indeterminate_names_the_remediation``.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:``
        marker -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:INDETERMINATE:" in self._probe_out, (
            "an unresolvable make (absent after the full discovery scale) must "
            "yield a LOUD INDETERMINATE naming the remediation (never a silent "
            f"degrade, never a FAIL); at HEAD {_CPP_RUNNER_MODULE} is absent so "
            f"the child probe could not produce it. {self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("VERDICT:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        lowered = reason.lower()
        assert any(token in lowered for token in ("install", "make")), (
            "the INDETERMINATE reason must NAME an actionable install path "
            "(e.g. 'install make') so the operator can act -- not a bare "
            f"failure; got {reason!r}. {self._probe_observed()}"
        )

    def then_the_discovered_at_ids_match(self, expected_ids: tuple[str, ...]) -> None:
        """The AT-discovery facet discovered exactly the declared TEST identities.

        Used by AC-4. Mirrors ``discover_kotlin_ats`` /
        ``discover_csharp_ats``'s AT-identity observable.

        Active-RED at HEAD: cpp_runner is absent, the child import fails
        (rc != 0, no ``DISCOVERY:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "DISCOVERY:AT_IDS:" in self._probe_out, (
            f"the C++ AT-discovery facet must discover the TEST(\"...\") "
            f"identities a regression file carries; at HEAD "
            f"{_CPP_RUNNER_MODULE} is absent so the child probe could not "
            f"produce a discovery result. {self._probe_observed()}"
        )
        line = next(
            ln
            for ln in self._probe_out.splitlines()
            if ln.startswith("DISCOVERY:AT_IDS:")
        )
        observed_ids = tuple(
            token
            for token in line.split("DISCOVERY:AT_IDS:", 1)[1].split("\x1f")
            if token
        )
        assert set(observed_ids) == set(expected_ids), (
            "the C++ AT-discovery facet must discover EXACTLY the "
            f"TEST(\"...\")-declared cases in the regression file: expected "
            f"{sorted(expected_ids)}, got {sorted(observed_ids)}. "
            f"{self._probe_observed()}"
        )

    def then_the_discovery_carries_a_content_seal(self) -> None:
        """The AT-discovery result carries a sha256 seal over the file's raw bytes.

        Used by AC-4. The content_hash must equal sha256 of the EXACT bytes on
        disk (no read-time-of-check/read-time-of-use gap), mirroring
        ``discover_kotlin_ats`` / ``discover_csharp_ats``.
        """
        import hashlib

        assert self._regression_file is not None, "no regression file was set"
        expected_hash = hashlib.sha256(self._regression_file.read_bytes()).hexdigest()
        assert self._probe_rc == 0 and "DISCOVERY:HASH:" in self._probe_out, (
            "the C++ AT-discovery facet must return a content_hash seal; at "
            f"HEAD {_CPP_RUNNER_MODULE} is absent so no seal was produced. "
            f"{self._probe_observed()}"
        )
        line = next(
            ln
            for ln in self._probe_out.splitlines()
            if ln.startswith("DISCOVERY:HASH:")
        )
        observed_hash = line.split("DISCOVERY:HASH:", 1)[1].strip()
        assert observed_hash == expected_hash, (
            "the C++ AT-discovery facet's content_hash must be the sha256 of "
            f"the regression file's raw bytes: expected {expected_hash!r}, got "
            f"{observed_hash!r}. {self._probe_observed()}"
        )

    def then_the_discovery_degrades_loud_naming_the_malformed_file(self) -> None:
        """discover_cpp_ats degrades LOUD when zero TEST cases are found.

        Used by AC-5 -- the malformed-file partner of AC-4, mirroring
        ``discover_kotlin_ats`` / ``discover_csharp_ats``'s zero-tests-found
        degrade-LOUD row (never a silently-empty discovery).
        """
        assert self._probe_rc == 0 and "DISCOVERY:INDETERMINATE:" in self._probe_out, (
            "a C++ regression file with ZERO TEST(\"...\") cases must degrade "
            "LOUD (RunnerAdapterUnavailable), never a silently-empty discovery; "
            f"at HEAD {_CPP_RUNNER_MODULE} is absent so the child probe could "
            f"not produce it. {self._probe_observed()}"
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
            "the degrade-LOUD reason must name the malformed regression file or "
            f"the zero-TEST condition; got {reason!r}. {self._probe_observed()}"
        )

    # ---- real-fixture helpers ------------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-cpp-runner-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_make(target: Path, scenario: MakeExitScenario) -> Path:
        """Write a REAL chmod+x fake ``make`` exhibiting ``scenario``'s exit code.

        A POSIX shell script (the run-facet shells it like a real make). It does
        NOT build anything or interpret its argv -- the fixture controls the
        exit code deterministically, independent of a real g++/make toolchain.
        Mirrors go/kotlin's ``_plant_fake_go`` / ``_plant_fake_gradlew``.
        RED exits 2 (mirroring the real GNU make wrapping behaviour verified
        during this DISTILL), not 1 -- proving the run-facet does not
        special-case a specific non-zero exit value.
        """
        exit_code = {MakeExitScenario.GREEN: 0, MakeExitScenario.RED: 2}[scenario]
        summary = {
            MakeExitScenario.GREEN: (
                "echo '[PASS] fixture test'\necho '1 test(s), 0 failure(s)'"
            ),
            MakeExitScenario.RED: (
                "echo '[FAIL] fixture test: assertion failed'\n"
                "echo '1 test(s), 1 failure(s)'"
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
        make, never an ambient host make, and the make-absent fixture genuinely
        finds nothing). HOME is the fixture's tmp home. When ``path`` is None
        (the AT-discovery probes, which never shell a binary) the ambient PATH
        is left untouched. ``src`` is prepended to PYTHONPATH so the in-tree
        ``des`` package is importable.
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

    tests/des/acceptance/cpp_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=cpp_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]


__all__ = [
    "_TWO_TEST_EXPECTED_IDS",
    "CppRunnerComposition",
]
