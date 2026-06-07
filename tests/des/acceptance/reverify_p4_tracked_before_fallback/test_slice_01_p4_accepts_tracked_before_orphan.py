"""slice-01 binder: P4 accepts a tracked-before-unmodified orphan AT.

Walking-skeleton / wiring_e2e: drives the real ``reverify_slice_commit``
CLI port end-to-end against a real temp-git repo carrying the canonical
carpaccio-split orphan shape.

RED scaffold: the `_tracked_before_at_presence` helper does not exist yet,
so P4 refuses the tracked-before orphan and this scenario fails on the
`then_presence_accepted` assertion (semantic AssertionError -- correct RED).
DELIVER's A_GREEN_ATS turns it green.
"""

from pytest_bdd import scenarios

# Step definitions -- shared vocabulary (Mandate 10 / Mandate-12).
from .steps.steps_reverify_p4 import *  # noqa: F403


scenarios("slice_01_p4_accepts_tracked_before_orphan.feature")
