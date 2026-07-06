"""Composition root for unified-language-adapter-registry slice-03 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): every
scenario drives the REAL production entry (`des.cli.run_contract_gate.main`,
or the REAL `LanguageAdapterRegistry`) inside a CHILD interpreter (`python -c`
one-shot program), never importing the net-new slice-03 production modules in
THIS test process. Mirrors `composition.py` (slice-02, Python reference
plugin) EXACTLY, generalized to the TypeScript plugin + its `"vitest"`
tool-name key -- the second-language proof that the slice-01 seam is
language-neutral (DDD-U5, DESIGN component IDs C12-C13).

WHY a child interpreter: at HEAD `scripts/install/plugins/nwave_lang_typescript.py`
and the 3 new TS adapters (`des.adapters.driven.{contract_gate,e2e,robustness}.
*_ts_adapter`) do NOT exist. Importing them in THIS process would raise
`ModuleNotFoundError` at COLLECTION -> a BROKEN test, not active-RED. Running
the import in a child `python -c` makes the absent module a CAPTURED
observable (child rc != 0, no success marker) that each Then turns into a
semantic AssertionError. Same pattern as slice-02's `Slice02Composition` and
the shipped `vitest_test_runner_adapter` slice-01 harness.

WHY a FAKE vitest binary (not a real Node/vitest toolchain): mirrors
`tests/des/acceptance/vitest_test_runner_adapter/steps/
composition_slice_01_vitest_runner.py` verbatim -- a real chmod+x shell script
planted on a controlled PATH deterministically emits an exit code (GREEN ->
0) without requiring a real Node/vitest install on the target machine
(target-machine agnosticism, CLAUDE.md architectural constraint: the only
runtime dependency is Python). The fake does NOT interpret its argv -- it is
resolved via the shared `resolve_tool` PATH rung exactly like a real vitest
would be, and the contract-gate CLI resolves the target's tool-name to
`"vitest"` via the REAL `resolve_runner`, which requires a genuine
`package.json` declaring a `vitest` devDependency (`test_runner_port.py`'s
`_RegistryRow(filename="package.json", runner="vitest",
requires_substring="vitest")`).

ZERO `des.adapters.*` / `scripts.install.plugins.nwave_lang_typescript` import
in THIS process: the SUT is only ever imported inside the child.
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import ContractGateRunObservable, RegistrySlotResolution


# The net-new production modules this slice ships (all absent at HEAD). Named
# as STRINGS only -- never imported in this process (P1 discipline).
_PLUGIN_MODULE = "scripts.install.plugins.nwave_lang_typescript"
_LANGUAGE_ADAPTER_PLUGIN_MODULE = "des.ports.language_adapter_plugin"
_REGISTRY_MODULE = "des.adapters.driven.runner.runner_registry"
_GATE_MODULE = "des.cli.run_contract_gate"

# The resolved tool-name the TS plugin registers under (DDD-U5: keyed on the
# RESOLVED TOOL-NAME, never `target_language`) -- mirrors the shipped vitest
# run-facet's own token (`test_runner_port.py` registry row).
_VITEST_TOKEN = "vitest"

# DISTILL-pinned observable (mirrors slice-02's resolution, feature-delta
# `[REF] Open questions`): the seam's routed arm must emit this boolean field
# on the EXISTING `ContractGateResult` event, additive + back-compatible.
_ROUTED_FIELD = "routed_via_registered_adapter"


def _find_and_register_snippet() -> str:
    """Child-program fragment: import the TS plugin, register into GLOBAL_REGISTRY.

    Discovers the single concrete `LanguageAdapterPlugin` subclass in the
    module by ABC subclass-scan (mirrors the shipped cargo-runner /
    slice-02 Python precedent) so the AT does not lock onto a class name the
    design has not frozen.
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
            raise SystemExit("no concrete LanguageAdapterPlugin in nwave_lang_typescript")
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
class Slice03Composition:
    """Drives the REAL slice-03 SUT (TS plugin + registry + gate) via child interpreters."""

    _passing_repo: Path | None = field(default=None)
    _universe_before: dict[str, object] | None = field(default=None)
    _registered_run: ContractGateRunObservable | None = field(default=None)
    _slot_resolution: RegistrySlotResolution | None = field(default=None)
    _child_path: str = field(default="")

    # ---- given (REAL filesystem + FAKE-vitest fixtures) ---------------------

    def given_passing_typescript_codebase(self, tmp_path: Path) -> None:
        """A real TS target repo whose `vitest` run is GREEN.

        A genuine `package.json` declaring `vitest` as a devDependency (so
        the REAL `resolve_runner` resolves the target's tool-name to
        `"vitest"`, matching `test_runner_port.py`'s registry row) plus a
        planted, real chmod+x fake `vitest` binary on a controlled PATH that
        exits 0 -- mirrors the shipped `vitest_test_runner_adapter` slice-01
        fixture technique so this AT never depends on a real Node/vitest
        toolchain being installed on the target machine.
        """
        repo = tmp_path / "passing-ts-codebase"
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "package.json").write_text(
            '{\n  "name": "fixture",\n  "devDependencies": {"vitest": "^1.0.0"}\n}\n',
            encoding="utf-8",
        )
        src_dir = repo / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "thing.test.ts").write_text(
            "// fixture test file (the fake vitest never reads it)\n",
            encoding="utf-8",
        )
        path_bin = tmp_path / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_vitest(path_bin / "vitest")
        self._child_path = str(path_bin) + os.pathsep + os.environ.get("PATH", "")
        self._passing_repo = repo

    # ---- when (drive the REAL SUT in a child interpreter) -------------------

    def when_plugin_wires_contract_gate_adapter(self) -> None:
        """Arm the WS run: register the TS plugin's adapters, drive the gate.

        Snapshots the read-only-contract universe BEFORE the child runs
        (Mandate 8), then runs ONE child program that (a) registers the
        plugin's adapters into the REAL `GLOBAL_REGISTRY`, then (b) drives
        the REAL `main(["--repo", ...])` -- proving the seam's registered
        arm is reachable end-to-end, for a SECOND language, with ZERO seam
        edit (the seam built for Python in slice-02 is exercised unmodified).
        """
        assert self._passing_repo is not None, (
            "the passing TypeScript codebase must be armed (Given) before "
            "driving the gate."
        )
        self._universe_before = self.capture_universe(self._passing_repo)
        program = (
            "import importlib\n"
            + _find_and_register_snippet()
            + _drive_gate_snippet(self._passing_repo)
        )
        self._registered_run = self._run_and_parse(program)

    def when_plugin_wires_all_slots(self) -> None:
        """The unification pin (mirrors slice-02 AT-3): TS plugin wires a FRESH registry.

        A fresh child imports the TS plugin + the registry module,
        constructs a NEW `LanguageAdapterRegistry()` (never `GLOBAL_REGISTRY`),
        calls `plugin.register_adapters(registry)` ONCE, then reports whether
        all 3 new slots resolved under the plugin's own runner token
        (`"vitest"`) -- the second-language proof that DDD-U2/DDD-U5's slot
        contract holds for ANY tool-name, not just Python's `"pytest"`.
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
                raise SystemExit("no concrete LanguageAdapterPlugin in nwave_lang_typescript")
            plugin = candidates[0]()
            registry_mod = importlib.import_module({_REGISTRY_MODULE!r})
            registry = registry_mod.LanguageAdapterRegistry()
            plugin.register_adapters(registry)
            cg = registry.lookup_contract_gate({_VITEST_TOKEN!r})
            e2e = registry.lookup_environmental_e2e({_VITEST_TOKEN!r})
            rd = registry.lookup_robustness_density({_VITEST_TOKEN!r})
            print(
                "SLOTS:"
                + str(int(cg is not None))
                + str(int(e2e is not None))
                + str(int(rd is not None))
            )
            """
        )
        rc, out, _err = self._run_python_c(program, use_child_path=False)
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
        """The TS codebase path the Given armed (for post-run universe reads)."""
        assert self._passing_repo is not None, (
            "the passing TypeScript codebase must have been armed (Given) "
            "before its path can be read back."
        )
        return self._passing_repo

    def registered_run(self) -> ContractGateRunObservable:
        assert self._registered_run is not None, (
            "the gate must have been driven with the TS adapter registered "
            "(When) before this observable is read."
        )
        return self._registered_run

    def slot_resolution(self) -> RegistrySlotResolution:
        assert self._slot_resolution is not None, (
            "the TS plugin must have wired a fresh registry (When) before "
            "this observable is read."
        )
        return self._slot_resolution

    def diag_registered(self) -> str:
        return self._diag(self._registered_run)

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

        Mirrors slice-02's universe exactly (the contract gate must not
        mutate the target's source tree), generalized from `*.py` to `*.ts`
        source files -- the TS codebase's own source-file count.
        """
        exists = repo.exists()
        ts_count = len(list(repo.rglob("*.ts"))) if exists else 0
        return {"repo.exists": exists, "repo.typescript_file_count": ts_count}

    def universe_before(self) -> dict[str, object]:
        assert self._universe_before is not None, (
            "the gate must have been driven (capturing the before-universe) "
            "before the read-only contract can be asserted."
        )
        return self._universe_before

    # ---- real-fixture helpers ------------------------------------------------

    @staticmethod
    def _plant_fake_vitest(target: Path) -> Path:
        """Write a REAL chmod+x fake `vitest` that always exits 0 (GREEN).

        Mirrors `vitest_test_runner_adapter`'s planted fake exactly: a POSIX
        shell script the run-facet/adapter shells like a real vitest. It does
        NOT interpret its argv (the reporter flag, subcommand, etc.) -- it
        deterministically emits a vitest-shaped passing summary and exits 0,
        so this AT is independent of the exact CLI invocation shape the
        `VitestContractGateAdapter` (C13) ends up choosing.
        """
        script = (
            "#!/bin/sh\n"
            "echo 'Test Files  1 passed (1)'\n"
            "echo 'Tests  1 passed (1)'\n"
            "exit 0\n"
        )
        target.write_text(script, encoding="utf-8")
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_and_parse(self, program: str) -> ContractGateRunObservable:
        rc, out, err = self._run_python_c(program, use_child_path=True)
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

        Defensive parse (mirrors the shipped `_verdict_payload` precedent):
        an unparseable / absent line yields `{}`, never a raised exception.
        """
        found: dict[str, object] = {}
        for line in stdout.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                import json

                parsed = json.loads(line)
            except Exception:
                continue
            if isinstance(parsed, dict) and "event" in parsed:
                found = parsed
        return found

    def _run_python_c(
        self, program: str, *, use_child_path: bool
    ) -> tuple[int, str, str]:
        """Run a one-shot `python -c` probe in a child interpreter.

        `src` + the repo root are on PYTHONPATH so the in-tree `des` package
        (and `scripts` for the plugin, once it exists) is importable in the
        child -- mirrors the shipped `Slice02Composition` precedent. When
        `use_child_path` is set, PATH is prefixed with the fixture's
        fake-vitest directory so the resolved contract-gate adapter (once
        DELIVER ships it) shells the deterministic fake, never an ambient
        host vitest.
        """
        env = dict(os.environ)
        if use_child_path and self._child_path:
            env["PATH"] = self._child_path
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
