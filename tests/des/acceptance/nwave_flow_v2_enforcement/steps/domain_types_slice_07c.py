"""Typed domain vocabulary for the nwave-flow-v2-enforcement slice-07c ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the slice-07c
Gherkin names is expressed once here as a typed enum, so the composition methods
consume typed parameters (no raw ``str`` where an enum exists) and the DSL
emerges from the type system rather than from decorator proliferation.

These types are TEST-LOCAL -- the ATs drive the SUT through the composition-root
driving ports (Mandate-13). ``GateDecision`` mirrors the observable allow/block
surface but is re-declared here so the slice-07c step modules stay
self-contained (each slice owns its vocabulary, per the slice-04/07/07b
precedent).
"""

from __future__ import annotations

from enum import Enum


class EntryPreconditions(Enum):
    """The product-SSOT precondition state the discuss entry gate reads.

    MET   -> ``docs/product/`` with the four required SSOT docs present.
    UNMET -> ``docs/product/`` absent entirely (the migration-gate unmet --
             the coarsest unmet shape the entry gate must veto).
    """

    MET = "met"
    UNMET = "unmet"


class GateDecision(Enum):
    """The observable hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"


class ReviewVerdictFlaw(Enum):
    """The closed set of unverifiable PO-review verdict shapes (07b routed gap).

    Each value is one ledger/artefact state under which the shipped
    ``DiscussReviewGate.evaluate`` pure core must degrade LOUD to
    INDETERMINATE -- never PASS, never VETOED (§17 / §22.7). The enum values
    are the Gherkin example-row literals.

    Post-demotion (oss-review-verdict-demotion S3): KEY_ABSENT is REMOVED --
    no signing key exists post-demotion, so key-absence is a non-event and
    cannot be a flaw. Three keyless flaws remain.
    """

    STALE_ARTEFACT = "stale-artefact"
    """A verdict that judged a DIFFERENT feature-delta content
    (hash drift -- the §21.2 seal idiom)."""

    SCHEMA_UNKNOWN = "schema-unknown"
    """A record whose schema_version this verifier does not know
    (§21.2.3: never confidently mis-parsed)."""

    UNKNOWN_VERDICT_LITERAL = "unknown-verdict-literal"
    """An artefact-current record whose verdict literal is outside
    the closed DiscussReviewToken set -- not a readable reviewer decision."""
