"""pytest-bdd binding for the wave-entering structural-signal scenarios (slice-07c).

Driving ports (Mandate-13 driving-port-only):
  * AT-1 / AT-2 -- Layer 4 wiring: the REAL prompt-submission anchor + the
    REAL PreToolUse hook adapter, both as subprocess black boxes over a tmp
    ``project_root`` (the hook adapter is the composition seat of the net-new
    peek_entry -> validate(wave_entering=...) -> clear-on-allow lifecycle).
    Observables: hook exit code / block reason + the floor record at the
    DESIGN-PINNED path.
  * AT-3 -- the SHIPPED pure core ``DiscussReviewGate.evaluate`` direct
    in-process (the 07b DESIGN-declared seam callable; slice-06 precedent;
    Mandate-13 adjudicated by the architect-reviewer, a06237ced).

Step bodies delegate to the composition roots (``composition_slice_07c.py``);
no business logic lives in a step body (Mandate-12). Each step decorator's
literal text is unique within this feature directory (S1) and disjoint from
the slice-04 / slice-07 / slice-07b literals.

Active-RED scaffold (ADR-025 + ADR-028, atdd_pure -- NOT @skip): until DELIVER
ships floor v1.1 (``entry_pending``), ``WaveActivationService``
(peek_entry / clear_entry), ``PreToolUseInput.wave_entering`` and the hook-
adapter clear-on-allow composition -- and DELETES the AD-66 keyword heuristic
-- the anchor writes a floor without the pending mark and a wording-free
dispatch is never entry-gated. AT-1 / AT-2 fail with a semantic
``AssertionError`` (the floor carries no entry-pending mark; the wording-free
dispatch is ALLOWED where the structural gate must BLOCK), never a
collection / import / setup error. AT-3 is GREEN-preservation: the 07b core
shipped; its four rows PIN the routed INDETERMINATE reasons.

SUT STATE MACHINE (C2): see the .feature header + composition docstring --
{NO_WAVE, ARMED+PENDING, ARMED+CLEARED} with arm / blocked-entry-stays /
allow-clears / never-re-gated transitions; the AT-3 audit maps each
unverifiable verdict shape to INDETERMINATE.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition_slice_07c import (
    ReviewVerdictAuditComposition,
    WaveEntryComposition,
)
from .domain_types_slice_07c import EntryPreconditions, ReviewVerdictFlaw


scenarios("../slice-07c-wave-entering-structural-signal.feature")


@pytest.fixture
def wave_entry() -> WaveEntryComposition:
    return WaveEntryComposition()


@pytest.fixture
def review_audit() -> ReviewVerdictAuditComposition:
    return ReviewVerdictAuditComposition()


# --- Given (wave entry) --------------------------------------------------------


@given("the operator arms the discuss wave with the explicit command")
def given_armed_discuss_via_command(
    wave_entry: WaveEntryComposition, tmp_path: Path
) -> None:
    wave_entry.given_armed_discuss_via_command(tmp_path)


@given("the product preconditions for discuss are unmet")
def given_preconditions_unmet(wave_entry: WaveEntryComposition) -> None:
    wave_entry.given_entry_preconditions(EntryPreconditions.UNMET)


@given("the product preconditions for discuss are met")
def given_preconditions_met(wave_entry: WaveEntryComposition) -> None:
    wave_entry.given_entry_preconditions(EntryPreconditions.MET)


# --- When (wave entry) ---------------------------------------------------------


@when("an in-wave dispatch whose wording never mentions entering is checked")
def when_wordless_dispatch_checked(wave_entry: WaveEntryComposition) -> None:
    wave_entry.when_wordless_in_wave_dispatch_checked()


@when("a later in-wave dispatch is checked after the preconditions have degraded")
def when_later_dispatch_checked(wave_entry: WaveEntryComposition) -> None:
    wave_entry.when_later_dispatch_checked_after_degraded_preconditions()


# --- Then (wave entry) ---------------------------------------------------------


@then("the arming command marked the wave entry as pending")
def then_arm_marked_entry_pending(wave_entry: WaveEntryComposition) -> None:
    wave_entry.then_arm_marked_entry_pending()


@then("the dispatch is allowed")
def then_dispatch_allowed(wave_entry: WaveEntryComposition) -> None:
    wave_entry.then_dispatch_allowed()


@then("the wave entry is cleared by the allowed entry")
def then_entry_cleared_by_allowed_entry(wave_entry: WaveEntryComposition) -> None:
    wave_entry.then_entry_cleared_by_allowed_entry()


@then("the later dispatch is allowed without re-running the entry preconditions")
def then_later_dispatch_not_regated(wave_entry: WaveEntryComposition) -> None:
    wave_entry.then_later_dispatch_not_regated()


# --- Given/When/Then (review-verdict audit, AT-3 outline) -----------------------


@given(parsers.parse("a recorded product-owner review verdict flawed as {flaw}"))
def given_flawed_verdict(
    review_audit: ReviewVerdictAuditComposition, flaw: str
) -> None:
    review_audit.given_flawed_verdict(ReviewVerdictFlaw(flaw))


@when("the review verdict is evaluated against the current artefact")
def when_verdict_evaluated(review_audit: ReviewVerdictAuditComposition) -> None:
    review_audit.when_verdict_evaluated()


@then(parsers.parse("the review gate result is indeterminate naming {cause}"))
def then_indeterminate_naming(
    review_audit: ReviewVerdictAuditComposition, cause: str
) -> None:
    review_audit.then_indeterminate_naming(cause)
