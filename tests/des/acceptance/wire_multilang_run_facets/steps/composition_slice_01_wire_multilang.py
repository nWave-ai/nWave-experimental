"""Composition root for wire-multilang-run-facets slice-01 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL PRODUCTION
REGISTRY DISPATCH driven in a CHILD interpreter. The SUT is NOT the run-facet in isolation --
it is the INTEGRATED dispatch path the production code takes:

    seed_runner_registry()                 # populate GLOBAL_REGISTRY (the seam under test)
    adapter = RunnerAdapter(name=token)     # the token resolve() returns for the target
    verdict = adapter.run(target_root, cmd) # -> GLOBAL_REGISTRY.lookup(token) -> run-facet

WHY this is the production dispatch and NOT the bypass: the C13/C14 ATs the adversarial
swarm (2026-06-24) flagged imported ``run_go_scope`` / ``run_vitest_scope`` DIRECTLY in a
child and called them -- proving the isolated function while BYPASSING the registry. This
harness NEVER imports a run-facet. It calls ``seed_runner_registry()`` and then
``RunnerAdapter(token).run(...)``, so the run-facet is only ever reached THROUGH
``GLOBAL_REGISTRY.lookup(token)`` -- the exact integrated path production uses. If the token
is not registered in ``seed_runner_registry``, the dispatch raises ``RunnerAdapterUnavailable``
(the run-facet is NEVER reached) -- which is precisely the RED-at-HEAD outcome this feature
fixes by adding the 2 registrations.

WHY a child interpreter (not a thin in-process call): the production dispatch resolves the
target's runner binary off PATH + known-locations and shells it. The child gives a HERMETIC
env -- PATH set to ONLY the fixture's controlled dir (so the fake go/vitest is resolved, never
an ambient host tool), HOME under the fixture, and the Go/Node env neutralised so a real
toolchain can never leak. ``src`` is prepended to PYTHONPATH so the in-tree ``des`` package is
importable. ZERO ``des.adapters.*`` / ``des.ports.*`` import in THIS process -- the SUT is only
ever imported in the CHILD.

RED-vs-GREEN observable (DispatchOutcome): the child prints a machine-readable marker:
  - ``OUTCOME:WIRED:PASS``        -- the dispatch REACHED the run-facet, which returned a
                                     ``RunVerdict`` (the fake exits 0 -> passed=True). GREEN.
  - ``OUTCOME:UNWIRED:<reason>``  -- the dispatch raised ``RunnerAdapterUnavailable`` because
                                     the token is NOT registered after seeding (the run-facet
                                     was never reached). RED at HEAD.
At HEAD ``seed_runner_registry`` registers only pytest + cargo-test, so go-test / vitest
lookup -> None -> RunnerAdapterUnavailable -> ``OUTCOME:UNWIRED`` -> each AC-1/AC-2 Then fires
a SEMANTIC AssertionError (active-RED, NOT @skip, NO collection/import error in this process).
AC-3 (preservation) seeds + asserts pytest + cargo-test lookup non-None -- live-green at HEAD.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_python_snippet_in_process

from .domain_types_wire_multilang import DispatchOutcome, RunnerToken, TargetLanguage


# The production seams the child interpreter drives (the SUT is the INTEGRATED dispatch).
# NOTE: NO go_runner / vitest_runner module is named here -- this harness NEVER imports a
# run-facet directly. The run-facet is reached ONLY through GLOBAL_REGISTRY.lookup(token).
_RUNNER_REGISTRY_MODULE = "des.adapters.driven.runner.runner_registry"
_TEST_RUNNER_PORT_MODULE = "des.ports.test_runner_port"

# The fixture: lockfile filename -> the resolve() token + the fake binary name, per
# TargetLanguage. resolve() already maps these (test_runner_port.py _REGISTRY:149-150).
_TARGET_SPEC: dict[TargetLanguage, tuple[str, str, RunnerToken, str]] = {
    # language: (lockfile_name, lockfile_body, resolve-token, fake-binary-name)
    TargetLanguage.GO: (
        "go.mod",
        "module fixture\n\ngo 1.22\n",
        RunnerToken.GO_TEST,
        "go",
    ),
    TargetLanguage.VITEST: (
        # package.json MUST contain the substring "vitest" so resolve() maps it to the
        # vitest token (test_runner_port.py:149 requires_substring="vitest").
        "package.json",
        '{\n  "name": "fixture",\n  "devDependencies": {"vitest": "^1.0.0"},\n'
        '  "scripts": {"test": "vitest run"}\n}\n',
        RunnerToken.VITEST,
        "vitest",
    ),
}

# The declared feature-scoped test_command tokens passed to the production dispatch as the
# per-runner "scope" (NOT a node-id list). The leading token is the binary the run-facet
# resolves; the rest is the subcommand shelled as-is.
_DECLARED_COMMAND: dict[TargetLanguage, tuple[str, ...]] = {
    TargetLanguage.GO: ("go", "test", "./..."),
    TargetLanguage.VITEST: ("vitest", "run"),
}


@dataclass
class WireMultilangComposition:
    """Drives the REAL production registry dispatch over a controlled fs + FAKE binary."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    _target_root: Path | None = field(default=None)
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    _language: TargetLanguage | None = field(default=None)
    # child-interpreter probe results
    _probe_rc: int | None = field(default=None)
    _probe_out: str = field(default="")
    _probe_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-binary fixtures) ---------------------

    def given_target_with_fake_runner(self, language: TargetLanguage) -> None:
        """Plant a REAL hermetic target tree + a chmod+x fake runner that exits 0.

        Used by AC-1 (go) and AC-2 (vitest). The target carries the lockfile resolve() keys
        off (go.mod / package.json+vitest), and a real fake ``go``/``vitest`` script lives on
        a controlled PATH. The PRODUCTION dispatch resolves the token (resolve maps the
        lockfile), looks the run-facet up in GLOBAL_REGISTRY, and -- if registered -- shells
        the fake (which exits 0 -> a PASS RunVerdict). The fake exiting 0 is the GREEN signal
        the dispatch REACHED the run-facet; an UNWIRED token never reaches it (the marker is
        ``UNWIRED`` instead).
        """
        lockfile_name, lockfile_body, _token, fake_name = _TARGET_SPEC[language]
        root = self._ensure_root()
        target = root / "target-module"
        target.mkdir(parents=True, exist_ok=True)
        (target / lockfile_name).write_text(lockfile_body, encoding="utf-8")
        self._target_root = target
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._plant_fake_runner(path_bin / fake_name)
        # the fake runner is on PATH (resolve_tool PATH rung).
        self._child_path = str(path_bin)
        self._language = language

    def given_the_registry_is_seeded(self) -> None:
        """AC-3 preservation fixture: no target binary needed.

        The preservation check drives ``seed_runner_registry()`` then asserts the
        pre-existing pytest + cargo-test tokens still resolve in GLOBAL_REGISTRY -- the
        wiring must ADD the multi-lang tokens without disturbing the existing ones.
        """
        root = self._ensure_root()
        # an empty controlled PATH is fine: the preservation check only inspects the registry
        # (lookup), it does not shell any runner.
        empty_path = root / "empty-path"
        empty_path.mkdir(parents=True, exist_ok=True)
        self._child_path = str(empty_path)

    # ---- when (drive the REAL production registry dispatch in a child) ------

    def when_the_production_dispatch_runs(self) -> None:
        """Invoke the REAL production dispatch over the fixture in a child.

        Drives the INTEGRATED path (NOT a direct run-facet import): the child imports the
        registry module + the port, calls ``seed_runner_registry()`` to populate
        GLOBAL_REGISTRY, builds ``RunnerAdapter(name=token)`` for the resolved token, and
        calls ``adapter.run(target_root, declared_command)``. ``RunnerAdapter.run`` looks the
        token up in GLOBAL_REGISTRY and -- only if registered -- reaches the run-facet,
        shelling the fake binary. The child prints a marker:
          - ``OUTCOME:WIRED:PASS`` / ``OUTCOME:WIRED:FAIL`` from a returned ``RunVerdict``
            (the dispatch REACHED the run-facet),
          - ``OUTCOME:UNWIRED:<reason>`` when ``RunnerAdapterUnavailable`` is raised (the
            token is not registered after seeding -- the run-facet was never reached).
        At HEAD the go-test / vitest tokens are not registered, so the dispatch raises
        ``RunnerAdapterUnavailable`` -> ``OUTCOME:UNWIRED`` (RED). Note ``RunnerAdapter.run``
        self-heals by re-seeding once, so the child does NOT even need to seed first -- but it
        does, exercising ``seed_runner_registry`` as the seam under test explicitly.
        """
        assert self._language is not None, (
            "fixture not initialised with a target language"
        )
        _lockfile_name, _body, token, _fake = _TARGET_SPEC[self._language]
        command = _DECLARED_COMMAND[self._language]
        program = (
            "import importlib, pathlib\n"
            f"target_root = {str(self._target_root)!r}\n"
            f"command = {tuple(command)!r}\n"
            f"registry_mod = importlib.import_module({_RUNNER_REGISTRY_MODULE!r})\n"
            f"port = importlib.import_module({_TEST_RUNNER_PORT_MODULE!r})\n"
            # Seed the registry -- the SEAM under test. At HEAD this registers only
            # pytest + cargo-test; the feature ADDS go-test + vitest here.
            "registry_mod.seed_runner_registry()\n"
            # Build the adapter for the token resolve() returns for this target, then drive
            # the PRODUCTION dispatch. RunnerAdapter.run does GLOBAL_REGISTRY.lookup(token)
            # -- the integrated path -- and reaches the run-facet ONLY if registered.
            f"adapter = port.RunnerAdapter(name={token.value!r})\n"
            "unavailable = port.RunnerAdapterUnavailable\n"
            "try:\n"
            "    verdict = adapter.run(pathlib.Path(target_root), command)\n"
            "except unavailable as exc:\n"
            "    print('OUTCOME:UNWIRED:' + str(exc))\n"
            "else:\n"
            "    print('OUTCOME:WIRED:' + ('PASS' if verdict.passed else 'FAIL'))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    def when_the_registry_is_seeded(self) -> None:
        """AC-3: seed the registry + report which existing tokens resolve.

        Drives ``seed_runner_registry()`` in a child, then probes
        ``GLOBAL_REGISTRY.lookup(token)`` for pytest + cargo-test, printing a marker naming
        which resolve (non-None). The preservation observable: both pre-existing tokens stay
        registered after the wiring adds the multi-lang tokens.
        """
        program = (
            "import importlib\n"
            f"registry_mod = importlib.import_module({_RUNNER_REGISTRY_MODULE!r})\n"
            "registry_mod.seed_runner_registry()\n"
            "reg = registry_mod.GLOBAL_REGISTRY\n"
            f"pytest_ok = reg.lookup({RunnerToken.PYTEST.value!r}) is not None\n"
            f"cargo_ok = reg.lookup({RunnerToken.CARGO_TEST.value!r}) is not None\n"
            "resolved = [n for n, ok in "
            f"(({RunnerToken.PYTEST.value!r}, pytest_ok), "
            f"({RunnerToken.CARGO_TEST.value!r}, cargo_ok)) if ok]\n"
            "print('SEEDED:' + ','.join(resolved))\n"
        )
        self._probe_rc, self._probe_out, self._probe_err = self._run_python_c(program)

    # ---- then (assert ON the production-dispatch OUTCOME) -------------------

    def then_the_dispatch_outcome_is(self, expected: DispatchOutcome) -> None:
        """The production dispatch reached (WIRED) or did not reach (UNWIRED) the run-facet.

        Used by AC-1 (go) + AC-2 (vitest). The expected outcome is WIRED: after DELIVER
        registers the token in ``seed_runner_registry``, ``RunnerAdapter(token).run(...)``
        looks it up, REACHES the run-facet, shells the fake (exit 0), and returns a PASS
        ``RunVerdict`` -> ``OUTCOME:WIRED:PASS``.

        Active-RED at HEAD: the token is NOT registered in ``seed_runner_registry`` (only
        pytest + cargo-test are), so the dispatch raises ``RunnerAdapterUnavailable`` ->
        ``OUTCOME:UNWIRED`` -> this AssertionError fires with the registration-missing reason.
        The WIRED-vs-UNWIRED distinction is the load-bearing observable: it separates "the
        production dispatch reached the run-facet" (the wiring works) from
        "RunnerAdapterUnavailable because the run-facet was never registered" (the theater the
        swarm flagged).
        """
        assert self._probe_rc == 0 and "OUTCOME:" in self._probe_out, (
            "the production registry dispatch (seed_runner_registry + "
            "RunnerAdapter(token).run) must run and report an outcome; the child probe "
            f"produced none. {self._probe_observed()}"
        )
        marker = self._probe_out.split("OUTCOME:", 1)[1].strip().splitlines()[0]
        observed_token = marker.split(":", 1)[0]  # WIRED | UNWIRED
        assert observed_token == expected.name, (
            f"the production dispatch outcome was {observed_token!r}, expected "
            f"{expected.name}. At HEAD seed_runner_registry registers ONLY pytest + "
            f"cargo-test (runner_registry.py:104-105), so the {self._language} token is "
            f"UNWIRED: GLOBAL_REGISTRY.lookup returns None and RunnerAdapter(token).run "
            f"raises RunnerAdapterUnavailable -- the run-facet is NEVER reached. GREEN "
            f"requires DELIVER to register the run-facet under its resolve() token in "
            f"seed_runner_registry (mirror the cargo registration at :105). "
            f"marker={marker!r}. {self._probe_observed()}"
        )

    def then_the_existing_runners_still_resolve(self) -> None:
        """AC-3 preservation: pytest + cargo-test still resolve after seeding (live-green).

        The wiring must ADD the multi-lang tokens WITHOUT disturbing the pre-existing
        registrations. Asserts the child reported BOTH pytest and cargo-test as resolving in
        GLOBAL_REGISTRY after ``seed_runner_registry()``. Live-green at HEAD: these two tokens
        are already registered (runner_registry.py:104-105) -- this guards against a
        regression where adding the go-test/vitest registrations drops an existing one.
        """
        assert self._probe_rc == 0 and "SEEDED:" in self._probe_out, (
            "seed_runner_registry() must run and report the resolving tokens; the child "
            f"probe produced none. {self._probe_observed()}"
        )
        resolved_csv = self._probe_out.split("SEEDED:", 1)[1].strip().splitlines()[0]
        resolved = {tok for tok in resolved_csv.split(",") if tok}
        expected = {RunnerToken.PYTEST.value, RunnerToken.CARGO_TEST.value}
        assert expected <= resolved, (
            "after seed_runner_registry() BOTH the pre-existing pytest and cargo-test "
            f"tokens must still resolve in GLOBAL_REGISTRY (preservation): expected "
            f"{sorted(expected)}, got {sorted(resolved)}. The wiring must ADD go-test + "
            f"vitest without dropping an existing registration. {self._probe_observed()}"
        )

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        """Create (once) a REAL tmp dir the fixtures plant files into."""
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-wire-multilang-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_fake_runner(target: Path) -> Path:
        """Write a REAL chmod+x fake runner that exits 0 (a green run).

        A POSIX shell script the run-facet resolves via resolve_tool's PATH rung and shells
        like the real tool. It emits a passing-shaped line and exits 0 -- so a WIRED dispatch
        maps it to ``RunVerdict(passed=True)`` (PASS). The fixture's job is only to let the
        dispatch REACH a run-facet over a controlled green binary; the run-facet's own exit-
        semantics are covered by the dedicated go/vitest adapter ATs, not re-tested here.
        """
        script = "#!/bin/sh\necho 'ok\tfixture\t0.010s'\nexit 0\n"
        target.write_text(script, encoding="utf-8")
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    # ---- driving-port invocation (Layer 3 subprocess) -----------------------

    def _run_python_c(self, program: str) -> tuple[int, str, str]:
        """Run a one-shot ``python -c`` probe in a child interpreter.

        HERMETIC env: PATH is set to ONLY the fixture's controlled dir (so the production
        dispatch resolves the FAKE runner, never an ambient host go/vitest). HOME is the
        fixture's tmp home and the Go/Node env is neutralised so a known-location / toolchain
        dir can never leak a real binary. ``src`` is prepended to PYTHONPATH so the in-tree
        ``des`` package is importable.
        """
        env = dict(os.environ)
        env["PATH"] = self._child_path
        env["HOME"] = self._child_home or self._child_path
        # neutralise the Go + Node env so a real host tool can never leak into resolution.
        for var in ("GOROOT", "GOPATH", "GOBIN", "NODE_PATH", "npm_config_prefix"):
            env.pop(var, None)
        root = _repo_root()
        src = str(root / "src")
        existing = env.get("PYTHONPATH", "")
        prepend = src + os.pathsep + str(root)
        env["PYTHONPATH"] = prepend + os.pathsep + existing if existing else prepend
        return run_python_snippet_in_process(program, cwd=str(root), env=env)

    # ---- diagnostics --------------------------------------------------------

    def _probe_observed(self) -> str:
        return (
            f"probe_rc={self._probe_rc!r}; "
            f"language={self._language!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"probe_out={self._probe_out!r}; "
            f"probe_err_tail={self._probe_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/wire_multilang_run_facets/steps/<file>
      parents: [0]=steps [1]=wire_multilang_run_facets [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
