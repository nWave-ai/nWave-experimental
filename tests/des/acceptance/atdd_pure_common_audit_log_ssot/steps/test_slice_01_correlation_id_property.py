"""AT-5 — correlation_id determinism + collision-freedom property test.

Layer 1 (pure function, no I/O): the ``derive_correlation_id`` helper is a
pure SHA-256-truncate-to-16-hex over the ``(feature_id, slice_id,
dispatch_seq)`` triple. Mandate 9 layer-1 PBT-full allowed: Hypothesis
``@given`` explores the operational input space; ``@example`` pins a
canonical case for reviewer readability.

DELIVERED (slice-01 core): the ``derive_correlation_id`` helper is live on
``src.des.adapters.driven.logging.at_completion_ledger`` and both properties
(determinism + collision-freedom) hold organically — the scenarios run green,
no xfail.

Mandate-12 criterion 3 compliance: the test bodies invoke the composition
service (``composition.when_correlation_id_derived_twice`` and
``then_correlation_ids_match`` / ``then_no_correlation_id_collision``);
no business logic lives in the test bodies.
"""

from __future__ import annotations

from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st

from .composition import CommonAuditLogSsotComposition


# slice-01 core DELIVERED: derive_correlation_id is live; the properties hold
# organically. No xfail — these run as normal green PBT.


# Mandate 9 layer-1 PBT: domain-realistic strategies, not unconstrained text.
# feature_id and slice_id are kebab-case ASCII identifiers; dispatch_seq is a
# 1..1_000_000 positive integer (per design D2 birthday-bound rationale).
_FEATURE_ID = st.from_regex(
    r"\A(?:fix|feat|chore|spike)-[a-z0-9-]{1,40}\Z", fullmatch=True
)
_SLICE_ID = st.from_regex(r"\Aslice-\d{2}\Z", fullmatch=True)
_DISPATCH_SEQ = st.integers(min_value=1, max_value=1_000_000)


@given(feature_id=_FEATURE_ID, slice_id=_SLICE_ID, dispatch_seq=_DISPATCH_SEQ)
@example(feature_id="fix-example", slice_id="slice-01", dispatch_seq=1)
@settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_correlation_id_is_deterministic_for_same_input(
    feature_id: str, slice_id: str, dispatch_seq: int
) -> None:
    """Determinism property: same input triple -> same 16-hex digest, every time."""
    composition = CommonAuditLogSsotComposition()
    first, second = composition.when_correlation_id_derived_twice(
        feature_id, slice_id, dispatch_seq
    )
    composition.then_correlation_ids_match(first, second)


@given(
    triples=st.lists(
        st.tuples(_FEATURE_ID, _SLICE_ID, _DISPATCH_SEQ),
        min_size=100,
        max_size=10_000,
        unique=True,
    )
)
@settings(
    max_examples=5,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
def test_correlation_id_collisions_are_absent_across_realistic_inputs(
    triples: list[tuple[str, str, int]],
) -> None:
    """Collision-freedom property: 100..10000 distinct triples -> no digest collision.

    The 16-hex (64-bit) digest space is birthday-bounded at ~4 billion entries
    per slice -- 10000-sample sweeps surface any structural collision in the
    derivation. Empirical floor for slice-01; the post-slice-05 production
    SLO measures actual collision rate over the full common-log volume.
    """
    composition = CommonAuditLogSsotComposition()
    for feature_id, slice_id, dispatch_seq in triples:
        composition.when_correlation_id_derived_twice(
            feature_id, slice_id, dispatch_seq
        )
    composition.then_no_correlation_id_collision()
