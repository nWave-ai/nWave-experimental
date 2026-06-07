"""Domain types for r3-gate-non-vacuity-build-tier slice-02 (Mandate-12 criterion 1).

slice-02 (PO REVISED, Ale): the per-slice exit gate must refuse LOUD when a
target's architecture tier EXISTS but collects ZERO invariant (the genuinely
malformed case), while still CLEARING a target that legitimately carries NO
architecture tier at all (genericità -- the `--feature-id` gate runs on the
TARGET repo during DELIVER, and an external target (TS/Go/minimal Python) has no
nWave `tests/build/` arch tier). The two holes are NOT symmetric:

  * Hole A -- arch tier ABSENT: `_arch_invariant_paths(repo)` returns `[]` when
    the repo has NO `tests/build/` dir. The join point's `if arch_paths:` is
    SKIPPED and the gate CLEARS -- now CORRECT BEHAVIOUR (no arch tier => no arch
    invariant to enforce). slice-02 adds an ABSENT *clear control* (genericità
    over-refusal guard). NOTE: current production over-refuses ABSENT with
    `arch-scope-empty` exit 2 -- the upcoming production change REMOVES that
    branch; the ABSENT control is the RED witness for that removal.
  * Hole B -- arch tier present-but-vacuous: when `tests/build/` EXISTS but the
    `--run` worker collects ZERO arch tests (the dir holds only tests that do
    NOT match `-m "unit or integration or acceptance"`), the current branch
    `if arch.collected > 0 and not arch.passed` falls through and SILENTLY
    clears. This IS malformed -- a present arch tier the gate would fingerprint
    vacuously.

Target contract (PO-revised):

  * arch tier ABSENT        -> `FeatureScopeCleared`, exit 0 (CLEAR, genericità).
  * arch tier collects zero  -> `FeatureScopeMalformed` reason
    `arch-scope-zero-collected`, exit 2 (REFUSED).

This mirrors the existing feature-scope M-1 floor (`zero-collected` /
`empty-intersection` reasons at `run_contract_gate.py:1010-1023`) but ONLY for a
present-but-vacuous tier -- the arch-coverage is non-vacuous when an arch tier is
present.

Mandate-12 SSOT: shared domain nouns (`FeatureId`, `SliceTag`, `GateVerdict`,
event-name constants) are RE-EXPORTED from `domain_types_slice_01` -- expressed
ONCE. Only the slice-02-specific nouns (`ArchScopeShape` + the
`arch-scope-zero-collected` reason) are declared here.
"""

from __future__ import annotations

from enum import Enum

# Re-export the shared domain vocabulary (Mandate-12: expressed once in slice-01).
from .domain_types_slice_01 import (  # noqa: F401  (re-exported SSOT vocabulary)
    ARCH_PROBE_FEATURE_ID,
    FEATURE_SCOPE_CLEARED_EVENT,
    FEATURE_SCOPE_MALFORMED_EVENT,
    PROBE_SLICE_TAG,
    FeatureId,
    GateVerdict,
    SliceTag,
)


class ArchScopeShape(str, Enum):
    """The SHAPE of the synthetic repo's architecture-tier SCOPE (slice-02).

    Where slice-01 quantified over a BROKEN-vs-CLEAN run-time outcome with a
    NON-VACUOUS arch tier, slice-02 quantifies over the VACUITY of the arch tier
    -- distinguishing the genuinely-malformed present-but-vacuous tier (REFUSE)
    from a legitimately-absent tier (CLEAR, genericità).

    * ABSENT -- the synthetic repo has a clean feature scope but NO `tests/build/`
      dir at all. `_arch_invariant_paths(repo)` returns `[]`. The gate CLEARS
      (exit 0 `FeatureScopeCleared`) -- a target with no arch tier carries no
      arch invariant to enforce (genericità). slice-02's *clear control* pins
      that the gate must NOT over-refuse this. (Current production over-refuses
      it with `arch-scope-empty` -- the RED this slice drives.)
    * ZERO_COLLECTED -- the repo HAS a `tests/build/` dir, but it holds ONLY an
      UNMARKED test (no `unit`/`integration`/`acceptance` mark). The `--run`
      worker filters on `-m "unit or integration or acceptance"`, so it collects
      ZERO arch node-ids. The gate must REFUSE LOUD: `FeatureScopeMalformed`
      reason `arch-scope-zero-collected` (a present arch tier that fingerprints
      vacuously is malformed). This is the real slice-02 value.
    * PRESENT -- the CONTROL: a non-vacuous arch tier whose invariants all hold
      (a `tests/build/` test carrying the load-bearing `unit` mark that runs
      GREEN). The gate must CLEAR (exit 0 `FeatureScopeCleared`) -- guards
      against over-refusal of a genuinely non-vacuous green tier.
    """

    ABSENT = "absent"  # no tests/build/ dir at all -- CLEAR (genericità)
    ZERO_COLLECTED = (
        "zero_collected"  # tests/build/ holds only an unmarked test -- REFUSE
    )
    PRESENT = "present"  # non-vacuous arch tier, all invariants hold -- CLEAR control


# The malformed `reason` the gate emits when a PRESENT arch tier fingerprints
# vacuously (collects zero under the `-m` filter). The AT asserts this for
# precision -- it distinguishes the present-but-vacuous refusal from the slice-01
# keystone refusal (`arch-invariant-failed`) and from the feature-scope floor
# reasons (`zero-collected` / `empty-intersection`).
ARCH_SCOPE_ZERO_COLLECTED_REASON = "arch-scope-zero-collected"
