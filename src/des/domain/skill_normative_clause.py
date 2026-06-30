"""Pure domain for the skill-normative-content gate (DISTILL active-RED scaffold).

Feature: skill-normative-content-gate (DESIGN §5, component `skill_normative_clause`).
Layer: Domain (pure) — NO filesystem, NO subprocess.

Responsibilities (DESIGN §5):
  - `normalize_whitespace`  (OQ-4 / ADR-SNCG-003): `" ".join(text.split())`.
  - `is_discriminating`     (OQ-3 / ADR-SNCG-004): `len(normalize_whitespace(m).split()) >= 2`.
  - `clause_present`        (OQ-4 / ADR-SNCG-003): normalized-substring match.
  - verdict assembly into the reused `GateVerdict` (gate_outcome.py).

slice-01 (walking skeleton) implements `normalize_whitespace`, `clause_present`,
and verdict assembly (`NormativeClause`, `FailingClause`, `NormativeVerdict`);
slice-02 implements `is_discriminating` (the discrimination rule).
"""

from __future__ import annotations

from dataclasses import dataclass

from des.domain.gate_outcome import GateVerdict


def normalize_whitespace(text: str) -> str:
    """Collapse every whitespace run to a single space, ends stripped (OQ-4)."""
    return " ".join(text.split())


def is_discriminating(marker: str) -> bool:
    """A marker is discriminating iff it has ≥2 whitespace-separated tokens (OQ-3).

    The boundary is word COUNT + uniqueness, never string length (AC-09 pins a
    short 3-token phrase as accepted). A bare common token (one word) cannot
    discriminate a clause from incidental substring matches and is rejected LOUD.
    """
    return len(normalize_whitespace(marker).split()) >= 2


def clause_present(marker: str, asset_text: str) -> bool:
    """True iff the whitespace-normalized marker is a substring of the asset (OQ-4)."""
    return normalize_whitespace(marker) in normalize_whitespace(asset_text)


@dataclass(frozen=True)
class NormativeClause:
    """One registered clause: a discriminating marker an asset must carry."""

    skill: str
    clause_id: str
    marker: str
    asset: str | None = None


@dataclass(frozen=True)
class FailingClause:
    """A clause whose marker is absent from its resolved asset (→ FAIL)."""

    skill: str
    clause_id: str

    def render(self) -> str:
        """The verdict line naming the failing skill and clause."""
        return f"{self.skill} — {self.clause_id}"


@dataclass(frozen=True)
class NonDiscriminatingClause:
    """A clause whose marker cannot discriminate (single common token → INDETERMINATE)."""

    skill: str
    clause_id: str
    marker: str

    def render(self) -> str:
        """The verdict line naming the offending skill, clause, and marker."""
        return f"{self.skill} — {self.clause_id}: non-discriminating marker {self.marker!r}"


@dataclass(frozen=True)
class UnreadableClause:
    """A clause whose asset is absent or undecodable (loud-absence → INDETERMINATE).

    Names the skill, clause, asset path, and the read failure (AC-06, AC-10) so the
    canon is never silently unprotected when the gate cannot read what it must check.
    """

    skill: str
    clause_id: str
    asset: str
    failure: str

    def render(self) -> str:
        """The verdict line naming the skill, clause, asset, and read failure."""
        return f"{self.skill} — {self.clause_id}: asset {self.asset!r} {self.failure}"


# The renderable findings that resolve to an INDETERMINATE verdict.
IndeterminateClause = NonDiscriminatingClause | UnreadableClause


@dataclass(frozen=True)
class NormativeVerdict:
    """The closed verdict over the corpus (reuses the gate exit-code ladder)."""

    verdict: GateVerdict
    failing: tuple[FailingClause, ...] = ()
    indeterminate: tuple[IndeterminateClause, ...] = ()

    @classmethod
    def over(cls, failing: tuple[FailingClause, ...]) -> NormativeVerdict:
        """PASS when no clause failed, FAIL naming each failing clause."""
        if failing:
            return cls(verdict=GateVerdict.FAIL, failing=failing)
        return cls(verdict=GateVerdict.PASS)

    @classmethod
    def indeterminate_for(
        cls, offending: tuple[IndeterminateClause, ...]
    ) -> NormativeVerdict:
        """INDETERMINATE: refuse to decide, LOUD — naming each offending finding.

        Two refusal causes share this verdict: a non-discriminating marker
        (refused at manifest load, before any asset is read) and an unreadable
        asset (absent / undecodable — loud-absence, AC-06/AC-10). The empty case
        is never an error (zero registered clauses → PASS via `over(())`).
        """
        return cls(verdict=GateVerdict.INDETERMINATE, indeterminate=offending)
