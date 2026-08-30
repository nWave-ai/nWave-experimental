"""K4 ATD compiler-boundary regression (2026-08-16).

DESIGN owns proof-protocol selection; ATD compiles and must not invoke a
runtime Skill or CodeFact. Dense semantic projections, resilient to Markdown
heading/prose refactors:

1. The generated role-skill-loading region renders zero runtime ON-TRIGGER
   rows and no `Skill` tool for the acceptance-designer.
2. Source prose explicitly forbids Skill/CodeFact invocation and restricts
   tools to exact set {Read, Write, Edit}, excluding Bash and Skill.
3. `catalog_only` stays nonempty and every listed skill is installed (SSOT
   parity between the registry and the skills tree).
4. RED_TO_GREEN orders compiling the smallest spatial portfolio before
   writing the compiled acceptance closure: Schema 1.4 carries one or more
   private support artifacts first, then exactly one public executable oracle
   (legacy 1.3 omits the field); it forbids any legacy delivery carrier or
   progress ledger.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
AGENTS_DIR = NWAVE_DIR / "agents"
SKILLS_DIR = NWAVE_DIR / "skills"
ROLE_SKILL_LOADING_PATH = NWAVE_DIR / "data" / "role-skill-loading.yaml"

ACCEPTANCE_DESIGNER_PATH = AGENTS_DIR / "nw-acceptance-designer.md"
ACCEPTANCE_DESIGNER = ACCEPTANCE_DESIGNER_PATH.read_text(encoding="utf-8")

_GENERATED_BLOCK = re.search(
    r"GENERATED:role-skill-loading START.*?GENERATED:role-skill-loading END",
    ACCEPTANCE_DESIGNER,
    re.DOTALL,
)
assert _GENERATED_BLOCK, (
    "acceptance-designer must carry a generated skill-loading block"
)


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_atd_generated_region_has_zero_runtime_on_trigger_rows_and_no_skill_tool() -> (
    None
):
    region = _GENERATED_BLOCK.group(0)
    assert "ON-TRIGGER" not in region
    assert "Skill(" not in region

    front, _, _ = ACCEPTANCE_DESIGNER.partition("\n---\n")
    tools_line = next(line for line in front.splitlines() if line.startswith("tools:"))
    tools = [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")]
    assert "Skill" not in tools


def test_atd_source_forbids_runtime_skill_and_codefact_and_restricts_bash_to_fill_contract() -> (
    None
):
    """Ale's construction-over-file correction (2026-08-20): ATD now holds
    `Bash`, but ONLY as the sole route to `des fill-contract` -- an
    installed PreToolUse hook locks every other Bash shape out (see
    `test_atd_fill_contract_bash_lockdown.py`). `Skill` remains absent
    entirely -- no runtime skill invocation, unchanged."""
    front, _, _ = ACCEPTANCE_DESIGNER.partition("\n---\n")
    tools_line = next(line for line in front.splitlines() if line.startswith("tools:"))
    tools = [tool.strip() for tool in tools_line.removeprefix("tools:").split(",")]
    assert "Skill" not in tools, "Skill must be absent from parsed tools"
    assert set(tools) == {"Read", "Write", "Edit", "Bash"}, (
        f"tools must be exactly {{Read, Write, Edit, Bash}}, got {set(tools)}"
    )

    body = _norm(ACCEPTANCE_DESIGNER)
    assert "code-fact" in body.lower(), (
        "source must name code-fact to explicitly forbid it"
    )
    forbidding_terms = ("must not invoke", "forbids", "forbidden", "no ", "never")
    skill_codefact_forbidden = any(term in body.lower() for term in forbidding_terms)
    assert skill_codefact_forbidden, "source must explicitly forbid Skill/code-fact"


def test_atd_catalog_only_nonempty_and_all_catalog_skills_installed() -> None:
    roles = yaml.safe_load(ROLE_SKILL_LOADING_PATH.read_text(encoding="utf-8"))["roles"]
    atd_entry = roles["nw-acceptance-designer"]
    catalog_only = atd_entry.get("catalog_only") or []
    assert catalog_only, "ATD must keep a nonempty catalog_only"
    assert "nw-bdd-methodology" in catalog_only
    assert "nw-at-completeness-check" in catalog_only
    for field in ("on_demand", "phase", "language_pbt"):
        assert field not in atd_entry, f"ATD must not carry {field}"

    for skill_name in catalog_only:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill_path.is_file(), f"{skill_name} is catalog_only but not installed"


def test_red_to_green_orders_spatial_portfolio_before_compiled_acceptance_closure() -> (
    None
):
    body = _norm(ACCEPTANCE_DESIGNER)
    spatial_marker = "Compile the smallest spatial portfolio"
    closure_marker = "Write the complete compiled acceptance closure"
    assert spatial_marker in body
    assert closure_marker in body
    assert body.index(spatial_marker) < body.index(closure_marker), (
        "spatial-portfolio compilation must precede authoring the closure"
    )
    assert "No legacy delivery carrier, slice vocabulary or progress ledger" in body


def test_red_to_green_supports_are_private_compiled_inputs_written_before_primary() -> (
    None
):
    body = _norm(ACCEPTANCE_DESIGNER)

    support_marker = "Write every listed support artifact first"
    primary_marker = "Write the primary oracle last"
    assert "`acceptance-tests.supporting-locators`" in body
    assert "private, contract-bound source/dependency artifacts" in body
    assert "never independent public oracles" in body
    assert "never separately selected by `verification-scope` commands" in body
    assert "contract order and identity exactly as supplied" in body
    assert "never choose, add, drop, reorder, search for or broaden" in body
    assert support_marker in body
    assert primary_marker in body
    assert body.index(support_marker) < body.index(primary_marker)


def test_supports_cannot_be_promoted_to_public_oracles_or_edited_green() -> None:
    """Reject appended positive mandates, while allowing explanatory
    prohibitions such as ``never separately selected`` and ``edits no``."""
    body = ACCEPTANCE_DESIGNER
    compact = _norm(body)

    assert re.search(r"exactly one public (?:executable )?oracle", compact, re.I)
    assert re.search(
        r"private, contract-bound source/dependency artifacts", compact, re.I
    )

    clauses = re.split(r"(?<=[.!?;])\s+|\n+", body)
    for clause in clauses:
        normalized = " ".join(clause.split()).casefold()
        positive_modal = re.search(r"\b(?:must|shall|should|required to)\b", normalized)
        if not positive_modal:
            continue
        negative_modal = re.search(
            r"\b(?:must not|shall not|should not|never|cannot|no|do not)\b",
            normalized,
        )
        if negative_modal:
            continue

        selects_support_as_public = (
            "support artifact" in normalized
            and "public oracle" in normalized
            and re.search(
                r"(?:separately select|select separately|separately selected)",
                normalized,
            )
        )
        edits_green_support = (
            "green_to_green" in normalized
            and "support" in normalized
            and "edit" in normalized
        )
        assert not selects_support_as_public, clause
        assert not edits_green_support, clause


def test_atd_readback_and_shape_checks_cover_closure_without_python_leakage() -> None:
    body = _norm(ACCEPTANCE_DESIGNER)

    assert "Read every artifact this role directly wrote back whole once" in body
    assert (
        "Python indentation/collection check applies only to Python artifacts" in body
    )
    assert (
        "never apply Python `def test_` assumptions to Go, Rust, Agda or TLA+" in body
    )


def test_green_to_green_binds_existing_complete_closure_without_artifact_edits() -> (
    None
):
    body = _norm(ACCEPTANCE_DESIGNER)

    assert "names the existing complete acceptance closure" in body
    assert "Do not search for, create, edit, broaden or reorder any member" in body
