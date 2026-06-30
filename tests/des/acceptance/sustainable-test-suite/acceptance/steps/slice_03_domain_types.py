"""Typed vocabulary for slice-03 ATs — the sustainability CONTENT GATE (Mandate-12).

slice-03 of sustainable-test-suite is the MECHANICAL CONTENT VALIDATION gate (DDD-2):
`des validate-feature-delta --require-sustainability --format=json` validates the
`## Test Reuse & Consolidation Analysis` section's ROWS (structure + decision token +
justification + DDD-9 exemptions) git-free, mirroring the shipped Reuse Analysis
validator. The driving port is the SHIPPED spine subprocess; the observable is a closed
verdict token + exit code.

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists):

  * `Verdict` — the closed `--require-sustainability` verdict-token set the gate emits.

The schema constants (canonical heading, 5 fixed columns, decision tokens) are REUSED
from slice_02_domain_types — slice-02 fixed them as the SCHEMA; slice-03 validates rows
against the SAME shape (single-home, Mandate-12). They are test-arrangement vocabulary,
legitimately test-local (promotion-rule clause (c)).

SCOPE (HARD): the `blind-add-detected` verdict is NOT in this slice-03 enum. It requires
the git-diff cross-check (declared CONSOLIDATE/REUSE vs the real added test-LOC) + the
A+C metrics calculator — a SEPARATE driven port that degrades-LOUD INDETERMINATE when git
is absent (DESIGN line 511, component-manifest `git-diff cross-check` port). It belongs to
slice-04/05 and is correctly ABSENT here; slice-03 is git-free section-content only.
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-02 schema SSOT (single-home, Mandate-12): the canonical heading + the
# 5 fixed columns + the closed decision-token set are fixed ONCE by slice-02 and the
# slice-03 gate validates rows against the SAME shape.
from .slice_02_domain_types import (
    CANONICAL_DECISION_TOKENS,
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    CANONICAL_SECTION_ID,
)


class Verdict(str, Enum):
    """The closed `--require-sustainability` verdict tokens the content gate emits.

    SSOT (DELIVER lands these): `src/des/cli/validate_feature_delta.py`, mirroring the
    shipped Reuse Analysis closed set (`VERDICT_STRUCTURALLY_ACCEPTED`,
    `VERDICT_MISSING_*`, `VERDICT_MALFORMED_*`, `VERDICT_UNJUSTIFIED_CREATE_NEW`, the
    DDD-9 exemptions). The AT reads the structured `verdict` token from the
    `--format=json` payload — an off-set token would prove the classifier drifted.

    DESIGN closed token set (line 508-512), git-free subset only:
      structurally-accepted · missing-sustainability-section ·
      malformed-sustainability-section · unjustified-create-new ·
      methodology-exempt · no-new-tests

    `blind-add-detected` is DELIBERATELY EXCLUDED — it is the git-dependent cross-check
    leg (slice-04/05), not section-content (slice-03).
    """

    STRUCTURALLY_ACCEPTED = "structurally-accepted"
    MISSING_SUSTAINABILITY_SECTION = "missing-sustainability-section"
    MALFORMED_SUSTAINABILITY_SECTION = "malformed-sustainability-section"
    UNJUSTIFIED_CREATE_NEW = "unjustified-create-new"
    METHODOLOGY_EXEMPT = "methodology-exempt"
    NO_NEW_TESTS = "no-new-tests"


#: The DDD-9 exemption marker the methodology-exempt scenario writes. Mirror of the
#: shipped `Reuse-Analysis: methodology-exempt` marker grammar, keyed to the
#: sustainability section's own marker namespace (`Test-Reuse-Analysis:`).
METHODOLOGY_EXEMPT_MARKER = "Test-Reuse-Analysis: methodology-exempt"


__all__ = [
    "CANONICAL_DECISION_TOKENS",
    "CANONICAL_SECTION_COLUMNS",
    "CANONICAL_SECTION_HEADING",
    "CANONICAL_SECTION_ID",
    "METHODOLOGY_EXEMPT_MARKER",
    "Verdict",
]
