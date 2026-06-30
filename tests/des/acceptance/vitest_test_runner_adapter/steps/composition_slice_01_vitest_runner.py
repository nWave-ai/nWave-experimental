"""Composition root for vitest-test-runner-adapter slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
production slice-01 SUT imported + invoked in a CHILD interpreter. The SUT is the
ONE net-new production seam the feature ships:

  the JS/TS run-facet ``run_vitest_scope`` (vitest_runner.py) -- mirrors
  run_go_scope / run_cargo_scope: resolves the target's ``vitest`` via the shared
  resolve_tool scale, shells the declared ``vitest run`` command over a real
  subprocess at ``cwd=target_root``, and maps the exit code to PASS / FAIL /
  INDETERMINATE.

WHY a child interpreter (not a thin in-process call): at HEAD ``vitest_runner``
does not exist (Tsunami: vitest_runner.py absent). Importing it in THIS process
would raise ModuleNotFoundError at COLLECTION -> a BROKEN test, not active-RED.
Running the import in a child ``python -c`` makes the absent module a CAPTURED
observable (child rc != 0, no ``VERDICT:``/``ARGV:`` marker) that each Then turns
into a SEMANTIC AssertionError. Same pattern as the go slice-01 / rust slice-02
harness.

ZERO ``des.adapters.*`` import in THIS process (slice-02-RC2 discipline): the SUT
is only ever imported in the CHILD interpreter, never here.

FAKE-vitest determinism (AC-1/2/4 -- explicit fixture approach): the exit-semantics
+ declared-command-shelled ATs do NOT require a real Node / vitest toolchain
(absent in CI). The fixture plants a REAL chmod+x ``vitest`` script on a controlled
child PATH that emits a controlled exit code + output AND records its argv + cwd to
a record file:
  - GREEN -> exit 0 (all pass)                  -> PASS verdict.
  - RED   -> emit test output, then exit 1      -> FAIL verdict (propagated, NOT
             swallowed into INDETERMINATE).
The run-facet resolves this fake vitest via the shared ``resolve_tool`` scale (PATH
rung) and shells it exactly like a real vitest -- so the exit-semantics + the
declared-subcommand-at-cwd contract are exercised end-to-end through the REAL
run-facet, deterministically, in CI.

VITEST-vs-cargo (like go): there is NO cargo-style exit-4 NO_MATCH empty-scope. So
the planted fake has only GREEN (0) and RED (non-zero) behaviours; there is NO
"vitest ran no tests -> INDETERMINATE" path. INDETERMINATE is reached ONLY by
AC-3's vitest-absent fixture.

AC-3 (vitest-unresolvable) drives ``run_vitest_scope`` over a fixture where
``vitest`` is absent everywhere (PATH scrubbed to an empty dir, known-locations
real-but-empty) and asserts the LOUD INDETERMINATE via ``resolve_tool``'s named
remediation.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD ``vitest_runner`` is absent,
so the child import fails (rc != 0, no marker) and each Then fires a semantic
AssertionError. GREEN once DELIVER ships vitest_runner.py. No @skip, no collection
/ import error in THIS process.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_vitest_runner import RunnerVerdict, VitestExitScenario


# The production seam the child interpreter imports + invokes (the SUT). Absent at
# HEAD -> the child import raises ModuleNotFoundError THERE (captured rc/stderr),
# never an import error in this test process.
_VITEST_RUNNER_MODULE = "des.adapters.driven.runner.vitest_runner"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The token TestRunnerPort.resolve returns for a package.json (vitest) target
# (test_runner_port.py:149 -- ``_RegistryRow(filename="package.json",
# runner="vitest", requires_substring="vitest")``).
_VITEST_TOKEN = "vitest"

# The fake-vitest binary name the run-facet resolves + shells. Literally "vitest"
# so the planted fake satisfies resolve_tool("vitest", ...) on the PATH rung
# exactly as a real vitest would.
_VITEST_NAME = "vitest"

# The declared feature-scoped test_command tokens passed to the run-facet as the
# per-runner "scope" (NOT a node-id list). The leading "vitest" is the binary the
# run-facet resolves; the rest ("run",) is the subcommand shelled as-is -- the
# adapter does NOT choose the subcommand (the feature declares it, AC-4).
_DECLARED_COMMAND = (_VITEST_NAME, "run")

# The argv tail the fake vitest must record + the run-facet must shell as-is
# (AC-4): everything after the resolved binary.
_DECLARED_SUBCOMMAND = _DECLARED_COMMAND[1:]


@dataclass
class VitestRunnerComposition:
    """Drives the REAL slice-01 SUT over a controlled filesystem + FAKE vitest."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the target tree the run-facet runs vitest in (cwd)
    _target_root: Path | None = field(default=None)
    # the file the fake vitest records its argv + cwd into (AC-4 observable)
    _record_path: Path | None = field(default=None)
    # the controlled child env: PATH carrying (or scrubbed of) the fake vitest,
    # HOME under the fixture, and the known_locations passed to resolve_tool
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # which exit behaviour the planted fake vitest exhibits (None = vitest absent)
    _exit_scenario: VitestExitScenario | None = field(default=None)
    _vitest_planted: bool = field(default=False)
    # child-interpreter probe results
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-vitest fixtures) ---------------------

    def given_target_with_fake_vitest(self, scenario: VitestExitScenario) -> None:
        """Plant a REAL chmod+x fake ``vitest`` exhibiting ``scenario``'s exit code.

        Used by AC-1 (GREEN -> PASS), AC-2 (RED -> FAIL), AC-4 (records argv/cwd).
        The fake vitest is a real shell script on a controlled PATH that the
        run-facet resolves via the shared resolve_tool PATH rung and shells like
        any vitest. This is the explicit FAKE-vitest determinism approach: the
        exit-semantics are exercised end-to-end through the REAL run-facet WITHOUT a
        real Node / vitest toolchain (absent in CI). The fake ALSO records its argv
        + cwd to a record file so AC-4 can assert the declared subcommand was
        shelled as-is at cwd=target_root.
        """
        root = self._ensure_root()
        target = root / "target-package"
        target.mkdir(parents=True, exist_ok=True)
        # a real package.json declaring vitest so the target is a genuine JS/TS tree
        # the run-facet runs in (mirrors the test_runner_port vitest registry row).
        (target / "package.json").write_text(
            '{\n  "name": "fixture",\n  "devDependencies": {"vitest": "^1.0.0"}\n}\n',
            encoding="utf-8",
        )
        self._target_root = target
        self._record_path = root / "vitest-argv-record.txt"
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_vitest(path_bin / _VITEST_NAME, scenario, self._record_path)
        # the fake vitest is on PATH (resolve_tool PATH rung); known_locations empty
        self._child_path = str(path_bin)
        self._known_locations = []
        self._exit_scenario = scenario
        self._vitest_planted = True

    def given_target_with_vitest_absent_everywhere(self) -> None:
        """Fixture for AC-3 (vitest-unresolvable).

        A real JS/TS target tree, but vitest exists NOWHERE: PATH is an empty dir
        AND the known_locations dirs are real-but-empty. The run-facet's
        resolve_tool scale exhausts -> the run-facet must degrade LOUD to
        INDETERMINATE naming the remediation (NOT a silent pass, NOT a FAIL).
        """
        root = self._ensure_root()
        target = root / "target-package"
        target.mkdir(parents=True, exist_ok=True)
        (target / "package.json").write_text(
            '{\n  "name": "fixture",\n  "devDependencies": {"vitest": "^1.0.0"}\n}\n',
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
        self._vitest_planted = False

    # ---- when (drive the REAL SUT in a child interpreter) -------------------

    def when_the_run_facet_runs_the_command(self) -> None:
        """Invoke the REAL ``run_vitest_scope`` over the fixture in a child.

        Drives the run-facet end-to-end: the child imports vitest_runner + the
        port, builds a ``RunnerAdapter(name="vitest")``, and calls
        ``run_vitest_scope(adapter, target_root, declared_command)``. The run-facet
        resolves the (fake or absent) vitest via resolve_tool, shells the declared
        command at cwd=target_root, and maps the exit code to a verdict. The child
        prints a machine-readable marker:
          - ``VERDICT:PASS`` / ``VERDICT:FAIL`` from a returned
            ``RunVerdict(passed=...)``,
          - ``VERDICT:INDETERMINATE:<reason>`` when the run-facet raises
            ``RunnerAdapterUnavailable`` (the degrade-LOUD channel) -- carried
            DISTINCTLY from FAIL.
        At HEAD vitest_runner is absent -> the child import raises
        ModuleNotFoundError (rc != 0, no marker), captured here as the observable.
        """
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(_DECLARED_COMMAND)!r}\n"
            f"runner_mod = importlib.import_module({_VITEST_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            f"adapter = port.RunnerAdapter(name={_VITEST_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = runner_mod.run_vitest_scope(\n"
            "        adapter, pathlib.Path(target_root), command)\n"
            "except unavailable as exc:\n"
            "    print('VERDICT:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('VERDICT:' + ('PASS' if verdict.passed else 'FAIL'))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the run-facet OUTCOME -- the port-exposed observable) -

    def then_the_verdict_is(self, expected: RunnerVerdict) -> None:
        """The run-facet mapped the vitest exit code to ``expected`` verdict.

        Used by AC-1 (PASS), AC-2 (FAIL), and AC-3 (INDETERMINATE
        vitest-unresolvable). Asserts the child reported the exact verdict marker.
        The FAIL vs INDETERMINATE distinction is load-bearing: a legit vitest RED
        must be FAIL (propagated), a vitest-absent must be INDETERMINATE -- never
        the other way, never a silent pass.

        Active-RED at HEAD: vitest_runner is absent, the child import fails (rc != 0,
        no ``VERDICT:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the vitest run-facet must run the declared command and map the exit "
            f"code to the {expected.name} verdict; at HEAD {_VITEST_RUNNER_MODULE} "
            f"is absent so the child probe could not produce a verdict. "
            f"{self._probe_observed()}"
        )
        marker = self._probe_out.split("VERDICT:", 1)[1].strip().splitlines()[0]
        observed = marker.split(":", 1)[0]  # PASS | FAIL | INDETERMINATE
        assert observed == expected.name, (
            f"the vitest run-facet mapped the {self._exit_scenario} fixture to the "
            f"WRONG verdict: expected {expected.name}, got {observed!r} "
            f"(marker={marker!r}). The exit-semantics require: exit 0 -> PASS, "
            f"non-zero-with-tests -> FAIL (propagated, NOT indeterminate), "
            f"vitest-absent -> INDETERMINATE. (Unlike cargo there is NO exit-4 "
            f"empty-scope row for vitest.) {self._probe_observed()}"
        )

    def then_the_indeterminate_names_the_remediation(self) -> None:
        """The vitest-unresolvable INDETERMINATE carries an actionable remediation.

        Used by AC-3. Asserts the INDETERMINATE reason NAMES an install path
        (``vitest`` / ``install`` / ``npm``) -- the LOUD degrade resolve_tool's
        named remediation flows through, never a bare/silent failure.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:`` marker
        -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:INDETERMINATE:" in self._probe_out, (
            "an unresolvable vitest (absent after the full discovery scale) must "
            "yield a LOUD INDETERMINATE naming the remediation (never a silent "
            f"degrade, never a FAIL); at HEAD {_VITEST_RUNNER_MODULE} is absent so "
            f"the child probe could not produce it. {self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("VERDICT:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        lowered = reason.lower()
        assert any(token in lowered for token in ("install", "vitest", "npm")), (
            "the INDETERMINATE reason must NAME an actionable install path (e.g. "
            "'install vitest' / 'npm install') so the operator can act -- not a "
            f"bare failure; got {reason!r}. {self._probe_observed()}"
        )

    def then_the_declared_subcommand_was_shelled(self) -> None:
        """The fake vitest recorded the declared subcommand as-is (AC-4).

        The run-facet must shell the feature's declared command tokens AFTER the
        resolved binary VERBATIM -- the adapter does NOT choose the subcommand (the
        feature declares ``vitest run``, mirroring go/cargo D5). Reads the record
        file the fake vitest wrote its argv into and asserts the tail equals the
        declared subcommand.

        Active-RED at HEAD: vitest_runner is absent, the fake vitest was never
        shelled, the record file is absent / the child probe failed -> this
        AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the vitest run-facet must shell the fake vitest (which records its "
            f"argv) and return a verdict; at HEAD {_VITEST_RUNNER_MODULE} is absent "
            f"so the fake vitest was never invoked. {self._probe_observed()}"
        )
        recorded = self._read_record()
        assert recorded is not None, (
            "the fake vitest must have been SHELLED by the run-facet (so it recorded "
            "its argv); the record file is absent -- the run-facet did not invoke "
            f"the resolved vitest. {self._probe_observed()}"
        )
        observed_argv = recorded["argv"][1:]  # drop argv[0] (the binary path)
        assert tuple(observed_argv) == _DECLARED_SUBCOMMAND, (
            "the vitest run-facet must shell the feature's declared subcommand AS-IS "
            f"(the adapter does NOT choose it): expected {list(_DECLARED_SUBCOMMAND)}, "
            f"the fake vitest was invoked with {observed_argv!r}. "
            f"{self._probe_observed()}"
        )

    def then_the_cwd_was_the_target_root(self) -> None:
        """The fake vitest recorded a cwd equal to the target root (AC-4).

        The run-facet must shell the declared command at ``cwd=target_root`` (so
        ``vitest run`` resolves the target's own config + tests). Reads the cwd the
        fake vitest recorded and asserts it is the target root.

        Active-RED at HEAD: vitest_runner is absent, the fake vitest was never
        shelled, the record file is absent -> this AssertionError fires.
        """
        recorded = self._read_record()
        assert recorded is not None, (
            "the fake vitest must have been SHELLED by the run-facet (so it recorded "
            "its cwd); the record file is absent -- the run-facet did not invoke "
            f"the resolved vitest. {self._probe_observed()}"
        )
        observed_cwd = Path(recorded["cwd"]).resolve()
        expected_cwd = Path(str(self._target_root)).resolve()
        assert observed_cwd == expected_cwd, (
            "the vitest run-facet must shell the declared command at cwd=target_root "
            f"(so 'vitest run' resolves the target's config + tests): expected "
            f"{str(expected_cwd)!r}, the fake vitest ran in {str(observed_cwd)!r}. "
            f"{self._probe_observed()}"
        )

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-vitest-runner-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_vitest(
        target: Path,
        scenario: VitestExitScenario,
        record_path: Path,
    ) -> Path:
        """Write a REAL chmod+x fake ``vitest`` exhibiting ``scenario``'s exit code.

        A POSIX shell script (the run-facet shells it like a real vitest). The
        script:
          1. RECORDS its argv + cwd to ``record_path`` as two lines:
               ARGV<TAB>arg0<TAB>arg1<TAB>...
               CWD<TAB><working-directory>
             (so AC-4 can assert the declared subcommand was shelled as-is at
             cwd=target_root -- the declared-command-shelled observable).
          2. emits vitest-shaped output and exits with the scenario's code:
               - GREEN -> emit a passing summary, exit 0.
               - RED   -> emit a failing summary (tests EXECUTED), exit 1.

        It does NOT interpret its argv (the declared subcommand) to choose an
        outcome -- the fixture controls the exit code deterministically, independent
        of a real vitest toolchain. (Unlike cargo there is no exit-4 row; like go,
        empty-scope is OUT-OF-SCOPE.)
        """
        exit_code = {VitestExitScenario.GREEN: 0, VitestExitScenario.RED: 1}[scenario]
        summary = {
            VitestExitScenario.GREEN: "echo 'Test Files  1 passed (1)'",
            VitestExitScenario.RED: (
                "echo 'FAIL  src/thing.test.ts > thing'\n"
                "echo 'Test Files  1 failed (1)'"
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
        """Read the argv + cwd the fake vitest recorded (AC-4), or None if absent.

        Returns ``{"argv": [arg0, arg1, ...], "cwd": "<dir>"}`` parsed from the
        tab-separated record file, or ``None`` when the fake vitest was never
        shelled (the file does not exist -- e.g. at HEAD where the run-facet is
        absent).
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
        run-facet resolves the FAKE vitest, never an ambient host vitest, and the
        vitest-absent fixture genuinely finds nothing). HOME is the fixture's tmp
        home and the Node env (NODE_PATH / npm_config_prefix / NPM_CONFIG_PREFIX) is
        neutralised so a known-location / global node_modules dir can never leak a
        real vitest. ``src`` is prepended to PYTHONPATH so the in-tree ``des``
        package is importable.
        """
        env = dict(os.environ)
        env["PATH"] = self._child_path
        env["HOME"] = self._child_home
        # neutralise the Node env so a real host vitest can never leak into
        # resolution.
        for var in ("NODE_PATH", "npm_config_prefix", "NPM_CONFIG_PREFIX"):
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
            f"vitest_planted={self._vitest_planted!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"record_present={self._record_path.is_file() if self._record_path else False!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/vitest_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=vitest_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
