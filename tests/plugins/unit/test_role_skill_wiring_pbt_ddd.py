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


def test_pbt_skills_remain_publicly_owned():
    public_agents = load_public_agents(NWAVE)
    ownership = build_ownership_map(AGENTS)
    assert all(
        is_public_skill(skill, public_agents, ownership_map=ownership)
        for skill in PBT_SKILLS
    )


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


def test_auto_hot_path_never_calls_charter_scaffold():
    body = (SKILLS / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
    assert "charter-scaffold" not in body


def test_source_blind_examiner_does_not_cross_into_implementation():
    examiner = _body("nw-user-examiner.md").lower().replace("‐", "-")
    normalized = " ".join(examiner.split())
    assert "source-blind" in normalized
    assert "do not execute commands" in normalized
    assert "inspect source" in normalized
    # The current negative-capability list reads "derive new evidence"
    # (line-wrapped in the source); "new" is meaningful — it distinguishes
    # deriving fresh evidence from consuming the evidence already supplied.
    assert "derive new evidence" in normalized


def test_authors_receive_ordered_batches_only_after_runner_binding():
    for agent in (
        "nw-acceptance-designer.md",
        "nw-software-crafter.md",
        "nw-functional-software-crafter.md",
    ):
        body = _body(agent).lower()
        assert "ordered batch" in body
        assert "value slice" not in body


def test_whole_request_reviewer_and_examiner_projections_exclude_slice_flow():
    """The only review and optional examination cover one whole candidate.

    The reviewer judges a whole-Request candidate diff, so it carries the
    literal "whole-request candidate" phrase. The examiner instead judges
    supplied installed-observation evidence source-blind over the whole
    Request — it never sees a "candidate diff" to name — so its scope is
    checked against its own declared wording (whole-Request source-blind
    judgment) rather than the reviewer's phrase.
    """
    reviewer = _body("nw-software-crafter-reviewer.md").lower()
    examiner = " ".join(_body("nw-user-examiner.md").lower().split())

    assert "whole-request candidate" in reviewer
    assert "judge the whole request" in examiner
    assert "source-blind" in examiner
    assert "value-slice" not in reviewer
    assert "value slice" not in examiner


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
