"""Step definitions: a prose-predecessor slice chain un-wedges end-to-end.

carpaccio-in-order-honest-non-at-attestation slice-01 (walking skeleton). The
skeleton carries BOTH US-01 (a ``SliceProseDelivered`` record is minted from a
doc-review APPROVED verdict) and US-02 (the live in-order gate accepts the prose
record so the successor proceeds) -- without both, the prose chain still wedges.

Mandate 13: the driving ports are the production producer CLI
(``des record-prose-delivered`` -> ``des.cli.record_prose_delivered.main``) and
the production live carpaccio intercept
(``des.adapters.drivers.hooks.carpaccio_intercept.evaluate_atdd_pure_dispatch``),
both invoked through ``ProseChainComposition`` (the composition root). NO
direct-domain call of ``prose_delivered_slices()`` or of
``_predecessor_satisfies_in_order``: the gate reads the prose record through the
REAL hook entry point, and the producer writes it through the REAL CLI.

Layer 3 composition. ``@real-io`` (the real ``AtCompletionLedger`` filesystem on
tmp_path). Example-only, no PBT machinery (Mandate 9 / 11). The mint has a
bounded-change contract (DDD-2): its observable effect is one new
``SliceProseDelivered`` line on the ledger AND the live gate's successor outcome
flipping wedged -> proceeds. The When/Then steps assert via ``assert_state_delta``
over a port-exposed ledger+gate universe (Mandate 8).

Step bodies delegate to ``ProseChainComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a composition call plus a state-delta
assertion.

slice-01 RED contract (fail-for-right-reason, Mandate 7 -- RED not BROKEN): the
``des record-prose-delivered`` producer does not exist on HEAD, so the mint step
raises ``AssertionError`` (missing functionality: the producer + the gate-accept
clause). Every dependency (state-delta port, pytest-bdd, the real ledger + the
real hook import) resolves cleanly -- a deliberate missing-functionality RED, not
a test bug. DELIVER greens it by shipping the producer (DDD-5) + the
``prose_delivered_slices()`` gate clause (DDD-1/-3/-8).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.common.state_delta import assert_state_delta, set_to, unchanged

from .composition import ProseChainComposition
from .domain_types import GateOutcome


scenarios("../walking-skeleton.feature")


@pytest.fixture
def chain(tmp_path: Path) -> ProseChainComposition:
    """Production-wired composition root over a tmp_path repository."""
    return ProseChainComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def box() -> dict[str, object]:
    """Carrier for the mint run + universe snapshot across When -> Then."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "a prose predecessor slice that has been doc-review approved with no acceptance tests"
)
def given_prose_predecessor(chain: ProseChainComposition) -> None:
    chain.create_prose_predecessor_repo()


@given("the successor slice is wedged because the predecessor carries no honest record")
def given_successor_wedged(chain: ProseChainComposition) -> None:
    assert chain.successor_is_wedged(), (
        "precondition: the successor must be wedged before the prose verdict is "
        "recorded (the predecessor carries no honest record yet)"
    )


# --- When --------------------------------------------------------------------


@when("the operator records the prose verdict for the predecessor")
def when_record_prose_verdict(
    chain: ProseChainComposition, box: dict[str, object]
) -> None:
    box["before"] = chain.capture_universe()
    box["mint"] = chain.record_prose_verdict()


@when("the operator dispatches the successor slice into delivery")
def when_dispatch_successor(
    chain: ProseChainComposition, box: dict[str, object]
) -> None:
    box["successor_outcome"] = chain.dispatch_successor_outcome()


# --- Then --------------------------------------------------------------------


@then("the in-order gate accepts the prose predecessor and the successor proceeds")
def then_successor_proceeds(
    chain: ProseChainComposition, box: dict[str, object]
) -> None:
    assert_state_delta(
        before=box["before"],
        after=chain.capture_universe(),
        universe={
            "ledger.prose_record_count",
            "ledger.fabricated_verified_count",
            "gate.successor_outcome",
        },
        expected={
            "ledger.prose_record_count": set_to(1),
            "ledger.fabricated_verified_count": unchanged(),
            "gate.successor_outcome": set_to(GateOutcome.PROCEEDS.value),
        },
    )


@then("the ledger carries one prose-delivered record attested by the doc-review")
def then_one_attested_prose_record(chain: ProseChainComposition) -> None:
    assert chain.prose_record_count() == 1, (
        "exactly one SliceProseDelivered record must be minted for the predecessor"
    )
    assert chain.latest_prose_record_is_attested_unverified(), (
        "the prose record must carry the honest fields: attested=true, "
        "at_verified=false, reason=prose_attested_by_doc_review, verdict=APPROVED"
    )


@then("the ledger carries no fabricated verified record for the prose predecessor")
def then_no_fabricated_verified(chain: ProseChainComposition) -> None:
    assert chain.fabricated_verified_count() == 0, (
        "honesty invariant: a prose slice must NEVER carry a fabricated "
        "SliceCommitVerified record"
    )
