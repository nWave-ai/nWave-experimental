"""Composition root for the carpaccio-in-order-honest-non-at-attestation slice-01.

Walking skeleton (US-01 record minted + US-02 gate accepts, shipped together).
Mandate 13 (Driving-Port-Only Boundary) + Mandate-12 (Pillar 3): wires TWO
PRODUCTION driving surfaces over a real ``AtCompletionLedger`` on ``tmp_path``:

  * the MINT surface -- the NEW ``des record-prose-delivered`` producer CLI
    (``des.cli.record_prose_delivered.main``, invoked via its argv ``main``
    entry). This module does NOT exist on HEAD -- the slice-01 RED arises here.
  * the GATE surface -- the production live carpaccio intercept
    ``des.adapters.drivers.hooks.carpaccio_intercept.evaluate_atdd_pure_dispatch``
    (the composition-root driving port the live PreToolUse hook delegates to).
    Its in-order predecessor check ``_carpaccio_order_block`` runs BEFORE the
    flavor composition, so injecting CLEARING gate-runners isolates the in-order
    predicate as the only gate that can block -- the exact seam under test.

NO direct-domain call of ``prose_delivered_slices()`` and NO direct-domain call
of ``_predecessor_satisfies_in_order``: the prose record is read by the LIVE gate
through the real hook entry point, and the record is written by the real producer
CLI. Business logic lives here as the single source of truth; step bodies delegate
to ``ProseChainComposition`` methods (Mandate-12 criterion 3: no inline logic).

Layer 3 composition: the producer CLI + the live hook are the driving ports; the
only driven port is the real filesystem (the ``AtCompletionLedger`` JSONL on
tmp_path) -> ``@real-io``. Example-only, no PBT machinery (Mandate 9 / 11): the
observable effect is one appended ledger line + one gate decision, asserted as a
named example, not a Hypothesis ``@given``.

slice-01 RED contract (fail-for-right-reason, Mandate 7 -- RED not BROKEN):

  * ``record_prose_delivered`` does not exist on HEAD. The producer driving port
    is resolved LAZILY inside ``record_prose_verdict`` (an importlib lookup that
    raises ``AssertionError`` -- a missing-functionality RED, classified RED by
    the red-gate snapshot, NOT a collection-time ``ModuleNotFoundError`` that
    would brick the whole module as BROKEN). So:
      - WS-1 raises ``AssertionError`` at the mint step (no producer module) ->
        no record minted -> the gate keeps wedging -> the "successor proceeds"
        Then-assertion never reaches a green gate. Missing functionality: the
        producer + the gate-accept clause.
      - WS-2 raises ``AssertionError`` at the mint step -> no record -> the
        "one prose-delivered record" Then-assertion fails. Missing functionality:
        the producer.
  * Every test dependency (state-delta port, pytest-bdd, the real
    ``AtCompletionLedger``, the real ``evaluate_atdd_pure_dispatch`` import)
    resolves cleanly -- so the failure is missing PRODUCTION functionality, not a
    test bug.

DELIVER greens these by (a) shipping ``des.cli.record_prose_delivered`` (DDD-5)
that mints a ``SliceProseDelivered`` via a thin ledger append (DDD-4), and (b)
adding the ``or predecessor in ledger.prose_delivered_slices()`` clause to
``_predecessor_satisfies_in_order`` (DDD-1/-3/-8).
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Production GATE driving port (the live carpaccio intercept the PreToolUse hook
# delegates to). Imported as the composition-root driving surface, invoked via
# its public function entry -- NOT a direct-domain call of the in-order predicate.
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    evaluate_atdd_pure_dispatch,
)

from .domain_types import FeatureId, GateOutcome, LedgerRecordKind, SliceId


_FEATURE_ID = FeatureId("carpaccio-in-order-honest-non-at-attestation")
_CARPACCIO_SLICE_MAX = 3
_REVIEWER_AGENT_ID = "nw-acceptance-designer-reviewer"
_OUT_OF_ORDER_EVENT = "CarpaccioSliceOutOfOrder"

# The NEW producer CLI (DDD-5) -- resolved LAZILY so its absence on HEAD is a
# missing-functionality RED raised inside a step, not a collection-time
# ModuleNotFoundError that would brick the module as BROKEN (Mandate 7).
_PRODUCER_MODULE = "des.cli.record_prose_delivered"


@dataclass
class MintRun:
    """Observable outcome of one prose-verdict mint invocation."""

    exit_code: int
    output: str


@dataclass
class ProseChainComposition:
    """Production-wired composition root for the slice-01 prose-chain skeleton.

    ``repo_dir`` is a real tmp_path directory acting as the repository root. A
    minimal atdd_pure config + an empty AT-completion ledger are provisioned so
    the real ``AtCompletionLedger`` and the real ``evaluate_atdd_pure_dispatch``
    hook read a coherent feature. The prose PREDECESSOR is ``slice-01``; the
    wedged SUCCESSOR is ``slice-02`` (its in-order check reads slice-01's record).
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

    # --- Given: a doc-review-approved prose predecessor, empty ledger ---------

    def create_prose_predecessor_repo(self) -> None:
        """Provision the repo: atdd_pure config + empty ledger, no AT files.

        The chained-narrative baseline (Pillar 2): a prose predecessor slice
        that was doc-review approved but authored NO acceptance tests, so it has
        no ``SliceCommitVerified`` record. The ledger starts empty -- the prose
        verdict has not been recorded yet (the un-wedge has not happened).
        """
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
        ledger = AtCompletionLedger(str(self.feature_id), self.repo_dir)
        ledger.ledger_path().parent.mkdir(parents=True, exist_ok=True)
        ledger.ledger_path().write_text("", encoding="utf-8")

    def successor_is_wedged(self) -> bool:
        """True iff dispatching the successor now blocks out-of-order.

        Establishes the chained precondition for US-02: before the prose verdict
        is recorded, the live gate BLOCKS the successor because the predecessor
        carries no honest record. Drives the REAL hook (no record present yet).
        """
        return self._dispatch_successor() == GateOutcome.WEDGED

    # --- When: record the prose verdict via the production producer CLI -------

    def record_prose_verdict(self) -> MintRun:
        """Mint a ``SliceProseDelivered`` record via the real producer CLI.

        Drives the NEW ``des record-prose-delivered`` producer through its argv
        ``main`` entry (the doc-review APPROVED verdict is the attestation,
        DDD-2). The producer is resolved lazily; its absence on HEAD raises an
        ``AssertionError`` (missing-functionality RED) so the slice-01 scenarios
        are RED-not-BROKEN.
        """
        producer_main = self._resolve_producer_main()
        argv = [
            "--feature-id",
            str(self.feature_id),
            "--slice-id",
            str(self.predecessor),
            "--verdict",
            "APPROVED",
            "--reviewer-agent-id",
            _REVIEWER_AGENT_ID,
            "--doc-review-ref",
            "doc-review/at-in-process-port-default-slice-02",
            "--repo-root",
            str(self.repo_dir),
        ]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            exit_code = self._invoke_main(producer_main, argv)
        return MintRun(exit_code=exit_code, output=buffer.getvalue())

    # --- When: dispatch the successor into delivery (drive the LIVE gate) -----

    def dispatch_successor_outcome(self) -> GateOutcome:
        """Dispatch the successor slice and observe the live in-order gate."""
        return self._dispatch_successor()

    # --- Then: observe the ledger (port-exposed reads) ------------------------

    def prose_record_count(self) -> int:
        """Number of ``SliceProseDelivered`` records for the predecessor."""
        return self._record_count(LedgerRecordKind.PROSE_DELIVERED)

    def fabricated_verified_count(self) -> int:
        """Number of ``SliceCommitVerified`` records for the prose predecessor.

        The honesty invariant: this MUST stay 0 -- a prose slice never carries a
        fabricated verified record.
        """
        return self._record_count(LedgerRecordKind.VERIFIED)

    def latest_prose_record_is_attested_unverified(self) -> bool:
        """True iff the latest prose record is attested by doc-review, not AT-run.

        Honesty fields (DDD-2): ``attested == true``, ``at_verified == false``,
        ``reason == "prose_attested_by_doc_review"``, ``verdict == "APPROVED"``.
        """
        records = self._records_for(LedgerRecordKind.PROSE_DELIVERED)
        if not records:
            return False
        record = records[-1]
        return (
            record.get("attested") is True
            and record.get("at_verified") is False
            and record.get("reason") == "prose_attested_by_doc_review"
            and record.get("verdict") == "APPROVED"
        )

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed observable snapshot for assert_state_delta (Mandate 8).

        Three port-exposed observables -- the prose-record count on the ledger,
        the fabricated-verified-record count (the honesty guardrail), and the
        live gate's outcome for the successor. No internal struct fields.
        """
        return {
            "ledger.prose_record_count": self.prose_record_count(),
            "ledger.fabricated_verified_count": self.fabricated_verified_count(),
            "gate.successor_outcome": self._dispatch_successor().value,
        }

    # --- internals -----------------------------------------------------------

    def _dispatch_successor(self) -> GateOutcome:
        """Drive the REAL ``evaluate_atdd_pure_dispatch`` for the successor.

        Injects CLEARING gate-runners for the flavor composition so the ONLY
        gate that can block is the in-order predecessor check
        (``_carpaccio_order_block``), which runs BEFORE the composition -- the
        exact seam under test. A ``CarpaccioSliceOutOfOrder`` block means the
        chain is WEDGED; any other decision means the successor PROCEEDS.
        """
        decision: InterceptDecision = evaluate_atdd_pure_dispatch(
            prompt=self._successor_dispatch_prompt(),
            feature_id=str(self.feature_id),
            project_root=self.repo_dir,
            carpaccio_runner=_clearing_runner,
            readiness_runner=_clearing_runner,
            wave_dispatch_runner=_clearing_runner,
            completeness_runner=_clearing_runner,
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

    def _resolve_producer_main(self) -> object:
        """Resolve the producer CLI ``main`` entry, RED if the module is absent.

        importlib lookup so the absence on HEAD is a missing-functionality
        ``AssertionError`` raised inside the When step (RED), not a
        collection-time ``ModuleNotFoundError`` (BROKEN).
        """
        try:
            module = importlib.import_module(_PRODUCER_MODULE)
        except ModuleNotFoundError as exc:
            raise AssertionError(
                "Not yet implemented -- the `des record-prose-delivered` producer "
                f"({_PRODUCER_MODULE}) does not exist; a prose slice cannot mint a "
                "SliceProseDelivered record (slice-01 RED)."
            ) from exc
        return module.main

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
