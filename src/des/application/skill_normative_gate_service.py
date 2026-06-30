"""Application service: orchestrate the skill-normative-content gate.

Feature: skill-normative-content-gate (DESIGN §5, component `SkillNormativeGateService`).
Layer: Application.

Orchestration (DESIGN §5):
  read manifest → for each clause resolve its skill asset via the reader →
  on absent/undecodable asset assemble INDETERMINATE → on non-discriminating
  marker assemble INDETERMINATE (load-time) → else assert each marker present →
  assemble the closed verdict (PASS / FAIL / INDETERMINATE). Owns NO matching
  logic (delegates to the pure domain).

Verdict + exit codes REUSE `GateOutcome`/`GateVerdict` (gate_outcome.py):
  PASS → 0, FAIL → 1, INDETERMINATE → 4 (DESIGN §6).

Status: IMPLEMENTED (DELIVER complete). `evaluate()` runs the full orchestration
above; the corpus-union resolver (`_resolve_assets`) reads the monolith
`<skill>/SKILL.md` plus every `<skill>-*/SKILL.md` sub-skill (monotonic).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.skill_corpus_reader import (
    ManifestAssetAbsent,
    ManifestAssetUndecodable,
)
from des.domain.skill_normative_clause import (
    FailingClause,
    NonDiscriminatingClause,
    NormativeClause,
    NormativeVerdict,
    UnreadableClause,
    clause_present,
    is_discriminating,
)


if TYPE_CHECKING:
    from des.adapters.driven.skill_corpus_reader import SkillCorpusReader


_SKILLS_SUBPATH = ("nWave", "skills")
_SKILL_FILE = "SKILL.md"


class SkillNormativeGateService:
    """Assembles the closed normative-content verdict over the manifest corpus."""

    def __init__(self, reader: SkillCorpusReader, root: Path) -> None:
        self._reader = reader
        self._root = root

    def evaluate(self, manifest_path: Path) -> NormativeVerdict:
        """Read the corpus and assemble the closed PASS/FAIL/INDETERMINATE verdict."""
        clauses = self._load_clauses(manifest_path)
        non_discriminating = self._non_discriminating(clauses)
        if non_discriminating:
            return NormativeVerdict.indeterminate_for(non_discriminating)
        unreadable, failing = self._check_assets(clauses)
        if unreadable:
            return NormativeVerdict.indeterminate_for(unreadable)
        return NormativeVerdict.over(
            tuple(FailingClause(skill=c.skill, clause_id=c.clause_id) for c in failing)
        )

    def _check_assets(
        self, clauses: tuple[NormativeClause, ...]
    ) -> tuple[tuple[UnreadableClause, ...], tuple[NormativeClause, ...]]:
        """Resolve every clause's asset; loud-absence wins over PASS/FAIL.

        Returns (unreadable findings, clauses whose marker is absent). An asset the
        reader cannot read names the skill+clause+asset+failure (AC-06, AC-10) — the
        gate refuses to certify what it cannot read.
        """
        unreadable: list[UnreadableClause] = []
        failing: list[NormativeClause] = []
        for clause in clauses:
            finding = self._read_clause_asset(clause)
            if isinstance(finding, UnreadableClause):
                unreadable.append(finding)
                continue
            if not finding:
                failing.append(clause)
        return tuple(unreadable), tuple(failing)

    def _read_clause_asset(self, clause: NormativeClause) -> UnreadableClause | bool:
        """Read the clause's asset corpus; map a typed read failure to UnreadableClause.

        A clause names a skill; after a monolith->lean decomposition the marked
        content may live in the skill's monolith `SKILL.md` OR any of its
        `<skill>-*` sub-skills. The marker is PRESENT if found in ANY readable
        asset of the corpus (union); the gate refuses to certify (INDETERMINATE)
        only when NO asset of the corpus is readable. An undecodable member is
        recorded but never vetoes a marker found elsewhere -- the resolution is
        monotonic: it cannot newly-FAIL a clause that passed against the monolith,
        only turn a FAIL into PASS where content legitimately moved to a sub-skill.
        """
        texts: list[str] = []
        unreadable: tuple[Path, str] | None = None
        for asset in self._resolve_assets(clause):
            try:
                texts.append(self._reader.read_asset(asset))
            except ManifestAssetAbsent:
                unreadable = unreadable or (asset, "not found")
            except ManifestAssetUndecodable:
                unreadable = (asset, "could not be read as UTF-8 text")
        if not texts:
            asset, failure = unreadable or (
                self._resolve_assets(clause)[0],
                "not found",
            )
            return self._unreadable(clause, asset, failure)
        return any(clause_present(clause.marker, text) for text in texts)

    @staticmethod
    def _unreadable(
        clause: NormativeClause, asset: Path, failure: str
    ) -> UnreadableClause:
        return UnreadableClause(
            skill=clause.skill,
            clause_id=clause.clause_id,
            asset=str(asset),
            failure=failure,
        )

    def _non_discriminating(
        self, clauses: tuple[NormativeClause, ...]
    ) -> tuple[NonDiscriminatingClause, ...]:
        """Reject non-discriminating markers at load time, before any asset read."""
        return tuple(
            NonDiscriminatingClause(
                skill=c.skill, clause_id=c.clause_id, marker=c.marker
            )
            for c in clauses
            if not is_discriminating(c.marker)
        )

    def _load_clauses(self, manifest_path: Path) -> tuple[NormativeClause, ...]:
        manifest = self._reader.read_manifest(manifest_path)
        return tuple(
            NormativeClause(
                skill=entry["skill"],
                clause_id=entry["clause_id"],
                marker=entry["marker"],
                asset=entry.get("asset"),
            )
            for entry in manifest["clauses"]
        )

    def _resolve_assets(self, clause: NormativeClause) -> tuple[Path, ...]:
        """Resolve a clause to its skill-asset corpus.

        An explicit `clause.asset` override resolves to that single file (the
        intent is a specific file, not a corpus). Otherwise the corpus is the
        skill's monolith `<skill>/SKILL.md` plus every `<skill>-*/SKILL.md`
        sub-skill produced by a monolith->lean decomposition. Ordering is
        deterministic: monolith first, then sub-skills sorted by path.
        """
        if clause.asset is not None:
            return (Path(clause.asset),)
        skills_root = self._root.joinpath(*_SKILLS_SUBPATH)
        monolith = skills_root.joinpath(clause.skill, _SKILL_FILE)
        sub_skills = sorted(skills_root.glob(f"{clause.skill}-*/{_SKILL_FILE}"))
        return (monolith, *sub_skills)
