"""Unit tests for the M7 AT-completion ledger substrate (slice-03 / U3).

slice-03 of F-DES-ATDD-PURE-HOOK-GATES. The acceptance suite
(`tests/des/acceptance/atdd_pure_spine_hardening/`) drives the writer +
integrity-read; these unit tests cover the M4 reconciliation surface
(`carpaccio_gate_slices`, `verified_slices`, `reconcile_dispatch_count`) and the
M7(a) flock-serialised concurrent-append invariant -- behaviours the
acceptance ATs do not reach.

Port-to-port: the driving port is the `AtCompletionLedger` public API; the
ledger JSONL file on `tmp_path` is the observable surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from des.adapters.driven.logging.at_completion_ledger import (
    DOC_COHERENCE_NOT_APPLICABLE,
    DOC_COHERENCE_VERIFIED,
    EXECUTION_REACH_NOT_APPLICABLE,
    EXECUTION_REACH_VERIFIED,
    FRESH_CLONE_NOT_APPLICABLE,
    FRESH_CLONE_VERIFIED,
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.domain.gate_outcome import GateVerdict
from des.domain.value_objects import SliceRef
from des.ports.driven_ports.at_completion_ledger_port import (
    ENVIRONMENTAL_E2E_NOT_APPLICABLE,
    ENVIRONMENTAL_E2E_VERIFIED,
)


_CARPACCIO_CLEARED = "CarpaccioGateCleared"
_CARPACCIO_REJECTED = "CarpaccioGateRejected"
_SLICE_VERIFIED = "SliceCommitVerified"
_SLICE_BLOCKED = "SliceCommitBlocked"


def _ledger(tmp_path: Path) -> AtCompletionLedger:
    return AtCompletionLedger("demo-feature", tmp_path)


# --- M7(b): monotonic seq + record_hash on append ---------------------------


@given(event_count=st.integers(min_value=1, max_value=20))
@settings(max_examples=50, deadline=None)
def test_append_assigns_gap_free_monotonic_seq(
    tmp_path_factory: pytest.TempPathFactory, event_count: int
) -> None:
    """For any number of appends, seq is the gap-free sequence 1..N."""
    ledger = _ledger(tmp_path_factory.mktemp("ledger"))
    for index in range(event_count):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}")

    records = ledger.read_records()
    assert [r["seq"] for r in records] == list(range(1, event_count + 1))
    assert all(isinstance(r["record_hash"], str) and r["record_hash"] for r in records)


def test_append_record_carries_event_and_slice(tmp_path: Path) -> None:
    """An appended record round-trips its event type and slice id."""
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(event=_SLICE_VERIFIED, slice_id="slice-07")

    assert record["event"] == _SLICE_VERIFIED
    assert record["slice_id"] == "slice-07"
    assert record["seq"] == 1
    assert record["feature_id"] == "demo-feature"


# --- SliceRef additive form (techdebt: at-completion-ledger-slice-ref-clump) -


def test_append_gate_event_accepts_slice_ref(tmp_path: Path) -> None:
    """ref=SliceRef(...) is an alternative to slice_id positional + feature_id=."""
    ledger = AtCompletionLedger(project_root=tmp_path)
    record = ledger.append_gate_event(
        event=_SLICE_VERIFIED,
        ref=SliceRef(feature_id="demo-feature", slice_id="slice-09"),
    )

    assert record["event"] == _SLICE_VERIFIED
    assert record["slice_id"] == "slice-09"
    assert record["feature_id"] == "demo-feature"


def test_append_gate_event_slice_ref_byte_identical_to_positional_form(
    tmp_path: Path,
) -> None:
    """The ref= form produces the SAME record shape as the legacy positional form."""
    via_positional = AtCompletionLedger(project_root=tmp_path / "a")
    via_ref = AtCompletionLedger(project_root=tmp_path / "b")

    positional_record = via_positional.append_gate_event(
        event=_SLICE_VERIFIED, slice_id="slice-01", feature_id="demo-feature"
    )
    ref_record = via_ref.append_gate_event(
        event=_SLICE_VERIFIED,
        ref=SliceRef(feature_id="demo-feature", slice_id="slice-01"),
    )

    for key in ("event", "slice_id", "feature_id", "seq"):
        assert positional_record[key] == ref_record[key]


def test_append_gate_event_rejects_mixing_ref_and_slice_id(tmp_path: Path) -> None:
    """Mixing ref= with slice_id/feature_id= is refused, never silently merged."""
    ledger = _ledger(tmp_path)

    with pytest.raises(TypeError):
        ledger.append_gate_event(
            event=_SLICE_VERIFIED,
            slice_id="slice-01",
            ref=SliceRef(feature_id="demo-feature", slice_id="slice-01"),
        )


def test_append_gate_event_requires_slice_id_or_ref(tmp_path: Path) -> None:
    """Neither slice_id nor ref= supplied is refused, never a silent no-op."""
    ledger = _ledger(tmp_path)

    with pytest.raises(TypeError):
        ledger.append_gate_event(event=_SLICE_VERIFIED)


def test_slice_ref_rejects_empty_feature_id() -> None:
    """SliceRef.feature_id must be non-empty (slice_id MAY be empty -- feature-scoped)."""
    with pytest.raises(ValueError):
        SliceRef(feature_id="", slice_id="slice-01")

    # slice_id == "" is a legitimate feature-scoped record (e.g.
    # FeatureEndReviewVerdict) -- must NOT raise.
    SliceRef(feature_id="demo-feature", slice_id="")


# --- M7(c): fail-closed integrity read --------------------------------------


def test_absent_ledger_is_empty_not_a_violation(tmp_path: Path) -> None:
    """An absent ledger file reads as empty -- distinct from a corrupt one."""
    assert _ledger(tmp_path).read_records() == []


def test_seq_gap_raises_integrity_violation(tmp_path: Path) -> None:
    """A deleted middle record (seq gap) fails the read closed."""
    ledger = _ledger(tmp_path)
    for index in range(3):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}")
    path = ledger.ledger_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "seq-gap"


def test_hash_tamper_raises_integrity_violation(tmp_path: Path) -> None:
    """A hand-edited field whose record_hash no longer matches fails closed."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id="slice-01")
    path = ledger.ledger_path()
    tampered = path.read_text(encoding="utf-8").replace("slice-01", "slice-99")
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "hash-mismatch"


def test_truncated_tail_raises_integrity_violation(tmp_path: Path) -> None:
    """A short final line (a killed append) fails the read closed."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id="slice-01")
    path = ledger.ledger_path()
    full = path.read_text(encoding="utf-8")
    path.write_text(full[: len(full) // 2], encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "truncated-tail"


# --- M4: dispatch-count reconciliation surface ------------------------------


@given(
    carpaccio_slices=st.sets(
        st.sampled_from(["slice-01", "slice-02", "slice-03", "slice-04"]),
        min_size=0,
        max_size=4,
    ),
    verified_slices=st.sets(
        st.sampled_from(["slice-01", "slice-02", "slice-03", "slice-04"]),
        min_size=0,
        max_size=4,
    ),
)
@settings(max_examples=50, deadline=None)
def test_reconciliation_surfaces_ungated_slices(
    tmp_path_factory: pytest.TempPathFactory,
    carpaccio_slices: set[str],
    verified_slices: set[str],
) -> None:
    """reconcile_dispatch_count returns exactly the entered-but-not-gated set.

    Invariant: a slice with a carpaccio gate event is reconciled away; a slice
    entered by the plan with no carpaccio event is surfaced as a discrepancy
    (the M4 R3-fix signal).
    """
    ledger = _ledger(tmp_path_factory.mktemp("ledger"))
    for slice_id in sorted(carpaccio_slices):
        ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id=slice_id)
    for slice_id in sorted(verified_slices):
        ledger.append_gate_event(event=_SLICE_VERIFIED, slice_id=slice_id)

    entered = frozenset(["slice-01", "slice-02", "slice-03", "slice-04"])

    assert ledger.carpaccio_gate_slices() == carpaccio_slices
    assert ledger.verified_slices() == verified_slices
    assert ledger.reconcile_dispatch_count(entered) == entered - carpaccio_slices


def test_rejected_carpaccio_event_counts_as_gated(tmp_path: Path) -> None:
    """A rejected gate still counts -- the slice WAS gated, just not cleared."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_REJECTED, slice_id="slice-01")

    assert ledger.carpaccio_gate_slices() == frozenset(["slice-01"])
    assert ledger.reconcile_dispatch_count(frozenset(["slice-01"])) == frozenset()


def test_blocked_slice_commit_is_not_a_verified_slice(tmp_path: Path) -> None:
    """A SliceCommitBlocked record does not count toward verified slices."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_SLICE_BLOCKED, slice_id="slice-01")

    assert ledger.verified_slices() == frozenset()


# --- M7(a): flock-serialised concurrent append ------------------------------


def test_concurrent_appends_serialise_without_seq_collision(tmp_path: Path) -> None:
    """Concurrent appender processes serialise -- no seq collision, no gap.

    Spawns N child processes each appending one record; the flock makes the
    read-seq -> write critical section atomic. The resulting ledger passes the
    integrity read with a gap-free 1..N sequence.
    """
    from concurrent.futures import ProcessPoolExecutor

    ledger_root = str(tmp_path)
    worker_count = 8

    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        list(
            pool.map(
                _append_one_record,
                [(ledger_root, i) for i in range(worker_count)],
            )
        )

    records = _ledger(tmp_path).read_records()
    assert [r["seq"] for r in records] == list(range(1, worker_count + 1))


def _append_one_record(args: tuple[str, int]) -> None:
    """Worker entry point -- append exactly one record to the shared ledger."""
    ledger_root, index = args
    AtCompletionLedger("demo-feature", Path(ledger_root)).append_gate_event(
        event=_CARPACCIO_CLEARED, slice_id=f"slice-{index}"
    )


# --- outcome kwarg (gate-outcome-record-seam slice-02, ADR-GV-003 D1) -------
#
# `append_gate_event` gains ONE optional kwarg: `outcome: GateVerdict | None
# = None`. Design contract (feature-delta.md "Gate-Outcome Record Contract" +
# component-manifest.yaml): absent -> the key is OMITTED entirely (never
# written as null); present -> threaded into `fields` and hashed into
# `record_hash` exactly like every other optional field (the 9th instance of
# the same signature-delta pattern `reason`/`commit_sha`/`predecessor`/etc.
# already established above).
#
# @contract-shape:bounded-change -- the kwarg addition itself: mutation set =
# {one new optional field}; every pre-existing call shape is untouched
# (test_omitting_outcome_produces_byte_identical_record_shape,
# test_append_gate_event_accepts_outcome_kwarg_and_threads_it_into_the_record,
# test_outcome_round_trips_through_the_jsonl_ledger_as_the_plain_string_value,
# test_absent_and_present_outcome_are_distinguishable_on_the_reread_record,
# test_outcome_is_hashed_into_record_hash_exactly_like_every_other_field,
# test_outcome_combines_with_gate_and_reason_without_interference,
# test_a_plain_string_matching_pass_value_is_accepted_at_runtime_mypy_only_guard).
#
# @contract-shape:unbounded-preservation -- the gate-outcome-verdict-mismatch
# domain declared in component-manifest.yaml (canonical-category C5): for ANY
# GateVerdict crossed with ANY gate/reason presence, the write is faithful
# and total; the ledger never validates outcome against gate truth
# (test_append_gate_event_records_any_verdict_faithfully_pure_write,
# test_ledger_records_a_stated_outcome_even_when_it_contradicts_the_gate_name).


def test_omitting_outcome_produces_byte_identical_record_shape(tmp_path: Path) -> None:
    """No outcome= kwarg -> the record carries no "outcome" key at all.

    Pins the byte-identical-when-absent invariant (component-manifest.yaml
    port-invariant): the 9th signature-delta addition on append_gate_event
    must leave every pre-existing call site's record shape untouched -- the
    key is OMITTED, never written as null.
    """
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(
        event=_CARPACCIO_CLEARED,
        slice_id="slice-01",
        gate="run-contract-gate",
        reason="pre-existing kwargs stay untouched",
    )

    assert "outcome" not in record


def test_append_gate_event_accepts_outcome_kwarg_and_threads_it_into_the_record(
    tmp_path: Path,
) -> None:
    """outcome=GateVerdict.PASS is threaded into the returned record."""
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(
        event=_CARPACCIO_CLEARED, slice_id="slice-01", outcome=GateVerdict.PASS
    )

    assert record["outcome"] == GateVerdict.PASS


def test_outcome_round_trips_through_the_jsonl_ledger_as_the_plain_string_value(
    tmp_path: Path,
) -> None:
    """After a write + re-read, outcome comes back as GateVerdict.<X>.value.

    JSON carries no enum type, so the re-read record's outcome is a plain
    str equal to the `.value` (e.g. "fail"), never the GateVerdict member --
    pinned here so no downstream reader assumes `isinstance(outcome,
    GateVerdict)` holds after a `read_records()` round trip.
    """
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(
        event=_CARPACCIO_CLEARED, slice_id="slice-01", outcome=GateVerdict.FAIL
    )

    (reread,) = ledger.read_records()
    assert reread["outcome"] == "fail"
    assert isinstance(reread["outcome"], str)
    assert not isinstance(reread["outcome"], GateVerdict)


def test_absent_and_present_outcome_are_distinguishable_on_the_reread_record(
    tmp_path: Path,
) -> None:
    """The re-read record is the one place absent-outcome != wrong-outcome.

    Per the design's own Handoff note: a spy double substituted for
    AtCompletionLedgerPort in a unit test can no longer distinguish "this
    call site passed the wrong outcome=" from "this call site passed no
    outcome= at all" -- both look identical to a spy that only asserts the
    method was called. The re-read JSONL record is the one place the two
    stay mechanically distinguishable: one record carries no "outcome" key,
    the other carries the exact typed verdict that was passed.
    """
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(event=_CARPACCIO_CLEARED, slice_id="slice-01")
    ledger.append_gate_event(
        event=_CARPACCIO_CLEARED,
        slice_id="slice-02",
        outcome=GateVerdict.INDETERMINATE,
    )

    silent_record, verdict_record = ledger.read_records()
    assert "outcome" not in silent_record
    assert verdict_record["outcome"] == "indeterminate"


def test_outcome_is_hashed_into_record_hash_exactly_like_every_other_field(
    tmp_path: Path,
) -> None:
    """A hand-edited outcome value breaks record_hash -- tamper-evident (M7)."""
    ledger = _ledger(tmp_path)
    ledger.append_gate_event(
        event=_CARPACCIO_CLEARED, slice_id="slice-01", outcome=GateVerdict.PASS
    )
    path = ledger.ledger_path()
    tampered = path.read_text(encoding="utf-8").replace(
        '"outcome":"pass"', '"outcome":"fail"'
    )
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "hash-mismatch"


def test_outcome_combines_with_gate_and_reason_without_interference(
    tmp_path: Path,
) -> None:
    """outcome, gate and reason are independent optional fields -- all coexist."""
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(
        event=_CARPACCIO_REJECTED,
        slice_id="slice-01",
        gate="mode-locus-gate",
        reason="scan found zero families",
        outcome=GateVerdict.FAIL,
    )

    assert record["gate"] == "mode-locus-gate"
    assert record["reason"] == "scan found zero families"
    assert record["outcome"] == GateVerdict.FAIL


def test_a_plain_string_matching_pass_value_is_accepted_at_runtime_mypy_only_guard(
    tmp_path: Path,
) -> None:
    """The `outcome: GateVerdict | None` annotation is a compile-time (mypy)
    guarantee only -- Python does not enforce it at call time.

    Named so the guarantee this slice buys is never overstated (mirrors the
    slice-01 Sentinel-corrected finding, applied here for slice-02's own
    kwarg): a bare string equal to `GateVerdict.PASS.value` threads through
    exactly like the real enum member -- nominal typing is a static check,
    not a runtime one.
    """
    ledger = _ledger(tmp_path)
    # Deliberately untyped at the call site (see docstring): a bare str is
    # NOT a GateVerdict instance, but Python raises nothing at call time.
    outcome_value: object = "pass"
    record = ledger.append_gate_event(
        event=_CARPACCIO_CLEARED,
        slice_id="slice-01",
        outcome=outcome_value,
    )

    assert record["outcome"] == "pass"
    assert record["outcome"] == GateVerdict.PASS


def test_ledger_records_a_stated_outcome_even_when_it_contradicts_the_gate_name(
    tmp_path: Path,
) -> None:
    """append_gate_event is a pure write -- it never disputes the outcome
    against the gate's actual result.

    Concrete instance of the unbounded gate-outcome-verdict-mismatch domain
    (component-manifest.yaml, canonical-category C5): a caller can pass
    GateVerdict.PASS for a gate named "a-gate-that-actually-failed" and the
    ledger faithfully records PASS -- outcome-correctness is explicitly NOT
    this layer's job (design Handoff / DDD-5 criterion).
    """
    ledger = _ledger(tmp_path)
    record = ledger.append_gate_event(
        event=_CARPACCIO_REJECTED,
        slice_id="slice-01",
        gate="a-gate-that-actually-failed",
        outcome=GateVerdict.PASS,
    )

    assert record["outcome"] == GateVerdict.PASS
    assert record["gate"] == "a-gate-that-actually-failed"


@given(
    outcome=st.sampled_from(list(GateVerdict)),
    gate=st.one_of(st.none(), st.text(min_size=1, max_size=40)),
    reason=st.one_of(st.none(), st.text(min_size=1, max_size=80)),
)
@settings(max_examples=50, deadline=None)
def test_append_gate_event_records_any_verdict_faithfully_pure_write(
    tmp_path_factory: pytest.TempPathFactory,
    outcome: GateVerdict,
    gate: str | None,
    reason: str | None,
) -> None:
    """For ANY GateVerdict crossed with gate/reason presence, the write is
    faithful and total -- the ledger does NOT verify outcome matches truth.

    gate-outcome-verdict-mismatch (component-manifest.yaml, C5): the domain
    of (gate_id, outcome, reason) triples a caller can construct is
    unbounded -- this property pins totality + faithfulness across all five
    GateVerdict members, never outcome-truth (which is explicitly out of
    this seam's scope, per the design's own Handoff note).
    """
    ledger = _ledger(tmp_path_factory.mktemp("ledger"))
    record = ledger.append_gate_event(
        event=_CARPACCIO_CLEARED,
        slice_id="slice-01",
        gate=gate,
        reason=reason,
        outcome=outcome,
    )
    (reread,) = ledger.read_records()

    assert record["outcome"] == outcome
    assert reread["outcome"] == outcome.value
    if gate is not None:
        assert reread["gate"] == gate
    else:
        assert "gate" not in reread
    if reason is not None:
        assert reread["reason"] == reason
    else:
        assert "reason" not in reread


# --- heartbeat-leg outcome retrofit (gate-outcome-record-seam slice-05) -----
#
# The 4 RM-1 heartbeat-leg families (env-e2e, fresh-clone, execution-reach,
# doc-coherence) already write a heartbeat ("...GateRan") + terminal-record
# pair ("...Verified" / "...NotApplicable"); before this slice the terminal
# record's PASS/NOT_APPLICABLE verdict was encoded ONLY in the event NAME
# string. Retrofitted here with the SAME `outcome` field slice-02 added to
# `append_gate_event`, baked into each of these 8 fixed-shape call sites --
# no new public parameter on any of the 8 methods (each method's own name
# already determines its verdict, so nothing becomes caller-configurable
# that was not already).
#
# @contract-shape:bounded-change -- mutation set = {one `outcome` field on
# each of the 8 terminal-record call sites}; the 4 heartbeat (`*_gate_ran`)
# siblings are untouched and pinned as such
# (test_heartbeat_gate_ran_records_carry_no_outcome_field) -- the Critical
# Rules mandate that a fix on one branch must not silently flatten its
# neighbours.

_VERIFIED_HEARTBEAT_LEG_CASES = [
    pytest.param(
        "append_environmental_e2e_verified", ENVIRONMENTAL_E2E_VERIFIED, id="env-e2e"
    ),
    pytest.param("append_fresh_clone_verified", FRESH_CLONE_VERIFIED, id="fresh-clone"),
    pytest.param(
        "append_execution_reach_verified",
        EXECUTION_REACH_VERIFIED,
        id="execution-reach",
    ),
    pytest.param(
        "append_doc_coherence_verified", DOC_COHERENCE_VERIFIED, id="doc-coherence"
    ),
]

_NOT_APPLICABLE_HEARTBEAT_LEG_CASES = [
    pytest.param(
        "append_environmental_e2e_not_applicable",
        ENVIRONMENTAL_E2E_NOT_APPLICABLE,
        id="env-e2e",
    ),
    pytest.param(
        "append_fresh_clone_not_applicable",
        FRESH_CLONE_NOT_APPLICABLE,
        id="fresh-clone",
    ),
    pytest.param(
        "append_execution_reach_not_applicable",
        EXECUTION_REACH_NOT_APPLICABLE,
        id="execution-reach",
    ),
    pytest.param(
        "append_doc_coherence_not_applicable",
        DOC_COHERENCE_NOT_APPLICABLE,
        id="doc-coherence",
    ),
]

_HEARTBEAT_GATE_RAN_METHOD_NAMES = [
    pytest.param("append_environmental_e2e_gate_ran", id="env-e2e"),
    pytest.param("append_fresh_clone_gate_ran", id="fresh-clone"),
    pytest.param("append_execution_reach_gate_ran", id="execution-reach"),
    pytest.param("append_doc_coherence_gate_ran", id="doc-coherence"),
]


@pytest.mark.parametrize("method_name,expected_event", _VERIFIED_HEARTBEAT_LEG_CASES)
def test_verified_heartbeat_leg_records_carry_explicit_pass_outcome(
    tmp_path: Path, method_name: str, expected_event: str
) -> None:
    """Each `_verified` terminal record states its own outcome explicitly.

    Before this slice a reader had to decode "PASS" from the event NAME
    (e.g. "EnvironmentalE2eVerified" ends in "Verified") -- retrofitted so
    the record carries GateVerdict.PASS on the `outcome` key directly,
    matching the `append_gate_event` contract slice-02 established.
    """
    ledger = _ledger(tmp_path)
    record = getattr(ledger, method_name)()

    assert record["event"] == expected_event
    assert record["outcome"] == GateVerdict.PASS


@pytest.mark.parametrize(
    "method_name,expected_event", _NOT_APPLICABLE_HEARTBEAT_LEG_CASES
)
def test_not_applicable_heartbeat_leg_records_carry_explicit_not_applicable_outcome(
    tmp_path: Path, method_name: str, expected_event: str
) -> None:
    """Each `_not_applicable` NA-marker record states its own outcome explicitly.

    Mirrors the `_verified` case above for the NA-marker sibling: retrofitted
    with GateVerdict.NOT_APPLICABLE on the `outcome` key, so a reader never
    decodes the verdict from the "NotApplicable" event-name suffix.
    """
    ledger = _ledger(tmp_path)
    record = getattr(ledger, method_name)()

    assert record["event"] == expected_event
    assert record["outcome"] == GateVerdict.NOT_APPLICABLE


@pytest.mark.parametrize("method_name", _HEARTBEAT_GATE_RAN_METHOD_NAMES)
def test_heartbeat_gate_ran_records_carry_no_outcome_field(
    tmp_path: Path, method_name: str
) -> None:
    """The heartbeat (`*GateRan`) sibling is untouched by the retrofit.

    Pins the neighbouring branch (Critical Rules mandate): the heartbeat
    fires BEFORE the real gate runs, so it structurally cannot know
    PASS/FAIL/NOT_APPLICABLE yet -- it must keep carrying no `outcome` key
    at all, exactly as before this slice.
    """
    ledger = _ledger(tmp_path)
    record = getattr(ledger, method_name)()

    assert "outcome" not in record


def test_heartbeat_leg_outcome_round_trips_through_the_jsonl_ledger_as_plain_string(
    tmp_path: Path,
) -> None:
    """One exemplar family (env-e2e / doc-coherence) proves the retrofit
    survives a re-read.

    Slice-02 already pins the general write -> JSONL -> re-read shape for
    the bare `outcome` field on `append_gate_event`; this exemplar proves
    the SAME shape holds when `outcome` is baked into a fixed-shape
    heartbeat-leg call site rather than passed by the caller. Not repeated
    per family -- the round-trip mechanism is identical across all 4 (same
    `_append_record` writer), so a second example would pin the writer
    twice, never the retrofit itself.
    """
    ledger = _ledger(tmp_path)
    ledger.append_environmental_e2e_verified()
    ledger.append_doc_coherence_not_applicable()

    verified_record, na_record = ledger.read_records()
    assert verified_record["outcome"] == "pass"
    assert na_record["outcome"] == "not_applicable"


def test_heartbeat_leg_outcome_is_hashed_into_record_hash(tmp_path: Path) -> None:
    """A hand-edited heartbeat-leg outcome breaks record_hash (M7), same as
    the bare `append_gate_event` kwarg case above -- tamper-evident, not
    merely present."""
    ledger = _ledger(tmp_path)
    ledger.append_fresh_clone_verified()
    path = ledger.ledger_path()
    tampered = path.read_text(encoding="utf-8").replace(
        '"outcome":"pass"', '"outcome":"fail"'
    )
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(LedgerIntegrityViolation) as exc:
        ledger.read_records()
    assert exc.value.detail == "hash-mismatch"
