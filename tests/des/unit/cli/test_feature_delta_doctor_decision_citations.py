# @node-d76
"""`des feature-delta-doctor` reports a dangling `per <ID>` decision citation
as a gap -- the residue D33's closure note declared and left for its own
node: "solo il caso ADR-refs e' presidiato" (only the ADR-refs case is
guarded). This wires `feature_delta_source.resolve_decision_citations` into
`diagnose()`'s existing repo_root-gated leg, alongside `_dangling_adr_ref_gaps`
(same gate, same file, same wiring shape -- D33's mechanism, extended).

covers: D76 (docs/mikado/EXECUTION-SSOT-des-optimization.md)
"""

from __future__ import annotations

from pathlib import Path

from des.cli.feature_delta_doctor import diagnose


def test_dangling_decision_citation_is_reported_as_a_gap(tmp_path: Path) -> None:
    content = (
        "## Wave: DESIGN / [REF] Decisions\n\n"
        "| ID | Decision | Rationale |\n"
        "|---|---|---|\n"
        "| DD-1 | Some locked decision. | Some rationale. |\n\n"
        "## Wave: DESIGN / [REF] Reuse Analysis\n\n"
        "This row's shape follows the sibling section per DD-9, which no "
        "row in this document declares.\n"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    gap_ids = [g["id"] for g in gaps]
    assert "dangling-decision-citation" in gap_ids
    dangling = next(g for g in gaps if g["id"] == "dangling-decision-citation")
    assert "DD-9" in dangling["what"]


def test_locally_declared_citation_is_not_a_gap(tmp_path: Path) -> None:
    content = (
        "## Wave: DESIGN / [REF] Decisions\n\n"
        "| DD-1 | Some locked decision. | Some rationale. |\n\n"
        "Every other section that touches this decision cites it per DD-1.\n"
    )
    gaps = diagnose(content, repo_root=tmp_path)
    assert "dangling-decision-citation" not in [g["id"] for g in gaps]


def test_cross_document_declaration_is_still_a_gap(tmp_path: Path) -> None:
    """The sharper case named by the dispatch brief: an id declared in a
    DIFFERENT feature-delta must not be silently accepted as resolving a
    citation in THIS one."""
    other = tmp_path / "docs" / "feature" / "other-feature" / "feature-delta.md"
    other.parent.mkdir(parents=True)
    other.write_text("| DD-9 | Declared over there. | rationale |\n")

    content = "This behavior mirrors the sibling per DD-9.\n"
    gaps = diagnose(content, repo_root=tmp_path)
    assert "dangling-decision-citation" in [g["id"] for g in gaps]


def test_no_repo_root_skips_the_decision_citation_leg_entirely(tmp_path: Path) -> None:
    """Mirrors `_dangling_adr_ref_gaps`'s own contract: with no repo_root,
    this doctor has no tree to check the AD-N external registry against, so
    it stays silent on that leg rather than guessing -- but local-only
    resolution still needs no tree, so this only characterizes the
    no-repo_root-at-all call shape used by callers that predate D76."""
    content = "Per DD-9, cited with no repo_root supplied at all.\n"
    gaps = diagnose(content, repo_root=None)
    assert "dangling-decision-citation" not in [g["id"] for g in gaps]


def test_ad_citation_could_not_verify_is_a_distinct_gap(tmp_path: Path) -> None:
    content = "The gate logic must stay git-free, per AD-21.\n"
    gaps = diagnose(content, repo_root=tmp_path)
    assert "decision-citation-could-not-verify" in [g["id"] for g in gaps]


def test_ad_citation_resolves_against_arch_tech_debt(tmp_path: Path) -> None:
    (tmp_path / "ARCH_TECH_DEBT.md").write_text(
        "| **AD-21** | Gates/waves depend on git. | drift | high |\n"
    )
    content = "The gate logic must stay git-free, per AD-21.\n"
    gaps = diagnose(content, repo_root=tmp_path)
    gap_ids = [g["id"] for g in gaps]
    assert "dangling-decision-citation" not in gap_ids
    assert "decision-citation-could-not-verify" not in gap_ids


def test_adr_family_citation_is_not_double_checked_here(tmp_path: Path) -> None:
    """ADR-N citations are D33's own family (`_dangling_adr_ref_gaps`) --
    this leg must never re-flag them a second, differently-shaped way."""
    content = "This decision is promoted per ADR-999, a nonexistent ADR.\n"
    gaps = diagnose(content, repo_root=tmp_path)
    assert "dangling-decision-citation" not in [g["id"] for g in gaps]
