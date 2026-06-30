"""Typed domain vocabulary for the nwave-flow-v2-enforcement slice-07b ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-07b
Gherkin names is expressed once here as a typed enum, so the composition methods
consume typed parameters (no raw ``str`` where an enum exists) and the DSL
emerges from the type system rather than from decorator proliferation.

These types are TEST-LOCAL (they never import production code) -- the ATs drive
the SUT only through the composition-root driving port (Mandate-13).
``GateDecision`` mirrors the slices' observable allow/block surface but is
re-declared here so the slice-07b step modules stay self-contained (each slice
owns its vocabulary, per the slice-04 / slice-07 precedent).
"""

from __future__ import annotations

from enum import Enum


class PoReviewVerdictShape(Enum):
    """The state of the recorded product-owner review verdict in the ledger.

    Post-demotion (oss-review-verdict-demotion S3): re-authored keyless. The
    TAMPERED state is RETIRED (no signature to tamper post-demotion). The AT
    arranges one of these ledger states under a tmp ``project_root`` and
    observes only the gate's allow/block decision + reason token (never the
    DiscussReviewGateResult VO directly).
    """

    NEEDS_REVISION = "needs-revision"
    """A keyless, artefact-current NEEDS_REVISION record -> VETOED."""

    APPROVED_CURRENT = "approved-current"
    """A keyless, artefact-current APPROVED record -> PASS."""

    ABSENT = "absent"
    """No DiscussReviewVerdict record in the ledger -> INDETERMINATE."""


class GateDecision(Enum):
    """The observable hook decision surface (allow vs block) for the gate-OUT."""

    ALLOW = "allow"
    BLOCK = "block"
