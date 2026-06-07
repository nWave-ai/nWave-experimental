"""Shared fixture helper -- seed every record U4 requires at feature-end.

This helper exists to neutralise the F-FROZENSET-EXTENSION-FIXTURE-CASCADE
defect class: each time the production `_REQUIRED_FEATURE_END_RECORDS`
frozenset in `subagent_stop_handler.py` grows by one record, every happy-path
fixture site needs the matching `append_*` call added or the in-flight
feature breaks at U4. Pre-helper this required hand-editing 5-6 composition
sites in lockstep -- twice in a single autonomous-night session shipping a
new feature-end record cost a 5-site cascade per slice.

Contract -- structural, registry-driven:
  * `_RECORD_WRITERS` enumerates every required-record kind once and binds
    it to the `AtCompletionLedger` writer that emits it. Adding a new
    required record now means one new `_RECORD_WRITERS` entry HERE, plus
    extending the production frozenset; the fixture sites need no change.
  * `seed_required_feature_end_records` walks `_RECORD_WRITERS` and invokes
    each writer with a sensible default payload (the `verdict_hash` for
    `FeatureEndReviewVerdict` is the only record-specific kwarg, overridable
    via `verdict_hash=...`).
  * `exclude={"RecordName", ...}` lets the partial-seeding fixture sites
    (e.g. `seed_feature_end_cycle_missing(missing_record)`) keep their
    "every record EXCEPT X" semantics without re-listing every writer.

Safety net: `tests/des/unit/test_required_record_writer_registry.py` asserts
every record name in the production frozenset has a matching `_RECORD_WRITERS`
entry. A future frozenset extension without a writer mapping fires LOUD
under that test instead of silently leaking the cascade back.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger


_DEFAULT_VERDICT_HASH = "fixture-verdict-hash"


def _write_ebatch_refactor_completed(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `EBatchRefactorCompleted` record via the feature-end writer.

    Dual-shape (slice-02d-N0):
    - ``feature_id=None`` (default) -- legacy ledger-bound path; the
      construction-time feature_id wins via ``_resolve_feature_id``.
    - ``feature_id="<id>"`` -- singleton-shape forward; the kw-only arg is
      passed straight through to ``ledger.append_*(feature_id=...)``.
    """
    if feature_id is None:
        return ledger.append_feature_end_event(event="EBatchRefactorCompleted")
    return ledger.append_feature_end_event(
        event="EBatchRefactorCompleted", feature_id=feature_id
    )


def _write_feature_end_review_verdict(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `FeatureEndReviewVerdict` record, optionally carrying the hash.

    ``verdict_hash=None`` reproduces the legacy hashless call shape one
    fixture site relied on (the carpaccio-spine CLI happy-path); a non-None
    value reproduces the explicit-hash shape every other site uses.

    Dual-shape (slice-02d-N0): ``feature_id`` forwards to the underlying
    writer under the singleton-shape; ``None`` keeps the legacy ledger-bound
    behaviour.
    """
    if feature_id is None:
        return ledger.append_feature_end_event(
            event="FeatureEndReviewVerdict", verdict_hash=verdict_hash
        )
    return ledger.append_feature_end_event(
        event="FeatureEndReviewVerdict",
        verdict_hash=verdict_hash,
        feature_id=feature_id,
    )


def _write_environmental_e2e_gate_ran(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `EnvironmentalE2eGateRan` RM-1 heartbeat."""
    if feature_id is None:
        return ledger.append_environmental_e2e_gate_ran()
    return ledger.append_environmental_e2e_gate_ran(feature_id=feature_id)


def _write_walking_skeleton_gate_ran(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `WalkingSkeletonGateRan` RM-1 heartbeat."""
    if feature_id is None:
        return ledger.append_walking_skeleton_gate_ran()
    return ledger.append_walking_skeleton_gate_ran(feature_id=feature_id)


def _write_coverage_map_verified_at_distill_exit(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `CoverageMapVerifiedAtDistillExit` touchpoint heartbeat."""
    if feature_id is None:
        return ledger.append_coverage_map_verified_at_distill_exit()
    return ledger.append_coverage_map_verified_at_distill_exit(feature_id=feature_id)


def _write_coverage_map_verified_at_deliver_exit(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None,
) -> dict[str, Any]:
    """Emit the `CoverageMapVerifiedAtDeliverExit` touchpoint heartbeat."""
    if feature_id is None:
        return ledger.append_coverage_map_verified_at_deliver_exit()
    return ledger.append_coverage_map_verified_at_deliver_exit(feature_id=feature_id)


# The registry mapping each required-record name to its writer wrapper.
# Adding a new required record = extend the production frozenset AND add ONE
# entry here. The arch test `test_required_record_writer_registry.py` is the
# safety net for the second half of that pair.
_RECORD_WRITERS: dict[str, Callable[..., dict[str, Any]]] = {
    "EBatchRefactorCompleted": _write_ebatch_refactor_completed,
    "FeatureEndReviewVerdict": _write_feature_end_review_verdict,
    "EnvironmentalE2eGateRan": _write_environmental_e2e_gate_ran,
    "WalkingSkeletonGateRan": _write_walking_skeleton_gate_ran,
    "CoverageMapVerifiedAtDistillExit": _write_coverage_map_verified_at_distill_exit,
    "CoverageMapVerifiedAtDeliverExit": _write_coverage_map_verified_at_deliver_exit,
}


def required_record_writer_names() -> frozenset[str]:
    """The set of record names the helper knows how to seed.

    The arch test compares this set against the production frozenset --
    a future-extension safety net for the cascade-detector class.
    """
    return frozenset(_RECORD_WRITERS.keys())


def seed_required_feature_end_records(
    ledger: AtCompletionLedger,
    *,
    feature_id: str | None = None,
    verdict_hash: str | None = _DEFAULT_VERDICT_HASH,
    exclude: Iterable[str] = (),
) -> None:
    """Seed every record U4 requires at feature-end on ``ledger``.

    Walks `_RECORD_WRITERS` in insertion order (Python dict guarantee since
    3.7) and invokes each writer. The only record-specific knob is the
    reviewer ``verdict_hash`` carried on `FeatureEndReviewVerdict` -- every
    other writer ignores it. Passing ``verdict_hash=None`` reproduces the
    legacy hashless `FeatureEndReviewVerdict` shape one fixture site
    (carpaccio-spine CLI happy-path) relied on.

    ``exclude`` skips named records; partial-seeding fixture sites use this
    to keep "every required record EXCEPT X" semantics without re-listing
    every writer in their own code. An unknown name in ``exclude`` is a
    silent no-op (matches the pre-helper `if missing_record != "X"` shape).

    Dual-shape contract (slice-02d-N0):

    - ``feature_id=None`` (default) -- legacy ledger-bound path. The 6 writer
      wrappers invoke the underlying ledger writers WITHOUT a per-call
      ``feature_id=`` kwarg, so the construction-time feature_id wins via
      ``AtCompletionLedger._resolve_feature_id``. The 5 existing fixture
      caller sites (which pass no ``feature_id``) remain byte-identical.
    - ``feature_id="<id>"`` -- singleton-shape forward. Every writer wrapper
      forwards the kw-only value to ``ledger.append_*(feature_id=...)``,
      so a fixture site constructed against
      ``AtCompletionLedger(project_root=...)`` (singleton shape) can drive
      the new common-audit-log substrate without re-listing every writer.
    """
    excluded = set(exclude)
    for record_name, writer in _RECORD_WRITERS.items():
        if record_name in excluded:
            continue
        writer(ledger, feature_id=feature_id, verdict_hash=verdict_hash)
