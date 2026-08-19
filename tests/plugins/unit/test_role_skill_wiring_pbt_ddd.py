"""High-value role wiring laws for the thin delivery model."""

from __future__ import annotations

from pathlib import Path

from scripts.shared.agent_catalog import (
    build_ownership_map,
    is_public_skill,
    load_public_agents,
)
from scripts.shared.frontmatter import parse_frontmatter_file


ROOT = Path(__file__).resolve().parents[3]
NWAVE = ROOT / "nWave"
AGENTS = NWAVE / "agents"
SKILLS = NWAVE / "skills"

PBT_SKILLS = (
    "nw-pbt-python",
    "nw-pbt-go",
    "nw-pbt-rust",
    "nw-pbt-haskell",
    "nw-pbt-jvm",
    "nw-pbt-dotnet",
    "nw-pbt-typescript",
    "nw-pbt-erlang-elixir",
)


def _body(agent: str) -> str:
    return (AGENTS / agent).read_text(encoding="utf-8")


def _frontmatter(agent: str) -> dict:
    metadata, _ = parse_frontmatter_file(AGENTS / agent)
    assert metadata is not None
    return metadata


def test_acceptance_designer_compiles_the_architect_selected_language_adapter():
    metadata = _frontmatter("nw-acceptance-designer.md")
    assert not set(PBT_SKILLS) & set(metadata.get("skills") or ())

    public_agents = load_public_agents(NWAVE)
    ownership = build_ownership_map(AGENTS)
    assert all(
        is_public_skill(skill, public_agents, ownership_map=ownership)
        for skill in PBT_SKILLS
    )

    body = _body("nw-acceptance-designer.md")
    architect = _body("nw-solution-architect.md")
    assert "exact language PBT adapter/framework" in architect
    assert "PBT/language adapter selection as sealed compiler input" in " ".join(
        body.split()
    )
    assert "holds no `Skill` tool" in body
    assert "Skill" not in metadata.get("tools", "")


def test_completeness_closes_cross_language_environment_without_python_fallback():
    body = (SKILLS / "nw-at-completeness-check" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for manifest in (
        "requirements",
        "pyproject.toml",
        "package.json",
        "Cargo.toml",
        "go.mod",
    ):
        assert manifest in body
    assert "never from an ambient interpreter" in body
    for layer in (
        "domain",
        "application/port",
        "adapter/integration",
        "infrastructure",
    ):
        assert layer in body


def test_auto_resolves_charter_axis_independently_and_uses_single_cli_shape():
    body = (SKILLS / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
    route = body[body.index("## Root inputs and spatial AB batch") :]
    normalized_route = " ".join(route.split())
    for state in ("SKIP", "REUSE", "AUTHOR", "BLOCK"):
        assert f"`{state}`" in route
    assert "charter-scaffold" not in route
    assert (
        "des resolve-charters --repo-root <root> --delivery-id <producer id> "
        "--examine <true|false>" in normalized_route
    )
    # fa7d9730a: compile-contract now runs between resolve-charters and
    # ATD's dispatch; the property protected here (ATD receives only the
    # CLI-printed producer envelope verbatim, never root-authored) is
    # unchanged -- only the exact pinned wording moved.
    assert (
        "ATD always receives the original fourteen-line producer stdout "
        "verbatim, unchanged by this step" in normalized_route
    )
    assert (
        "For `examine=true, Author`, PO concurrently receives only the "
        "producer-emitted DeliveryId, namespace, root and VALUE-SEED"
        in normalized_route
    )
    assert "For Reuse/Skip, omit PO." in normalized_route


def test_auto_hot_path_never_calls_charter_scaffold():
    body = (SKILLS / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
    assert "charter-scaffold" not in body


def test_role_ownership_keeps_charter_and_executable_oracle_independent():
    owner = _body("nw-product-owner.md")
    designer = _body("nw-acceptance-designer.md")
    examiner = _body("nw-user-examiner.md")

    assert "value-side facts" in owner
    assert "Do not read a design contract" in owner
    assert "Do not create a feature workspace, plan, ledger" in " ".join(owner.split())
    assert "never implement production code or author the expectation" in designer
    assert "CONTRACT-LOCATOR:" in designer
    assert "CONTRACT-SCHEMA:" in designer
    assert "DELIVERY-CONTRACT-SHA256" not in designer
    assert "Source blind" in examiner
    assert "Every charter, no filtering" in examiner
    assert "One pass" in examiner
    assert "Create or edit nothing" in examiner


def test_green_route_binds_existing_oracle_and_red_route_closes_whole_value():
    designer = _body("nw-acceptance-designer.md")
    auto = (SKILLS / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
    normalized_auto = " ".join(auto.lower().split())
    for token in (
        "RED_TO_GREEN",
        "GREEN_TO_GREEN",
        "BROAD_INPUT_DOMAIN",
        "EVIDENCE_GAP",
    ):
        assert token in designer
    for token in (
        "observe every value-seed clause at its real port",
        "internal proxies and later-slice promises are `evidence_gap`",
        "complete only when the original value-seed is observed",
    ):
        assert token in normalized_auto


def test_crafters_neither_declare_nor_emit_language_pbt_authoring_skills():
    ownership = build_ownership_map(AGENTS)
    for filename in (
        "nw-software-crafter.md",
        "nw-functional-software-crafter.md",
    ):
        metadata = _frontmatter(filename)
        body = _body(filename)
        assert not set(PBT_SKILLS) & set(metadata.get("skills") or ())
        assert not any(skill in body for skill in PBT_SKILLS)
    for skill in PBT_SKILLS:
        assert not ownership.get(skill, set()) & {
            "software-crafter",
            "functional-software-crafter",
        }


def test_ddd_reviewer_uses_lazy_algebra_and_provider_neutral_code_facts():
    body = _body("nw-ddd-architect-reviewer.md")
    metadata = _frontmatter("nw-ddd-architect-reviewer.md")
    lazy = ("nw-algebraic-design-protocol", "nw-certainty-by-construction")
    assert not set(lazy) & set(metadata.get("skills") or ())
    assert all(f"Invoke Skill({skill}) ON-TRIGGER" in body for skill in lazy)
    assert "nw-code-analysis-port" in body
    assert "mcp__tsunami" not in body
    assert "graphify" not in body.lower()
