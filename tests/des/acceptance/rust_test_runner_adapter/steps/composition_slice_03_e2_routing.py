"""Composition root for f-rust-test-runner-adapter slice-03 ATs.

ONE driving surface, Mandate-13 driving-port-only (Layer 3 subprocess): the REAL
operator-facing contract gate ``python -m des.cli.run_contract_gate
--repo <target> --feature-id <f> --entering-slice slice-NN`` run as a child
process over a GENUINE controlled filesystem + a FAKE-cargo executable on a
controlled PATH. This is the EXACT subprocess
``verify_slice_commit_completeness._run_contract_gate`` composes (a pure
pass-through, verify_slice_commit_completeness.py:253-262), so driving the
contract gate directly observes the same E2 verdict an operator's
``des verify-slice-commit`` would -- hermetically + fast.

The slice-03 SUT is the E2-routing short-circuit inside
``run_contract_gate._mode_feature_scoped`` (feature-delta §V.A, line 1229). At
HEAD it does NOT exist: ``_mode_feature_scoped`` runs the pytest-bound
``_collect_node_ids`` worker (line 1273) unconditionally, so a Cargo.toml target
(no Python tests) collects ZERO and the gate emits
``FeatureScopeMalformed / zero-collected`` -- the pytest-collection bug this
feature fixes. slice-03 ships three wiring points (the SUT):

  1. ``_mode_feature_scoped`` runner-resolution short-circuit (~line 1229,
     BEFORE the pytest collection): seed_runner_registry() -> resolve(repo) ->
     if cargo-test, DERIVE ``binary(/<snake_feature_id>/)`` (snake =
     feature_id.replace("-", "_")), read the OPTIONAL runner.json override, run
     the cargo facet, map exit -> verdict; else fall through to pytest UNCHANGED.
  2. Registry dispatch in ``RunnerAdapter.run`` (test_runner_port.py:89-93):
     GLOBAL_REGISTRY.lookup(self.name) instead of the hardcoded if name=="pytest".
  3. ``runner_json.py`` optional-override reader (NEW): read_runner_json(...) ->
     dict | None, returns None on absence (the NORMAL zero-config case).

DRIVING the gate (not a thin in-process call): the gate is the operator's real
entry. We run it as the real subprocess; the OBSERVABLE is the JSON verdict it
emits on stdout. ZERO ``des.adapters.*`` / ``des.cli.*`` / ``des.domain.*``
import in THIS process -- the SUT is exercised ONLY across the subprocess
boundary.

FAKE-cargo determinism (no real Rust toolchain -- absent in CI): the fixture
plants a REAL chmod+x fake ``cargo`` on a controlled PATH. The fake:
  - WRITES every invocation's argv to a sentinel file (so an AT can observe WHICH
    selector the gate actually drove -- the convention-derived ``binary(...)`` vs
    a ``runner.json`` override's ``test_command``), then
  - emits a passing cargo summary and exits 0 (a green run -> the gate CLEARS).
The slice-03 wiring resolves this fake via the slice-01 ``resolve_tool`` PATH rung
and shells it -- so the E2-routing is exercised end-to-end through the REAL gate,
deterministically, in CI, with NO real cargo/nextest.

Active-RED scaffold (atdd_pure -- NOT @skip): at HEAD the slice-03 wiring is
absent, so the gate runs the pytest worker and emits ``FeatureScopeMalformed /
zero-collected`` on the Cargo target (NOT ``FeatureScopeCleared``, and the
sentinel records NO cargo invocation). Each Then turns that captured observable
into a semantic AssertionError. GREEN once DELIVER ships the three wiring points.
No @skip, no import / collection error in THIS process.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types_e2_routing import GateOutcome, RunnerJsonPresence


# The operator-facing driving port (Layer 3 subprocess) -- the REAL contract gate
# CLI module run in a child interpreter. This IS the subprocess
# verify_slice_commit_completeness composes for E2.
_CONTRACT_GATE_MODULE = "des.cli.run_contract_gate"

# The convention-following validation feature-id (kebab) and its derived snake
# form -- the gate must DERIVE binary(/<snake>/) from the kebab feature-id (D7 v3).
_FEATURE_ID = "hardcoded-credential-binding-aware"
_SNAKE_FEATURE_ID = _FEATURE_ID.replace("-", "_")
_ENTERING_SLICE = "slice-01"

# The convention-derived selector the gate must produce for a zero-config target
# (the binary() axis over the FULL snake feature-id -- §V.B, load-bearing).
_DERIVED_BINARY_SELECTOR = f"binary(/{_SNAKE_FEATURE_ID}/)"

# The override selector a runner.json ships (a DISTINCT, observable token so an AT
# can tell the override drove the run, not the convention default).
_OVERRIDE_TEST_COMMAND = "cargo nextest run --test override_driver_binary"
_OVERRIDE_SENTINEL_TOKEN = "override_driver_binary"

_CARGO_NAME = "cargo"


@dataclass
class E2RoutingComposition:
    """Drives the REAL contract gate over a controlled Cargo target + FAKE cargo."""

    _tmp: tempfile.TemporaryDirectory | None = field(default=None)
    _root: Path | None = field(default=None)
    _target_root: Path | None = field(default=None)
    _child_path: str = field(default="")
    _child_home: str = field(default="")
    # the sentinel the fake cargo appends its argv to (one line per invocation)
    _cargo_argv_log: Path | None = field(default=None)
    _runner_json_presence: RunnerJsonPresence = field(default=RunnerJsonPresence.ABSENT)
    # child gate results
    _gate_rc: int | None = field(default=None)
    _gate_out: str = field(default="")
    _gate_err: str = field(default="")

    # ---- given (REAL filesystem + FAKE-cargo fixtures) ----------------------

    def given_convention_following_rust_target_no_runner_json(self) -> None:
        """A Rust target that FOLLOWS the ``<snake_feature_id>_*`` convention and
        ships NO ``runner.json`` -- the zero-config common case (AT-8, AT-10).

        Plants a real Cargo.toml target, a feature ``.feature`` carrying the
        ``@feature-<id>`` + ``@slice-NN`` tags (so the gate's tag resolution
        finds the feature scope), and a green fake cargo on PATH. NO runner.json.
        """
        self._build_target(presence=RunnerJsonPresence.ABSENT)

    def given_convention_following_rust_target_with_runner_json_override(self) -> None:
        """A Rust target that SHIPS a ``runner.json`` ``test_command`` override
        (AT-9-override).

        Same as the zero-config target, PLUS a ``runner.json`` at
        ``docs/feature/<id>/runner.json`` whose ``test_command`` carries a
        DISTINCT selector token. An AT observes that the gate drove the OVERRIDE
        command (the sentinel records the override token), not the convention
        default.
        """
        self._build_target(presence=RunnerJsonPresence.OVERRIDE)

    def _build_target(self, presence: RunnerJsonPresence) -> None:
        root = self._ensure_root()
        target = root / "rust-target"
        target.mkdir(parents=True, exist_ok=True)
        (target / "Cargo.toml").write_text(
            '[package]\nname = "fixture"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        # the feature .feature so the gate's @feature-/@slice- tag resolution
        # finds a feature scope (the M-8 intersection) -- the cargo path still
        # short-circuits BEFORE the pytest M-1 collection.
        feature_dir = target / "tests"
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / f"{_SNAKE_FEATURE_ID}.feature").write_text(
            f"@feature-{_FEATURE_ID} @{_ENTERING_SLICE}\n"
            "Feature: convention-following rust target\n"
            f"  @{_ENTERING_SLICE}\n"
            "  Scenario: the slice ships its rust behaviour\n"
            "    Given the rust crate compiles\n",
            encoding="utf-8",
        )
        if presence is RunnerJsonPresence.OVERRIDE:
            runner_json_dir = target / "docs" / "feature" / _FEATURE_ID
            runner_json_dir.mkdir(parents=True, exist_ok=True)
            (runner_json_dir / "runner.json").write_text(
                json.dumps(
                    {
                        "feature_id": _FEATURE_ID,
                        "test_command": _OVERRIDE_TEST_COMMAND,
                        "slice": _ENTERING_SLICE,
                    }
                ),
                encoding="utf-8",
            )
        self._target_root = target
        self._runner_json_presence = presence

        # green fake cargo on a controlled PATH; logs its argv to the sentinel
        path_bin = root / "path-bin"
        path_bin.mkdir(parents=True, exist_ok=True)
        self._cargo_argv_log = root / "cargo-argv.log"
        self._plant_logging_fake_cargo(path_bin / _CARGO_NAME, self._cargo_argv_log)
        self._child_path = str(path_bin)

    # ---- when (drive the REAL gate as a subprocess) -------------------------

    def when_the_operator_runs_the_feature_scoped_gate(self) -> None:
        """Run the REAL ``run_contract_gate --feature-id`` over the target.

        This IS the operator's E2 driving port (the subprocess
        verify_slice_commit_completeness composes). The gate's emitted JSON
        verdict on stdout is the observable. At HEAD the gate runs the pytest
        worker on the Cargo target -> ``FeatureScopeMalformed / zero-collected``
        (and the fake cargo is NEVER invoked -> the sentinel stays empty).
        """
        argv = [
            sys.executable,
            "-m",
            _CONTRACT_GATE_MODULE,
            "--repo",
            str(self._target_root),
            "--feature-id",
            _FEATURE_ID,
            "--entering-slice",
            _ENTERING_SLICE,
        ]
        self._gate_rc, self._gate_out, self._gate_err = self._run_child(argv)

    # ---- then (assert ON the gate's emitted verdict -- port-exposed) ---------

    def then_the_gate_outcome_is(self, expected: GateOutcome) -> None:
        """The gate emitted the ``expected`` verdict for the Rust target.

        AT-8: a convention-following zero-config Rust target CLEARS (the cargo
        path ran feature-scoped and passed) -- NEVER the pytest-collection
        ``FeatureScopeMalformed / zero-collected`` the HEAD pytest path emits.

        Active-RED at HEAD: the E2-routing short-circuit is absent, so the gate
        runs the pytest worker, collects zero on the crate, and emits
        ``FeatureScopeMalformed / zero-collected`` -> this AssertionError fires.
        """
        observed = self._observed_outcome()
        assert observed is expected, (
            f"the E2 contract gate must route a Rust (Cargo.toml) target through "
            f"the cargo run-facet and emit {expected.name}; instead it emitted "
            f"{observed.name if observed else None}. At HEAD "
            f"_mode_feature_scoped runs the pytest-bound _collect_node_ids worker "
            f"unconditionally, so the crate collects zero tests and the gate "
            f"degrades to FeatureScopeMalformed/zero-collected (the pytest bug "
            f"this slice fixes). The slice-03 short-circuit must seed the "
            f"registry + resolve(repo) FIRST and run cargo BEFORE any pytest "
            f"collection. {self._gate_observed()}"
        )

    def then_the_gate_does_not_emit_a_pytest_collection_failure(self) -> None:
        """AT-10: a Rust target NEVER reaches the pytest worker.

        The resolve-first short-circuit sits ABOVE the pytest collection, so a
        Cargo.toml target must NOT produce the pytest-collection verdict
        (``FeatureScopeMalformed`` with reason ``zero-collected`` /
        ``collection-failed``) -- the cargo facet is what runs.

        Active-RED at HEAD: the gate runs the pytest worker -> the crate collects
        zero -> ``FeatureScopeMalformed / zero-collected`` -> this fires.
        """
        verdict = self._verdict_payload()
        is_pytest_collection_failure = verdict.get(
            "event"
        ) == "FeatureScopeMalformed" and verdict.get("reason") in {
            "zero-collected",
            "collection-failed",
        }
        assert not is_pytest_collection_failure, (
            "a Rust (Cargo.toml) target must NEVER reach the pytest collection "
            "worker -- the runner-resolution short-circuit sits ABOVE the pytest "
            "collection, so a crate can never produce a pytest-collection "
            f"FeatureScopeMalformed verdict. The gate emitted {verdict!r}. At HEAD "
            "the short-circuit is absent, so the pytest worker runs and the crate "
            f"collects zero. {self._gate_observed()}"
        )

    def then_the_gate_drove_the_convention_derived_selector(self) -> None:
        """AT-9-absent: with NO runner.json, the gate DERIVED + drove
        ``binary(/<snake_feature_id>/)`` -- the zero-config NORMAL case.

        Observable: the fake cargo logged an invocation whose argv carries the
        convention-derived ``binary(/<snake>/)`` selector, and does NOT carry the
        override token. A missing runner.json must NOT degrade to INDETERMINATE
        and must NOT fall back to whole-crate.

        Active-RED at HEAD: the gate never invokes cargo (pytest path), so the
        sentinel is empty -> this AssertionError fires.
        """
        invocations = self._cargo_invocations()
        assert invocations, (
            "with no runner.json the gate must DERIVE the convention selector "
            f"{_DERIVED_BINARY_SELECTOR!r} from the feature-id and DRIVE cargo "
            "feature-scoped (the zero-config NORMAL case -- NOT an INDETERMINATE, "
            "NOT a whole-crate fall-back); at HEAD the gate runs the pytest path "
            f"and never invokes cargo so the sentinel is empty. {self._gate_observed()}"
        )
        joined = "\n".join(invocations)
        assert _DERIVED_BINARY_SELECTOR in joined, (
            "the gate must derive + drive the CONVENTION selector "
            f"{_DERIVED_BINARY_SELECTOR!r} (binary() axis over the FULL snake "
            "feature-id -- NOT test(), NOT a prefix, NOT whole-crate). cargo was "
            f"invoked as:\n{joined}\n{self._gate_observed()}"
        )
        assert _OVERRIDE_SENTINEL_TOKEN not in joined, (
            "with NO runner.json present the gate must NOT drive any override "
            f"command; the override token {_OVERRIDE_SENTINEL_TOKEN!r} must be "
            f"absent. cargo was invoked as:\n{joined}\n{self._gate_observed()}"
        )

    def then_the_gate_drove_the_runner_json_override(self) -> None:
        """AT-9-override: a runner.json ``test_command`` OVERRODE the derived
        selector -- the gate drove the OVERRIDE command, not the convention one.

        Observable: the fake cargo logged an invocation carrying the override's
        DISTINCT selector token, and NOT the convention-derived
        ``binary(/<snake>/)`` selector.

        Active-RED at HEAD: the gate never invokes cargo (pytest path), so the
        sentinel is empty -> this AssertionError fires.
        """
        invocations = self._cargo_invocations()
        assert invocations, (
            "with a runner.json override the gate must read it and DRIVE the "
            f"override test_command {_OVERRIDE_TEST_COMMAND!r}; at HEAD the gate "
            "runs the pytest path and never invokes cargo so the sentinel is "
            f"empty. {self._gate_observed()}"
        )
        joined = "\n".join(invocations)
        assert _OVERRIDE_SENTINEL_TOKEN in joined, (
            "the runner.json test_command must OVERRIDE the convention-derived "
            f"selector -- the gate must drive the override token "
            f"{_OVERRIDE_SENTINEL_TOKEN!r}. cargo was invoked as:\n{joined}\n"
            f"{self._gate_observed()}"
        )
        assert _DERIVED_BINARY_SELECTOR not in joined, (
            "when a runner.json override is present the gate must drive the "
            f"OVERRIDE command, NOT the convention-derived {_DERIVED_BINARY_SELECTOR!r} "
            f"selector. cargo was invoked as:\n{joined}\n{self._gate_observed()}"
        )

    # ---- observable parsing -------------------------------------------------

    def _verdict_payload(self) -> dict[str, object]:
        """The gate's verdict JSON line (the LAST parseable JSON on stdout).

        The gate prefixes a ``des.runtime.freshness.autoskipped`` JSON line; the
        VERDICT is the last well-formed JSON object emitted. Parse defensively:
        an unparseable / empty stdout (e.g. the child crashed) yields ``{}``, so
        the Then asserts against an honest "no verdict" rather than throwing.
        """
        verdict: dict[str, object] = {}
        for line in self._gate_out.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict) and "event" in parsed:
                verdict = parsed
        return verdict

    def _observed_outcome(self) -> GateOutcome | None:
        verdict = self._verdict_payload()
        event = verdict.get("event")
        reason = verdict.get("reason")
        if event == "FeatureScopeCleared":
            return GateOutcome.CLEARED
        if event == "FeatureScopeMalformed" and reason == "zero-collected":
            return GateOutcome.PYTEST_ZERO_COLLECTED
        # any other loud runner-resolution / indeterminate verdict
        if event in {"RunnerIndeterminate", "InterpreterUnavailable"} or (
            event == "FeatureScopeMalformed"
            and reason not in {"zero-collected", "collection-failed"}
        ):
            return GateOutcome.RUNNER_INDETERMINATE
        return None

    def _cargo_invocations(self) -> list[str]:
        """The argv lines the fake cargo logged (one per invocation)."""
        if self._cargo_argv_log is None or not self._cargo_argv_log.is_file():
            return []
        return [
            line
            for line in self._cargo_argv_log.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # ---- real-fixture helpers ----------------------------------------------

    def _ensure_root(self) -> Path:
        if self._root is None:
            self._tmp = tempfile.TemporaryDirectory(prefix="nwave-e2-routing-")
            self._root = Path(self._tmp.name)
            self._child_home = str(self._root / "home")
            (self._root / "home").mkdir(parents=True, exist_ok=True)
        return self._root

    @staticmethod
    def _plant_logging_fake_cargo(target: Path, argv_log: Path) -> Path:
        """Write a REAL chmod+x fake ``cargo`` that LOGS its argv then passes.

        On every invocation the fake appends its full argv (one line) to
        ``argv_log`` so an AT can observe WHICH selector the gate drove, then
        emits a passing cargo summary and exits 0 (a green run -> the gate
        CLEARS). It ignores the real cargo semantics -- the fixture controls the
        outcome deterministically, with no real cargo/nextest toolchain.
        """
        target.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> {str(argv_log)!r}\n'
            "echo 'test result: ok. 4 passed; 0 failed'\n"
            "exit 0\n",
            encoding="utf-8",
        )
        mode = target.stat().st_mode
        target.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return target

    def _run_child(self, argv: list[str]) -> tuple[int, str, str]:
        """Run the gate subprocess under a HERMETIC env.

        PATH carries ONLY the fixture's controlled dir (so the slice-03 wiring
        resolves the FAKE cargo, never an ambient host cargo). HOME is the
        fixture tmp home and CARGO_HOME is neutralised so a ``~`` known-location
        can never leak a real cargo. ``src`` + the repo root are on PYTHONPATH so
        the in-tree ``des`` package + the ``scripts`` plugin are importable in the
        child gate.
        """
        env = dict(os.environ)
        env["PATH"] = self._child_path
        env["HOME"] = self._child_home
        env.pop("CARGO_HOME", None)
        root = _repo_root()
        src = str(root / "src")
        existing = env.get("PYTHONPATH", "")
        prepend = src + os.pathsep + str(root)
        env["PYTHONPATH"] = prepend + os.pathsep + existing if existing else prepend
        completed = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        return completed.returncode, completed.stdout, completed.stderr

    # ---- diagnostics --------------------------------------------------------

    def _gate_observed(self) -> str:
        return (
            f"gate_rc={self._gate_rc!r}; "
            f"runner_json={self._runner_json_presence!r}; "
            f"target_root={str(self._target_root)!r}; "
            f"cargo_invocations={self._cargo_invocations()!r}; "
            f"gate_out={self._gate_out!r}; "
            f"gate_err_tail={self._gate_err[-600:]!r}"
        )


def _repo_root() -> Path:
    """Return the repo checkout root.

    tests/des/acceptance/rust_test_runner_adapter/steps/<file>
      parents: [0]=steps [1]=rust_test_runner_adapter [2]=acceptance [3]=des
      [4]=tests [5]=REPO_ROOT.
    """
    return Path(__file__).resolve().parents[5]
