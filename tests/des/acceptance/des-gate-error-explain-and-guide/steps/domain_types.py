"""Domain types for the des-gate-error-explain-and-guide slice-01 ATs.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw `str` where a domain enum exists.

Bounded context: the `FeatureScopeMalformed` refusal emitted by
`des run-contract-gate --feature-id` when the feature's scope is unusable.

The enrichment (slice-01) adds three fields to the existing JSON payload:
  - `what`  -- which check refused (domain name for the scoping check)
  - `why`   -- the specific reason, expanded (human-readable cause clause)
  - `next`  -- the concrete CLI command or file fix to remediate the refusal

The existing five fields (`event`, `cause`, `feature_id`, `reason`, `error`)
and the exit code (2) are UNCHANGED (D-1 additive-output-only invariant).

REASON TOKEN SET (complete, from DESIGN [REF] §1):
  ZERO_COLLECTED      -- no .feature file carries the @feature-<id> tag; the
                         scoped gate would pass vacuously
  EMPTY_INTERSECTION  -- feature .feature files found but none carries
                         @<entering_slice>; the scoped gate would pass vacuously
  COLLECTION_FAILED   -- pytest collection raised _CollectionError
  ARCH_INVARIANT_FAILED -- arch-tier collection or run failure
  ARCH_SCOPE_ZERO_COLLECTED -- arch tier present but collected == 0

slice-01 exercises ZERO_COLLECTED (scenario 1+2) and EMPTY_INTERSECTION
(scenario 3). The remaining tokens are deferred to subsequent slices per the
DISCUSS carpaccio ceiling (≤3 ATs / slice-01).
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class MalformedScopeReason(str, Enum):
    """The `reason` token emitted inside a FeatureScopeMalformed event.

    Maps one-to-one onto the five token strings accepted by the
    `_explain_and_guide` mapper (DESIGN [REF] §1 reason token set).

    ZERO_COLLECTED        -- no .feature tagged @feature-<id> in the repo tree
    EMPTY_INTERSECTION    -- feature files found but none tagged @<entering_slice>
    COLLECTION_FAILED     -- pytest collection invocation failed with a
                             _CollectionError (subprocess error)
    ARCH_INVARIANT_FAILED -- architecture-tier run could not be trusted or
                             a run-time arch invariant FAILED
    ARCH_SCOPE_ZERO_COLLECTED -- architecture tier present but collected == 0
    """

    ZERO_COLLECTED = "zero-collected"
    EMPTY_INTERSECTION = "empty-intersection"
    COLLECTION_FAILED = "collection-failed"
    ARCH_INVARIANT_FAILED = "arch-invariant-failed"
    ARCH_SCOPE_ZERO_COLLECTED = "arch-scope-zero-collected"


class ExplainAndGuideField(str, Enum):
    """The three additive JSON fields in the enriched FeatureScopeMalformed event.

    Absent at authorship HEAD (the `_explain_and_guide` mapper does not exist
    yet); present after DELIVER ships the mapper + payload.update() call.

    WHAT  -- names the check that refused (domain-language identifier)
    WHY   -- expands the `reason` token to a human-readable cause clause
    NEXT  -- the concrete CLI command or file-fix to remediate the refusal
    """

    WHAT = "what"
    WHY = "why"
    NEXT = "next"


# Exit code for a malformed feature scope (FeatureScopeMalformed).
# Unchanged by slice-01 (D-1 additive-output-only invariant).
MALFORMED_SCOPE_EXIT = 2

# The canonical event name for a malformed scope refusal.
FEATURE_SCOPE_MALFORMED_EVENT = "FeatureScopeMalformed"

# The canonical cause field value for all malformed-scope refusals.
MALFORMED_SCOPE_CAUSE = "malformed"

# A synthetic feature-id used in slice-01 AT substrates.
FeatureId = NewType("FeatureId", str)

# A synthetic slice tag label (e.g. "slice-01").
SliceTag = NewType("SliceTag", str)
