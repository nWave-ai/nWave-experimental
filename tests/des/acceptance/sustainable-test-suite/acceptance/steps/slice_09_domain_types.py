"""Typed vocabulary for slice-09 ATs — EXISTING-BASE CONTINUOUS REDUCTION (Mandate-12).

slice-09 of sustainable-test-suite is the EXISTING-BASE continuous-reduction slice
(DDD-16C + DDD-17C, the ACTIVE counter-gradient). The shipped A+C metrics + the slice-07
consolidate-on-add gain measure reuse at the ADD boundary — they are PASSIVE w.r.t. the
thousands of pre-existing near-duplicate steps. slice-09 closes that: each `/nw-distill`
run measurably REDUCES the EXISTING base's near-duplicate-step duplication, the gate
REPORTS the existing-base near-duplicate-step ratio (AST step-similarity behind the
`CodeFactPort`, git-free) as an EVIDENCE cell, and the trend must NOT regress slice-on-slice
(advisory-LOUD first, gated on a downward trend). So the existing base IMPROVES gradually,
not just stays-lean-on-add.

Driving port (Mandate-13, Layer 3 subprocess): the SHIPPED spine entry
`des validate-feature-delta --require-sustainability --with-metrics --existing-base-trend
[--prior-existing-base-ratio=<float>] --format=json` EXTENDS the slice-04 metrics mode. The
`--existing-base-trend` MODE flag (DISTINCT from the `--prior-existing-base-ratio` VALUE) is
the DISCRIMINATOR that activates the existing-base leg — it fires ONLY when the mode flag is
present, so a plain `--with-metrics` run (slice-04) and a `--consolidate-on-add` run
(slice-07) are never routed through the existing-base trend path. When the existing-base
mode is active the JSON `metrics` object ALSO carries:

  * `existing_base_duplication_ratio` — the near-duplicate-step ratio over the EXISTING test
    base (near-duplicate step groups / total step definitions), a real number in [0.0, 1.0]
    computed over an AST step-shape corpus the CodeFactPort supplies;

and the gate emits a closed `existing_base_trend` cross-check object whose verdict compares
the current run's ratio against the prior committed value (read git-free from the prior
feature-delta section, supplied as the `--prior-existing-base-ratio` VALUE):

  * `improved`       — the current ratio is STRICTLY BELOW the prior committed ratio (the
                       existing base improved this run); accepted on trend, exit 0;
  * `regressed`      — the current ratio is ABOVE the prior committed ratio (the existing
                       base got WORSE); the trend break is gated (rejected), exit non-zero,
                       top verdict `existing-base-duplication-regressed`;
  * `indeterminate`  — the AST step-shape corpus is unavailable (CodeFactPort degrades to a
                       below-AST tier / no step-shape fact), so the ratio cannot be computed.
                       DDD-17C degrade-LOUD: exit non-zero, NEVER a fabricated `0.0` ratio and
                       NEVER a fabricated downward trend.

This module owns the TEST-SIDE typed vocabulary the step bodies coerce Gherkin literals
into (no raw `str` where an enum exists):

  * `Verdict` — the top-level closed `--require-sustainability --with-metrics` verdict-token
    set, WIDENED with `existing-base-duplication-regressed` — the verdict the gate emits when
    the existing-base ratio REGRESSES against the prior committed value.
  * `ExistingBaseTrendVerdict` — the closed cross-check verdict the existing-base trend leg
    reports (improved / regressed / INDETERMINATE-when-corpus-absent).

The schema constants (canonical heading, 5 columns, decision tokens) are REUSED from
slice_02_domain_types (single-home, Mandate-12 / DDD-2C — reuse composition lives in code,
not re-declaration). They are test-arrangement vocabulary, legitimately test-local
(promotion-rule clause (c)).
"""

from __future__ import annotations

from enum import Enum

# Reuse the slice-02 schema SSOT (single-home, Mandate-12 / DDD-2C): the canonical heading
# + the 5 fixed columns + the closed decision-token set are fixed ONCE by slice-02; slice-09
# arranges sustainability sections against the SAME shape — authored reuse, not a re-declared
# schema.
from .slice_02_domain_types import (
    CANONICAL_DECISION_TOKENS,
    CANONICAL_SECTION_COLUMNS,
    CANONICAL_SECTION_HEADING,
    CANONICAL_SECTION_ID,
)


class Verdict(str, Enum):
    """The closed top-level `--require-sustainability --with-metrics` verdict tokens.

    SSOT (DELIVER lands these): `src/des/cli/validate_feature_delta.py`. slice-09 WIDENS the
    slice-04/07 set with `existing-base-duplication-regressed` — the verdict the gate emits
    when the existing-base near-duplicate-step ratio REGRESSES (rises) against the prior
    committed value under the `--existing-base-trend` mode. The slice-04/07 tokens are carried
    forward (the gate is one closed classifier).
    """

    STRUCTURALLY_ACCEPTED = "structurally-accepted"
    MISSING_SUSTAINABILITY_SECTION = "missing-sustainability-section"
    MALFORMED_SUSTAINABILITY_SECTION = "malformed-sustainability-section"
    UNJUSTIFIED_CREATE_NEW = "unjustified-create-new"
    BLIND_ADD_DETECTED = "blind-add-detected"
    CONSOLIDATE_ON_ADD_NOT_REALIZED = "consolidate-on-add-not-realized"
    EXISTING_BASE_DUPLICATION_REGRESSED = "existing-base-duplication-regressed"
    NO_NEW_TESTS = "no-new-tests"
    METHODOLOGY_EXEMPT = "methodology-exempt"


class ExistingBaseTrendVerdict(str, Enum):
    """The closed cross-check verdict the existing-base trend leg reports.

    SSOT (DELIVER lands these): the existing-base trend classification in
    `src/des/cli/validate_feature_delta.py`, over the pure
    `existing_base_duplication_ratio` (`src/des/domain/sustainability_metrics.py`) +
    the prior committed ratio:

      * `improved`       — the current run's existing-base near-duplicate-step ratio is
                           STRICTLY BELOW the prior committed ratio; the existing base improved
                           this run (the active counter-gradient bent the existing-base curve);
      * `regressed`      — the current ratio is ABOVE the prior committed ratio; the existing
                           base got WORSE; the trend break is gated (the DDD-16C downward-trend
                           gate); drives the top-level `existing-base-duplication-regressed`;
      * `indeterminate`  — the AST step-shape corpus is unavailable (the CodeFactPort returns
                           no step-shape fact / degrades below the AST tier), so the ratio
                           cannot be computed. DDD-17C degrade-LOUD: exit non-zero, NEVER a
                           fabricated `0.0` ratio and NEVER a fabricated downward trend.
    """

    IMPROVED = "improved"
    REGRESSED = "regressed"
    INDETERMINATE = "indeterminate"


__all__ = [
    "CANONICAL_DECISION_TOKENS",
    "CANONICAL_SECTION_COLUMNS",
    "CANONICAL_SECTION_HEADING",
    "CANONICAL_SECTION_ID",
    "ExistingBaseTrendVerdict",
    "Verdict",
]
