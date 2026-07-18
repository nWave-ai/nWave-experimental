"""Composition root for the des-e2-contract-gate-degrade-loud ATs (slice-01).

The interpreter-absence degrade-loud story across three production surfaces +
a Python happy-path preservation guard. Mandate-13 (driving-port-only) +
Pillar 3: every assertion reads an artifact the REAL SUT shipped (a captured
stdout JSON event, a process exit code, a record on the real
``AtCompletionLedger``) -- never a structure the test fabricated.

Driving ports (one per AC):

* AC-1 -- the REAL ``des.cli.run_contract_gate`` ``main`` (Layer-3 subprocess).
  The interpreter-absence branch is FORCED deterministically: a tiny in-line
  driver monkeypatches the production ``des.runtime.interpreter.python_for`` to
  raise ``InterpreterUnavailable`` BEFORE invoking the real gate ``main`` with
  the real ``--feature-id``/``--entering-slice`` args, so the gate's own
  ``_mode_feature_scoped`` collection path hits the absent-interpreter seam --
  not an environment accident (feature-delta §AT_INSUFFICIENT_FOR_GREEN).

* AC-2 -- the REAL ``des.cli.verify_slice_commit_completeness`` ``main``
  (Layer-3 subprocess), same forced-INDETERMINATE E2. The observable is the
  real on-disk ledger read back through the production ``AtCompletionLedger``.

* AC-3 -- the REAL U1 carpaccio PreToolUse intercept
  ``intercept_atdd_pure_dispatch`` (Layer-3 composition). The predicate under
  test is ``_carpaccio_order_block`` (``carpaccio_intercept.py`` lines 423/432:
  ``predecessor in ledger.verified_slices()``). The substrate seeds a
  ``SliceCommitIndeterminate`` predecessor through the production ledger writer
  and reads the intercept verdict back.

* AC-4 -- the REAL ``verify_slice_commit_completeness`` ``main`` with a usable
  interpreter and a passing feature-scoped gate; the preserved
  ``SliceCommitVerified`` mint + exit 0 is read back from the real ledger.

The git repo, the feature-delta ``[REF] Slice Plan``, the ``.feature`` files,
and the ledger JSONL are all real I/O -- a Layer-3 ``@real-io`` surface
(Mandate 9/11: example-only, no PBT machinery; sad/edge paths enumerated
explicitly). Business logic lives in the production modules; step bodies
delegate to ``DegradeLoudComposition`` methods and never inline logic
(Mandate-12 criterion 3).
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import des.adapters.driven.runner.pytest_runner as _pytest_runner
import des.runtime.interpreter as _interp
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    intercept_atdd_pure_dispatch,
)
from des.cli import run_contract_gate as _run_contract_gate_mod
from des.cli import verify_slice_commit_completeness as _verify_mod
from des.runtime.interpreter import InterpreterUnavailable, des_subprocess_env
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    EntryGateVerdict,
    FeatureId,
    GateOutcome,
    LedgerRecord,
)


_FEATURE_ID = FeatureId("e2-degrade-loud-demo")

# The LOUD INDETERMINATE marker the degrade-loud gate must emit on
# interpreter-absence. This is the observable AC-1 binds to: the gate ROUTES to
# a LOUD-INDETERMINATE-and-proceed (mirroring the committed-scope
# `health.gate.committed-scope.indeterminate` shape at run_contract_gate.py:825)
# rather than the status-quo `InterpreterUnavailable` exit-2 event. The exact
# event name is a production decision DELIVER pins; this AT asserts the
# observable INVARIANTS: NOT the exit-2 `InterpreterUnavailable` event AND a
# non-2 return code AND a loud "indeterminate" signal on stdout.
_EXIT2_REFUSE_EVENT = "InterpreterUnavailable"
_INDETERMINATE_TOKEN = "indeterminate"


def _git(repo: Path, *args: str) -> str:
    """Run a real git command in ``repo`` (no test double -- real I/O)."""
    completed = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return completed.stdout.strip()


@contextlib.contextmanager
def _force_interpreter_absent() -> Iterator[None]:
    """Force the production interpreter resolver to raise IN-PROCESS.

    The faithful in-process analogue of the old hermetic ``python -c`` driver,
    which monkeypatched ``des.runtime.interpreter.python_for`` to raise BEFORE
    importing the gate (so the gate's transitive ``from ... import python_for``
    bound the raising stub). In-process every module is ALREADY imported, so the
    name-bound copies must be patched directly: ``interpreter.python_for`` (the
    ``des_spawn`` path verify-slice-commit reaches) AND
    ``pytest_runner.python_for`` (the ``pytest_interpreter`` path
    run_contract_gate's feature-scoped collection reaches). Both restored in
    ``finally`` — shared-process safe. Every resolution path hits the
    absent-interpreter seam deterministically, never an environment accident.
    """

    def _raise(capability: object = None, *, repo_root: object = None) -> str:
        # `repo_root` (slice-02, defect #79 D1): production `python_for` now
        # accepts an optional `repo_root=` kwarg (`pytest_interpreter`
        # threads it through) -- the double must accept the SAME call shape
        # so every resolution path still hits this forced-absent seam,
        # rather than crashing on an unexpected keyword argument.
        raise InterpreterUnavailable(str(capability or "pytest"), ["<forced-absent>"])

    prior_interp = _interp.python_for
    prior_runner = _pytest_runner.python_for
    _interp.python_for = _raise  # type: ignore[assignment]
    _pytest_runner.python_for = _raise  # type: ignore[assignment]
    try:
        yield
    finally:
        _interp.python_for = prior_interp
        _pytest_runner.python_for = prior_runner


@contextlib.contextmanager
def _des_subprocess_pythonpath() -> Iterator[None]:
    """Apply ``des_subprocess_env`` PYTHONPATH to ``os.environ`` IN-PROCESS.

    The subprocess forks ran with ``env=des_subprocess_env()`` so any child the
    gate spawns inherited ``des`` on PYTHONPATH. In-process the gate inherits the
    live ``os.environ``; mirror the same PYTHONPATH prepend (and ONLY that — the
    rest of the env is identical) around the call, restored in ``finally``.
    """
    prior = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = des_subprocess_env()["PYTHONPATH"]
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop("PYTHONPATH", None)
        else:
            os.environ["PYTHONPATH"] = prior


@dataclass
class GateRun:
    """The observable result of one real CLI gate invocation."""

    returncode: int
    stdout: str
    stderr: str

    def events(self) -> list[dict[str, object]]:
        """Every single-line JSON event the gate emitted across both channels."""
        records: list[dict[str, object]] = []
        for stream in (self.stdout, self.stderr):
            for line in stream.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
        return records


@dataclass
class EntryGateOutcome:
    """The observable result of one carpaccio in-order guard evaluation."""

    verdict: EntryGateVerdict
    event: str | None


class DegradeLoudComposition:
    """Production-wired composition root for the E2 degrade-loud slice.

    Holds the real tmp git repo, the real feature-delta + ``.feature``
    substrate, and the real ``AtCompletionLedger``. Each ``drive_*`` method
    invokes a REAL production driving port; each ``observe_*`` reads back a real
    shipped artifact.
    """

    def __init__(self, repo: Path) -> None:
        self._repo = repo
        self._feature_id = _FEATURE_ID
        self._predecessor = "slice-01"
        self._successor = "slice-02"
        self._ledger = AtCompletionLedger(self._feature_id, repo)
        self._gate_run: GateRun | None = None

    # --- precondition substrate (real git + real feature scope) -------------

    def init_repo(self) -> None:
        """Initialise a real git repo + the feature's `.feature` scope on disk.

        A genuinely-collectable feature scope (a `.feature` whose `@slice-NN`
        tags the gate resolves) so that, WITH an interpreter, the gate would
        reach a real collection -- the interpreter-absent branch is the only
        thing the force-driver short-circuits (AC-1/AC-2 fail for the right
        reason, never a substrate-missing accident).
        """
        _git(self._repo, "init")
        _git(self._repo, "config", "user.email", "t@t.com")
        _git(self._repo, "config", "user.name", "T")
        self._write_feature_delta()
        self._write_feature_file()
        self._write_collectable_scope_test()
        (self._repo / "README.md").write_text("seed\n", encoding="utf-8")
        _git(self._repo, "add", "-A")
        _git(
            self._repo,
            "commit",
            "-m",
            f"feat: seed slice work\n\nSlice-Id: {self._predecessor}",
        )

    def _write_feature_delta(self) -> None:
        """Write a minimal feature-delta carrying a ``[REF] Slice Plan`` row."""
        delta_dir = self._repo / "docs" / "feature" / self._feature_id
        delta_dir.mkdir(parents=True, exist_ok=True)
        (delta_dir / "feature-delta.md").write_text(
            "# Feature Delta: e2-degrade-loud-demo\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement | Status | Annotation | Justification |\n"
            "|-------|-----------------|--------|------------|---------------|\n"
            f"| {self._predecessor} | seed | pending | | one |\n"
            f"| {self._successor} | next | pending | | two |\n",
            encoding="utf-8",
        )

    def _write_feature_file(self) -> Path:
        """Write the feature's `.feature` AT file (real collectable scope)."""
        slice_dir = (
            self._repo
            / "tests"
            / "des"
            / "acceptance"
            / self._feature_id
            / "acceptance"
        )
        slice_dir.mkdir(parents=True, exist_ok=True)
        feature_file = slice_dir / "demo.feature"
        feature_file.write_text(
            f"@feature-{self._feature_id}\n"
            "Feature: demo feature\n\n"
            f"  @{self._predecessor}\n"
            "  Scenario: predecessor work\n    Given y\n\n"
            f"  @{self._successor}\n"
            "  Scenario: successor work\n    Given z\n",
            encoding="utf-8",
        )
        return feature_file

    def _write_collectable_scope_test(self) -> Path:
        """Write a genuinely-collectable passing test in the feature's scope.

        The E2 feature-scoped gate's M-1 floor requires the feature's test scope
        to GENUINELY collect at least one runnable node-id under the contract
        marker (`unit or integration or acceptance`) -- a bare `.feature` with
        no bound step module collects zero and the gate refuses (zero-collected,
        never a vacuous pass). This trivially-passing acceptance-marked test
        gives the WITH-interpreter happy path (AC-4) a real collectable+passing
        scope so the genuine ``SliceCommitVerified`` mint is exercised; it is
        irrelevant to AC-1/AC-2 (their interpreter never resolves) and to AC-3
        (the in-order guard reads the ledger, not the test scope).
        """
        scope_dir = (
            self._repo
            / "tests"
            / "des"
            / "acceptance"
            / self._feature_id
            / "acceptance"
        )
        scope_dir.mkdir(parents=True, exist_ok=True)
        test_file = scope_dir / "test_demo_scope.py"
        test_file.write_text(
            "import pytest\n\n"
            "pytestmark = pytest.mark.acceptance\n\n\n"
            "def test_demo_scope_passes():\n    assert True\n",
            encoding="utf-8",
        )
        return test_file

    def seed_predecessor_indeterminate_record(self) -> None:
        """Append a real ``SliceCommitIndeterminate`` predecessor ledger record.

        The AC-3 precondition: the honest "unverified on this machine" record
        the interpreter-absent E2 path mints, written through the PRODUCTION
        ledger writer (``append_gate_event``) onto the carpaccio chain's read
        substrate -- the exact substrate ``_carpaccio_order_block`` reads.
        """
        self._ledger.append_gate_event(
            LedgerRecord.SLICE_COMMIT_INDETERMINATE.value, self._predecessor
        )

    def seed_predecessor_verified_record(self) -> None:
        """Append a real ``SliceCommitVerified`` predecessor record (control)."""
        self._ledger.append_gate_event(
            LedgerRecord.SLICE_COMMIT_VERIFIED.value, self._predecessor
        )

    # --- driving-port invocation (real production surfaces) -----------------

    def drive_run_contract_gate_without_interpreter(self) -> None:
        """Drive the REAL run_contract_gate with the interpreter forced absent.

        Layer-3 subprocess: a hermetic driver monkeypatches the production
        ``python_for`` resolver to raise ``InterpreterUnavailable``, then calls
        the real ``run_contract_gate.main`` with the real feature-scoped argv.
        The gate's own ``_mode_feature_scoped`` collection seam hits the
        absent-interpreter branch -- the genuine production code path.
        """
        argv = [
            "--repo",
            str(self._repo),
            "--feature-id",
            str(self._feature_id),
            "--entering-slice",
            self._predecessor,
        ]
        self._gate_run = self._run_forced_absent(_run_contract_gate_mod.main, argv)

    def drive_verify_slice_commit_without_interpreter(self) -> None:
        """Drive the REAL verify-slice-commit with the E2 interpreter absent.

        Layer-3 subprocess: same forced-absent driver wrapping the real
        ``verify_slice_commit_completeness.main`` ``--feature-id`` exit gate, so
        its E2 contract-gate half resolves INDETERMINATE.
        """
        argv = [
            "--repo",
            str(self._repo),
            "--commit",
            "HEAD",
            "--feature-id",
            str(self._feature_id),
        ]
        self._gate_run = self._run_forced_absent(_verify_mod.main, argv)

    def drive_verify_slice_commit_with_interpreter(self) -> None:
        """Drive the REAL verify-slice-commit with a usable interpreter (AC-4).

        No forcing: the running interpreter resolves pytest, the feature-scoped
        gate collects + passes, and the producer mints ``SliceCommitVerified``.
        The preservation guard -- the Python happy path is unchanged.
        """
        argv = [
            "--repo",
            str(self._repo),
            "--commit",
            "HEAD",
            "--feature-id",
            str(self._feature_id),
        ]
        with _des_subprocess_pythonpath():
            returncode, stdout, stderr = run_cli_in_process(
                argv, cwd=self._repo, main=_verify_mod.main
            )
        self._gate_run = GateRun(returncode, stdout, stderr)

    def drive_in_order_guard_for_successor(self) -> EntryGateOutcome:
        """Evaluate the REAL U1 carpaccio in-order guard for the successor slice.

        Layer-3 composition: the production ``intercept_atdd_pure_dispatch``
        driving port. The carpaccio + readiness runners are pre-cleared so the
        sole observable is ``_carpaccio_order_block``'s predecessor-satisfied
        decision against the seeded ``SliceCommitIndeterminate`` record.
        """
        decision = intercept_atdd_pure_dispatch(
            prompt=_dispatch_prompt(self._successor),
            feature_id=str(self._feature_id),
            project_root=self._repo,
            carpaccio_runner=lambda _f, _s: (
                0,
                json.dumps({"event": "SliceCleared", "slice_id": _s}),
            ),
            readiness_runner=lambda _f, _s: (0, ""),
        )
        return EntryGateOutcome(
            verdict=(
                EntryGateVerdict.BLOCKED
                if decision.is_block
                else EntryGateVerdict.ALLOWED
            ),
            event=decision.event,
        )

    def _run_forced_absent(
        self, main: Callable[[list[str]], int], argv: list[str]
    ) -> GateRun:
        """Run ``main(argv)`` IN-PROCESS with ``python_for`` forced to raise.

        The faithful in-process analogue of the old hermetic ``python -c``
        driver: ``_force_interpreter_absent`` patches the production resolver so
        the gate's collection seam hits the absent-interpreter branch, then the
        real ``main(argv)`` is driven in-process (output captured), restored on
        exit. Behaviour-identical to the subprocess for every assertion.
        """
        with _force_interpreter_absent(), _des_subprocess_pythonpath():
            returncode, stdout, stderr = run_cli_in_process(
                argv, cwd=self._repo, main=main
            )
        return GateRun(returncode, stdout, stderr)

    # --- observable readback (shipped artifacts) ----------------------------

    def observed_gate_outcome(self) -> GateOutcome:
        """Classify the last gate run's observable outcome (stdout events + rc).

        INDETERMINATE iff the gate emitted a LOUD ``indeterminate`` signal AND
        did NOT hard-refuse (return != 2) AND did NOT emit the status-quo
        exit-2 ``InterpreterUnavailable`` event. HARD_REFUSE iff it emitted that
        event or returned 2. PASS iff it returned 0.
        """
        run = self._require_gate_run()
        events = run.events()
        emitted_event_names = {str(e.get("event", "")) for e in events}
        raw = (run.stdout + run.stderr).lower()
        hard_refused = run.returncode == 2 or _EXIT2_REFUSE_EVENT in emitted_event_names
        if run.returncode == 0:
            return GateOutcome.PASS
        if _INDETERMINATE_TOKEN in raw and not hard_refused:
            return GateOutcome.INDETERMINATE
        return GateOutcome.HARD_REFUSE

    def ledger_has_record(self, record: LedgerRecord) -> bool:
        """Whether the real on-disk ledger carries any ``record`` event."""
        return any(r.get("event") == record.value for r in self._ledger.read_records())

    def gate_returncode(self) -> int:
        """The last gate run's process exit code (a shipped artifact)."""
        return self._require_gate_run().returncode

    def _require_gate_run(self) -> GateRun:
        assert self._gate_run is not None, "no gate has been driven yet"
        return self._gate_run


def _dispatch_prompt(slice_id: str) -> str:
    """Render a valid atdd_pure A_GREEN_ATS dispatch entering ``slice_id``."""
    return (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : A_GREEN_ATS -->\n"
        f"<!-- DES-SLICE : {slice_id} -->\n"
        "\natdd_pure dispatch body.\n"
    )
