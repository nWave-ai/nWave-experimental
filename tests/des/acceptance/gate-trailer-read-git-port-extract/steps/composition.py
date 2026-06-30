"""Composition root for the deliver-integrity trailer-read seam (slice-01).

This is the *only* place the production system is wired for the slice-01 ATs.
It drives the production ``des verify-integrity`` CLI end-to-end as a subprocess
black box (Mandate-13 driving-port-only, Layer 3 subprocess), mirroring the
proven subprocess driving-port pattern of the sibling suite
``tests/des/acceptance/oss-dormant-seam-gate/steps/composition.py``.

DRIVING PORT (load-bearing): ``_shipped_slices`` and the (future)
``CommitTrailerReadPort`` are NEVER imported-and-called at the step boundary --
the SUT is exercised only through the CLI subprocess
``python -m des.cli.verify_deliver_integrity <project-dir> --feature-id <id>``.
The observable surface is the process exit code, the single-line JSON
``FeatureIndeterminate`` event on stdout, and the human-readable reason -- nothing
else. The composition root default-wires the real ``GitCommitTrailerReadAdapter``
(post-GREEN), so the genuine git-absence degrade is exercised end-to-end.

SYNTHETIC SUBSTRATE (precondition state, NOT the SUT): a tmp deliver project that
carries a PRESENT, integrity-clean AT-completion ledger (a ``SliceCommitVerified``
record for slice-01 plus the 6 required feature-end records, written via the
real ``AtCompletionLedger`` + the shared ``feature_end_seeding`` helper) under an
``atdd_pure`` ``.nwave/config.yaml``. The substrate's git readability is the only
variable:

  * NOT_A_WORK_TREE: no ``.git`` -- ``git log`` raises ``CalledProcessError`` ->
    the seam MUST degrade LOUD to INDETERMINATE (exit 4), never the silent
    ``frozenset()`` that reads as "nothing shipped".
  * GIT_BINARY_ABSENT: same non-work-tree substrate, but the subprocess runs with
    a PATH from which ``git`` is removed -> ``git log`` raises
    ``FileNotFoundError`` -> the SAME LOUD INDETERMINATE (exit 4).
  * REAL_WORK_TREE_WITH_SLICE: a genuine ``git init`` work-tree whose history
    carries a ``Slice-Id: slice-01`` trailer + the matching ledger record ->
    the history IS readable -> the gate reconciles cleanly (exit 0). The
    non-vacuity control (KPI #2 guardrail).

PURE-READ CONTRACT (Mandate 8, layer-3 universe guard): des verify-integrity is a
pure observer of the deliver project -- it MUST NOT mutate it. ``capture_universe``
snapshots the port-exposed filesystem observables (the ledger + config + the
.git presence); the When-step asserts every entry is ``unchanged`` across the
invocation.

RED-for-right-reason (empirically confirmed at authorship HEAD): on master
``_shipped_slices`` swallows git-absence as
``except (CalledProcessError, FileNotFoundError): return frozenset()``
(verify_deliver_integrity.py:207-208). With a present, integrity-clean ledger and
NO readable git history, the gate falls through to the feature-end check and
EXITS 0 ("All slices have a complete AT-completion ledger trace"). The
``verdict`` therefore resolves to ``OTHER`` (exit 0, no ``FeatureIndeterminate``
event), so the cannot-evaluate Then-steps fail with a semantic AssertionError --
the LOUD verdict is absent. At GREEN (port + adapter + re-point) the verdict is
``CANNOT_EVALUATE`` (exit 4 + the event) and the assertions bind.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
that state. Step functions in ``test_slice_01_*.py`` are thin delegations to these
methods (Mandate-12 criterion 3: no business logic in step bodies).

DRIVING-SURFACE AMBIGUITY FOR THE CRAFTER (DELIVER): the AT pins the OBSERVABLE
verdict (exit 4 + a ``FeatureIndeterminate`` JSON event on stdout carrying a
cannot-evaluate reason), NOT the exact event-field shape. DESIGN names the event
``health.gate.deliver-integrity.indeterminate`` with a ``{"event":
"FeatureIndeterminate", "feature_id": ..., "reason": ...}`` payload; if DELIVER
chooses a slightly different field set, keep the ``FeatureIndeterminate`` event
marker + the exit-4 code + a human reason on stdout and the ATs still bind.
``_CANNOT_EVALUATE_EXIT`` and the event markers are the stable contract.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .domain_types import (
    CANNOT_EVALUATE_EVENT,
    CANNOT_EVALUATE_EXIT,
    INDETERMINATE_JSON_EVENT,
    FeatureId,
    GateVerdict,
    GitSubstrate,
)


# tests/des/acceptance/gate-trailer-read-git-port-extract/steps/composition.py
#   parents[5] = REPO_ROOT
REPO_ROOT = Path(__file__).resolve().parents[5]

# The production CLI module under test (present at HEAD; its silent-frozenset
# behavior is what slice-01 flips to LOUD).
VERIFY_MODULE = "des.cli.verify_deliver_integrity"

_FEATURE_ID = FeatureId("gate-trailer-read-probe-feat")
_SHIPPED_SLICE = "slice-01"
_VERDICT_HASH = "gate-trailer-read-slice-01-verdict-hash"

# The exit-1 unreconciled verdict tokens -- the cannot-evaluate refusal must be
# DISTINCT from these (DDD-G4: never conflate cannot-evaluate with unreconciled).
_UNRECONCILED_TOKENS: tuple[str, ...] = ("FeatureUnreconciled", "unreconciled")

# The silent-pass tokens -- the today-bug "nothing shipped" / clean-trace pass
# the refusal must NOT emit (the silent-fabrication this feature kills).
_NOTHING_SHIPPED_TOKENS: tuple[str, ...] = (
    "All slices have a complete",
    "FeatureReconciled",
)


@dataclass
class TrailerReadGateComposition:
    """Drives the production des verify-integrity CLI for the slice-01 ATs."""

    _tmp: Path | None = field(default=None)
    _project_dir: Path | None = field(default=None)
    _substrate: GitSubstrate = field(default=GitSubstrate.NOT_A_WORK_TREE)
    _completed: subprocess.CompletedProcess[str] | None = field(default=None)

    # ---- given ---------------------------------------------------------

    def given_non_work_tree_demanding_reconciliation(self) -> None:
        """A reconciliation-demanding deliver project that is NOT a git work-tree."""
        self._substrate = GitSubstrate.NOT_A_WORK_TREE
        self._build_substrate(GitSubstrate.NOT_A_WORK_TREE)

    def given_git_binary_unavailable_demanding_reconciliation(self) -> None:
        """A reconciliation-demanding deliver project with the git binary masked."""
        self._substrate = GitSubstrate.GIT_BINARY_ABSENT
        self._build_substrate(GitSubstrate.GIT_BINARY_ABSENT)

    def given_real_work_tree_with_recorded_slice(self) -> None:
        """A real git work-tree carrying a recorded shipped slice (non-vacuity control)."""
        self._substrate = GitSubstrate.REAL_WORK_TREE_WITH_SLICE
        self._build_substrate(GitSubstrate.REAL_WORK_TREE_WITH_SLICE)

    # ---- when ----------------------------------------------------------

    def when_operator_runs_verify_integrity(self) -> None:
        """Invoke the REAL des verify-integrity CLI as a subprocess black box.

        Universe-bound pure-read guard (Mandate 8): the deliver project is
        snapshot before and after; the gate is an observer and mutates nothing.
        """
        before = self.capture_universe()
        self._run_verify_integrity()
        self._assert_pure_read(before)

    # ---- then ----------------------------------------------------------

    def then_refuses_with_loud_cannot_evaluate(self) -> None:
        """The gate refuses with exit 4 AND the LOUD INDETERMINATE event."""
        completed = self._require_completed()
        assert self.verdict() is GateVerdict.CANNOT_EVALUATE, (
            "the gate must refuse with the LOUD cannot-evaluate verdict (exit "
            f"{CANNOT_EVALUATE_EXIT} + a {INDETERMINATE_JSON_EVENT} event on "
            f"stdout); got verdict={self.verdict().value!r}, "
            f"returncode={completed.returncode}. On master _shipped_slices "
            "silently returns frozenset() so the gate falls through to exit 0 -- "
            f"the silent fabrication this slice flips to LOUD. {self._observed()}"
        )

    def then_names_cannot_evaluate_reason(self) -> None:
        """The loud verdict names a cannot-evaluate reason (the seam could not read)."""
        event = self._indeterminate_event()
        reason = str(event.get("reason", "")).lower()
        assert reason.strip() != "", (
            "the cannot-evaluate verdict must carry a non-empty human reason "
            "naming why the trailer history could not be read (git absent / not "
            f"a work-tree). {self._observed()}"
        )

    def then_does_not_silently_report_nothing_shipped(self) -> None:
        """Non-vacuity: the refusal is NOT the today-bug silent nothing-shipped pass."""
        completed = self._require_completed()
        stdout = completed.stdout
        assert completed.returncode != 0, (
            "git-absence must never produce a passing exit 0 -- that is the "
            "silent-fabrication (frozenset() read as 'nothing shipped'). "
            f"{self._observed()}"
        )
        assert not any(token in stdout for token in _NOTHING_SHIPPED_TOKENS), (
            "the gate must not report the delivery as reconciled / 'nothing "
            "shipped' when it could not read the trailer history. "
            f"{self._observed()}"
        )

    def then_does_not_mutate_the_deliver_project(self) -> None:
        """Pure-read: the universe guard already ran in the When-step.

        The Mandate-8 state-delta assertion fires inside
        ``when_operator_runs_verify_integrity`` (the mutation, if any, happens
        during the invocation). This Then re-affirms the contract by confirming
        the run completed -- the actual no-mutation proof is the When-step's
        ``_assert_pure_read``.
        """
        self._require_completed()

    def then_cannot_evaluate_distinct_from_unreconciled(self) -> None:
        """The cannot-evaluate refusal is structurally distinct from unreconciled."""
        completed = self._require_completed()
        assert self.verdict() is GateVerdict.CANNOT_EVALUATE, (
            "the refusal must be the cannot-evaluate verdict (exit "
            f"{CANNOT_EVALUATE_EXIT}), not the exit-1 unreconciled verdict. "
            f"{self._observed()}"
        )
        assert completed.returncode != 1, (
            "cannot-evaluate (git unreadable) must NEVER be conflated with "
            "FeatureUnreconciled (exit 1, history read but a slice lacks a "
            f"ledger record) -- DDD-G4. {self._observed()}"
        )
        assert not any(token in completed.stdout for token in _UNRECONCILED_TOKENS), (
            "the cannot-evaluate refusal must not emit the unreconciled event; "
            f"the two non-passes are structurally distinct. {self._observed()}"
        )

    def then_reconciles_cleanly(self) -> None:
        """Non-vacuity control: a readable git history reconciles cleanly (exit 0)."""
        self._require_completed()
        assert self.verdict() is GateVerdict.RECONCILED, (
            "a real git work-tree carrying a recorded shipped slice must "
            "reconcile cleanly (exit 0 + FeatureReconciled); the cannot-evaluate "
            "refusal is bound to git-UNreadability and must not fire here. "
            f"{self._observed()}"
        )

    # ---- observable-verdict parsing ------------------------------------

    def verdict(self) -> GateVerdict:
        """Map the observable subprocess surface onto the user verdict.

        Reads the exit code + the single-line JSON events on stdout. Exit 4 with
        the INDETERMINATE event -> CANNOT_EVALUATE; exit 1 / FeatureUnreconciled
        -> UNRECONCILED; exit 0 / FeatureReconciled -> RECONCILED; anything else
        (incl. today's silent exit-0 clean-trace pass) -> OTHER.
        """
        completed = self._require_completed()
        rc = completed.returncode
        stdout = completed.stdout
        if rc == CANNOT_EVALUATE_EXIT and self._has_indeterminate_event():
            return GateVerdict.CANNOT_EVALUATE
        if rc == 1 or any(t in stdout for t in _UNRECONCILED_TOKENS):
            return GateVerdict.UNRECONCILED
        if rc == 0 and "FeatureReconciled" in stdout:
            return GateVerdict.RECONCILED
        return GateVerdict.OTHER

    def _has_indeterminate_event(self) -> bool:
        return self._find_indeterminate_event() is not None

    def _indeterminate_event(self) -> dict[str, object]:
        """The parsed LOUD INDETERMINATE event, or a semantic RED AssertionError.

        Raises (RED-for-right-reason) when the CLI emitted no parseable
        ``FeatureIndeterminate`` event -- on master the gate silently exits 0, so
        no such event exists and this raise IS the right-reason failure.
        """
        event = self._find_indeterminate_event()
        if event is None:
            raise AssertionError(
                "des verify-integrity produced no parseable single-line JSON "
                f"{INDETERMINATE_JSON_EVENT} event (the "
                f"{CANNOT_EVALUATE_EVENT} cannot-evaluate verdict is absent -- "
                "the gate silently passed instead of refusing LOUD). "
                f"{self._observed()}"
            )
        return event

    def _find_indeterminate_event(self) -> dict[str, object] | None:
        completed = self._require_completed()
        for line in reversed(completed.stdout.splitlines()):
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (
                isinstance(payload, dict)
                and payload.get("event") == INDETERMINATE_JSON_EVENT
            ):
                return payload
        return None

    def _observed(self) -> str:
        completed = self._require_completed()
        return (
            f"gate returncode={completed.returncode}; "
            f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
        )

    # ---- universe (Mandate 8 pure-read guard) --------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read guard (Mandate 8).

        Every entry is a port-exposed filesystem observable the gate could be
        tempted to touch -- never an internal struct field. The gate is a pure
        observer; the When-step asserts every entry is ``unchanged``.
        """
        project = self._require_project()
        ledger = project / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
        return {
            "config.yaml.exists": (project / ".nwave" / "config.yaml").exists(),
            "ledger.exists": ledger.exists(),
            "ledger.bytes": ledger.stat().st_size if ledger.exists() else 0,
            "git.exists": (project / ".git").exists(),
        }

    def _assert_pure_read(self, before: dict[str, object]) -> None:
        from tests.common.state_delta import assert_state_delta, unchanged

        assert_state_delta(
            before=before,
            after=self.capture_universe(),
            universe={
                "config.yaml.exists",
                "ledger.exists",
                "ledger.bytes",
                "git.exists",
            },
            expected={
                "config.yaml.exists": unchanged(),
                "ledger.exists": unchanged(),
                "ledger.bytes": unchanged(),
                "git.exists": unchanged(),
            },
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ----------

    def _build_substrate(self, substrate: GitSubstrate) -> None:
        """Build a tmp deliver project carrying a present, integrity-clean ledger.

        The ledger demands reconciliation (a `SliceCommitVerified` record for
        slice-01) AND records the 6 feature-end records, so the ONLY thing that
        can flip the verdict is the git readability of the substrate. git is
        consulted by `_shipped_slices`; on a non-work-tree it raises, which today
        is swallowed silently (RED) and post-GREEN degrades LOUD (exit 4).
        """
        self._tmp = Path(tempfile.mkdtemp(prefix="trailer-read-gate-at-"))
        self._project_dir = self._tmp
        nwave = self._tmp / ".nwave"
        nwave.mkdir(parents=True, exist_ok=True)
        (nwave / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )
        self._seed_clean_ledger()
        if substrate is GitSubstrate.REAL_WORK_TREE_WITH_SLICE:
            self._init_git_with_recorded_slice()

    def _seed_clean_ledger(self) -> None:
        """Write a genuine M7 integrity-clean ledger via the real AtCompletionLedger.

        A `SliceCommitVerified` record for slice-01 (the reconciliation demand)
        plus the 6 U4-required feature-end records, seeded structurally via the
        shared helper so a frozenset extension stays a one-line change.
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        project = self._require_project()
        ledger = AtCompletionLedger(_FEATURE_ID, project)
        ledger.append_gate_event(event="SliceCommitVerified", slice_id=_SHIPPED_SLICE)
        seed_required_feature_end_records(ledger, verdict_hash=_VERDICT_HASH)

    def _init_git_with_recorded_slice(self) -> None:
        """Make the substrate a real git work-tree carrying a Slice-Id commit.

        The committed history carries a `Slice-Id: slice-01` trailer so
        `_shipped_slices` reads slice-01 as shipped; the ledger (seeded above)
        already records its `SliceCommitVerified`, so the gate reconciles cleanly
        (exit 0). The non-vacuity control.
        """
        project = self._require_project()
        run = lambda *a: subprocess.run(  # noqa: E731 -- terse local for the git setup
            list(a), cwd=project, check=True, capture_output=True, text=True
        )
        run("git", "init", "-q")
        run("git", "config", "user.email", "at@example.com")
        run("git", "config", "user.name", "at")
        (project / "README.md").write_text(
            "trailer-read-gate control\n", encoding="utf-8"
        )
        run("git", "add", "-A")
        run(
            "git",
            "commit",
            "-q",
            "-m",
            f"ship the recorded slice\n\nSlice-Id: {_SHIPPED_SLICE}",
        )

    def _run_verify_integrity(self) -> None:
        """Run `python -m des.cli.verify_deliver_integrity` as a subprocess black box.

        Env-parity: a clean subprocess env with `NWAVE_FRESHNESS=skip` +
        `PIPENV_DONT_LOAD_ENV=1`. The freshness opt-out (`skip`, the §1.8 operator
        opt-out token) is REQUIRED because cwd is the synthetic non-git tmp tree:
        without it the freshness CLI wrapper finds no install manifest and refuses
        with exit 78 BEFORE the verifier logic runs, masking the trailer-read
        verdict entirely. `skip` isolates the SUT (the trailer-read seam) from the
        orthogonal freshness concern. `src` on PYTHONPATH so the importable
        `des.cli` module resolves the same way the kebab dispatcher would. cwd is
        the synthetic project. For GIT_BINARY_ABSENT the PATH is narrowed to a
        single tmp dir holding no `git`, so the subprocess's `git` resolution
        raises FileNotFoundError -- the genuine binary-absent degrade.
        """
        project = self._require_project()
        env = dict(os.environ)
        env["NWAVE_FRESHNESS"] = "skip"
        env["PIPENV_DONT_LOAD_ENV"] = "1"
        env["PYTHONPATH"] = (
            str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        )
        if self._substrate is GitSubstrate.GIT_BINARY_ABSENT:
            # Narrow PATH to a git-free directory so the gate cannot resolve the
            # git binary (FileNotFoundError) -- the binary-absent failure mode.
            # The in-process gate still forks `git` (external tool); the swapped
            # os.environ PATH makes that fork unresolvable, faithfully.
            git_free = self._tmp / "_no_git_path" if self._tmp else None
            assert git_free is not None
            git_free.mkdir(parents=True, exist_ok=True)
            env["PATH"] = str(git_free)
        from des.cli import verify_deliver_integrity
        from tests.common.in_process_cli import run_cli_in_process

        exit_code, stdout, stderr = run_cli_in_process(
            [str(project), "--feature-id", str(_FEATURE_ID)],
            cwd=str(project),
            main=verify_deliver_integrity.main,
            env=env,
            catch_all=True,
        )
        self._completed = subprocess.CompletedProcess(
            args=[
                "python",
                "-m",
                VERIFY_MODULE,
                str(project),
                "--feature-id",
                str(_FEATURE_ID),
            ],
            returncode=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    def _require_project(self) -> Path:
        assert self._project_dir is not None, (
            "the synthetic deliver project must be built (Given) before "
            "capturing its universe or running the gate (When)"
        )
        return self._project_dir

    def _require_completed(self) -> subprocess.CompletedProcess[str]:
        assert self._completed is not None, (
            "des verify-integrity must be run (When) before asserting on its "
            "observable verdict surface (Then)"
        )
        return self._completed

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
