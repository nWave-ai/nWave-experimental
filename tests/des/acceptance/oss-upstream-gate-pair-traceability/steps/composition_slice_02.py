"""Composition root for the traceability gate report-quality slice (slice-02).

Extends the slice-01 walking-skeleton composition (``composition.py``) with the
two slice-02 outcome assertions:

* **DT-4** -- the loud warning resolves each unwitnessed clause-ID to its SUMMARY
  text on one line (``DT-ORPHAN (<summary>): unwitnessed-no-at ...``), never the
  bare ``DT-ORPHAN``. EMPIRICAL FINDING (2026-05-31): slice-01's gate ALREADY
  renders this format -- ``decision_table_traceability_gate.py:130`` emits
  ``f"  - {c.clause_id} ({c.summary}): {UNWITNESSED_NO_AT_TOKEN} ..."`` (the
  gate's own docstring line 21-22 claims "NO ID->summary report tightening" but
  the CODE is the SSOT and the code already tightens). So DT-4 is GREEN now: it
  ships as a REGRESSION-PIN that LOCKS the ID->summary co-location contract
  slice-01 happened to deliver, so a future refactor cannot silently regress to
  bare-ID dumping. It is NOT a RED driver -- authoring it as RED would fabricate
  feature debt that does not exist (empirical-read-before-assumption).
* **DT-10** -- the gate APPENDS a ``DecisionTableTraceabilityWarned`` record to
  the existing AT-completion ledger; the assertion READS IT BACK through the
  production ``AtCompletionLedger.read_records`` reader. slice-01 appends no
  traceability record (grep-confirmed: zero ``append_gate_event`` in the gate
  module; the hook's ``_run_decision_table_traceability_gate`` only emits to
  stderr), so this assertion is the SOLE genuine RED driver for slice-02.

DRIVING PORT (Mandate-13, unchanged from slice-01): the real
``handle_subagent_stop`` SubagentStop hook over its JSON stdin protocol as a
subprocess (Layer 3/4 wiring_e2e). slice-02 REUSES the entire slice-01
given/when machinery verbatim by subclassing -- the only NEW code is the two
Then-assertions over the same observable surfaces (stderr warning + the ledger
file the hook wrote during the SAME run). This is Pillar-2 chained narrative: the
slice-02 ``Given`` IS the slice-01 ``Given``, the ``When`` IS the slice-01
``When``; only the ``Then`` tightens.

LEDGER READ-BACK (S2 tolerable variant, same class slice-01 SEEDS through): the
ledger record DT-10 asserts is a slice-02 OUTCOME of the SUT (the gate writing
it), read through the production ``AtCompletionLedger.read_records`` reader on the
SAME ``feature_id`` + ``project_root`` the hook subprocess resolved from the
seeded markers. NO production gate module is imported here -- the SUT is exercised
only via the hook subprocess; the ledger reader is substrate plumbing (read), not
the SUT.
"""

from __future__ import annotations

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

from .composition import _FEATURE_ID, _UNWITNESSED_CLAUSE, TraceabilityGateComposition


# The summary cell the slice-01 substrate writer (``_write_decision_table``)
# emits for a clause is ``summary for <clause-id>``. DT-4 binds to THIS exact
# distinct summary text so a gate that echoes only the bare clause-ID FAILS.
_EXPECTED_SUMMARY = f"summary for {_UNWITNESSED_CLAUSE}"

# The ledger event NAME the gate appends on a warn verdict (architecture.md §6 /
# DT-10). The feature-delta fixes this string as the join-free audit anchor.
_WARNED_EVENT = "DecisionTableTraceabilityWarned"


class TraceabilityReportComposition(TraceabilityGateComposition):
    """slice-02 composition: report ID->summary (DT-4) + ledger record (DT-10).

    Inherits all slice-01 given_/when_ step methods (Pillar-2 reuse). Adds only
    the two slice-02 Then-assertions.
    """

    # ---- then (slice-02 outcomes) --------------------------------------

    def then_warning_resolves_clause_to_summary(self) -> None:
        """DT-4: clause-ID AND its summary co-located on ONE warning line.

        REGRESSION-PIN (GREEN now): slice-01 already renders ``DT-ORPHAN
        (summary for DT-ORPHAN): unwitnessed-no-at ...`` on one line. This
        assertion LOCKS that ID->summary co-location so a future refactor cannot
        regress to bare-ID dumping. Non-vacuous: a gate that dumped the bare
        clause-ID (summary absent) or that split ID and summary across lines
        WOULD fail -- the contract is the inline ID->summary resolution, not the
        mere presence of two substrings anywhere.
        """
        warning = self._warning_text()
        assert _EXPECTED_SUMMARY in warning, (
            f"the warning did not resolve the unwitnessed clause "
            f"{_UNWITNESSED_CLAUSE!r} to its summary {_EXPECTED_SUMMARY!r}; a "
            f"report that emits the bare clause-ID is not comprehensible "
            f"(DT-4 comprehension-key contract). {self._observed()}"
        )
        co_located = any(
            _UNWITNESSED_CLAUSE in line and _EXPECTED_SUMMARY in line
            for line in warning.splitlines()
        )
        assert co_located, (
            f"the warning mentioned both {_UNWITNESSED_CLAUSE!r} and its summary "
            f"{_EXPECTED_SUMMARY!r} but not together on one line; every report "
            f"line must resolve ID->summary inline (DT-4). {self._observed()}"
        )

    def then_ledger_records_traceability_verdict(self) -> None:
        """DT-10: the warn verdict is appended to + read back from the ledger.

        Reads the ledger the hook subprocess wrote during this SAME run, through
        the production ``AtCompletionLedger.read_records`` reader, on the seeded
        ``feature_id`` + ``project_root``. Asserts a
        ``DecisionTableTraceabilityWarned`` record is present. A gate that emits
        the warning but writes NO ledger record FAILS here -- binding DT-10 to
        the actual persisted record content, never merely to "the gate ran".
        """
        events = self._recorded_traceability_events()
        assert _WARNED_EVENT in events, (
            f"the gate emitted its warning but recorded no {_WARNED_EVENT!r} "
            f"verdict in the AT-completion ledger (DT-10 reuse-first audit "
            f"anchor); ledger events read back = {sorted(events)!r}. "
            f"{self._observed()}"
        )

    # ---- read-back plumbing (substrate reader, NOT the SUT) ------------

    def _recorded_traceability_events(self) -> set[str]:
        """Event names in the ledger the hook wrote, via the production reader."""
        assert self._project_root is not None
        ledger = AtCompletionLedger(_FEATURE_ID, self._project_root)
        return {str(record["event"]) for record in ledger.read_records()}
