"""Step definitions: a non-Python target's slice chain un-wedges on a degrade.

carpaccio-in-order-honest-non-at-attestation slice-02 (US-03 / Raj). The
beta-tester drives ``des commit-slice`` on a non-Python target where no pytest
interpreter resolves. slice-02 routes the committed-scope-digest degrade path to
MINT the EXISTING ``SliceCommitIndeterminate`` record (with a free-text
``reason``), which the in-order gate already accepts -- so the chain progresses
instead of wedging, the degrade is never silent, and a fabricated
``SliceCommitVerified`` is NEVER written.

Mandate 13: the driving ports are the production producer CLI
(``des commit-slice`` -> ``des.cli.commit_slice.main``) and the production live
carpaccio intercept (``evaluate_atdd_pure_dispatch``), both invoked through
``DegradedCommitComposition`` (the composition root). NO direct-domain call of
``indeterminate_slices()`` or ``_predecessor_satisfies_in_order``: the gate reads
the indeterminate record through the REAL hook, and the producer writes it
through the REAL CLI.

Layer 3 composition. ``@real-io`` (a real git repo + the real
``AtCompletionLedger`` filesystem on tmp_path). Example-only, no PBT machinery
(Mandate 9 / 11). The mint has a bounded-change contract (DDD-6): its observable
effect is one new ``SliceCommitIndeterminate`` line AND the live gate's successor
outcome flipping wedged -> proceeds. The When/Then steps assert via
``assert_state_delta`` over a port-exposed ledger+gate universe (Mandate 8).

Step bodies delegate to ``DegradedCommitComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a composition call plus a state-delta or
example assertion.

slice-02 RED contract (fail-for-right-reason, Mandate 7 -- RED not BROKEN): on
HEAD ``des commit-slice``'s degrade branch (``commit_slice.py:302``) returns 1
with NO ledger record and ``--feature-id`` is an unknown arg, so no
``SliceCommitIndeterminate`` is minted. The record-count assertions raise
``AssertionError`` (missing functionality: the degrade-mint routing + the
``--feature-id`` arg). Every dependency (git, the real ledger, the real
``commit_slice`` + ``evaluate_atdd_pure_dispatch`` imports, the state-delta port)
resolves cleanly -- a deliberate missing-functionality RED, not a test bug.
DELIVER greens it by routing the degrade branch to the existing
``SliceCommitIndeterminate`` mint with a ``reason`` and adding the additive
``--feature-id`` arg (DDD-6).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition_slice_02 import DegradedCommitComposition
from .domain_types import CommitOutcome, GateOutcome


scenarios("../slice-02-non-python-indeterminate.feature")


@pytest.fixture
def chain(tmp_path: Path) -> DegradedCommitComposition:
    """Production-wired composition root over a tmp_path git repository."""
    return DegradedCommitComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def box() -> dict[str, object]:
    """Carrier for the commit run + universe snapshot across When -> Then."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "a committed predecessor slice on a non-Python target where the "
    "interpreter is unavailable"
)
def given_non_python_target(chain: DegradedCommitComposition) -> None:
    chain.create_degraded_target_repo()


@given("the successor slice is wedged because the predecessor carries no honest record")
def given_successor_wedged(chain: DegradedCommitComposition) -> None:
    assert chain.successor_is_wedged(), (
        "precondition: the successor must be wedged before the predecessor is "
        "committed (the predecessor carries no honest record yet)"
    )


# --- When --------------------------------------------------------------------


@when("the operator commits the predecessor slice with des commit-slice")
def when_commit_under_degrade(
    chain: DegradedCommitComposition, box: dict[str, object]
) -> None:
    box["before"] = chain.capture_universe()
    box["run"] = chain.commit_predecessor_under_degrade()


@when("the operator dispatches the successor slice into delivery")
def when_dispatch_successor(
    chain: DegradedCommitComposition, box: dict[str, object]
) -> None:
    box["successor_outcome"] = chain.dispatch_successor_outcome()


# --- Then --------------------------------------------------------------------


@then(
    "the in-order gate accepts the indeterminate predecessor and the successor proceeds"
)
def then_successor_proceeds(
    chain: DegradedCommitComposition, box: dict[str, object]
) -> None:
    assert_state_delta(
        before=box["before"],
        after=chain.capture_universe(),
        universe={
            "ledger.indeterminate_record_count",
            "ledger.fabricated_verified_count",
            "gate.successor_outcome",
        },
        expected={
            "ledger.indeterminate_record_count": set_to(1),
            "ledger.fabricated_verified_count": unchanged(),
            "gate.successor_outcome": set_to(GateOutcome.PROCEEDS.value),
        },
    )


@then("the predecessor commit lands carrying its slice trailers")
def then_commit_landed(chain: DegradedCommitComposition) -> None:
    assert chain.commit_landed_with_trailers() == CommitOutcome.LANDED, (
        "the degraded commit must still LAND on HEAD carrying its Slice-Id "
        "trailer -- the digest could not be pinned, but the commit was written"
    )


@then("the ledger carries one indeterminate record naming the degrade reason")
def then_one_indeterminate_with_reason(chain: DegradedCommitComposition) -> None:
    assert chain.indeterminate_record_count() == 1, (
        "exactly one SliceCommitIndeterminate record must be minted on the "
        "interpreter-unavailable degrade (degrade-LOUD, never silent)"
    )
    assert chain.latest_indeterminate_names_degrade_reason(), (
        "the indeterminate record must carry the honest free-text reason "
        "gate_scope_interpreter_unavailable (DDD-6)"
    )


@then("the ledger carries no fabricated verified record for the degraded predecessor")
def then_no_fabricated_verified(chain: DegradedCommitComposition) -> None:
    assert chain.fabricated_verified_count() == 0, (
        "honesty invariant: a degraded commit must NEVER carry a fabricated "
        "SliceCommitVerified record"
    )


@then("the indeterminate record is honest with no real gate-scope digest")
def then_no_real_digest(chain: DegradedCommitComposition) -> None:
    assert chain.indeterminate_record_count() == 1, (
        "the indeterminate record must exist before its honesty fields are "
        "asserted (degrade-mint, slice-02)"
    )
    assert chain.latest_indeterminate_has_no_real_digest(), (
        "degrade-LOUD honesty: the indeterminate record must carry no fabricated "
        "committed-scope digest and must not claim at_verified -- it is honestly "
        "unverified on this machine"
    )
