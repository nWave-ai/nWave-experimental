"""Composition root for the deliver-integrity GIT-FREE CORE seam (slice-02).

This is the *only* place the production gate core is wired for the slice-02 ATs.
Where slice-01 drove the production CLI as a subprocess black box (the real git
adapter, the git-ABSENCE degrade), slice-02 proves the distinct genericita claim
slice-01 leaves untested: the gate CORE is genuinely git-FREE -- a NON-git
``CommitTrailerReadPort`` can feed the verdict and reconcile / refuse WITHOUT any
git involvement at all.

DRIVING SEAM (Mandate-13, tolerable contract-AT variant -- the R3 slice-03 shape):
the value "the core is git-free, the port is genuinely swappable" CANNOT be proven
through the slice-01 subprocess black box, because ``main()`` HARDCODES
``trailer_port=GitCommitTrailerReadAdapter()`` (verify_deliver_integrity.py:645) --
no env/flag selects a non-git source. The honest seam is the gate core's PUBLIC
DESIGN-INTENDED INJECTION POINT:

    ``_verify_atdd_pure(project_dir, roadmap_path, feature_id, trailer_port=<fake>)``

-- the driving-side-consumed driven-port boundary the DESIGN composition-root
wiring exists for. A FAKE ``CommitTrailerReadPort`` honoring the SAME interface is
substituted (Architecture-of-Reference: an in-memory double for a driven port).
This is NOT a forbidden direct-domain import: the substrate is exercised THROUGH
the port boundary the architecture designed for substitution -- the test never
reaches into the trailer-scan internals (``_shipped_slices``'s `re` scan, the
ledger reconciliation set), it only supplies the port's return value and reads the
observable verdict (exit code + the single-line JSON events the core prints). The
fake is the ONLY driven adapter in the composition, so per Mandate 9 v2
OR-reduction this slice is ``@in-memory`` and example-based + ``assert_state_delta``
is the correct treatment.

GIT-FREEDOM PROOF (the load-bearing genericita assertion): every Given builds a
``tmp_path`` that is NOT a git work-tree (no ``.git``). If the gate core had ANY
residual git coupling it would itself raise on the non-work-tree; instead the
verdict is derived ENTIRELY from what the fake port returns. The core reconciling
/ refusing on a non-git tree, fed only by the fake, IS the proof it is git-free.

NON-VACUITY: the RECORDS_SHIPPED_SLICE source (reconciles, exit 0) is paired with
MISSING_SHIPPED_SLICE (unreconciled, exit 1) and CANNOT_READ (Indeterminate, exit
4). The verdict genuinely depends on what the port returns -- reconciliation is
not vacuously always-on, and the LOUD refusal is a port-contract property (any
unreadable source refuses), not git-specific.

PURE-READ CONTRACT (Mandate 8, layer-2 universe guard): the gate core is a pure
observer of the deliver project. ``capture_universe`` snapshots the port-exposed
filesystem observables (the ledger + config + the .git ABSENCE); the When-step
asserts every entry is ``unchanged`` across the invocation -- AND that
``git.exists`` stays ``False`` throughout, the structural git-freedom guard.

State lives on the instance; every ``given_/when_/then_`` method mutates or reads
that state. Step functions in ``test_slice_02_*.py`` are thin delegations to these
methods (Mandate-12 criterion 3: no business logic in step bodies).
"""

from __future__ import annotations

import io
import json
import shutil
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path

from des.ports.driven_ports.commit_trailer_read_port import (
    CommitMessages,
    CommitTrailerReadPort,
    Indeterminate,
)

from .domain_types_slice_02 import (
    CANNOT_EVALUATE_EXIT,
    INDETERMINATE_JSON_EVENT,
    FeatureId,
    GateVerdict,
    NonGitTrailerSource,
)


_FEATURE_ID = FeatureId("gate-trailer-read-non-git-core-feat")
_DEMANDED_SLICE = "slice-01"
# A DIFFERENT slice id the MISSING_SHIPPED_SLICE source records -- present in the
# (fake) trailer stream but NOT the slice the ledger demands reconciliation for,
# so the core leaves the delivery unreconciled (the non-vacuity control).
_OTHER_SLICE = "slice-99"
_VERDICT_HASH = "gate-trailer-read-slice-02-verdict-hash"

# The exit-1 unreconciled verdict tokens -- the cannot-evaluate refusal must be
# DISTINCT from these (DDD-G4: never conflate cannot-evaluate with unreconciled).
_UNRECONCILED_TOKENS: tuple[str, ...] = ("FeatureUnreconciled", "unreconciled")


class _FakeNonGitTrailerSource(CommitTrailerReadPort):
    """An in-memory, NON-git CommitTrailerReadPort honoring the same interface.

    This is the whole point of slice-02: the gate core depends only on the
    ``CommitTrailerReadPort`` abstraction, so a source that has NOTHING to do
    with git (here a hand-built message stream) feeds the verdict identically.
    ``commit_messages`` ignores ``repo`` entirely -- it consults no filesystem,
    spawns no subprocess, touches no git -- and returns the pre-built result.
    """

    def __init__(self, result: CommitMessages | Indeterminate) -> None:
        self._result = result

    def commit_messages(self, repo: Path) -> CommitMessages | Indeterminate:
        # Git-free by construction: no filesystem read, no subprocess, no `repo`
        # consultation -- the source IS the in-memory stream supplied at build.
        return self._result


def _build_fake_source(source: NonGitTrailerSource) -> CommitTrailerReadPort:
    """Map the typed non-git source mode onto a fake port returning its stream."""
    if source is NonGitTrailerSource.RECORDS_SHIPPED_SLICE:
        return _FakeNonGitTrailerSource(
            CommitMessages((f"ship the demanded slice\n\nSlice-Id: {_DEMANDED_SLICE}",))
        )
    if source is NonGitTrailerSource.MISSING_SHIPPED_SLICE:
        return _FakeNonGitTrailerSource(
            CommitMessages((f"ship an unrelated slice\n\nSlice-Id: {_OTHER_SLICE}",))
        )
    return _FakeNonGitTrailerSource(
        Indeterminate("non-git trailer source could not read its history")
    )


@dataclass
class GitFreeCoreComposition:
    """Drives the production deliver-integrity gate core via a non-git port."""

    _tmp: Path | None = field(default=None)
    _project_dir: Path | None = field(default=None)
    _source: NonGitTrailerSource = field(
        default=NonGitTrailerSource.RECORDS_SHIPPED_SLICE
    )
    _port: CommitTrailerReadPort | None = field(default=None)
    _exit_code: int | None = field(default=None)
    _stdout: str = field(default="")

    # ---- given ---------------------------------------------------------

    def given_non_git_tree_demanding_reconciliation(self) -> None:
        """A reconciliation-demanding deliver project in a NON-git tree (no .git)."""
        self._build_substrate()

    def given_source_records_shipped_slice(self) -> None:
        """The non-git source records the demanded slice's trailer."""
        self._set_source(NonGitTrailerSource.RECORDS_SHIPPED_SLICE)

    def given_source_missing_shipped_slice(self) -> None:
        """The non-git source records only an UNRELATED slice's trailer."""
        self._set_source(NonGitTrailerSource.MISSING_SHIPPED_SLICE)

    def given_source_cannot_read(self) -> None:
        """The non-git source returns Indeterminate (it could not read)."""
        self._set_source(NonGitTrailerSource.CANNOT_READ)

    # ---- when ----------------------------------------------------------

    def when_operator_verifies_through_git_free_core(self) -> None:
        """Drive `_verify_atdd_pure(..., trailer_port=<fake>)` -- the git-free core.

        Universe-bound pure-read guard (Mandate 8) + the git-freedom guard: the
        deliver project is snapshot before and after; the core mutates nothing AND
        never makes the tree a git work-tree (``git.exists`` stays False).
        """
        before = self.capture_universe()
        self._run_git_free_core()
        self._assert_pure_read_and_git_free(before)

    # ---- then ----------------------------------------------------------

    def then_reconciles_cleanly_without_git(self) -> None:
        """The core reconciles (exit 0 + FeatureReconciled) fed by the non-git port."""
        assert self.verdict() is GateVerdict.RECONCILED, (
            "a non-git CommitTrailerReadPort recording the demanded slice must "
            "reconcile the delivery cleanly (exit 0 + FeatureReconciled) -- the "
            "gate core is git-free, so the verdict is derived purely from the "
            f"port. {self._observed()}"
        )

    def then_does_not_mutate_the_deliver_project(self) -> None:
        """Pure-read + git-free: the guard already ran in the When-step.

        The Mandate-8 state-delta assertion (incl. ``git.exists`` unchanged-False)
        fires inside ``when_operator_verifies_through_git_free_core``. This Then
        re-affirms the contract by confirming the run completed.
        """
        self._require_completed()

    def then_leaves_delivery_unreconciled(self) -> None:
        """Non-vacuity: a non-matching non-git source leaves the delivery unreconciled."""
        assert self.verdict() is GateVerdict.UNRECONCILED, (
            "a non-git source recording an UNRELATED slice (not the demanded one) "
            "must leave the delivery unreconciled (exit 1 + FeatureUnreconciled) "
            "-- the reconciliation genuinely depends on what the port returns, it "
            f"is not vacuously always-on. {self._observed()}"
        )

    def then_unreconciled_distinct_from_cannot_evaluate(self) -> None:
        """The unreconciled verdict is structurally distinct from cannot-evaluate."""
        exit_code = self._require_completed()
        assert exit_code != CANNOT_EVALUATE_EXIT, (
            "unreconciled (the history WAS read, a slice lacks a ledger record) "
            "must NEVER be conflated with cannot-evaluate (the source could not "
            f"read -> exit {CANNOT_EVALUATE_EXIT}) -- DDD-G4. {self._observed()}"
        )
        assert INDETERMINATE_JSON_EVENT not in self._stdout, (
            "the unreconciled verdict must not emit the cannot-evaluate event; "
            f"the two non-passes are structurally distinct. {self._observed()}"
        )

    def then_refuses_with_loud_cannot_evaluate(self) -> None:
        """A non-git source that cannot read refuses LOUD (port-contract degrade)."""
        assert self.verdict() is GateVerdict.CANNOT_EVALUATE, (
            "a non-git source returning Indeterminate must make the core refuse "
            f"with the LOUD cannot-evaluate verdict (exit {CANNOT_EVALUATE_EXIT} + "
            f"a {INDETERMINATE_JSON_EVENT} event) -- the degrade-LOUD path is a "
            "PORT-CONTRACT property (any unreadable source refuses), not a "
            f"git-specific behavior. {self._observed()}"
        )

    # ---- observable-verdict parsing ------------------------------------

    def verdict(self) -> GateVerdict:
        """Map the observable verdict surface onto the user verdict.

        Reads the in-process exit code + the single-line JSON events the core
        printed. Exit 4 + the INDETERMINATE event -> CANNOT_EVALUATE; exit 1 /
        FeatureUnreconciled -> UNRECONCILED; exit 0 / FeatureReconciled ->
        RECONCILED; anything else -> OTHER.
        """
        exit_code = self._require_completed()
        if exit_code == CANNOT_EVALUATE_EXIT and self._has_indeterminate_event():
            return GateVerdict.CANNOT_EVALUATE
        if exit_code == 1 or any(t in self._stdout for t in _UNRECONCILED_TOKENS):
            return GateVerdict.UNRECONCILED
        if exit_code == 0 and "FeatureReconciled" in self._stdout:
            return GateVerdict.RECONCILED
        return GateVerdict.OTHER

    def _has_indeterminate_event(self) -> bool:
        return self._find_indeterminate_event() is not None

    def _find_indeterminate_event(self) -> dict[str, object] | None:
        for line in reversed(self._stdout.splitlines()):
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
        return f"core exit_code={self._exit_code}; stdout={self._stdout!r}"

    # ---- universe (Mandate 8 pure-read + git-freedom guard) ------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for the pure-read + git-freedom guard.

        Every entry is a port-exposed filesystem observable. ``git.exists`` is the
        load-bearing git-freedom guard: the core must NEVER make the tree a git
        work-tree (it stays False before and after), proving no git side-effect.
        """
        project = self._require_project()
        ledger = project / ".nwave" / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"
        return {
            "config.yaml.exists": (project / ".nwave" / "config.yaml").exists(),
            "ledger.exists": ledger.exists(),
            "ledger.bytes": ledger.stat().st_size if ledger.exists() else 0,
            "git.exists": (project / ".git").exists(),
        }

    def _assert_pure_read_and_git_free(self, before: dict[str, object]) -> None:
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
                # git.exists stays unchanged -- and it started False (non-git
                # tree), so this also pins git-freedom: the core never made the
                # tree a work-tree.
                "git.exists": unchanged(),
            },
        )
        assert self.capture_universe()["git.exists"] is False, (
            "the gate core must remain git-free: the substrate is NOT a git "
            "work-tree and the core must never create one -- the verdict is "
            "derived purely from the non-git port."
        )

    # ---- substrate plumbing (precondition state, NOT the SUT) ----------

    def _set_source(self, source: NonGitTrailerSource) -> None:
        self._source = source
        self._port = _build_fake_source(source)

    def _build_substrate(self) -> None:
        """Build a NON-git tmp deliver project carrying a present integrity-clean ledger.

        The ledger demands reconciliation (a `SliceCommitVerified` record for the
        demanded slice) AND records the required feature-end records, so the ONLY
        thing that flips the verdict is what the NON-git port returns. The tree is
        deliberately NOT a git work-tree (no `.git`) -- the git-freedom proof.
        """
        self._tmp = Path(tempfile.mkdtemp(prefix="git-free-core-at-"))
        self._project_dir = self._tmp
        nwave = self._tmp / ".nwave"
        nwave.mkdir(parents=True, exist_ok=True)
        (nwave / "config.yaml").write_text(
            "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
        )
        self._seed_clean_ledger()

    def _seed_clean_ledger(self) -> None:
        """Write an M7 integrity-clean ledger via the real AtCompletionLedger.

        A `SliceCommitVerified` record for the demanded slice (the reconciliation
        demand) plus the required feature-end records, seeded structurally via the
        shared helper (a frozenset extension stays a one-line change).
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
        )
        from tests.des._helpers.feature_end_seeding import (
            seed_required_feature_end_records,
        )

        project = self._require_project()
        ledger = AtCompletionLedger(_FEATURE_ID, project)
        ledger.append_gate_event(event="SliceCommitVerified", slice_id=_DEMANDED_SLICE)
        seed_required_feature_end_records(ledger, verdict_hash=_VERDICT_HASH)

    def _run_git_free_core(self) -> None:
        """Drive the production `_verify_atdd_pure` with the fake non-git port.

        The gate core's PUBLIC injection seam: `_verify_atdd_pure(project_dir,
        roadmap_path, feature_id, trailer_port=<fake>)`. The core prints its
        single-line JSON verdict events to stdout and returns the exit code; both
        are captured here as the observable verdict surface. NO git is involved --
        the fake port supplies the trailer stream directly.
        """
        from des.cli.verify_deliver_integrity import _verify_atdd_pure

        project = self._require_project()
        roadmap_path = project / "roadmap.json"  # absent -- atdd_pure is roadmap-free
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self._exit_code = _verify_atdd_pure(
                project,
                roadmap_path,
                str(_FEATURE_ID),
                trailer_port=self._require_port(),
            )
        self._stdout = buffer.getvalue()

    def _require_project(self) -> Path:
        assert self._project_dir is not None, (
            "the synthetic non-git deliver project must be built (Given) before "
            "capturing its universe or running the core (When)"
        )
        return self._project_dir

    def _require_port(self) -> CommitTrailerReadPort:
        assert self._port is not None, (
            "the non-git CommitTrailerReadPort must be selected (Given) before "
            "driving the git-free core (When)"
        )
        return self._port

    def _require_completed(self) -> int:
        assert self._exit_code is not None, (
            "the git-free gate core must be run (When) before asserting on its "
            "observable verdict surface (Then)"
        )
        return self._exit_code

    def cleanup(self) -> None:
        if self._tmp is not None and self._tmp.exists():
            shutil.rmtree(self._tmp, ignore_errors=True)
