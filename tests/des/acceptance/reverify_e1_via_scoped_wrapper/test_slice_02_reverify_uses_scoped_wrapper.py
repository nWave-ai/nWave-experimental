"""slice-02 binder: reverify swaps E1 to the feature-scoped wrapper.

Walking-skeleton / wiring_e2e: drives the real ``reverify_slice_commit.main``
in-process against a real temp-git repo (the layer-3 acceptance pattern
established by ``tests/des/acceptance/test_reverify_slice_commit.py`` and the
sibling ``reverify_p4_tracked_before_fallback`` suite).

Witnesses the decision-table rows the existing reverify ATs miss:
  - R4 (>=2 features sharing @slice-NN, feature-scoped) -- THE closing AT for
    F-REVERIFY-E1-GLOBAL-SCOPE-COLLISION. With slice-01's wrapper unwired,
    reverify's E1 walks every feature's @slice-NN file globally; a collider's
    .feature file fails completeness and blocks recovery. After slice-02's
    swap, E1 calls ``check_slice_at_completeness`` with ``--feature-id``, so
    the collider is invisible and reverify clears.
  - R3 (single-feature, feature-scoped) -- regression guard for the 10
    existing reverify ATs (the single-feature shape MUST still reverify
    green after the swap).

The reverify CLI's E1 invocation is the SUT change shipped by slice-02; the
two scenarios assert the success outcome (``ReverifyE1Outcome.SUCCESS``).
"""

from pytest_bdd import scenarios

from .steps.steps_reverify_e1 import *


scenarios("slice_02_reverify_uses_scoped_wrapper.feature")
