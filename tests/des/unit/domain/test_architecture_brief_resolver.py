"""Unit tests for the architecture-brief citation parser
(`des compile-contract`'s parsing half).

Covers the line-wrap regression a real ADR-SSOT-002 brief (K4 run-13,
maintenance-windows) exposed: markdown word-wraps a long inline-code
citation with no space marker at the wrap point, and a naive regex over the
raw text mistook the fragment after the break for its own, wrong, file
citation (`hc/api/management/commands/sendalerts.py:24-55` split at the
`commands/` line boundary produced a spurious `sendalerts.py` target).
"""

from __future__ import annotations

from pathlib import Path

from des.domain.architecture_brief_resolver import (
    FILE_LINE_CITATION_RE,
    PBT_FAMILY_SKILL,
    canonical_paradigm,
    declared_imports_for_target,
    extract_acceptance_support_locators,
    extract_declared_import_candidates,
    extract_declared_oracle_locator_candidates,
    extract_declared_paradigms,
    extract_declared_target_locators,
    extract_obligations,
    extract_oracle_citations,
    extract_skill_citations,
    extract_target_citations,
    first_unparsed_obligation_candidate,
    malformed_acceptance_support_locator_lines,
    resolve_pbt_adapter,
    skill_citations_for_repo,
)


def test_paradigm_projection_tolerates_unambiguous_human_spellings() -> None:
    brief = "Paradigm: FP\n+ Paradigm: OO (Python, ports and adapters)\n"
    declared = extract_declared_paradigms(brief)
    assert declared == ["FP", "OO (Python, ports and adapters)"]
    assert [canonical_paradigm(value) for value in declared] == [
        "functional",
        "object_oriented",
    ]


def _atoms_by_target(mapping: dict[str, frozenset[str]]):
    """A fake `target_atoms` callable simulating a binding-resolved
    CodeFact grounding (Q-90/Q-91 acceptance law): the domain resolver
    receives resolved atoms, never reads the file itself. The real
    envelope decision (confidence/provider) is exercised against the
    composed chain in `tests/des/unit/application/test_compile_contract.py`."""
    return lambda target: mapping.get(target, frozenset())


#: An unreliable resolution (noisy provider, Failed, Unsupported, missing
#: file) arrives at the domain as the empty set for every target.
_NO_GROUNDED_ATOMS = _atoms_by_target({})


def test_extracts_one_citation_per_file() -> None:
    # `FILE_LINE_CITATION_RE`'s own shape: it captures the FIRST line
    # number of a `file:line-range` citation, never the trailing `-30`.
    brief = "See `pkg/mod.py:10` and `pkg/mod.py:20-30` and `pkg/other.py:5`."
    citations = extract_target_citations(brief)
    assert citations == {
        "pkg/mod.py": ["pkg/mod.py:10", "pkg/mod.py:20"],
        "pkg/other.py": ["pkg/other.py:5"],
    }


def test_citation_split_across_a_markdown_line_wrap_is_joined() -> None:
    # Reproduces the exact K4 run-13 shape: a long inline-code span wrapped
    # mid-path at 80 columns, with no space at the break.
    brief = (
        "Observation point: `hc/api/management/commands/\n"
        "sendalerts.py:24-55`, the sole driving entry."
    )
    citations = extract_target_citations(brief)
    assert citations == {
        "hc/api/management/commands/sendalerts.py": [
            "hc/api/management/commands/sendalerts.py:24"
        ]
    }
    # The regression: no spurious short-fragment target.
    assert "sendalerts.py" not in citations


def test_no_citation_yields_empty_mapping() -> None:
    assert extract_target_citations("no file references here at all") == {}


def test_a_documentary_citation_never_becomes_a_target() -> None:
    # SF friction report 2026-08-20, item 2b: a brief cites a design doc as
    # SUPPORTING EVIDENCE for a code target -- the doc citation must never
    # itself become a contract target (DESIGN/DELIVER change and verify
    # CODE, never prose).
    brief = "See `pkg/widget.go:3` and also `docs/design.md:1` for the law."
    citations = extract_target_citations(brief)
    assert citations == {"pkg/widget.go": ["pkg/widget.go:3"]}
    assert "docs/design.md" not in citations


def test_a_formal_proof_citation_never_becomes_a_target() -> None:
    brief = "See `pkg/widget.go:3`; the proof lives at `spec/Law.agda:42`."
    citations = extract_target_citations(brief)
    assert citations == {"pkg/widget.go": ["pkg/widget.go:3"]}
    assert "spec/Law.agda" not in citations


def test_a_brief_citing_only_documentary_files_yields_no_targets() -> None:
    brief = "See `docs/design.md:1` and `spec/Law.agda:42`."
    assert extract_target_citations(brief) == {}


def test_extracts_schema_closed_obligation_tokens_in_order() -> None:
    brief = (
        "1. **REUSE_CANDIDATE** -- law: reuse the validator.\n"
        "2. **INVALID_STATE** -- law: reject negative duration.\n"
        "3. **REUSE_CANDIDATE** -- repeated, must not duplicate.\n"
    )
    assert extract_obligations(brief) == ["REUSE_CANDIDATE", "INVALID_STATE"]


def test_extracts_schema_closed_obligation_tokens_when_the_number_is_inside_the_bold_span() -> (
    None
):
    """Run 17 (K4 matrix, $3.13/791s): `des compile-contract` refused a
    real DESIGN brief because its obligation labels were `**N. TOKEN**`
    (the numbering INSIDE the bold span) while the parser only ever
    recognized `N. **TOKEN**` (numbering outside). Two of our own
    producers disagreeing on a format is a compiler defect, not a
    DESIGN defect -- the parse is on the SEMANTICS (a numbered bold
    label), never the exact byte layout, so both unambiguous shapes
    must parse identically."""
    brief = (
        "**1. REUSE_CANDIDATE** -- law: reuse the validator.\n"
        "**2. INVALID_STATE** -- law: reject negative duration.\n"
        "**3. REUSE_CANDIDATE** -- repeated, must not duplicate.\n"
    )
    assert extract_obligations(brief) == ["REUSE_CANDIDATE", "INVALID_STATE"]


def test_extracts_obligations_with_a_trailing_colon_inside_the_bold_span() -> None:
    """The accepted shapes tolerate a trailing colon/spacing inside the
    bold markers -- the label is still unambiguously a schema token,
    just punctuated slightly differently."""
    brief = "**REUSE_CANDIDATE:** reuse the validator."
    assert extract_obligations(brief) == ["REUSE_CANDIDATE"]


def test_real_k4_run17_brief_obligations_parse_in_order() -> None:
    """Run 17 (K4 matrix): the REAL DESIGN brief that `des compile-
    contract` refused, byte-for-byte -- every obligation label in this
    brief is the `**N. TOKEN**` shape (number inside the bold span),
    e.g. `**1. REUSE_CANDIDATE**` / `**2. ARCHITECTURE_BOUNDARY_
    CHANGE**` / `**3. PRESERVATION**` / `**4. INVALID_STATE**`."""
    brief = (
        Path(__file__).parent / "fixtures" / "run17_maintenance_windows_brief.md"
    ).read_text(encoding="utf-8")
    assert extract_obligations(brief) == [
        "REUSE_CANDIDATE",
        "ARCHITECTURE_BOUNDARY_CHANGE",
        "PRESERVATION",
        "INVALID_STATE",
    ]


def test_non_schema_bold_token_is_ignored() -> None:
    brief = "### Reuse survey (decision: **EXTEND**, not CREATE_NEW)"
    assert extract_obligations(brief) == []


def test_first_unparsed_obligation_candidate_quotes_a_genuine_near_miss() -> None:
    """A bold span with an uppercase letter that still doesn't match
    either accepted shape (here: lowercase mixed in, not a schema
    token's own closed alphabet) is quoted verbatim -- an empty-
    obligations refusal that names this line is diagnosable; one that
    doesn't is a bare, useless 'not found'."""
    brief = "See `pkg/widget.py:5`.\n**Reuse_Candidate** is not a valid label.\n"
    assert (
        first_unparsed_obligation_candidate(brief)
        == "**Reuse_Candidate** is not a valid label."
    )


def test_first_unparsed_obligation_candidate_is_none_when_nothing_looks_attempted() -> (
    None
):
    assert first_unparsed_obligation_candidate("no bold labels here at all") is None


def test_extracts_backtick_symbol_candidates_deduplicated() -> None:
    brief = "Reuse `Check.get_grace_start` and `CronSim`, again `CronSim`."
    assert extract_declared_import_candidates(brief) == [
        "Check.get_grace_start",
        "CronSim",
    ]


def test_backtick_symbol_split_across_a_line_wrap_is_joined() -> None:
    brief = "Reuse `hc.api.views.\nguess_kind` for validation."
    assert extract_declared_import_candidates(brief) == ["hc.api.views.guess_kind"]


_MODULE_WITH_IMPORT_AND_CLASS = """
from cronsim import CronSim


class Check:
    def get_grace_start(self):
        return None
"""


def _seed(tmp_path: Path, relative: str, source: str) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def test_declared_imports_admits_bare_name_bound_in_target_file(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/mod.py", _MODULE_WITH_IMPORT_AND_CLASS)
    brief = "Reuse `CronSim` and `Check` here."
    assert declared_imports_for_target(
        tmp_path, "pkg/mod.py", brief, target_atoms=_NO_GROUNDED_ATOMS
    ) == [
        "CronSim",
        "Check",
    ]


def test_declared_imports_drops_dotted_class_attribute_chain(
    tmp_path: Path,
) -> None:
    # `Check.get_grace_start` is neither a bare bound name nor a resolvable
    # dotted MODULE path (`Check` is a class, not a module file) -- the
    # existing `des dispatch` declared-import validator cannot verify this
    # shape either, so emitting it would fail "passes by construction".
    _seed(tmp_path, "pkg/mod.py", _MODULE_WITH_IMPORT_AND_CLASS)
    brief = "Reuse `Check.get_grace_start` for occurrence computation."
    assert (
        declared_imports_for_target(
            tmp_path, "pkg/mod.py", brief, target_atoms=_NO_GROUNDED_ATOMS
        )
        == []
    )


def test_declared_imports_admits_resolvable_dotted_module_path(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/helpers.py", "def guess_kind(x):\n    return x\n")
    _seed(tmp_path, "pkg/mod.py", "class Check:\n    pass\n")
    brief = "Reuse `pkg.helpers.guess_kind` for validation."
    assert declared_imports_for_target(
        tmp_path, "pkg/mod.py", brief, target_atoms=_NO_GROUNDED_ATOMS
    ) == ["pkg.helpers.guess_kind"]


def test_declared_imports_drops_unverifiable_invented_symbol(
    tmp_path: Path,
) -> None:
    _seed(tmp_path, "pkg/mod.py", "class Check:\n    pass\n")
    brief = "Reuse `TotallyInventedHelper` which does not exist anywhere."
    assert (
        declared_imports_for_target(
            tmp_path, "pkg/mod.py", brief, target_atoms=_NO_GROUNDED_ATOMS
        )
        == []
    )


_POLYGLOT_TARGET_TABLE_BRIEF = """\
# Architecture Brief

| Target | Decision | Why |
| --- | --- | --- |
| `pkg/alpha/handler.go` | EXTEND | schedule parsing reuses `netip` |
| `web/router.ts` | EXTEND | route wiring reuses `Router` |

Extend `pkg/alpha/handler.go` by authoring `HandleCron` in this delivery.
Oracle target locator: `pkg/alpha/handler.go::HandleCron` (EXTEND, authored here).
"""


def test_declared_imports_for_a_non_python_target_are_target_local(
    tmp_path: Path,
) -> None:
    """SF friction FAIL reproduction 2026-08-21 (polyglot root): the
    non-Python branch used to return `extract_declared_import_candidates`
    over the WHOLE brief, so every non-Python target received the
    identical global symbol list -- the prose's global scope conflated
    with a target-local binding, and unverifiable-here conflated with
    admitted-here. Consumer ATD correctly refused EVIDENCE_GAP. Each
    target admits ONLY the symbols cited on its own lines (its
    Target-table row or prose naming its path) that its own resolved
    atom set carries -- `netip` and `Router` arrive as CodeFact-resolved
    atoms of their target files (Q-90/Q-91: grounding, not citation, is
    what admits them)."""
    target_atoms = _atoms_by_target(
        {
            "pkg/alpha/handler.go": frozenset({"netip"}),
            "web/router.ts": frozenset({"Router"}),
        }
    )
    assert declared_imports_for_target(
        tmp_path,
        "pkg/alpha/handler.go",
        _POLYGLOT_TARGET_TABLE_BRIEF,
        target_atoms=target_atoms,
    ) == ["netip"]
    assert declared_imports_for_target(
        tmp_path,
        "web/router.ts",
        _POLYGLOT_TARGET_TABLE_BRIEF,
        target_atoms=target_atoms,
    ) == ["Router"]


def test_declared_imports_for_a_non_python_target_never_emit_a_declared_future_symbol(
    tmp_path: Path,
) -> None:
    # `HandleCron` sits on a target-bound line, but it is a product of
    # THIS delivery: it is not among the target file's atoms at base, so
    # grounding excludes it by construction -- no matter which grammar
    # (`Oracle target locator:` line, table row, prose) declared it.
    result = declared_imports_for_target(
        tmp_path,
        "pkg/alpha/handler.go",
        _POLYGLOT_TARGET_TABLE_BRIEF,
        target_atoms=_atoms_by_target({"pkg/alpha/handler.go": frozenset({"netip"})}),
    )
    assert "HandleCron" not in result


def test_declared_imports_for_a_non_python_target_with_no_bound_symbols_is_empty(
    tmp_path: Path,
) -> None:
    # Scoping that finds nothing yields honest absence -- never the old
    # global fallback.
    brief = (
        "| Target | Decision | Why |\n"
        "| --- | --- | --- |\n"
        "| `src/main.rs` | EXTEND | wire the flag |\n\n"
        "Reuse `serde` broadly across the codebase.\n"
    )
    assert (
        declared_imports_for_target(
            tmp_path, "src/main.rs", brief, target_atoms=_NO_GROUNDED_ATOMS
        )
        == []
    )


def test_declared_imports_for_a_non_python_target_ground_in_the_atom_set(
    tmp_path: Path,
) -> None:
    """Q-90/Q-91 acceptance law (SF one-row canonical, 2026-08-21): a
    candidate is existing ONLY when it is among the target file's
    CodeFact-resolved atoms. `pkg/store.go` declares only
    `ExistingStore`; the authority's one row cites both `ExistingStore`
    and `FutureSnapshot` -- the future product is not an atom at base,
    so it is excluded by construction, whatever grammar the prose used
    (Q-83 residual: locator syntax alone missed table rows and "Extend
    with `X`" prose)."""
    brief = (
        "| Target | Existing | Decision |\n"
        "| --- | --- | --- |\n"
        "| `pkg/store.go` | `ExistingStore` | Extend with `FutureSnapshot` |\n"
    )
    assert declared_imports_for_target(
        tmp_path,
        "pkg/store.go",
        brief,
        target_atoms=_atoms_by_target({"pkg/store.go": frozenset({"ExistingStore"})}),
    ) == ["ExistingStore"]


def test_declared_imports_for_a_non_python_target_drop_a_symbol_absent_at_base(
    tmp_path: Path,
) -> None:
    # A symbol cited on the target's own line but absent from the target
    # file's atom set is excluded -- honest absence, never admission by
    # citation alone.
    brief = "Extend `pkg/store.go` reusing `MissingHelper` for persistence.\n"
    assert (
        declared_imports_for_target(
            tmp_path,
            "pkg/store.go",
            brief,
            target_atoms=_atoms_by_target(
                {"pkg/store.go": frozenset({"ExistingStore"})}
            ),
        )
        == []
    )


def test_extract_skill_citations_finds_backtick_quoted_nw_names() -> None:
    brief = "Use `nw-pbt-python` for the properties; see also `nw-pbt-python`."
    assert extract_skill_citations(brief) == ["nw-pbt-python"]


def test_extract_skill_citations_preserves_first_appearance_order() -> None:
    brief = "First `nw-certainty-by-construction`, then `nw-pbt-python`."
    assert extract_skill_citations(brief) == [
        "nw-certainty-by-construction",
        "nw-pbt-python",
    ]


def test_extract_skill_citations_ignores_non_skill_backtick_tokens() -> None:
    # `CronSim` and a dotted symbol are declared-import shapes, not
    # `nw-*` skill-name shapes -- never mistaken for one another.
    brief = "Reuse `CronSim` and `pkg.helpers.guess_kind`, per `nw-pbt-python`."
    assert extract_skill_citations(brief) == ["nw-pbt-python"]


def _seed_skill(repo_root: Path, skill_name: str) -> None:
    skill_dir = repo_root / "nWave" / "skills" / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")


def test_skill_citations_for_repo_admits_an_installed_skill(tmp_path: Path) -> None:
    _seed_skill(tmp_path, "nw-pbt-python")
    brief = "Author properties per `nw-pbt-python`."
    assert skill_citations_for_repo(tmp_path, brief) == ["nw-pbt-python"]


def test_skill_citations_for_repo_drops_an_uninstalled_skill_name(
    tmp_path: Path,
) -> None:
    # No `nWave/skills/nw-does-not-exist/SKILL.md` under `tmp_path` -- a
    # cited name this repository never shipped is never trusted, mirrors
    # `declared_imports_for_target`'s own base-tree grounding discipline.
    brief = "Author properties per `nw-does-not-exist`."
    assert skill_citations_for_repo(tmp_path, brief) == []


def test_skill_citations_for_repo_yields_empty_list_when_brief_cites_none(
    tmp_path: Path,
) -> None:
    _seed_skill(tmp_path, "nw-pbt-python")
    assert skill_citations_for_repo(tmp_path, "No skill cited here at all.") == []


def test_resolve_pbt_adapter_returns_none_without_a_pbt_citation(
    tmp_path: Path,
) -> None:
    result = resolve_pbt_adapter(
        tmp_path, ["nw-certainty-by-construction"], ["pkg/mod.py"]
    )
    assert result is None


def test_resolve_pbt_adapter_resolves_family_citation_from_non_python_targets(
    tmp_path: Path,
) -> None:
    # Ale, 2026-08-20: nw-pbt-python is too Python-centric -- nWave is
    # language-agnostic. Citing the FAMILY skill must resolve to the
    # target language's own adapter, never default to Python.
    _seed_skill(tmp_path, "nw-pbt-go")
    result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], ["pkg/mod.go"])
    assert result == {
        "cited": PBT_FAMILY_SKILL,
        "resolved-variant": "nw-pbt-go",
        "status": "resolved",
        "reason": "target extension '.go' maps to 'nw-pbt-go'",
    }


def test_resolve_pbt_adapter_resolves_specific_variant_matching_targets(
    tmp_path: Path,
) -> None:
    _seed_skill(tmp_path, "nw-pbt-rust")
    result = resolve_pbt_adapter(tmp_path, ["nw-pbt-rust"], ["pkg/mod.rs"])
    assert result is not None
    assert result["status"] == "resolved"
    assert result["resolved-variant"] == "nw-pbt-rust"


def test_resolve_pbt_adapter_maps_module_variant_javascript_and_typescript_targets(
    tmp_path: Path,
) -> None:
    # Friction 2026-09-15: an ESM-only Node repository's targets are `.mjs`.
    # The ES-module / CommonJS variants belong to the same family as `.js` and
    # `.ts`, so they resolve to its adapter, never to the family fallback.
    _seed_skill(tmp_path, "nw-pbt-typescript")
    for target in ("lib/calc.mjs", "lib/calc.cjs", "lib/calc.mts", "lib/calc.cts"):
        result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], [target])
        assert result is not None
        assert (target, result["status"], result["resolved-variant"]) == (
            target,
            "resolved",
            "nw-pbt-typescript",
        )


def test_resolve_pbt_adapter_flags_discrepancy_when_cited_variant_disagrees(
    tmp_path: Path,
) -> None:
    # A Python-specific citation over a Go target: the TARGET-derived
    # variant wins, never the citation's own claimed language -- but the
    # mismatch itself is surfaced, never silently swapped with no signal.
    _seed_skill(tmp_path, "nw-pbt-go")
    result = resolve_pbt_adapter(tmp_path, ["nw-pbt-python"], ["pkg/mod.go"])
    assert result is not None
    assert result["status"] == "discrepancy"
    assert result["resolved-variant"] == "nw-pbt-go"
    assert "nw-pbt-python" in result["reason"]
    assert "nw-pbt-go" in result["reason"]


def test_resolve_pbt_adapter_falls_back_to_family_when_target_language_has_no_adapter(
    tmp_path: Path,
) -> None:
    # Ale, 2026-08-20 follow-up: a missing language-specific adapter is
    # NOT an error -- it degrades to the generic, installed family skill
    # rather than refusing. `.zig` maps to no shipped nw-pbt-<lang> at all.
    _seed_skill(tmp_path, PBT_FAMILY_SKILL)
    result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], ["pkg/mod.zig"])
    assert result is not None
    assert result["status"] == "family-fallback"
    assert result["resolved-variant"] == PBT_FAMILY_SKILL
    assert ".zig" in result["reason"]


def test_resolve_pbt_adapter_falls_back_to_family_when_targets_span_multiple_languages(
    tmp_path: Path,
) -> None:
    _seed_skill(tmp_path, PBT_FAMILY_SKILL)
    result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], ["pkg/a.go", "pkg/b.rs"])
    assert result is not None
    assert result["status"] == "family-fallback"
    assert result["resolved-variant"] == PBT_FAMILY_SKILL
    assert "nw-pbt-go" in result["reason"]
    assert "nw-pbt-rust" in result["reason"]


def test_resolve_pbt_adapter_falls_back_to_family_when_target_variant_not_installed(
    tmp_path: Path,
) -> None:
    # The extension maps to nw-pbt-go, but this repository never shipped
    # it -- a usable skill (the family) always wins over an absent
    # language-specific upgrade.
    _seed_skill(tmp_path, PBT_FAMILY_SKILL)
    result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], ["pkg/mod.go"])
    assert result is not None
    assert result["status"] == "family-fallback"
    assert result["resolved-variant"] == PBT_FAMILY_SKILL
    assert "nw-pbt-go" in result["reason"]


def test_resolve_pbt_adapter_unresolved_only_when_family_fallback_also_missing(
    tmp_path: Path,
) -> None:
    # The doubly-degenerate case: nothing usable is installed at all --
    # this stays a LOUD, real refusal, never silent.
    result = resolve_pbt_adapter(tmp_path, [PBT_FAMILY_SKILL], ["pkg/mod.zig"])
    assert result is not None
    assert result["status"] == "unresolved"
    assert result["resolved-variant"] is None
    assert PBT_FAMILY_SKILL in result["reason"]


# -- oracle-vs-target discrimination -- SF friction report 2026-08-20,
# sister reproduction: a test/spec-shaped citation is an oracle-binding
# candidate, never a contract target.


def test_a_test_shaped_citation_never_becomes_a_target() -> None:
    brief = "See `pkg/widget.go:3` and `pkg/widget_test.go:5` for the law."
    citations = extract_target_citations(brief)
    assert citations == {"pkg/widget.go": ["pkg/widget.go:3"]}
    assert "pkg/widget_test.go" not in citations


def test_extract_oracle_citations_selector_shape_preserved_verbatim() -> None:
    brief = (
        "Bound as `go-shell/drive/verified_checkpoint_live_test.go"
        "::TestVerifiedCheckpointLiveBoundary`."
    )
    assert extract_oracle_citations(brief) == [
        "go-shell/drive/verified_checkpoint_live_test.go"
        "::TestVerifiedCheckpointLiveBoundary"
    ]


def test_extract_oracle_citations_test_shaped_file_line_yields_path_only() -> None:
    brief = "The oracle sketch sits at `pkg/widget_test.go:12`."
    assert extract_oracle_citations(brief) == ["pkg/widget_test.go"]


def test_extract_acceptance_support_locators_preserves_declared_order() -> None:
    brief = (
        "Test dependency locator: `spec/a.tla`\n"
        "Test dependency locator: `tests/support/data.json`\n"
    )

    assert extract_acceptance_support_locators(brief) == [
        "spec/a.tla",
        "tests/support/data.json",
    ]


def test_extract_acceptance_support_locators_keeps_legacy_label_compatible() -> None:
    brief = "Acceptance support locator: `tests/support/data.json`\n"

    assert extract_acceptance_support_locators(brief) == [
        "tests/support/data.json",
    ]


def test_extract_acceptance_support_locators_exposes_malformed_declaration() -> None:
    brief = "Test dependency locator: tests/support/data.json\n"

    assert extract_acceptance_support_locators(brief) == []
    assert malformed_acceptance_support_locator_lines(brief) == [brief.rstrip()]


def test_test_dependency_term_in_prose_is_not_a_declaration() -> None:
    brief = "The canonical term is `Test dependency locator:`.\n"

    assert extract_acceptance_support_locators(brief) == []
    assert malformed_acceptance_support_locator_lines(brief) == []


def test_extract_oracle_citations_keeps_first_durable_identity_for_same_file() -> None:
    # Primary ownership follows durable authority order. A later technical
    # selector is not allowed to rewrite the already-bound public oracle.
    brief = (
        "Sketch at `pkg/widget_test.go:12`, bound as `pkg/widget_test.go::TestWidget`."
    )
    assert extract_oracle_citations(brief) == ["pkg/widget_test.go"]


def test_extract_oracle_citations_ignores_documentary_files() -> None:
    brief = "See `docs/test_plan.md:3` and `spec/TestLaw.agda:7`."
    assert extract_oracle_citations(brief) == []


def test_extract_oracle_citations_ignores_production_files() -> None:
    brief = "See `pkg/widget.go:3` and `pkg/other.go:9`."
    assert extract_oracle_citations(brief) == []


def test_extract_oracle_citations_admits_a_bare_declared_oracle_locator() -> None:
    # ADR-AUM-001 reproduction (2026-08-22): the authority declared its
    # oracle under THIS compiler's own typed `Oracle target locator:`
    # label, with a bare backticked path -- no `:line` (the file is
    # CREATE_NEW on a RED_TO_GREEN slice, so it has no lines to cite yet)
    # and no `::Selector`. Neither citation regex matched, the declaration
    # was dropped silently, and the compiler refused with "the brief cites
    # no test/spec oracle" -- false, and therefore unactionable.
    brief = (
        "   Oracle target locator: `tests/des/unit/cli/test_update.py` "
        "(CREATE_NEW -- lands in this repo's real des CLI test tier).\n"
    )
    assert extract_oracle_citations(brief) == ["tests/des/unit/cli/test_update.py"]


def test_a_declared_oracle_locator_outranks_an_earlier_test_dependency_citation() -> (
    None
):
    # Reproduction: a brief lists its Test dependency locator lines (each of
    # which cites a real, existing test file at `path:line` -- itself a
    # test-shaped citation extract_oracle_citations already admits) BEFORE
    # its explicit Oracle target locator declaration. Textual position
    # alone made the earlier dependency citation win; DESIGN's typed
    # declaration is the judgment call and must outrank it regardless of
    # where either sits in the brief.
    brief = (
        "Test dependency locator: `tests/release/existing_dep_test.py:5`\n"
        "Oracle target locator: `tests/release/test_nwave_ai_cli.py` (CREATE_NEW).\n"
    )
    assert extract_oracle_citations(brief) == [
        "tests/release/test_nwave_ai_cli.py",
        "tests/release/existing_dep_test.py",
    ]


def test_a_declared_oracle_locator_naming_a_production_file_is_never_an_oracle() -> (
    None
):
    # The label alone never promotes a non-test-shaped path: the shape rule
    # stays the discriminator, exactly as for any other citation source.
    brief = "Oracle target locator: `src/des/cli/update.py` (CREATE_NEW)."
    assert extract_oracle_citations(brief) == []


def test_a_declared_module_variant_javascript_oracle_is_admitted_and_never_a_target() -> (
    None
):
    # Friction 2026-09-15: an ESM-only Node repository declared its oracle as
    # `test/install.test.mjs` and cited the same suite at `path:line`. With no
    # `.mjs` test convention the declaration was refused as a production file,
    # and the cited test files were compiled as contract TARGETS instead.
    brief = (
        "Oracle target locator: `test/install.test.mjs`\n"
        "The defining assertion is `test/install.test.mjs:41`, the parity check is "
        "`test/version.test.mjs:98`, and the fix lands in `scripts/install.mjs:26`.\n"
    )
    assert extract_oracle_citations(brief) == [
        "test/install.test.mjs",
        "test/version.test.mjs",
    ]
    assert extract_target_citations(brief) == {
        "scripts/install.mjs": ["scripts/install.mjs:26"]
    }


def test_declared_oracle_locator_candidates_are_shape_only_and_ordered() -> None:
    # Every declaration the brief makes, admissible or not -- so a refusal
    # can name the one it did NOT admit and why (GDP-3), instead of
    # claiming the brief declared nothing.
    brief = (
        "Oracle target locator: `src/des/cli/update.py` (CREATE_NEW).\n"
        "Oracle target locator: `tests/des/unit/cli/test_update.py` (CREATE_NEW).\n"
    )
    assert extract_declared_oracle_locator_candidates(brief) == [
        "src/des/cli/update.py",
        "tests/des/unit/cli/test_update.py",
    ]


def test_extract_oracle_citations_pytest_class_selector_chain() -> None:
    brief = "Bound as `tests/test_widget.py::TestWidget::test_color`."
    assert extract_oracle_citations(brief) == [
        "tests/test_widget.py::TestWidget::test_color"
    ]


def test_production_files_with_embedded_test_substring_stay_targets() -> None:
    # Review BLOCK 2026-08-20: the substring test-shape rule made genuine
    # production citations (contest.go, latest_config.go) VANISH from
    # targets while contest.go became the bound oracle.
    brief = (
        "EXTEND `pkg/contest.go:12` and `pkg/latest_config.go:5`; the "
        "oracle is `pkg/widget_test.go::TestWidget`."
    )
    assert set(extract_target_citations(brief)) == {
        "pkg/contest.go",
        "pkg/latest_config.go",
    }
    assert extract_oracle_citations(brief) == ["pkg/widget_test.go::TestWidget"]


def test_a_bare_name_citation_folds_into_the_qualified_citation_with_same_basename() -> (
    None
):
    # ADR-CFG-001 reproduction (2026-08-20): prose re-cites an already
    # path-qualified file by bare basename (`artifact_versioning.py:131`)
    # -- the SAME file, never a new one at repository root.
    brief = (
        "Kernel `src/des/domain/artifact_versioning.py:106` is reused; the "
        "same kernel (`artifact_versioning.py:131`) guarantees idempotence."
    )
    assert extract_target_citations(brief) == {
        "src/des/domain/artifact_versioning.py": [
            "src/des/domain/artifact_versioning.py:106",
            "artifact_versioning.py:131",
        ]
    }


def test_a_bare_name_citation_with_no_qualified_sibling_never_becomes_a_target() -> (
    None
):
    # A bare basename resolves to no path in the base tree -- unresolvable
    # is DROPPED, never promoted to a new file at repository root.
    brief = "Legacy tier today (`des_config.py:60`) folds into the new file."
    assert extract_target_citations(brief) == {}


def test_a_bare_name_citation_ambiguous_across_two_qualified_files_is_dropped() -> None:
    brief = "See `a/mod.py:1`, `b/mod.py:2`, and the earlier note (`mod.py:3`)."
    assert extract_target_citations(brief) == {
        "a/mod.py": ["a/mod.py:1"],
        "b/mod.py": ["b/mod.py:2"],
    }


def test_extract_declared_target_locators_parses_path_symbol_and_decision() -> None:
    # The exact declared shape nw-solution-architect emits (ADR-CFG-001):
    # the parenthesized decision may wrap to the next line after the token.
    brief = (
        "   - Oracle target locator: `src/des/domain/config_merge.py"
        "::merge_config` (CREATE_NEW,\n"
        "     single new pure function - no existing module owns this law).\n"
    )
    [locator] = extract_declared_target_locators(brief)
    assert locator.path == "src/des/domain/config_merge.py"
    assert locator.symbol == "merge_config"
    assert locator.decision == "CREATE_NEW"
    assert locator.citation == "src/des/domain/config_merge.py::merge_config"


def test_extract_declared_target_locators_dedups_a_same_repeat_keeping_decision() -> (
    None
):
    brief = (
        "   - Oracle target locator: `pkg/domain/config_merge.py"
        "::merge_config` (CREATE_NEW, single new pure function).\n"
        "   - Oracle target locator: same `pkg/domain/config_merge.py"
        "::merge_config`.\n"
    )
    [locator] = extract_declared_target_locators(brief)
    assert locator.path == "pkg/domain/config_merge.py"
    assert locator.decision == "CREATE_NEW"


def test_extract_declared_target_locators_never_admits_a_test_shaped_path() -> None:
    # A test-shaped declared path is an oracle binding, never a target.
    brief = "Oracle target locator: `tests/test_widget.py::test_color` (CREATE_NEW)."
    assert extract_declared_target_locators(brief) == []


# --- Target-declaration table (ADR-CFG-001 Amendment shape, 2026-08-21):
# a markdown pipe table whose header names both Target and Decision is the
# authority's explicit target-set declaration -- transcribed, never
# inferred. Any other pipe table (reuse survey, budget) never matches.


def test_target_table_rows_transcribe_in_declaration_order() -> None:
    from des.domain.architecture_brief_resolver import (
        DeclaredTargetTableRow,
        extract_declared_target_table,
    )

    text = (
        "| Target | Decision | Why |\n"
        "|---|---|---|\n"
        "| `pkg/a.py` | **EXTEND** | Existing seam. |\n"
        "| `pkg/b.py` | **CREATE_NEW** | Confirmed absent. |\n"
    )
    assert extract_declared_target_table(text) == [
        DeclaredTargetTableRow(path="pkg/a.py", decision="EXTEND"),
        DeclaredTargetTableRow(path="pkg/b.py", decision="CREATE_NEW"),
    ]


def test_non_target_pipe_tables_never_match() -> None:
    from des.domain.architecture_brief_resolver import (
        extract_declared_target_table,
    )

    text = (
        "| Candidate | Location | Verdict |\n"
        "|---|---|---|\n"
        "| `merge_config` | `pkg/domain/config_merge.py` | REUSE as-is. |\n"
    )
    assert extract_declared_target_table(text) is None


def test_a_go_module_proxy_target_locator_is_extracted_verbatim() -> None:
    # SF blocker 2026-08-23: the four hand-copied path-citation character
    # classes in this module admitted no '@', so a brief declaring an
    # artifact under the Go module-proxy convention
    # (`<module>/@v/<version>.<ext>`) was silent-wrong twice over -- the
    # declared target locator VANISHED from the result, and a `file:line`
    # citation was TRUNCATED to `v/v1.2.0.info:1`, a different path that
    # could plausibly exist. Extraction is a superset of the contract
    # schema's own `repositoryRelativePath`; the schema, not this regex,
    # decides admissibility, so an inadmissible path is refused LOUD.
    text = (
        "- **PRESERVATION**: Oracle target locator: "
        "`vendor/example.com/mod/@v/v1.2.0.mod::TestProxy` (CREATE_NEW)\n"
        "  Insertion point: `vendor/example.com/mod/@v/v1.2.0.info:1`\n"
    )

    assert [
        (locator.path, locator.symbol, locator.decision)
        for locator in extract_declared_target_locators(text)
    ] == [("vendor/example.com/mod/@v/v1.2.0.mod", "TestProxy", "CREATE_NEW")]
    assert FILE_LINE_CITATION_RE.findall(text) == [
        "vendor/example.com/mod/@v/v1.2.0.info:1"
    ]
