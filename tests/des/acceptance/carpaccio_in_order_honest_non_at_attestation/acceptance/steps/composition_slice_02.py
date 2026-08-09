"""Composition root for carpaccio-in-order-honest-non-at-attestation slice-02.

The non-Python-target degrade path (US-03 / Raj). Mandate 13
(Driving-Port-Only Boundary) + Mandate-12 (Pillar 3): wires TWO PRODUCTION
driving surfaces over a real git repo + a real ``AtCompletionLedger`` on
``tmp_path``:

  * the MINT surface -- the production ``des commit-slice`` producer CLI
    (``des.cli.commit_slice.main``, invoked via its argv ``main`` entry). On the
    InterpreterUnavailable degrade (non-Python target) slice-02 must route this
    to MINT an existing ``SliceCommitIndeterminate`` record carrying a free-text
    ``reason`` -- the WIRING fix (DDD-6). On HEAD it lands the commit but writes
    NO ledger record (``commit_slice.py:302-305`` returns 1 record-less), so the
    record-count assertion is the slice-02 RED.
  * the GATE surface -- the production live carpaccio intercept
    ``des.adapters.drivers.hooks.carpaccio_intercept.evaluate_atdd_pure_dispatch``
    (the composition-root driving port the live PreToolUse hook delegates to).
    Its in-order predecessor check ALREADY accepts an ``indeterminate_slices()``
    predecessor (DDD-3, verified at ``carpaccio_intercept.py:465``) -- so once the
    record is minted the successor proceeds.

The non-Python target is SIMULATED honestly: the committed-scope digest seam
``commit_slice._committed_scope_digest_value`` is forced to return its
``InterpreterUnavailable`` refusal (a ``_CommittedScopeRefusal``) -- the exact
value the production seam returns on a machine with no resolvable pytest
interpreter (``run_contract_gate.py:803`` -> ``_CommittedScopeRefusal``). The
real ``commit_slice.main`` then takes its degrade branch. No interpreter fork,
no real Rust toolchain needed -- the fault is injected at the production seam the
degrade is keyed on, driving the REAL ``main`` in-process.

NO direct-domain call of ``indeterminate_slices()`` or of
``_predecessor_satisfies_in_order``: the gate reads the indeterminate record
through the REAL hook entry point, and the record is written by the real
``commit-slice`` producer. Step bodies delegate to
``DegradedCommitComposition`` (Mandate-12 criterion 3: no inline logic).

Layer 3 composition. ``@real-io`` (real git repo + real ``AtCompletionLedger``
filesystem on tmp_path). Example-only, no PBT machinery (Mandate 9 / 11): the
observable effect is one appended ``SliceCommitIndeterminate`` line + the live
gate's successor outcome flipping wedged -> proceeds, asserted as a named
example.

slice-02 RED contract (fail-for-right-reason, Mandate 7 -- RED not BROKEN): on
HEAD ``des commit-slice`` has no ``--feature-id`` arg and its degrade path mints
NO ledger record. The composition passes ``--feature-id`` and asserts a
``SliceCommitIndeterminate`` record was minted; on HEAD no record is written
(the degrade ``return 1`` is record-less), so the When/Then steps raise
``AssertionError`` (missing functionality: the degrade-mint routing + the
``--feature-id`` arg). Every dependency (git, the real ledger, the real
``commit_slice`` + ``evaluate_atdd_pure_dispatch`` imports, the state-delta port)
resolves cleanly -- a deliberate missing-functionality RED, not a test bug.

DELIVER greens it by routing ``commit_slice``'s degrade branch
(``commit_slice.py:302``) to the existing ``SliceCommitIndeterminate`` mint with
a free-text ``reason``, and adding the additive ``--feature-id`` arg (DDD-6).
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from unittest import mock

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    evaluate_atdd_pure_dispatch,
)
from des.cli import commit_slice as commit_slice_module
from des.cli.run_contract_gate import _CommittedScopeRefusal

from .domain_types import (
    DEGRADE_REASON_INTERPRETER_UNAVAILABLE,
    CommitOutcome,
    FeatureId,
    GateOutcome,
    LedgerRecordKind,
    SliceId,
)


_FEATURE_ID = FeatureId("carpaccio-in-order-honest-non-at-attestation")
_CARPACCIO_SLICE_MAX = 3
_OUT_OF_ORDER_EVENT = "CarpaccioSliceOutOfOrder"

# The 64-zero-hex placeholder commit-slice stamps on the pre-amend commit. When
# the degrade fires BEFORE the amend, this is the trailer the landed commit
# carries -- proof the commit landed even though the digest could not be pinned.
_PLACEHOLDER_DIGEST = "0" * 64


@dataclass
class CommitRun:
    """Observable outcome of one ``des commit-slice`` invocation under degrade."""

    exit_code: int
    output: str
    landed_commit: str | None


@dataclass
class DegradedCommitComposition:
    """Production-wired composition root for the slice-02 degraded-commit path.

    ``repo_dir`` is a real tmp_path directory acting as a git repository with a
    minimal atdd_pure config + an empty AT-completion ledger. The predecessor is
    ``slice-01`` (committed under the simulated interpreter-unavailable degrade);
    the wedged successor is ``slice-02`` (its in-order check reads slice-01's
    record).
    """

    repo_dir: Path
    feature_id: FeatureId = field(default=_FEATURE_ID)
    predecessor: SliceId = field(default=SliceId("slice-01"))
    successor: SliceId = field(default=SliceId("slice-02"))

    # --- paths ---------------------------------------------------------------

    @property
    def _nwave_dir(self) -> Path:
        return self.repo_dir / ".nwave"

    @property
    def config_path(self) -> Path:
        return self._nwave_dir / "config.yaml"

    # --- Given: a real git repo on a non-Python target, empty ledger ----------

    def create_degraded_target_repo(self) -> None:
        """Provision a real git repo with a stageable change + empty ledger.

        The chained-narrative baseline (Pillar 2): a beta-tester's non-Python
        target where no pytest interpreter resolves. A real git repo is created
        (commit-slice commits through its git driven adapter), an atdd_pure
        config + an empty ledger are written, and one stageable file is left
        un-committed so commit-slice has a slice to commit. The ledger starts
        empty -- the predecessor has not been committed yet.
        """
        import yaml

        self.repo_dir.mkdir(parents=True, exist_ok=True)
        self._git("init", "-q")
        self._git("config", "user.email", "raj@example.com")
        self._git("config", "user.name", "Raj")
        self._git("config", "commit.gpgsign", "false")

        self._nwave_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            yaml.safe_dump(
                {
                    "workflow": {"mode": "atdd_pure"},
                    "atdd_pure": {"carpaccio_slice_max": _CARPACCIO_SLICE_MAX},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        # A base commit so HEAD exists (commit-slice amends the slice commit).
        (self.repo_dir / "README.md").write_text("base\n", encoding="utf-8")
        self._git("add", "README.md")
        self._git("commit", "-q", "-m", "chore: base")

        ledger = AtCompletionLedger(str(self.feature_id), self.repo_dir)
        ledger.ledger_path().parent.mkdir(parents=True, exist_ok=True)
        ledger.ledger_path().write_text("", encoding="utf-8")

        # The slice's stageable change (the predecessor's work product).
        (self.repo_dir / "src.rs").write_text("fn main() {}\n", encoding="utf-8")

    def successor_is_wedged(self) -> bool:
        """True iff dispatching the successor now blocks out-of-order.

        Establishes the chained precondition for US-03: before the predecessor
        is committed (and its honest record minted), the live gate BLOCKS the
        successor. Drives the REAL hook (no record present yet).
        """
        return self._dispatch_successor() == GateOutcome.WEDGED

    # --- When: commit the predecessor under the simulated degrade -------------

    def commit_predecessor_under_degrade(self) -> CommitRun:
        """Drive ``des commit-slice`` with the committed-scope digest degraded.

        The non-Python target is simulated by forcing
        ``commit_slice._committed_scope_digest_value`` to return its
        ``InterpreterUnavailable`` refusal -- the exact production value on a
        machine with no resolvable pytest interpreter. The real ``commit_slice``
        ``main`` then takes its degrade branch (``commit_slice.py:302``), which
        slice-02 must route to MINT the ``SliceCommitIndeterminate`` record.

        On HEAD the degrade branch returns 1 with NO ledger record and
        ``--feature-id`` is an unknown arg -- so the mint never happens. The
        observable effect (a minted record) is asserted by the Then steps; its
        absence is the slice-02 missing-functionality RED.
        """
        argv = [
            "--repo",
            str(self.repo_dir),
            "--message",
            "feat(rust-slice): predecessor work on a non-Python target",
            "--slice-id",
            str(self.predecessor),
            "--feature-id",
            str(self.feature_id),
            "--all",
        ]
        buffer = io.StringIO()
        with self._interpreter_unavailable_degrade():
            with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
                exit_code = self._invoke_main(commit_slice_module.main, argv)
        landed = self._head_sha_if_slice_committed()
        return CommitRun(
            exit_code=exit_code, output=buffer.getvalue(), landed_commit=landed
        )

    def dispatch_successor_outcome(self) -> GateOutcome:
        """Dispatch the successor slice and observe the live in-order gate."""
        return self._dispatch_successor()

    # --- Then: observe the ledger + the landed commit (port-exposed reads) ----

    def indeterminate_record_count(self) -> int:
        """Number of ``SliceCommitIndeterminate`` records for the predecessor."""
        return self._record_count(LedgerRecordKind.INDETERMINATE)

    def fabricated_verified_count(self) -> int:
        """Number of ``SliceCommitVerified`` records for the degraded predecessor.

        The honesty invariant: this MUST stay 0 -- a degraded commit never
        carries a fabricated verified record.
        """
        return self._record_count(LedgerRecordKind.VERIFIED)

    def commit_landed_with_trailers(self) -> CommitOutcome:
        """Whether the predecessor commit landed carrying its slice trailers.

        The degrade still COMMITS (the commit lands before the digest step); the
        landed HEAD must carry the ``Slice-Id: slice-01`` trailer.
        """
        sha = self._head_sha_if_slice_committed()
        return CommitOutcome.LANDED if sha is not None else CommitOutcome.REFUSED

    def latest_indeterminate_names_degrade_reason(self) -> bool:
        """True iff the latest indeterminate record carries the honest reason.

        Honest degrade fields (DDD-6): a free-text ``reason`` (first value
        ``gate_scope_interpreter_unavailable``).
        """
        records = self._records_for(LedgerRecordKind.INDETERMINATE)
        if not records:
            return False
        return records[-1].get("reason") == DEGRADE_REASON_INTERPRETER_UNAVAILABLE

    def latest_indeterminate_has_no_real_digest(self) -> bool:
        """True iff the indeterminate record carries no fabricated gate-scope digest.

        Honesty (degrade-LOUD): the indeterminate record must NOT carry a real
        committed-scope digest (it could not be computed). It carries
        ``gate_scope == "INDETERMINATE"`` (or no real digest at all), never a
        fabricated 64-hex value pretending the scope was verified.
        """
        records = self._records_for(LedgerRecordKind.INDETERMINATE)
        if not records:
            return False
        record = records[-1]
        gate_scope = record.get("gate_scope")
        at_verified = record.get("at_verified")
        # No fabricated real digest: gate_scope is the INDETERMINATE sentinel (or
        # absent), and the record is honestly not-AT-verified.
        digest_is_real = isinstance(gate_scope, str) and gate_scope not in {
            "INDETERMINATE",
            _PLACEHOLDER_DIGEST,
        }
        return (not digest_is_real) and at_verified is not True

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        Three port-exposed observables -- the indeterminate-record count on the
        ledger, the fabricated-verified-record count (the honesty guardrail), and
        the live gate's outcome for the successor. No internal struct fields.
        """
        return {
            "ledger.indeterminate_record_count": self.indeterminate_record_count(),
            "ledger.fabricated_verified_count": self.fabricated_verified_count(),
            "gate.successor_outcome": self._dispatch_successor().value,
        }

    # --- internals -----------------------------------------------------------

    @staticmethod
    def _interpreter_unavailable_degrade() -> object:
        """Force the committed-scope digest seam to its InterpreterUnavailable refusal.

        Patches the name ``commit_slice`` imported (``_committed_scope_digest_value``)
        to return a ``_CommittedScopeRefusal`` -- the exact production value on a
        machine with no resolvable pytest interpreter (a non-Python target). The
        real ``commit_slice.main`` then takes its degrade branch unchanged; only
        the interpreter availability is simulated.
        """
        return mock.patch.object(
            commit_slice_module,
            "_committed_scope_digest_value",
            return_value=_CommittedScopeRefusal(1),
        )

    def _dispatch_successor(self) -> GateOutcome:
        """Drive the REAL ``evaluate_atdd_pure_dispatch`` for the successor.

        Injects CLEARING gate-runners so the ONLY gate that can block is the
        in-order predecessor check, which runs BEFORE the composition -- the seam
        under test. A ``CarpaccioSliceOutOfOrder`` block means WEDGED; any other
        decision means the successor PROCEEDS.
        """
        decision: InterceptDecision = evaluate_atdd_pure_dispatch(
            prompt=self._successor_dispatch_prompt(),
            feature_id=str(self.feature_id),
            project_root=self.repo_dir,
            carpaccio_runner=_clearing_runner,
            readiness_runner=_clearing_runner,
            wave_dispatch_runner=_clearing_runner,
        )
        if decision.is_block and decision.event == _OUT_OF_ORDER_EVENT:
            return GateOutcome.WEDGED
        return GateOutcome.PROCEEDS

    def _successor_dispatch_prompt(self) -> str:
        """A valid atdd_pure A_GREEN dispatch prompt for the successor slice."""
        return (
            "<!-- DES-VALIDATION : required -->\n"
            "<!-- DES-MODE : atdd_pure -->\n"
            "<!-- DES-PHASE : A_GREEN -->\n"
            f"<!-- DES-SLICE : {self.successor} -->\n"
            f"<!-- DES-PROJECT-ID : {self.feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self.repo_dir} -->\n"
        )

    def _head_sha_if_slice_committed(self) -> str | None:
        """The HEAD SHA iff HEAD carries the predecessor's Slice-Id trailer."""
        try:
            body = self._git("log", "-1", "--format=%B")
            sha = self._git("rev-parse", "HEAD").strip()
        except subprocess.CalledProcessError:
            return None
        if f"Slice-Id: {self.predecessor}" in body:
            return sha
        return None

    def _records_for(self, kind: LedgerRecordKind) -> list[dict[str, object]]:
        ledger = AtCompletionLedger(str(self.feature_id), self.repo_dir)
        path = ledger.ledger_path()
        records: list[dict[str, object]] = []
        if not path.is_file():
            return records
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if record.get("event") == kind.value and str(record.get("slice_id")) == str(
                self.predecessor
            ):
                records.append(record)
        return records

    def _record_count(self, kind: LedgerRecordKind) -> int:
        return len(self._records_for(kind))

    def _git(self, *args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=self.repo_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout

    @staticmethod
    def _invoke_main(entry: object, argv: list[str]) -> int:
        """Invoke a CLI ``main`` and normalise ``SystemExit`` to an exit code."""
        try:
            return entry(argv)  # type: ignore[operator,no-any-return]
        except SystemExit as exc:
            return (
                int(exc.code)
                if isinstance(exc.code, int)
                else (0 if exc.code is None else 1)
            )


def _clearing_runner(_feature_id: str, _slice_id: str) -> tuple[int, str]:
    """A gate-runner that always clears (exit 0), isolating the in-order gate."""
    return 0, ""
