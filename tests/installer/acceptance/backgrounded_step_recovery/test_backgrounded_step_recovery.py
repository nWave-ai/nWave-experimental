"""pytest wrapper around the public oracle for backgrounded-step recovery.

The observation itself lives in ``public_oracle.py``, which is runnable on its
own (`uv run python tests/installer/acceptance/backgrounded_step_recovery/
public_oracle.py`) so its exit status carries the verdict for an examiner who
reads no source. This wrapper re-exports it into the suite, and adds the
predicate-level checks that keep the oracle honest against synthetic phrasings
that were never written against it.
"""

from __future__ import annotations

from tests.installer.acceptance.backgrounded_step_recovery.public_oracle import (  # noqa: F401
    bullets_of,
    published_skill,
    states_the_backgrounded_recovery,
    test_a_backgrounded_step_is_recovered_by_reading_the_requests_state,
    test_the_recovery_stays_guidance_and_never_becomes_a_gate,
)


SATISFYING = (
    "- A step that buys a role turn can run for minutes. Invoke it in the "
    "foreground; a backgrounded step has no notification, so waiting for a "
    "notification cannot work. DES records the turn it bought, so read the Request "
    "with `des state --repo-root ABSOLUTE_ROOT` to see whether the turn "
    "landed and what it names as NEXT.\n"
)

HAZARD_WITHOUT_RECOVERY = (
    "- Invoke it in the foreground with an explicit long timeout; a "
    "backgrounded step reaches no notification, so you would wait on a turn "
    "that has already ended.\n"
)

RECOVERY_WITHOUT_HAZARD = (
    "- DES records the turn it bought, so read the Request with `des state` "
    "to learn what is owed next.\n"
)

SPLIT_ACROSS_TWO_BULLETS = HAZARD_WITHOUT_RECOVERY + RECOVERY_WITHOUT_HAZARD


def test_the_predicate_accepts_a_bullet_that_carries_the_whole_recovery() -> None:
    assert any(states_the_backgrounded_recovery(b) for b in bullets_of(SATISFYING))


def test_the_predicate_rejects_todays_hazard_only_bullet() -> None:
    # This is the published text as measured before the change: the falsifier.
    assert not any(
        states_the_backgrounded_recovery(b) for b in bullets_of(HAZARD_WITHOUT_RECOVERY)
    )


def test_the_predicate_rejects_a_recovery_that_never_names_the_hazard() -> None:
    assert not any(
        states_the_backgrounded_recovery(b) for b in bullets_of(RECOVERY_WITHOUT_HAZARD)
    )


def test_the_predicate_rejects_the_claims_split_across_two_bullets() -> None:
    # Co-occurrence in ONE bullet is the point: an agent must meet the failing
    # move and the working one together.
    assert not any(
        states_the_backgrounded_recovery(b)
        for b in bullets_of(SPLIT_ACROSS_TWO_BULLETS)
    )
