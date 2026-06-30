"""Typed vocabulary for slice-07 ATs — CONSOLIDATE-ON-ADD (add-AND-improve, Mandate-12).

slice-07 of sustainable-test-suite is the CONSOLIDATE-ON-ADD slice (DDD-4 + DDD-5 +
DDD-6, the "add-AND-improve" / test-suite REFACTOR phase). The shipped slice-04
`--with-metrics` mode reports ONE feature's net test-LOC delta against its OWN git diff;
it is PASSIVE — it cannot tell a feature that ADDED a slice AND consolidated existing
surface from a feature that only added. slice-07 closes that: the gate measures the
consolidate-on-add GAIN — the net test-LOC of the consolidating run relative to the
add-only BASELINE for the same added scope — so the counter-gradient that bends the
+94%/feature curve (slice-06 H) has the same mechanical force as the completeness gate.

Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --consolidate-on-add
--add-only-baseline-loc=<N> --format=json` EXTENDS the slice-04 metrics mode. The
`--consolidate-on-add` MODE flag (DISTINCT from the `--add-only-baseline-loc` VALUE) is the
DISCRIMINATOR that activates the coa-leg — it fires ONLY when the mode flag is present, so a
plain `--with-metrics` run (slice-04) is never routed through the coa indeterminate/reject
path. When the coa mode is active the JSON `metrics` object ALSO carries:

  * `consolidate_on_add_gain_loc` — the net test-LOC of the consolidating run MINUS the
    declared add-only baseline (≤ 0 ⇒ the add-AND-improve actually bent the curve);
  * a closed `consolidate_on_add` verdict the gate emits when a run DECLARES
    consolidate-on-add (CONSOLIDATE/REUSE) but its net test-LOC is NOT below the add-only
    baseline — the add-only-masquerade the counter-gradient must unmask.

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists):

  * `Verdict` — the top-level closed `--require-sustainability --with-metrics` verdict-token
    set, WIDENED with `consolidate-on-add-not-realized` — the verdict the gate emits when a
    declared add-AND-improve run does NOT beat the add-only baseline (the masquerade).
  * `ConsolidateOnAddVerdict` — the closed cross-check verdict the consolidate-on-add leg
    reports (realized / not-realized / INDETERMINATE-when-baseline-absent).

The schema constants (canonical heading, 5 columns, decision tokens) are REUSED from
slice_02_domain_types (single-home, Mandate-12 / DDD-2C — reuse composition lives in code,
not re-declaration). slice-02 fixed them as the SCHEMA; slice-07 builds consolidate-on-add
sections against the SAME shape. They are test-arrangement vocabulary, legitimately
test-local (promotion-rule clause (c)).
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-02 schema SSOT (single-home, Mandate-12 / DDD-2C): the canonical heading
# + the 5 fixed columns + the closed decision-token set are fixed ONCE by slice-02; slice-07
# arranges consolidate-on-add sections against the SAME shape — authored reuse, not a
# re-declared schema.
from .slice_02_domain_types import (
    CANONICAL_DECISION_TOKENS,
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    CANONICAL_SECTION_ID,
)


class Verdict(str, Enum):
    """The closed top-level `--require-sustainability --with-metrics` verdict tokens.

    SSOT (DELIVER lands these): `src/des/cli/validate_feature_delta.py`. slice-07 WIDENS the
    slice-04 set with `consolidate-on-add-not-realized` — the verdict the gate emits when a
    section DECLARES consolidate-on-add (CONSOLIDATE/REUSE) but the run's net test-LOC is NOT
    below the declared add-only baseline (the add-only masquerade the counter-gradient must
    unmask). The slice-04 tokens are carried forward (the gate is one closed classifier).

    DESIGN closed token set (component-manifest `typed-error-set`, port
    `des validate-feature-delta --require-sustainability`):
      structurally-accepted · missing-sustainability-section ·
      malformed-sustainability-section · unjustified-create-new ·
      blind-add-detected · consolidate-on-add-not-realized · no-new-tests · methodology-exempt
    """

    STRUCTURALLY_ACCEPTED = "structurally-accepted"
    MISSING_SUSTAINABILITY_SECTION = "missing-sustainability-section"
    MALFORMED_SUSTAINABILITY_SECTION = "malformed-sustainability-section"
    UNJUSTIFIED_CREATE_NEW = "unjustified-create-new"
    BLIND_ADD_DETECTED = "blind-add-detected"
    CONSOLIDATE_ON_ADD_NOT_REALIZED = "consolidate-on-add-not-realized"
    NO_NEW_TESTS = "no-new-tests"
    METHODOLOGY_EXEMPT = "methodology-exempt"


class ConsolidateOnAddVerdict(str, Enum):
    """The closed cross-check verdict the consolidate-on-add (add-AND-improve) leg reports.

    SSOT (DELIVER lands these): the consolidate-on-add calc in
    `src/des/domain/sustainability_metrics.py` (a pure function over the run's net test-LOC
    delta + the declared add-only baseline). The leg compares the consolidating run's net
    test-LOC against the add-only baseline for the same added scope:

      * `realized`       — the consolidating run's net test-LOC is BELOW the add-only baseline
                           (`consolidate_on_add_gain_loc` ≤ 0); the add-AND-improve actually
                           bent the curve relative to pure-add;
      * `not-realized`   — the section DECLARES consolidate-on-add but the run's net test-LOC
                           is NOT below the add-only baseline (gain > 0); the add-AND-improve
                           claim is unmasked as an add-only masquerade; drives the top-level
                           `consolidate-on-add-not-realized` verdict;
      * `indeterminate`  — no add-only baseline was supplied, so the gain cannot be computed.
                           DDD-4 / DDD-10: degrade LOUD, exit non-zero, NEVER a fabricated
                           pass — the baseline is the denominator, an absent denominator is
                           never a silent green.
    """

    REALIZED = "realized"
    NOT_REALIZED = "not-realized"
    INDETERMINATE = "indeterminate"


__all__ = [
    "CANONICAL_DECISION_TOKENS",
    "CANONICAL_SECTION_COLUMNS",
    "CANONICAL_SECTION_HEADING",
    "CANONICAL_SECTION_ID",
    "ConsolidateOnAddVerdict",
    "Verdict",
]
