"""Typed vocabulary for slice-04 ATs — the BALANCED DENOMINATOR (Mandate-12).

slice-04 of sustainable-test-suite is the BALANCED-DENOMINATOR slice (DDD-4 + DDD-5 +
DDD-10): the gate now reports the A+C metrics EVIDENCE cells — A (consolidation-delta,
net test-LOC per slice) + C (generic-framework-adoption-ratio) — AND a blind-add
cross-check computed against the REAL git diff, so the "less" gradient has the same
mechanical force as the completeness "more" gate.

Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --format=json`
EXTENDS the slice-03 content gate so the JSON verdict ALSO carries:

  * a `metrics` evidence object (consolidation-delta net test-LOC + adoption-ratio), and
  * a `blind_add` cross-check verdict computed against the real git diff,

degrading LOUD to an INDETERMINATE cross-check verdict (never a fabricated pass) when
git is unavailable (DDD-4 / DDD-10 git-diff cross-check = unbounded-preservation port).

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists):

  * `Verdict` — the top-level closed `--require-sustainability` verdict-token set the gate
    emits, WIDENED with the git-dependent `blind-add-detected` verdict slice-03 deferred
    here (slice-03 SCOPE block; slice_03_domain_types DELIBERATELY EXCLUDED it).
  * `BlindAddVerdict` — the closed cross-check verdict-token set (consistent / blind-add /
    INDETERMINATE) the git-diff cross-check leg reports.

The schema constants (canonical heading, 5 columns, decision tokens) are REUSED from
slice_02_domain_types (single-home, Mandate-12) — slice-02 fixed them as the SCHEMA;
slice-04 builds metrics-bearing sections against the SAME shape. They are
test-arrangement vocabulary, legitimately test-local (promotion-rule clause (c)).
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-02 schema SSOT (single-home, Mandate-12): the canonical heading + the
# 5 fixed columns + the closed decision-token set are fixed ONCE by slice-02; slice-04
# arranges metrics-bearing sections against the SAME shape.
from .slice_02_domain_types import (
    CANONICAL_DECISION_TOKENS,
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    CANONICAL_SECTION_ID,
)


class Verdict(str, Enum):
    """The closed top-level `--require-sustainability --with-metrics` verdict tokens.

    SSOT (DELIVER lands these): `src/des/cli/validate_feature_delta.py`. slice-04 WIDENS
    the slice-03 set with `blind-add-detected` — the git-dependent cross-check verdict
    slice-03 explicitly DEFERRED here (`slice_03_domain_types` DELIBERATELY EXCLUDED it;
    its `.feature` SCOPE block names slice-04 as the owner).

    DESIGN closed token set (component-manifest `typed-error-set`, port
    `des validate-feature-delta --require-sustainability`):
      structurally-accepted · missing-sustainability-section ·
      malformed-sustainability-section · unjustified-create-new ·
      blind-add-detected · no-new-tests · methodology-exempt
    """

    STRUCTURALLY_ACCEPTED = "structurally-accepted"
    MISSING_SUSTAINABILITY_SECTION = "missing-sustainability-section"
    MALFORMED_SUSTAINABILITY_SECTION = "malformed-sustainability-section"
    UNJUSTIFIED_CREATE_NEW = "unjustified-create-new"
    BLIND_ADD_DETECTED = "blind-add-detected"
    NO_NEW_TESTS = "no-new-tests"
    METHODOLOGY_EXEMPT = "methodology-exempt"


class BlindAddVerdict(str, Enum):
    """The closed cross-check verdict the git-diff blind-add leg reports.

    SSOT (DELIVER lands these): the git-diff cross-check adapter +
    `src/des/domain/sustainability_metrics.py`. The cross-check compares the section's
    declared CONSOLIDATE/REUSE intent against the REAL net added test-LOC from the git
    diff:

      * `consistent`     — the declared intent matches the observed net test-LOC delta;
      * `blind-add`      — the section CLAIMS consolidate/reuse but the diff shows a net
                           test-LOC INCREASE inconsistent with the claim (the claim is
                           unmasked); drives the top-level `blind-add-detected` verdict;
      * `indeterminate`  — the git-diff cross-check could NOT run (git absent / not a repo).
                           DDD-4 / DDD-10: degrade LOUD, exit non-zero, NEVER a fabricated
                           pass. git is NOT a hard dependency.
    """

    CONSISTENT = "consistent"
    BLIND_ADD = "blind-add"
    INDETERMINATE = "indeterminate"


__all__ = [
    "CANONICAL_DECISION_TOKENS",
    "CANONICAL_SECTION_COLUMNS",
    "CANONICAL_SECTION_HEADING",
    "CANONICAL_SECTION_ID",
    "BlindAddVerdict",
    "Verdict",
]
