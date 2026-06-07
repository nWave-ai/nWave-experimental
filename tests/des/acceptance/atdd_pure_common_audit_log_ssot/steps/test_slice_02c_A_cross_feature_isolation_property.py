"""AT-A3 -- cross-feature isolation property for the singleton-shape audit log.

**Property (machine-readable contract)**:

    for all (feature_a, feature_b, dispatch_seq) where feature_a != feature_b:
        read_records(feature_id=feature_b)
        intersect
        records_seeded(feature_id=feature_a, dispatch_seq=dispatch_seq)
        ==
        empty set

Any cross-feature visibility is a contract violation.

**Input domain** (per architect M51 amendment spec, dimensional completeness
M55 MEDIUM-3 requirement): Hypothesis ``@given`` over open-ended kebab-case
feature_id pairs and 1..1_000_000 dispatch_seq integers. A canonical
``@example`` pins the (alpha, beta, 1) triple for reviewer readability.

**Failure mode**: any record returned for ``feature_id=feature_b`` whose
``feature_id`` field equals ``feature_a`` is a leak. The composition service
asserts via ``AssertionError`` with the leaking record's raw payload.

**Shrinking strategy**: Hypothesis preferentially shrinks toward minimal
kebab-case identifiers (shortest fullmatch on the regex strategy) and
smallest dispatch_seq (toward 1). Document failure on the smallest
reproducer in the test output.

**Layer-1 PBT-machinery (Mandate 9)**: the test uses ``@given`` (PBT-full
machinery) per the architect's M51 spec. I/O happens via composition
subprocess delegation (Mandate-13 boundary: every production invocation in
spawned subprocess; ``from des.adapters.*`` lives only in the stub string).
``max_examples`` is held to 25 to keep the wall-clock under 60s -- this is
a probabilistic safety net beyond AT-A2's deterministic example.

**RED scaffold (Mandate 7 / ADR-025)**: the singleton-shape
``AtCompletionLedger(project_root)`` constructor + ``read_records(
feature_id=...)`` filter kwarg are both required for the property to
evaluate. Pre-DELIVER A_GREEN the writer/reader contract isn't fully wired
at every callsite -- ``TypeError`` on construction or filter mismatch reds
the property for the right reason (MISSING_FUNCTIONALITY).

**Mandate-12 criterion 3 compliance**: the test body invokes the composition
service (``composition.given_multi_feature_substrate_seeded`` +
``composition.when_reader_queries_filtered_by_feature`` +
``composition.then_query_returned_no_records_for_other_feature``); no
business logic lives in the test body.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from .composition import CommonAuditLogSsotComposition
from .domain_types import EventKind, FeatureId, SliceId


# Same xfail discipline as AT-A1/AT-A2 BDD scenarios: the slice-02c-A
# crafter has not yet shipped the 6-production-callsite + 16-fixture-
# fanout atomic bundle. The composition's singleton-shape writer driver
# will spawn against today's substrate; if the writer at any of the 6
# production callsites still references the legacy per-feature path, the
# multi-feature substrate seed does NOT land under the common log and the
# filter returns zero rows of either feature_id -- the property then reds
# at the count-assertion side (AT-A2 mode) or trivially passes vacuously
# (AT-A3 mode). strict=False so the post-GREEN organic pass is tolerated
# without XPASS.
pytestmark = pytest.mark.xfail(
    reason=(
        "RED scaffold -- slice-02c-A production migration not yet shipped; "
        "multi-feature substrate seed may not land under the common log "
        "until the 6 production callsites all use singleton-shape"
    ),
    strict=False,
    raises=(AssertionError, ModuleNotFoundError, ImportError, TypeError),
)


# Domain strategies: kebab-case feature_ids on the same regex as
# slice-01 AT-5 (canonical project convention) + 1..1_000_000 dispatch_seq
# matching the design D2 birthday-bound rationale.
_FEATURE_ID = st.from_regex(
    r"\A(?:fix|feat|chore|spike)-[a-z0-9-]{1,40}\Z", fullmatch=True
)
_DISPATCH_SEQ = st.integers(min_value=1, max_value=1_000_000)


@given(
    feature_a=_FEATURE_ID,
    feature_b=_FEATURE_ID,
    dispatch_seq=_DISPATCH_SEQ,
)
@example(feature_a="fix-alpha", feature_b="fix-beta", dispatch_seq=1)
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_cross_feature_isolation_filter_never_leaks(
    feature_a: str, feature_b: str, dispatch_seq: int
) -> None:
    """For every (feature_a, feature_b, seq) where a != b: filter(b) MUST NOT see a's records.

    The composition service seeds the multi-feature substrate via the
    production singleton-shape writer (one CarpaccioGateCleared under
    feature_a, one SliceCommitVerified under feature_b), then drives
    the filtered reader for feature_b, then asserts feature_a is invisible.

    Hypothesis prunes the trivially-true case (feature_a == feature_b) via
    the precondition assume so the property body always exercises the
    non-trivial cross-feature isolation invariant.
    """
    from hypothesis import assume

    assume(feature_a != feature_b)
    composition = CommonAuditLogSsotComposition()
    composition.given_fresh_project_repository()
    composition.given_multi_feature_substrate_seeded(
        [
            (
                FeatureId(feature_a),
                SliceId(f"slice-{dispatch_seq:02d}"),
                EventKind.CARPACCIO_GATE_CLEARED,
            ),
            (
                FeatureId(feature_b),
                SliceId(f"slice-{dispatch_seq:02d}"),
                EventKind.SLICE_COMMIT_VERIFIED,
            ),
        ]
    )
    composition.when_reader_queries_filtered_by_feature(FeatureId(feature_b))
    composition.then_query_returned_no_records_for_other_feature(
        FeatureId(feature_b), FeatureId(feature_a)
    )
