"""Typed vocabulary for slice-02 ATs — the sustainability SECTION SCHEMA (Mandate-12).

slice-02 of sustainable-test-suite is the SECTION SCHEMA (DDD-3) + its output-contract
registration (DDD-11). The driving port is the SHIPPED spine subprocess
`des validate-feature-delta --require-registry-sections distill --format=json`; the
observable is a closed verdict token + exit code.

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists), plus the CANONICAL SCHEMA CONSTANTS that ARE
the section schema (DDD-3, the mirror of `## Reuse Analysis`):

  * the canonical H2 heading `## Test Reuse & Consolidation Analysis`,
  * the canonical [REF] section id (its registry/output-contract identity),
  * the 5 fixed-order columns,
  * the closed decision-token set REUSE/EXTEND/CONSOLIDATE/CREATE_NEW.

These are test-arrangement vocabulary, legitimately test-local (Mandate-12 promotion-rule
clause (c) — feature-local schema specifics stay local). They are the SCHEMA the slice-02
section author must produce; the slice-03 gate (NOT authored here) will validate the rows
mechanically against this same shape.
"""

from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    """The closed registry-section verdict tokens the driving port emits.

    SSOT: `src/des/cli/validate_feature_delta.py` (`VERDICT_REGISTRY_SECTIONS_ACCEPTED`
    / `VERDICT_UNDECLARED_SECTION`). The AT reads the structured `verdict` token from
    the `--format=json` payload — an off-set token would prove the classifier drifted.
    """

    ACCEPTED = "accepted"
    UNDECLARED_SECTION = "undeclared-section"


#: The canonical [REF] section ID — the section's identity in the DISTILL
#: output-contract registry (DDD-11) AND the `[REF]` heading tail the carried-section
#: scanner extracts. This exact string must be what `distill.yaml`
#: output_contract.ref_sections declares (DELIVER adds it) and what the feature-delta
#: heading `## Wave: DISTILL / [REF] <this>` carries. The schema is this exact id.
CANONICAL_SECTION_ID = "Test Reuse & Consolidation Analysis"

#: The canonical bare H2 heading (the mirror of `## Reuse Analysis`, DDD-3). The
#: section-author writes this exact heading; the slice-03 content gate (NOT here) will
#: parse the table under it.
CANONICAL_SECTION_HEADING = "## Test Reuse & Consolidation Analysis"

#: The 5 fixed-order columns of the section table (DDD-3, mirror of REUSE_ANALYSIS_COLUMNS).
CANONICAL_SECTION_COLUMNS: tuple[str, ...] = (
    "Existing Test/DSL-Step",
    "File",
    "Overlap",
    "Decision",
    "Justification",
)

#: The closed decision-token set a section row may carry (DDD-3, #3). Mirror of the
#: Reuse Analysis EXTEND/CREATE_NEW set, widened with REUSE/CONSOLIDATE for the
#: sustainability section. The slice-03 gate validates rows against this set; slice-02
#: only fixes the schema constant.
CANONICAL_DECISION_TOKENS: frozenset[str] = frozenset(
    {"REUSE", "EXTEND", "CONSOLIDATE", "CREATE_NEW"}
)


__all__ = [
    "CANONICAL_DECISION_TOKENS",
    "CANONICAL_SECTION_COLUMNS",
    "CANONICAL_SECTION_HEADING",
    "CANONICAL_SECTION_ID",
    "Verdict",
]
