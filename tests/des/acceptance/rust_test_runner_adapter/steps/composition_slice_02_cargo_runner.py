"""Composition root for f-rust-test-runner-adapter slice-02 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
production slice-02 SUT imported + invoked in a CHILD interpreter. The SUT is
three net-new production seams the feature ships:

  C1  the cargo run-facet ``run_cargo_scope`` (cargo_runner.py) -- shells the
      target's cargo over a real subprocess, mapping the 4 §C1 exit-semantics to
      PASS / FAIL / INDETERMINATE.
  C2  the plugin-populated ``RunnerRegistry`` (runner_registry.py) -- the
      ``GLOBAL_REGISTRY`` + the ``seed_runner_registry()`` D6 entry-points seeding.
  C3  the ``nwave-lang-rust`` ``LanguageAdapterPlugin`` (nwave_lang_rust.py) --
      whose ``register_adapters(registry)`` writes ``run_cargo_scope`` under the
      EXISTING ``"cargo-test"`` token (D8 -- no rename); the UNIFICATION.

WHY a child interpreter (not a thin in-process call): at HEAD NONE of
``cargo_runner`` / ``runner_registry`` / ``nwave_lang_rust`` exist (Tsunami
callers-of register_adapters: 0; the run dispatch is a hardcoded
``if self.name == "pytest"``). Importing them in THIS process would raise
ModuleNotFoundError at COLLECTION -> a BROKEN test, not active-RED. Running the
import in a child ``python -c`` makes the absent module a CAPTURED observable
(child rc != 0, no ``VERDICT:``/``REGISTERED:`` marker) that each Then turns into
a SEMANTIC AssertionError. Same pattern as the slice-01 harness.

ZERO ``des.adapters.*`` import in THIS process (slice-02-RC2 discipline): the SUT
is only ever imported in the CHILD interpreter, never here.

FAKE-cargo determinism (AT-4/5/6 -- explicit fixture approach): the exit-semantics
ATs do NOT require a real Rust toolchain (absent in CI). The fixture plants a REAL
chmod+x ``cargo`` script on a controlled child PATH that emits a controlled exit
code + output:
  - GREEN  -> exit 0 (all pass)                  -> PASS verdict.
  - RED    -> emit test output, then exit 1      -> FAIL verdict (propagated, NOT
              swallowed into INDETERMINATE).
  - NO_MATCH -> exit 4 (cargo "no test matched") -> INDETERMINATE empty-scope.
The run-facet resolves this fake cargo via the slice-01 ``resolve_tool`` scale
(PATH rung) and shells it exactly like a real cargo -- so the exit-semantics are
exercised end-to-end through the REAL run-facet, deterministically, in CI.

AT-7 (the unification pin) is a PURE in-process/child WIRING check: a fresh child
imports the plugin + the registry, runs ``plugin.register_adapters(registry)``,
and asserts ``registry.lookup("cargo-test")`` resolves to the cargo run-facet --
i.e. the runner registers THROUGH the plugin, never hardcoded. No fake-cargo
needed there. The cargo-unresolvable continuation drives ``run_cargo_scope`` over
a fixture where cargo is absent everywhere (PATH scrubbed, known-locations empty)
and asserts the LOUD INDETERMINATE via ``resolve_tool``'s named remediation.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the slice-02 modules are
absent, so the child import fails (rc != 0, no marker) and each Then fires a
semantic AssertionError. GREEN once DELIVER ships cargo_runner.py +
runner_registry.py + nwave_lang_rust.py. No @skip, no collection/import error in
THIS process.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_cargo_runner import CargoExitScenario, RunnerVerdict


# The production seams the child interpreter imports + invokes (the SUT). All
# absent at HEAD -> the child import raises ModuleNotFoundError THERE (captured
# rc/stderr), never an import error in this test process.
_CARGO_RUNNER_MODULE = "des.adapters.driven.runner.cargo_runner"
_RUNNER_REGISTRY_MODULE = "des.adapters.driven.runner.runner_registry"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The EXISTING token TestRunnerPort.resolve already returns for a Cargo.toml
# target (test_runner_port.py:134); the registry key + the plugin registration
# key MUST agree on THIS token (D8 -- no rename).
_CARGO_TOKEN = "cargo-test"

# The fake-cargo binary name the run-facet resolves + shells. It is literally
# "cargo" so the planted fake satisfies resolve_tool("cargo", ...) on the PATH
# rung exactly as a real cargo would.
_CARGO_NAME = "cargo"

# The declared feature-scoped test_command tokens passed to the run-facet as the
# per-runner "scope" (NOT a node-id list -- §C1 step 3). The leading "cargo" is
# the binary the run-facet resolves; the rest are the subcommand the fake echoes.
_DECLARED_COMMAND = (_CARGO_NAME, "nextest", "run", "--test", "ws_driver")


@dataclass
class CargoRunnerComposition:
    """Drives the REAL slice-02 SUT over a controlled filesystem + FAKE cargo."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    # the target tree the run-facet runs cargo in (cwd)
    _target_root: Path | None = field(default=None)
    # the controlled child env: PATH carrying (or scrubbed of) the fake cargo,
    # HOME under the fixture, and the known_locations passed to resolve_tool
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _known_locations: list[str] = field(default_factory=list)
    # which exit behaviour the planted fake cargo exhibits (None = cargo absent)
    _exit_scenario: CargoExitScenario | None = field(default=None)
    _cargo_planted: bool = field(default=False)
    # child-interpreter probe results
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-cargo fixtures) ----------------------

    def given_target_with_fake_cargo(self, scenario: CargoExitScenario) -> None:
        """Plant a REAL chmod+x fake ``cargo`` exhibiting ``scenario``'s exit code.

        Used by AT-4 (GREEN -> PASS), AT-5 (RED -> FAIL), AT-6 (NO_MATCH ->
        INDETERMINATE). The fake cargo is a real shell script on a controlled
        PATH that the run-facet resolves via the slice-01 resolve_tool PATH rung
        and shells like any cargo. This is the explicit FAKE-cargo determinism
        approach: the §C1 exit-semantics are exercised end-to-end through the REAL
        run-facet WITHOUT a real Rust toolchain (absent in CI).
        """
        root = self._ensure_root()
        target = root / "target-crate"
        target.mkdir(parents=True, exist_ok=True)
        # a real Cargo.toml so the target is a genuine Rust tree the run-facet runs in
        (target / "Cargo.toml").write_text(
            '[package]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        self._target_root = target
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_cargo(path_bin / _CARGO_NAME, scenario)
        # the fake cargo is on PATH (resolve_tool PATH rung); known_locations empty
        self._child_path = str(path_bin)
        self._known_locations = []
        self._exit_scenario = scenario
        self._cargo_planted = True

    def given_target_with_cargo_absent_everywhere(self) -> None:
        """Fixture for the cargo-unresolvable continuation of AT-7.

        A real Rust target tree, but cargo exists NOWHERE: PATH is an empty dir
        AND the known_locations dirs are real-but-empty. The run-facet's
        resolve_tool scale exhausts -> the run-facet must degrade LOUD to
        INDETERMINATE naming the remediation (NOT a silent pass, NOT a FAIL).
        """
        root = self._ensure_root()
        target = root / "target-crate"
        target.mkdir(parents=True, exist_ok=True)
        (target / "Cargo.toml").write_text(
            '[package]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        self._target_root = target
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        empty_known = root / "empty-known"
        empty_known.mkdir(parents=True, exist_ok=True)
        self._child_path = str(empty_path)
        self._known_locations = [str(empty_known)]
        self._exit_scenario = None
        self._cargo_planted = False

    # ---- when (drive the REAL SUT in a child interpreter) --------------------

    def when_the_run_facet_runs_the_command(self) -> None:
        """Invoke the REAL ``run_cargo_scope`` over the fixture in a child.

        Drives the run-facet (C1) end-to-end: the child imports cargo_runner +
        the port, builds a ``RunnerAdapter(name="cargo-test")``, and calls
        ``run_cargo_scope(adapter, target_root, declared_command)``. The
        run-facet resolves the (fake or absent) cargo via resolve_tool, shells
        the declared command, and maps the exit code to a verdict. The child
        prints a machine-readable marker:
          - ``VERDICT:PASS`` / ``VERDICT:FAIL`` from a returned
            ``RunVerdict(passed=...)``,
          - ``VERDICT:INDETERMINATE:<reason>`` when the run-facet raises
            ``RunnerAdapterUnavailable`` (the degrade-LOUD channel) -- carried
            DISTINCTLY from FAIL.
        At HEAD cargo_runner is absent -> the child import raises
        ModuleNotFoundError (rc != 0, no marker), captured here as the observable.
        """
        program = (
            "import importlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(_DECLARED_COMMAND)!r}\n"
            f"runner_mod = importlib.import_module({_CARGO_RUNNER_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            "import pathlib\n"
            f"adapter = port.RunnerAdapter(name={_CARGO_TOKEN!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = runner_mod.run_cargo_scope(\n"
            "        adapter, pathlib.Path(target_root), command)\n"
            "except unavailable as exc:\n"
            "    print('VERDICT:INDETERMINATE:' + str(exc))\n"
            "else:\n"
            "    print('VERDICT:' + ('PASS' if verdict.passed else 'FAIL'))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    def when_the_plugin_registers_through_the_registry(self) -> None:
        """Drive the UNIFICATION (AT-7): the plugin registers the cargo run-facet.

        A fresh child imports the ``nwave-lang-rust`` plugin + the runner
        registry, runs ``plugin.register_adapters(registry)`` over a registry
        instance, then looks up the EXISTING ``"cargo-test"`` token and reports
        whether it resolved to the cargo run-facet. The check is structural: a
        resolved facet must BE the same callable the cargo_runner module exposes
        (``run_cargo_scope``) -- proving the runner registers THROUGH the plugin,
        never via a hardcoded ``if name == ...`` branch. The child prints:
          - ``REGISTERED:run_cargo_scope`` when the looked-up facet IS
            ``cargo_runner.run_cargo_scope``,
          - ``REGISTERED-WRONG:<repr>`` when the token resolves to something else,
          - ``NOT-REGISTERED`` when the token is absent after register_adapters.

        The plugin class name is not coupled: the child imports the
        ``nwave_lang_rust`` module and instantiates its single concrete
        ``LanguageAdapterPlugin`` subclass (discovered by ABC subclass-scan), so
        the AT does not lock onto a class name the design has not frozen.
        """
        program = (
            "import importlib, inspect\n"
            f"plugin_mod = importlib.import_module({'scripts.install.plugins.nwave_lang_rust'!r})\n"
            f"registry_mod = importlib.import_module({_RUNNER_REGISTRY_MODULE!r})\n"
            f"runner_mod = importlib.import_module({_CARGO_RUNNER_MODULE!r})\n"
            "from des.ports.language_adapter_plugin import LanguageAdapterPlugin\n"
            # find the single concrete LanguageAdapterPlugin subclass in the module
            "candidates = [\n"
            "    obj for _n, obj in inspect.getmembers(plugin_mod, inspect.isclass)\n"
            "    if issubclass(obj, LanguageAdapterPlugin)\n"
            "    and obj is not LanguageAdapterPlugin\n"
            "    and obj.__module__ == plugin_mod.__name__\n"
            "]\n"
            "if not candidates:\n"
            "    raise SystemExit('no concrete LanguageAdapterPlugin in nwave_lang_rust')\n"
            "plugin = candidates[0]()\n"
            # a fresh registry instance (not the global) so the AT proves the
            # plugin POPULATES a registry, independent of any module-level state
            "registry = registry_mod.RunnerRegistry()\n"
            "plugin.register_adapters(registry)\n"
            f"facet = registry.lookup({_CARGO_TOKEN!r})\n"
            "if facet is None:\n"
            "    print('NOT-REGISTERED')\n"
            "elif facet is runner_mod.run_cargo_scope:\n"
            "    print('REGISTERED:run_cargo_scope')\n"
            "else:\n"
            "    print('REGISTERED-WRONG:' + repr(facet))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the run-facet OUTCOME -- the port-exposed observable) -

    def then_the_verdict_is(self, expected: RunnerVerdict) -> None:
        """The run-facet mapped the cargo exit code to ``expected`` verdict.

        Used by AT-4 (PASS), AT-5 (FAIL), AT-6 (INDETERMINATE empty-scope), and
        the AT-7 cargo-unresolvable continuation (INDETERMINATE). Asserts the
        child reported the exact verdict marker. The FAIL vs INDETERMINATE
        distinction is load-bearing: a legit cargo RED must be FAIL (propagated),
        a no-test-run (exit 4) / cargo-absent must be INDETERMINATE -- never the
        other way, never a silent pass.

        Active-RED at HEAD: the slice-02 modules are absent, the child import
        fails (rc != 0, no ``VERDICT:`` marker) -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:" in self._probe_out, (
            f"the cargo run-facet must run the declared command and map the exit "
            f"code to the {expected.name} verdict; at HEAD {_CARGO_RUNNER_MODULE} "
            f"is absent so the child probe could not produce a verdict. "
            f"{self._probe_observed()}"
        )
        marker = self._probe_out.split("VERDICT:", 1)[1].strip().splitlines()[0]
        observed = marker.split(":", 1)[0]  # PASS | FAIL | INDETERMINATE
        assert observed == expected.name, (
            f"the cargo run-facet mapped the {self._exit_scenario} fixture to the "
            f"WRONG verdict: expected {expected.name}, got {observed!r} "
            f"(marker={marker!r}). The §C1 exit-semantics require: exit 0 -> PASS, "
            f"non-zero-with-tests -> FAIL (propagated, NOT indeterminate), exit 4 "
            f"-> INDETERMINATE empty-scope, cargo-absent -> INDETERMINATE. "
            f"{self._probe_observed()}"
        )

    def then_the_indeterminate_names_the_remediation(self) -> None:
        """The cargo-unresolvable INDETERMINATE carries an actionable remediation.

        Used by the AT-7 cargo-unresolvable continuation (the WSL2-gotcha
        continuation). Asserts the INDETERMINATE reason NAMES an install path
        (``rustup`` / ``cargo install`` / ``install``) -- the LOUD degrade
        resolve_tool's named remediation flows through, never a bare/silent
        failure.

        Active-RED at HEAD: the module is absent -> no ``INDETERMINATE:`` marker
        -> this AssertionError fires.
        """
        assert self._probe_rc == 0 and "VERDICT:INDETERMINATE:" in self._probe_out, (
            "an unresolvable cargo (absent after the full discovery scale) must "
            "yield a LOUD INDETERMINATE naming the remediation (never a silent "
            f"degrade, never a FAIL); at HEAD {_CARGO_RUNNER_MODULE} is absent so "
            f"the child probe could not produce it. {self._probe_observed()}"
        )
        reason = (
            self._probe_out.split("VERDICT:INDETERMINATE:", 1)[1]
            .strip()
            .splitlines()[0]
        )
        lowered = reason.lower()
        assert any(token in lowered for token in ("install", "rustup", "cargo")), (
            "the INDETERMINATE reason must NAME an actionable install path (e.g. "
            "'install via rustup' / 'cargo install') so the operator can act -- "
            f"not a bare failure; got {reason!r}. {self._probe_observed()}"
        )

    def then_the_token_resolves_to_the_cargo_facet(self) -> None:
        """After the plugin's register_adapters, the registry resolves the facet.

        Used by AT-7 (the unification pin). Asserts the child reported
        ``REGISTERED:run_cargo_scope`` -- i.e. ``registry.lookup("cargo-test")``,
        AFTER ``plugin.register_adapters(registry)``, IS the cargo run-facet. This
        proves the runner registers THROUGH the ``nwave-lang-rust`` plugin under
        the EXISTING ``"cargo-test"`` token (D8), NOT via a hardcoded
        ``if name == "pytest"`` branch -- the unification Ale directed.

        Active-RED at HEAD: nwave_lang_rust + runner_registry are absent, the
        child import fails (rc != 0, no ``REGISTERED:`` marker) -> AssertionError.
        """
        assert (
            self._probe_rc == 0 and "REGISTERED:run_cargo_scope" in self._probe_out
        ), (
            "the cargo run-facet must register THROUGH "
            "nwave-lang-rust.register_adapters(registry) under the EXISTING "
            f"{_CARGO_TOKEN!r} token (the unification): after register_adapters, "
            f"registry.lookup({_CARGO_TOKEN!r}) must resolve to cargo_runner."
            "run_cargo_scope. At HEAD the registry + plugin are absent so the "
            "child probe could not wire it. Observed markers: NOT-REGISTERED "
            "means the plugin did not register the token; REGISTERED-WRONG means "
            "it registered a different facet (the runner must register THROUGH "
            f"the plugin, not hardcoded). {self._probe_observed()}"
        )

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-cargo-runner-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_cargo(target: Path, scenario: CargoExitScenario) -> Path:
        """Write a REAL chmod+x fake ``cargo`` exhibiting ``scenario``'s exit code.

        A POSIX shell script (the run-facet shells it like a real cargo). The
        script emits cargo-shaped output and exits with the scenario's code:
          - GREEN    -> emit a passing summary, exit 0.
          - RED      -> emit a failing summary (tests EXECUTED), exit 1.
          - NO_MATCH -> emit a "no tests to run" notice, exit 4.
        It IGNORES its argv (the declared subcommand) -- the fixture controls the
        outcome deterministically, independent of a real cargo/nextest toolchain.
        """
        exit_code = {
            CargoExitScenario.GREEN: 0,
            CargoExitScenario.RED: 1,
            CargoExitScenario.NO_MATCH: 4,
        }[scenario]
        summary = {
            CargoExitScenario.GREEN: "echo 'test result: ok. 4 passed; 0 failed'",
            CargoExitScenario.RED: (
                "echo 'running 4 tests'\necho 'test result: FAILED. 3 passed; 1 failed'"
            ),
            CargoExitScenario.NO_MATCH: "echo 'no tests to run'",
        }[scenario]
        target.write_text(
            f"#!/bin/sh\n{summary}\nexit {exit_code}\n",
            encoding="utf-8",
        )
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_python_c(self, program: str) -> tuple[int, str, str]:
        """Run a one-shot ``python -c`` probe in a child interpreter.

        HERMETIC env: PATH is set to ONLY the fixture's controlled dir (so the
        run-facet resolves the FAKE cargo, never an ambient host cargo, and the
        cargo-absent fixture genuinely finds nothing). HOME is the fixture's tmp
        home and CARGO_HOME is neutralised so a ``~`` known-location can never
        leak a real cargo. ``src`` is prepended to PYTHONPATH so the in-tree
        ``des`` package (and ``scripts`` for the plugin) is importable.
        """
        env = dict(os.environ)
        env["PATH"] = self._child_path
        env["HOME"] = self._child_home
        env.pop("CARGO_HOME", None)
        root = _repo_root()
        src = str(root / "src")
        existing = env.get("PYTHONPATH", "")
        # repo root on PYTHONPATH too so ``scripts.install.plugins.nwave_lang_rust``
        # is importable in the child (the plugin lives under scripts/, not src/).
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
            f"cargo_planted={self._cargo_planted!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/rust_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=rust_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
