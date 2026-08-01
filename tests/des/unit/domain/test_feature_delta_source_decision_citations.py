# @node-d76
"""D76 -- an internal `per DD-N`-shaped decision citation resolves to a
declared row/heading/checklist-item, or is NAMED dangling -- never silence.

Residue declared by D33's closure note (EXECUTION-SSOT-des-optimization.md):
"Nessun controllo che una citazione interna <<per DD-N>> risolva a una riga
esistente -- solo il caso ADR-refs e' presidiato." D33 built
`dereference_adr_refs` for the ADR family only; this closes the rest of the
same defect class -- any `<PREFIX>-<N>` decision id cited via `per <ID>`.

Three states, mirroring `AdrRefDereference`'s own precedent plus the
aggregate third state `_dangling_adr_ref_gaps` added for the tree-unreadable
case (D6/DD-9):

* ``resolved-local``   -- the id is declared (table row / heading /
  checklist item) in the SAME document as the citation. This is the primary
  case the `nw-design` Decision-once convention defines ("within this
  delta... every other section... cites it").
* ``resolved-external`` -- the id's prefix names a KNOWN, closed external
  registry: ``AD-N`` (ARCH_TECH_DEBT.md, a repo-global table) or ``GDP-N``
  (the fixed GDP-1..GDP-8 enumeration). The ADR family itself is explicitly
  EXCLUDED (out of scope -- already covered by `dereference_adr_refs`;
  building a second checker for the same family would be the duplication
  the dispatch brief warns against).
* ``could-not-verify`` -- an AD-N citation cannot be checked because
  ARCH_TECH_DEBT.md is absent/unreadable at `repo_root` -- the TREE, not the
  id, is the problem (GDP-6: reporting nothing here would silently agree it
  resolved).
* ``dangling``          -- none of the above: the id resolves nowhere this
  gate can see. The exact defect class this node closes.
"""

from __future__ import annotations

from pathlib import Path

from des.domain.feature_delta_source import (
    extract_decision_citations,
    extract_decision_declarations,
    resolve_decision_citations,
)


class TestExtractDecisionDeclarations:
    def test_plain_table_row_declares_id(self) -> None:
        text = "| DD-2 | Some decision. | Some rationale. |\n"
        assert "DD-2" in extract_decision_declarations(text)

    def test_bold_table_row_declares_id(self) -> None:
        text = "| **D-7** | `job_id: infrastructure-only`. | infra_gotcha. |\n"
        assert "D-7" in extract_decision_declarations(text)

    def test_heading_declares_id(self) -> None:
        text = "### DDD-1 -- Token measurement: tiktoken cl100k_base\n\nBody.\n"
        assert "DDD-1" in extract_decision_declarations(text)

    def test_checklist_item_declares_id(self) -> None:
        text = "- [ ] AC-5: Every Tier-1 section has the canonical heading.\n"
        assert "AC-5" in extract_decision_declarations(text)

    def test_running_prose_mention_does_not_declare(self) -> None:
        text = "This follows the pattern set per DD-2 earlier in the document.\n"
        assert extract_decision_declarations(text) == frozenset()

    def test_declaration_is_case_normalized_to_upper(self) -> None:
        text = "| dd-2 | lowercase id in the source | rationale |\n"
        assert "DD-2" in extract_decision_declarations(text)


class TestExtractDecisionCitations:
    def test_finds_per_id_citation(self) -> None:
        text = "Every other section cites it (per DD-3) instead of restating.\n"
        citations = extract_decision_citations(text)
        assert [c.id for c in citations] == ["DD-3"]
        assert citations[0].line == 1

    def test_finds_backticked_citation(self) -> None:
        text = "See the rationale per `DD-3` for the full argument.\n"
        citations = extract_decision_citations(text)
        assert [c.id for c in citations] == ["DD-3"]

    def test_excludes_adr_family_out_of_scope(self) -> None:
        # ADR-refs already has its own dedicated, wired checker
        # (dereference_adr_refs / _dangling_adr_ref_gaps) -- this module
        # must not re-check the same family a second, differently-shaped way.
        text = "This decision is promoted per ADR-030 in the ADR Refs section.\n"
        assert extract_decision_citations(text) == ()

    def test_multiple_citations_across_lines(self) -> None:
        text = "First per DD-1.\nSecond per DD-2.\n"
        citations = extract_decision_citations(text)
        assert [(c.id, c.line) for c in citations] == [("DD-1", 1), ("DD-2", 2)]


class TestResolveDecisionCitationsLocal:
    def test_citation_resolves_to_same_document_declaration(self) -> None:
        text = "| DD-2 | The decision. | The rationale. |\n\nRestated per DD-2 elsewhere.\n"
        results = resolve_decision_citations(text, repo_root=None)
        assert len(results) == 1
        assert results[0].state == "resolved-local"

    def test_citation_with_no_local_declaration_is_dangling(self) -> None:
        text = "This behavior is required per DD-9, which is never declared here.\n"
        results = resolve_decision_citations(text, repo_root=None)
        assert len(results) == 1
        assert results[0].state == "dangling"

    def test_cross_document_declaration_does_not_resolve_a_citation(
        self, tmp_path: Path
    ) -> None:
        """The sharper case: an id declared in a DIFFERENT document must NOT
        be accepted as resolving a citation in THIS document -- same-document
        scope is the whole point (`nw-design` SKILL.md: "within this
        delta")."""
        other_doc = tmp_path / "docs" / "feature" / "other-feature" / "feature-delta.md"
        other_doc.parent.mkdir(parents=True)
        other_doc.write_text("| DD-9 | Declared over there, not here. | rationale |\n")

        this_doc_text = "This behavior is required per DD-9.\n"
        results = resolve_decision_citations(this_doc_text, repo_root=tmp_path)
        assert len(results) == 1
        assert results[0].state == "dangling"

    def test_sub_item_citation_resolves_against_its_base_id(self) -> None:
        text = (
            "- [ ] AC-5: Every Tier-1 section has canonical heading.\n"
            "- [ ] AC-5.b: Every expansion section has canonical heading.\n"
            "\nSee AC-5.b, per AC-5.\n"
        )
        results = resolve_decision_citations(text, repo_root=None)
        assert all(r.state == "resolved-local" for r in results)


class TestResolveDecisionCitationsExternalRegistries:
    def test_gdp_citation_in_closed_set_resolves_external(self) -> None:
        text = "This gate follows GDP-6 discipline, per GDP-6.\n"
        results = resolve_decision_citations(text, repo_root=None)
        assert results[0].state == "resolved-external"

    def test_gdp_citation_outside_closed_set_is_dangling(self) -> None:
        text = "This gate follows a made-up rule, per GDP-99.\n"
        results = resolve_decision_citations(text, repo_root=None)
        assert results[0].state == "dangling"

    def test_ad_citation_resolves_against_arch_tech_debt(self, tmp_path: Path) -> None:
        (tmp_path / "ARCH_TECH_DEBT.md").write_text(
            "| **AD-21** | Gates/waves depend on git. | drift | high |\n"
        )
        text = "The gate logic must move behind a port (AD-21), per AD-21.\n"
        results = resolve_decision_citations(text, repo_root=tmp_path)
        assert results[0].state == "resolved-external"

    def test_ad_citation_not_declared_in_arch_tech_debt_is_dangling(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "ARCH_TECH_DEBT.md").write_text(
            "| **AD-21** | Gates/waves depend on git. | drift | high |\n"
        )
        text = "Per AD-999, which does not exist in the tech-debt register.\n"
        results = resolve_decision_citations(text, repo_root=tmp_path)
        assert results[0].state == "dangling"

    def test_ad_citation_could_not_verify_when_arch_tech_debt_absent(
        self, tmp_path: Path
    ) -> None:
        text = "Per AD-21, tracked in a register this tree does not carry.\n"
        results = resolve_decision_citations(text, repo_root=tmp_path)
        assert results[0].state == "could-not-verify"

    def test_ad_citation_could_not_verify_when_repo_root_is_none(self) -> None:
        text = "Per AD-21, with no tree supplied to check it against.\n"
        results = resolve_decision_citations(text, repo_root=None)
        assert results[0].state == "could-not-verify"
