"""Typed domain vocabulary for the feature-delta-section-schema ATs (Mandate-12).

Every Gherkin domain noun is expressed here as a typed enum / dataclass so step
bodies coerce literal tokens to typed values and never carry raw `str` where a
domain enum exists. The composition modules consume these types.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Wave(str, Enum):
    """The eight waves a section's consumed_by set may contain (§S.3, kebab)."""

    DISCOVER = "discover"
    DIVERGE = "diverge"
    DISCUSS = "discuss"
    DESIGN = "design"
    DEVOPS = "devops"
    DISTILL = "distill"
    DELIVER = "deliver"
    REVIEW = "review"


class ConstructorName(str, Enum):
    """The five §S.1 closed-sum constructor names."""

    KEYED_BLOCK = "KeyedBlock"
    TABLE = "Table"
    PROSE = "Prose"
    REF_LIST = "RefList"
    COMPOSITE = "Composite"


class Verdict(str, Enum):
    """The gate-verify (P1) closed verdict tokens (§S.4, fail-closed)."""

    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


class DocFixture(str, Enum):
    """Named feature-delta document shapes the verify ATs arrange on disk."""

    WELL_FORMED = "well-formed"
    BAD_SLICE_PLAN = "bad-slice-plan"  # offending Slice Plan Table → FAIL(named)
    UNREADABLE = "unreadable"  # bytes that cannot decode → INDETERMINATE
    REORDERED_CONTRACT_TESTS = "reordered-contract-tests"
    REORDERED_ARCH_TESTS = "reordered-arch-tests"
    GOOD_CONVERGENCE = "good-convergence"  # valid two-sub-table Composite section


@dataclass(frozen=True)
class CliResult:
    """The observable surface of a `des feature-delta-schema` subprocess call."""

    exit_code: int
    stdout: str
    stderr: str
