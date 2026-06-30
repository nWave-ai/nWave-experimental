"""Typed domain vocabulary for skill-normative-content-gate ATs (Mandate-12 c1).

Every domain noun the Gherkin uses is expressed once here as an enum / typed
constant. The composition root consumes these typed parameters (Mandate-12 c2 —
no raw `str` where an enum exists); step bodies pass them through (c3).

Real-Surface Binding (AC-08): the markers, clause ids, and skill names below are
the BYTE-EXACT anchors verified present in the real shipped skill files
(`nw-test-design-mandates/SKILL.md:419`, `nw-at-completeness-check/SKILL.md:86`,
`nw-distill/SKILL.md:657`) — DESIGN §6 seed manifest. The ATs read those real
files, never a fabricated string.
"""

from __future__ import annotations

from enum import Enum


class Verdict(str, Enum):
    """The closed three-valued gate verdict (DD-D4); exit codes reuse GateOutcome."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# Exit-code contract (DESIGN §6 — reuse gate_outcome._EXIT_BY_VERDICT).
EXIT_BY_VERDICT: dict[Verdict, int] = {
    Verdict.PASS: 0,
    Verdict.FAIL: 1,
    Verdict.INDETERMINATE: 4,
}


class ProtectedSkill(str, Enum):
    """A skill name the seed manifest protects (resolves to nWave/skills/<v>/SKILL.md)."""

    TEST_DESIGN_MANDATES = "nw-test-design-mandates-composition-contract"
    AT_COMPLETENESS_CHECK = "nw-at-completeness-check"
    DISTILL = "nw-distill"


class ClauseId(str, Enum):
    """A stable clause id named in the FAIL verdict (AC-01)."""

    PROTOCOL_DRIVER = "protocol-driver:assert-shipped-artifact"
    ZERO_OBLIGATION = "zero-obligation:override"
    WALKING_SKELETON = "walking-skeleton:canonical-definition"


# The real, byte-exact discriminating markers (DESIGN §6, grep-verified present).
MARKER_BY_CLAUSE: dict[ClauseId, str] = {
    ClauseId.PROTOCOL_DRIVER: "artifact the SUT actually shipped",
    ClauseId.ZERO_OBLIGATION: (
        "Absence of an explicit Zero scenario for any iterative surface"
    ),
    ClauseId.WALKING_SKELETON: (
        "thinnest slice of real functionality that runs end-to-end"
    ),
}

# Each clause's owning skill (the seed manifest topology).
SKILL_BY_CLAUSE: dict[ClauseId, ProtectedSkill] = {
    ClauseId.PROTOCOL_DRIVER: ProtectedSkill.TEST_DESIGN_MANDATES,
    ClauseId.ZERO_OBLIGATION: ProtectedSkill.AT_COMPLETENESS_CHECK,
    ClauseId.WALKING_SKELETON: ProtectedSkill.DISTILL,
}


class MarkerShape(str, Enum):
    """Discrimination edge-case shapes (OQ-3 / ADR-SNCG-004 pinned table)."""

    BARE_COMMON_TOKEN = "table"  # 1 token — the empirical defect class
    SHORT_MULTI_WORD = "zero is an obligation"  # 3 tokens, short — accepted (AC-09)


class AssetFault(str, Enum):
    """The two reads-and-catches faults the reader must survive (AC-06, AC-10)."""

    ABSENT = "absent"  # path does not resolve → ManifestAssetAbsent
    UNDECODABLE = "undecodable"  # exists but not UTF-8 → ManifestAssetUndecodable
