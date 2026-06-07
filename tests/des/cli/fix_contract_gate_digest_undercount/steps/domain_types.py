"""Typed domain vocabulary for the contract-gate digest-undercount ATs (Mandate-12).

One enum per domain noun used in the Gherkin; no raw strings in step signatures.

Domain nouns:
  - ``SuiteShape``     -- the shape of the test tree the gate fingerprints (slice-01).
  - ``Coverage``       -- whether the digest fingerprints the FULL canonical
    collected scope or only a collapsed PROPER SUBSET (slice-01).
  - ``ScopeIntegrity`` -- whether a tree's collected scope is honest or
    suppressed-after-collection (the lying tree) (slice-02).
  - ``GateVerdict``    -- the observable exit-gate outcome: a trustworthy
    verdict, or a fail-closed refusal (slice-02).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SuiteShape(Enum):
    """The shape of the test tree the contract gate is asked to fingerprint."""

    # The live nwave-dev contract suite -- the real-repo parity probe shape.
    CANONICAL_LIVE = "canonical-live"
    # A tmp project carrying a class-grouped file whose methods share a class
    # docstring -- the empirically-smallest collapse pattern.
    COLLAPSE_PRONE = "collapse-prone"


class Coverage(Enum):
    """Whether the digest fingerprints the full collected scope or a subset."""

    # The digest input fingerprints EVERY canonical collected identity.
    FULL_CANONICAL = "full-canonical"
    # The digest input collapsed to a proper subset (the undercount defect).
    COLLAPSED_SUBSET = "collapsed-subset"


class ScopeIntegrity(Enum):
    """Whether a tree's collected scope is honest or suppressed after collection.

    SUPPRESSED -- the lying tree: a populated suite is collected, then a
    ``tryfirst pytest_collection_finish`` hook empties ``session.items`` so the
    per-test identities are dropped before the scope is fingerprinted (the
    sibling atdd_pure_spine_dogfood_defects tamper mechanism, verbatim).
    HONEST     -- a normal tree with no collection tamper.
    """

    HONEST = "honest"
    SUPPRESSED = "suppressed"


class GateVerdict(Enum):
    """The observable outcome of the exit-gate ``--verify-gate-scope`` path.

    FAILED_CLOSED -- the gate refused to produce a verdict because the
    collected scope could not be trusted (CLI exit 2, malformed-input).
    PRODUCED      -- the gate produced a trustworthy verdict (CLI exit 0 or 1:
    a digest was verified, mismatched, or the trailer was absent -- the gate
    reached a conclusion rather than failing closed on an untrustworthy scope).
    """

    FAILED_CLOSED = "failed-closed"
    PRODUCED = "produced"


@dataclass(frozen=True)
class GateOutcome:
    """The exit-gate observable: a typed verdict plus the raw CLI evidence."""

    verdict: GateVerdict
    exit_code: int
    stdout: str
    stderr: str
