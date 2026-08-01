# @feature-unified-event-store
"""Adapter-integration slice: UnifiedEventStoreAdapter (unified-event-store slice-02).

CONTRACT_SHAPE: bounded-change -- `StoreAvailabilityProbe.probe()` / `append()` /
`append_derived()` each perform a BOUNDED canary/append against the real
filesystem, never an unbounded read.

Mandate 9 v2 treatment 3 (Adapter integration slice,
`nw-test-design-mandates-layered-mechanics`): the SUT here is the ADAPTER
itself (`UnifiedEventStoreAdapter` / `StoreAvailabilityProbe`), driven via its
constructor DIRECTLY against a REAL filesystem (`@real-io`) -- the explicit,
permitted exception to the Driving-Port-Only Boundary mandate for exactly
this class of test (10-property matrix; nw-distill-coverage-obligations
"Adapter Integration Slice Authoring"). Example-based, no PBT (OR-reduction:
>=1 driven adapter real == example-based, never PBT-generated).

Outcome anchor (feature-delta.md [REF] Staging Plan, slice-02 row): "the
composition root refuses to start on probe failure" (DD-14) + "AtCompletionLedger
EXTEND: add append_event(scope, event, **fields)... so CONTEXT/MIKADO writers
share the one flock-serialised critical section" (Reuse Analysis row 2).

RED at HEAD: `UnifiedEventStoreAdapter` / `StoreAvailabilityProbe` are
DISTILL-authored scaffolds (`__SCAFFOLD__ = True`) whose methods raise a bare
`AssertionError`. Every test below targets the FINAL contract
(`StoreProbeFailed` / `PartitionKeyRequired` / `ReductionKeyIneligible` / a
real MIKADO round-trip) -- none of it is scaffold-aware -- so each fails
TODAY because the scaffold's `AssertionError` propagates OUT of the narrower
`pytest.raises(<final-exception>)` context manager uncaught (that context
manager does not catch a mismatched exception type), never because of an
import/collection error. DELIVER makes these green by implementing the real
behaviour; this file is never rewritten to do so.
"""

from __future__ import annotations

import errno
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from des.adapters.driven.logging.store_availability_probe import StoreAvailabilityProbe
from des.adapters.driven.logging.unified_event_store_adapter import (
    UnifiedEventStoreAdapter,
)
from des.domain.telemetry_paths import LedgerFamily, telemetry_root
from des.ports.driven_ports.event_store_port import (
    EventRecord,
    InvalidScope,
    PartitionKeyRequired,
    ReductionKey,
    ReductionKeyIneligible,
)
from des.ports.driven_ports.probeable_port import StoreProbeFailed


if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def _healthy_sandbox(tmp_path: Path) -> Path:
    """A real repo root with an already-provisioned, empty telemetry root."""
    telemetry_root(tmp_path).mkdir(parents=True, exist_ok=True)
    return tmp_path


# --- property #1 (error class taxonomy) + #8 (fail-mode contract: fail-LOUD,
# never a false ProbeResult(ok=True)) -----------------------------------


class TestStoreAvailabilityProbeFaultInjection:
    """Three induced filesystem faults (the charter's own fault matrix) plus
    an injected ENOSPC (constraint 8: a real full disk cannot be induced
    portably with Python + filesystem alone, so an `OSError(errno.ENOSPC)` is
    injected at the stdlib write seam instead)."""

    def test_probe_refuses_when_telemetry_directory_is_missing(
        self, tmp_path: Path
    ) -> None:
        # covers: R5
        probe = StoreAvailabilityProbe(project_root=tmp_path)  # no .nwave/telemetry/

        with pytest.raises(StoreProbeFailed) as exc_info:
            probe.probe()

        assert exc_info.value.fault == "missing-directory"
        assert str(tmp_path) in str(exc_info.value.path), (
            "the refusal must name a path INSIDE the given project_root, "
            f"never the real installation's store -- got {exc_info.value.path!r}"
        )
        message = str(exc_info.value)
        assert "WHAT" in message
        assert "WHY" in message
        assert "HOW" in message

    def test_probe_refuses_when_telemetry_directory_denies_permission(
        self, tmp_path: Path
    ) -> None:
        # covers: R5
        root = telemetry_root(_healthy_sandbox(tmp_path))
        root.chmod(0o000)
        try:
            probe = StoreAvailabilityProbe(project_root=tmp_path)
            with pytest.raises(StoreProbeFailed) as exc_info:
                probe.probe()
            assert exc_info.value.fault == "permission-denied"
            assert str(tmp_path) in str(exc_info.value.path)
        finally:
            root.chmod(0o755)

    def test_probe_refuses_when_telemetry_path_is_a_file_not_a_directory(
        self, tmp_path: Path
    ) -> None:
        # covers: R5
        root = telemetry_root(tmp_path)
        root.parent.mkdir(parents=True, exist_ok=True)
        root.write_text("not a directory", encoding="utf-8")

        probe = StoreAvailabilityProbe(project_root=tmp_path)
        with pytest.raises(StoreProbeFailed) as exc_info:
            probe.probe()
        assert exc_info.value.fault == "not-a-directory"

    def test_probe_refuses_on_injected_enospc(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        # covers: R14
        _healthy_sandbox(tmp_path)
        real_open = open

        def _enospc_open(path, mode="r", *args, **kwargs):
            if any(flag in mode for flag in ("w", "a", "x")):
                raise OSError(errno.ENOSPC, "No space left on device", str(path))
            return real_open(path, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", _enospc_open)

        probe = StoreAvailabilityProbe(project_root=tmp_path)
        with pytest.raises(StoreProbeFailed) as exc_info:
            probe.probe()
        assert exc_info.value.fault == "enospc"

    def test_healthy_probe_succeeds_and_leaves_no_residue(self, tmp_path: Path) -> None:
        # covers: R6
        root = telemetry_root(_healthy_sandbox(tmp_path))
        before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        probe = StoreAvailabilityProbe(project_root=tmp_path)
        result = probe.probe()

        assert result.ok is True
        after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
        assert after == before, (
            "a healthy probe's canary write/flock/read/delete must leave NO "
            f"residue under {root} -- before={before!r} after={after!r}"
        )

    def test_probe_is_idempotent_across_two_consecutive_healthy_runs(
        self, tmp_path: Path
    ) -> None:
        """nfr: `idempotency: idempotent` (nWave/gates/event-store-probe.yaml)
        -- running the probe twice in a row against the same healthy
        substrate must produce the SAME success outcome both times, with no
        residue accumulating between runs."""
        # covers: R16
        root = telemetry_root(_healthy_sandbox(tmp_path))
        probe = StoreAvailabilityProbe(project_root=tmp_path)

        first = probe.probe()
        after_first = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))
        second = probe.probe()
        after_second = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

        assert first.ok is True
        assert second.ok is True
        assert after_first == after_second == [], (
            "two consecutive healthy probe runs must leave the SAME (empty) "
            f"residue -- after_first={after_first!r} after_second={after_second!r}"
        )


# --- security: a refusal must never leak a path outside the sandbox --------


class TestProbeRefusalNeverLeaksOutsideSandbox:
    """The charter's own oracle: 'The refusal names a path OUTSIDE
    $UES_SANDBOX. That means it fell back to the real store, which is worse
    than refusing.' A substring match alone cannot distinguish a genuinely
    contained path from a coincidental prefix collision -- assert STRUCTURAL
    containment via `Path.relative_to`, which raises `ValueError` for any
    path that is not actually inside the sandbox."""

    def test_refusal_path_is_structurally_inside_the_given_project_root(
        self, tmp_path: Path
    ) -> None:
        # covers: R17
        probe = StoreAvailabilityProbe(project_root=tmp_path)  # missing dir fault

        with pytest.raises(StoreProbeFailed) as exc_info:
            probe.probe()

        refused_path = exc_info.value.path
        try:
            Path(refused_path).relative_to(tmp_path)
        except ValueError:
            pytest.fail(
                f"the refusal's path {refused_path!r} is NOT structurally "
                f"inside the given project_root {tmp_path!r} -- a refusal "
                "naming a path outside the sandbox means the store fell "
                "back to a different substrate, which is worse than refusing."
            )


# --- property #10 (driving-port purity / witness-independence, GDP-8) ------


class TestUnifiedEventStoreAdapterProbeDelegation:
    """Peer-review MEDIUM finding, closed (feature-delta.md [REF] Driven
    Ports + Adapters): `probe()` MUST delegate to `StoreAvailabilityProbe`,
    never inline a second copy -- two checks sharing one implementation are
    one check wearing two names, not two differently-lensed witnesses.

    Honest limit of this mechanism (stated, not silently overstated): a spy
    proves the delegation call HAPPENS -- it cannot prove the adapter does
    NOT *also* inline a second, duplicate canary implementation alongside
    it. Closing that residual gap would need a source-shape check (e.g. an
    AST scan of `UnifiedEventStoreAdapter.probe`'s body), which this
    behavioural AT does not attempt."""

    def test_probe_delegates_to_store_availability_probe(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        # covers: R10
        calls: list[Path] = []
        original_probe = StoreAvailabilityProbe.probe

        def _spy(self: StoreAvailabilityProbe):
            calls.append(self._project_root)
            return original_probe(self)

        monkeypatch.setattr(StoreAvailabilityProbe, "probe", _spy)

        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        with pytest.raises(StoreProbeFailed):
            adapter.probe()

        assert calls == [tmp_path], (
            "UnifiedEventStoreAdapter.probe() must DELEGATE to "
            "StoreAvailabilityProbe.probe() -- never reimplement the canary "
            f"logic inline (witness-independence, GDP-8). Recorded calls: {calls!r}"
        )


# --- DD-5: PartitionKeyRequired ---------------------------------------------


class TestAppendPartitionKeyRequired:
    """DD-5: `scope != "feature"` with an empty/missing `partition_key` ->
    `PartitionKeyRequired` -- never a silently-accepted write that later
    collides with another session/node under the same absent key."""

    @pytest.mark.parametrize("scope", ["session", "node"])
    def test_append_session_or_node_scope_without_partition_key_raises(
        self, tmp_path: Path, scope: str
    ) -> None:
        # covers: R7
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        record = EventRecord(
            family=LedgerFamily.CONTEXT,
            event="SomeEvent",
            scope=scope,
            partition_key=None,
        )

        with pytest.raises(PartitionKeyRequired) as exc_info:
            adapter.append(record)

        message = str(exc_info.value)
        assert scope in message
        assert "partition_key" in message

    def test_append_feature_scope_omits_the_partition_key_requirement(
        self, tmp_path: Path
    ) -> None:
        """Sibling-branch pin: scope="feature" must NOT raise
        PartitionKeyRequired even with partition_key=None -- proves the
        refusal is scoped to session/node, not a blanket rejection. At HEAD
        the scaffold raises a bare AssertionError for EVERY input (including
        this one), so this test fails RED today for the right reason; once
        DELIVER differentiates the branches it passes with no exception."""
        # covers: R7
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        record = EventRecord(
            family=LedgerFamily.ATDD_PURE,
            event="SomeEvent",
            scope="feature",
            feature_id="unified-event-store",
            partition_key=None,
        )

        try:
            adapter.append(record)
        except PartitionKeyRequired:
            pytest.fail(
                "scope='feature' with partition_key=None must NOT raise "
                "PartitionKeyRequired (DD-5 scopes the refusal to "
                "scope != 'feature') -- got PartitionKeyRequired anyway."
            )


# --- DD-8: ReductionKeyIneligible -------------------------------------------


class TestAppendDerivedReductionKeyIneligible:
    """DD-8: `append_derived` with a null `agent_id` -> `ReductionKeyIneligible`
    -- never a silent MAX-based collapse under an unproven identity."""

    def test_append_derived_with_null_agent_id_raises(self, tmp_path: Path) -> None:
        # covers: R8
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        record = EventRecord(
            family=LedgerFamily.CONTEXT,
            event="ContextAdmission",
            scope="feature",
            feature_id="unified-event-store",
            agent_id=None,
        )
        reduction = ReductionKey(reduction_key="k", reducer_version="v1")

        with pytest.raises(ReductionKeyIneligible) as exc_info:
            adapter.append_derived(record, reduction)

        assert "agent_id" in str(exc_info.value)


# --- constraint 9: every id/key exercised at N >= 2 -------------------------


class TestAppendSeqAndCorrelationIdDistinctness:
    """A single-firing test cannot distinguish a per-event key from a
    per-content one -- exercise seq/correlation_id with two records."""

    def test_two_appends_produce_distinct_seq_and_correlation_id(
        self, tmp_path: Path
    ) -> None:
        # covers: R11
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        first = adapter.append(
            EventRecord(
                family=LedgerFamily.MIKADO,
                event="NodeTouched",
                scope="node",
                partition_key="node-a",
            )
        )
        second = adapter.append(
            EventRecord(
                family=LedgerFamily.MIKADO,
                event="NodeTouched",
                scope="node",
                partition_key="node-a",
            )
        )

        assert first.seq != second.seq, (
            "two independent append() calls must be assigned DISTINCT "
            f"monotonic seq values -- got {first.seq!r} twice"
        )
        assert first.correlation_id != second.correlation_id, (
            "two independent append() calls must produce DISTINCT "
            "correlation_id values (a per-event key, not a per-content one) "
            f"-- got {first.correlation_id!r} twice"
        )


# --- D70 landing site + general per-family routing --------------------------
#
# Measured finding (verified independently, this worktree): AtCompletionLedger
# is FAMILY-BLIND today -- `_append_record` writes to `self.ledger_path()`,
# fixed at construction time, and never consults
# `telemetry_paths.ledger_path(repo, family, partition_key)`. Recomputing the
# expected destination via `ledger_path(...)` (the SAME resolver a naive
# DELIVER implementation might -- or might not -- actually call) would be the
# constraint-10 tautology class applied to the destination PATH instead of
# the record CONTENT: if the implementation ignores `record.family` entirely
# (writing every record to the legacy/singleton path regardless of family),
# a test whose expectation is *also* computed by calling the family-aware
# resolver could still coincidentally match, or could silently move in
# lockstep with a resolver bug. So every path below is spelled out LITERALLY,
# segment by segment, exactly as `test_telemetry_paths.py` pins
# `ledger_path()`'s own output -- and exercised at N>=2 DISTINCT families
# (mikado, context) so a single-family coincidence cannot pass silently.


class TestAppendRoutesToPerFamilyDestination:
    """`append()`'s write target is determined by `EventRecord.family` -- a
    family with no reachable physical path is a defect, not a
    not-yet-written state (the exact `LedgerFamily.RED_GREEN` class D80
    exists to kill). D70 (node-closure) is designed-not-built; the MIKADO
    case below is its reserved landing site (Open Question 5) -- an AT
    asserting only that `LedgerFamily.MIKADO` exists is worthless, so this
    asserts the PHYSICAL round-trip against a LITERAL path. (`read()` is
    slice-03 scope, so this reads the physical file directly rather than
    through `UnifiedEventStoreAdapter.read` -- an observable side effect per
    Dormant-Seam Reconciliation, Mandate 15.)"""

    def test_mikado_scope_node_record_lands_at_the_literal_mikado_path(
        self, tmp_path: Path
    ) -> None:
        # covers: R9, R12
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        node_id = "D80-close"
        appended = adapter.append(
            EventRecord(
                family=LedgerFamily.MIKADO,
                event="NodeClosureAttested",
                scope="node",
                partition_key=node_id,
            )
        )

        raw_path = tmp_path / ".nwave" / "telemetry" / "mikado" / f"{node_id}.jsonl"
        self._assert_physically_landed(raw_path, appended, event="NodeClosureAttested")

    def test_context_feature_scope_record_lands_at_the_literal_context_path(
        self, tmp_path: Path
    ) -> None:
        # covers: R12
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        feature_id = "unified-event-store"
        appended = adapter.append(
            EventRecord(
                family=LedgerFamily.CONTEXT,
                event="ContextAdmission",
                scope="feature",
                feature_id=feature_id,
            )
        )

        raw_path = tmp_path / ".nwave" / "telemetry" / "context" / f"{feature_id}.jsonl"
        self._assert_physically_landed(raw_path, appended, event="ContextAdmission")

    @staticmethod
    def _assert_physically_landed(raw_path: Path, appended, *, event: str) -> None:
        assert raw_path.is_file(), (
            f"append() must physically write to the LITERAL per-family path "
            f"{raw_path} -- a family with no reachable path is a defect "
            "(family validates syntactically but has zero effect on where "
            "the record lands), not a not-yet-written state."
        )
        lines = [ln for ln in raw_path.read_text(encoding="utf-8").splitlines() if ln]
        records = [json.loads(ln) for ln in lines]
        matching = [r for r in records if r.get("seq") == appended.seq]
        assert len(matching) == 1, (
            f"expected exactly 1 physical record with seq={appended.seq!r} "
            f"in {raw_path} -- found {len(matching)} (records on disk: {records!r})"
        )
        on_disk = matching[0]
        assert on_disk["event"] == event
        assert on_disk["record_hash"] == appended.record_hash
        assert on_disk["correlation_id"] == appended.correlation_id


# --- DD-6-style declared-shape refusal: scope outside the closed vocabulary -


class TestAppendInvalidScopeRefusal:
    """`scope` is checkable locally, on one record, against the closed
    `EventScope` vocabulary (DD-6's own strongest formulation, applied to
    `scope` rather than `tool_use_id`) -- a typo (`"nodes"`) must never
    silently write a record no consumer can ever query by its declared
    scope."""

    def test_append_refuses_a_scope_outside_the_closed_vocabulary(
        self, tmp_path: Path
    ) -> None:
        # covers: R13
        adapter = UnifiedEventStoreAdapter(project_root=tmp_path)
        record = EventRecord(
            family=LedgerFamily.MIKADO,
            event="NodeTouched",
            scope="nodes",  # typo -- not "node"
            partition_key="node-a",
        )

        with pytest.raises(InvalidScope) as exc_info:
            adapter.append(record)

        assert "nodes" in str(exc_info.value)
