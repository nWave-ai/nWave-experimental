"""Composition root for unified-language-adapter-registry slice-02 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): every
scenario drives the REAL production entry (`des.cli.run_contract_gate.main`,
or the REAL `LanguageAdapterRegistry`) inside a CHILD interpreter (`python -c`
one-shot program), never importing the net-new slice-02 production modules in
THIS test process. Mirrors the shipped
`tests/des/acceptance/rust_test_runner_adapter/steps/composition_slice_02_cargo_runner.py`
precedent exactly (fresh-registry unification pin + child-interpreter
wiring), generalized from the cargo run-facet to the 3 NEW
`LanguageAdapterRegistry` slots this feature ships.

WHY a child interpreter (not a thin in-process call): at HEAD
`scripts/install/plugins/nwave_lang_python.py` and the 3 new adapters
(`des.adapters.driven.{contract_gate,e2e,robustness}.*`) do NOT exist.
Importing them in THIS process would raise `ModuleNotFoundError` at
COLLECTION -> a BROKEN test, not active-RED. Running the import in a child
`python -c` makes the absent module a CAPTURED observable (child rc != 0, no
success marker) that each Then turns into a semantic AssertionError. Same
pattern as the shipped cargo-runner / e2-routing harnesses.

ZERO `des.adapters.*` / `scripts.install.plugins.nwave_lang_python` import in
THIS process: the SUT is only ever imported inside the child.

Scenario 1 (walking-skeleton) and Scenario 2 (parity) both drive
`GLOBAL_REGISTRY` -- the SAME production module-level singleton
`des.cli.run_contract_gate.main`'s seam consults -- from WITHIN one child
process: the child (a) imports the plugin, (b) calls
`plugin.register_adapters(GLOBAL_REGISTRY)`, THEN (c) calls the REAL
`main(["--repo", ...])`. This is the REAL registration + REAL seam, in one
process, without needing to fabricate an `nwave.lang.adapter` entry-point
distribution (that packaging/discovery machinery is unchanged, already
shipped infra for `nwave-lang-rust` -- out of this feature's C8-C11 scope,
per the Reuse Analysis).

Scenario 3 (the unification pin) constructs a FRESH `LanguageAdapterRegistry`
instance (never the global) inside its own child, mirroring AT-7 of the
shipped cargo-runner precedent exactly: the plugin must populate a registry
it is HANDED, independent of any module-level state.

Active-RED scaffold (atdd_pure -- NOT @skip). At HEAD:
  * `scripts/install/plugins/nwave_lang_python.py` is absent (Component C11).
  * `des.adapters.driven.contract_gate.pytest_contract_gate_adapter`,
    `...e2e.python_environmental_e2e_adapter`, and
    `...robustness.python_robustness_density_adapter` are absent (C8-C10).
  * `_maybe_route_through_registered_contract_gate` (shipped, slice-01) emits
    NO `ContractGateResult`-shaped event of its own on the routed arm today --
    DISTILL pins that DELIVER adds the emit (open-question resolution above).
Every child program below imports `scripts.install.plugins.nwave_lang_python`
first; ModuleNotFoundError propagates out of the child uncaught -> non-zero
exit, no success marker on stdout -> every Then fires a named AssertionError.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import ContractGateRunObservable, RegistrySlotResolution


# The net-new production modules this slice ships (all absent at HEAD). Named
# as STRINGS only -- never imported in this process (P1 discipline).
_PLUGIN_MODULE = "scripts.install.plugins.nwave_lang_python"
_LANGUAGE_ADAPTER_PLUGIN_MODULE = "des.ports.language_adapter_plugin"
_REGISTRY_MODULE = "des.adapters.driven.runner.runner_registry"
_GATE_MODULE = "des.cli.run_contract_gate"

# DISTILL-pinned observable (feature-delta [REF] Open questions resolution):
# the seam's routed arm must emit this NEW boolean field on the EXISTING
# `ContractGateResult` event, additive + back-compatible.
_ROUTED_FIELD = "routed_via_registered_adapter"


def _find_and_register_snippet() -> str:
    """Child-program fragment: import the plugin, register into GLOBAL_REGISTRY.

    Discovers the single concrete `LanguageAdapterPlugin` subclass in the
    module by ABC subclass-scan (mirrors the shipped cargo-runner precedent)
    so the AT does not lock onto a class name the design has not frozen.
    """
    return textwrap.dedent(
        f"""\
        import importlib, inspect
        plugin_mod = importlib.import_module({_PLUGIN_MODULE!r})
        from {_LANGUAGE_ADAPTER_PLUGIN_MODULE} import LanguageAdapterPlugin
        candidates = [
            obj for _n, obj in inspect.getmembers(plugin_mod, inspect.isclass)
            if issubclass(obj, LanguageAdapterPlugin)
            and obj is not LanguageAdapterPlugin
            and obj.__module__ == plugin_mod.__name__
        ]
        if not candidates:
            raise SystemExit("no concrete LanguageAdapterPlugin in nwave_lang_python")
        plugin = candidates[0]()
        registry_mod = importlib.import_module({_REGISTRY_MODULE!r})
        plugin.register_adapters(registry_mod.GLOBAL_REGISTRY)
        """
    )


def _drive_gate_snippet(repo: Path) -> str:
    """Child-program fragment: drive the REAL contract-gate entry, print EXIT."""
    return textwrap.dedent(
        f"""\
        gate_mod = importlib.import_module({_GATE_MODULE!r})
        rc = gate_mod.main(["--repo", {str(repo)!r}])
        print("GATE_EXIT:" + str(rc))
        """
    )


@dataclass
class Slice02Composition:
    """Drives the REAL slice-02 SUT (plugin + registry + gate) via child interpreters."""

    _passing_repo: Path | None = field(default=None)
    _failing_repo: Path | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)
    _registered_run: ContractGateRunObservable | None = field(default=None)
    _unregistered_run: ContractGateRunObservable | None = field(default=None)
    _slot_resolution: RegistrySlotResolution | None = field(default=None)

    # ---- given (REAL filesystem fixtures) -----------------------------------

    def given_passing_python_codebase(self, tmp_path: Path) -> None:
        """A real Python target repo whose whole-tree pytest suite is GREEN."""
        repo = tmp_path / "passing-codebase"
        tests_dir = repo / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_trivial.py").write_text(
            "def test_ok():\n    assert True\n", encoding="utf-8"
        )
        self._passing_repo = repo

    def given_failing_python_codebase(self, tmp_path: Path) -> None:
        """A real Python target repo whose whole-tree pytest suite is RED."""
        repo = tmp_path / "failing-codebase"
        tests_dir = repo / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_trivial.py").write_text(
            "def test_broken():\n    assert False\n", encoding="utf-8"
        )
        self._failing_repo = repo

    # ---- when (drive the REAL SUT in a child interpreter) -------------------

    def when_plugin_wires_contract_gate_adapter(self) -> None:
        """Arm the WS run: register the Python plugin's adapters, drive the gate.

        Snapshots the read-only-contract universe BEFORE the child runs
        (Mandate 8), then runs ONE child program that (a) registers the
        plugin's adapters into the REAL `GLOBAL_REGISTRY`, then (b) drives the
        REAL `main(["--repo", ...])` -- proving the seam's registered arm is
        reachable end-to-end, in one process.
        """
        assert self._passing_repo is not None, (
            "the passing codebase must be armed (Given) before driving the gate."
        )
        self._universe_before = self.capture_universe(self._passing_repo)
        program = (
            "import importlib\n"
            + _find_and_register_snippet()
            + _drive_gate_snippet(self._passing_repo)
        )
        self._registered_run = self._run_and_parse(program)

    def when_gate_runs_registered_then_unregistered(self) -> None:
        """Parity fixture: run the failing codebase WITH, then WITHOUT, the adapter.

        Two independent child processes -- each starts with its OWN empty
        `GLOBAL_REGISTRY` (module-level, process-scoped), so isolation is
        structural, not fixture-managed.
        """
        assert self._failing_repo is not None, (
            "the failing codebase must be armed (Given) before driving the gate."
        )
        registered_program = (
            "import importlib\n"
            + _find_and_register_snippet()
            + _drive_gate_snippet(self._failing_repo)
        )
        self._registered_run = self._run_and_parse(registered_program)

        unregistered_program = "import importlib\n" + _drive_gate_snippet(
            self._failing_repo
        )
        self._unregistered_run = self._run_and_parse(unregistered_program)

    def when_plugin_wires_all_slots(self) -> None:
        """The unification pin (AT-7 precedent): plugin wires a FRESH registry.

        A fresh child imports the plugin + the registry module, constructs a
        NEW `LanguageAdapterRegistry()` (never `GLOBAL_REGISTRY`), calls
        `plugin.register_adapters(registry)` ONCE, then reports whether all 3
        new slots resolved under the plugin's own runner token (`"pytest"`).
        """
        program = textwrap.dedent(
            f"""\
            import importlib, inspect
            plugin_mod = importlib.import_module({_PLUGIN_MODULE!r})
            from {_LANGUAGE_ADAPTER_PLUGIN_MODULE} import LanguageAdapterPlugin
            candidates = [
                obj for _n, obj in inspect.getmembers(plugin_mod, inspect.isclass)
                if issubclass(obj, LanguageAdapterPlugin)
                and obj is not LanguageAdapterPlugin
                and obj.__module__ == plugin_mod.__name__
            ]
            if not candidates:
                raise SystemExit("no concrete LanguageAdapterPlugin in nwave_lang_python")
            plugin = candidates[0]()
            registry_mod = importlib.import_module({_REGISTRY_MODULE!r})
            registry = registry_mod.LanguageAdapterRegistry()
            plugin.register_adapters(registry)
            cg = registry.lookup_contract_gate("pytest")
            e2e = registry.lookup_environmental_e2e("pytest")
            rd = registry.lookup_robustness_density("pytest")
            print(
                "SLOTS:"
                + str(int(cg is not None))
                + str(int(e2e is not None))
                + str(int(rd is not None))
            )
            """
        )
        rc, out, _err = self._run_python_c(program)
        child_import_ok = rc == 0 and "SLOTS:" in out
        bits = ""
        if child_import_ok:
            bits = out.split("SLOTS:", 1)[1].strip().splitlines()[0]
        self._slot_resolution = RegistrySlotResolution(
            child_import_ok=child_import_ok,
            contract_gate_resolved=child_import_ok and bits[:1] == "1",
            environmental_e2e_resolved=child_import_ok and bits[1:2] == "1",
            robustness_density_resolved=child_import_ok and bits[2:3] == "1",
        )

    # ---- observable accessors -------------------------------------------------

    def passing_repo(self) -> Path:
        """The passing codebase path the Given armed (for post-run universe reads)."""
        assert self._passing_repo is not None, (
            "the passing codebase must have been armed (Given) before its path "
            "can be read back."
        )
        return self._passing_repo

    def registered_run(self) -> ContractGateRunObservable:
        assert self._registered_run is not None, (
            "the gate must have been driven with the adapter registered (When) "
            "before this observable is read."
        )
        return self._registered_run

    def unregistered_run(self) -> ContractGateRunObservable:
        assert self._unregistered_run is not None, (
            "the gate must have been driven WITHOUT the adapter registered "
            "(When) before this observable is read."
        )
        return self._unregistered_run

    def slot_resolution(self) -> RegistrySlotResolution:
        assert self._slot_resolution is not None, (
            "the plugin must have wired a fresh registry (When) before this "
            "observable is read."
        )
        return self._slot_resolution

    def diag_registered(self) -> str:
        return self._diag(self._registered_run)

    def diag_unregistered(self) -> str:
        return self._diag(self._unregistered_run)

    def diag_slots(self) -> str:
        r = self._slot_resolution
        if r is None:
            return "(the plugin never wired a registry)"
        return (
            f"(child_import_ok={r.child_import_ok}, "
            f"contract_gate_resolved={r.contract_gate_resolved}, "
            f"environmental_e2e_resolved={r.environmental_e2e_resolved}, "
            f"robustness_density_resolved={r.robustness_density_resolved})"
        )

    @staticmethod
    def _diag(obs: ContractGateRunObservable | None) -> str:
        if obs is None:
            return "(the gate was never driven)"
        return (
            f"(child_import_ok={obs.child_import_ok}, exit_code={obs.exit_code}, "
            f"event_found={obs.event_found}, "
            f"routed_via_registered_adapter={obs.routed_via_registered_adapter}, "
            f"runner={obs.runner!r}, pytest_exit_code={obs.pytest_exit_code}, "
            f"passed={obs.passed}, stdout={obs.stdout!r}, "
            f"stderr_tail={obs.stderr[-600:]!r})"
        )

    # ---- universe (Mandate 8 -- port-exposed observable snapshot) -----------

    def capture_universe(self, repo: Path) -> dict[str, object]:
        """Port-exposed observable snapshot for `assert_state_delta` (Mandate 8).

        The contract gate reads the codebase and must not mutate its Python
        source tree. The universe is the repo's existence and the count of
        ``*.py`` files under it -- port-exposed filesystem observables, never
        internal struct fields. Incidental tool caches (``.pytest_cache``,
        ``__pycache__``) are NOT ``*.py`` files and so never perturb the count.
        """
        exists = repo.exists()
        py_count = len(list(repo.rglob("*.py"))) if exists else 0
        return {"repo.exists": exists, "repo.python_file_count": py_count}

    def universe_before(self) -> dict[str, object]:
        assert self._universe_before is not None, (
            "the gate must have been driven (capturing the before-universe) "
            "before the read-only contract can be asserted."
        )
        return self._universe_before

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_and_parse(self, program: str) -> ContractGateRunObservable:
        rc, out, err = self._run_python_c(program)
        child_import_ok = "GATE_EXIT:" in out
        event = self._last_json_event(out)
        return ContractGateRunObservable(
            exit_code=rc,
            stdout=out,
            stderr=err,
            event_found=bool(event),
            routed_via_registered_adapter=bool(event.get(_ROUTED_FIELD, False)),
            runner=event.get("runner")
            if isinstance(event.get("runner"), str)
            else None,
            pytest_exit_code=(
                event.get("pytest_exit_code")
                if isinstance(event.get("pytest_exit_code"), int)
                else None
            ),
            passed=(
                event.get("passed") if isinstance(event.get("passed"), bool) else None
            ),
            child_import_ok=child_import_ok,
        )

    @staticmethod
    def _last_json_event(stdout: str) -> dict[str, object]:
        """The LAST well-formed JSON dict carrying an "event" key on stdout.

        Defensive parse (mirrors the shipped `_verdict_payload` precedent): an
        unparseable / absent line yields `{}`, never a raised exception.
        """
        found: dict[str, object] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "event" in parsed:
                found = parsed
        return found

    def _run_python_c(self, program: str) -> tuple[int, str, str]:
        """Run a one-shot `python -c` probe in a child interpreter.

        `src` + the repo root are on PYTHONPATH so the in-tree `des` package
        (and `scripts` for the plugin, once it exists) is importable in the
        child -- mirrors the shipped `rust_test_runner_adapter` precedent.
        """
        env = dict(os.environ)
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


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/unified_language_adapter_registry/steps/<file>
      parents: [0]=steps [1]=unified_language_adapter_registry [2]=acceptance
      [3]=des [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
