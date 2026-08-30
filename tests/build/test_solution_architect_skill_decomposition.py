"""The solution architect routes distinct DESIGN procedures through skills."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "nWave/agents/nw-solution-architect.md"
AUTO = ROOT / "nWave/skills/nw-solution-architect-auto-consult/SKILL.md"
FULL = ROOT / "nWave/skills/nw-solution-architect-full-design/SKILL.md"
FORMAL = ROOT / "nWave/skills/nw-solution-architect-formal-verification/SKILL.md"
REGISTRY = ROOT / "nWave/data/role-skill-loading.yaml"
REVIEWER = ROOT / "nWave/agents/nw-solution-architect-reviewer.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_core_is_lean_and_routes_the_three_distinct_procedures() -> None:
    body = _text(AGENT)

    assert len(body.splitlines()) <= 400
    assert "AUTO-ARCHITECTURE-CONSULT:" in body
    assert "ARCHITECTURE-COVERED:" in body
    for skill in (
        "nw-solution-architect-auto-consult",
        "nw-solution-architect-full-design",
        "nw-solution-architect-formal-verification",
    ):
        assert f"Invoke Skill({skill}) ON-TRIGGER" in body


def test_extracted_procedures_have_disjoint_parent_triggers_and_gates() -> None:
    auto = _text(AUTO)
    full = _text(FULL)
    formal = _text(FORMAL)

    assert "exact AUTO-ARCHITECTURE-CONSULT envelope" in auto
    assert "not an AUTO-ARCHITECTURE-CONSULT envelope" in full
    assert "local totality, inhabitation, canonicalization, or preservation" in formal
    assert "state-machine reachability, liveness, concurrency, or recovery" in formal
    for body in (auto, full, formal):
        assert "## Deterministic sequence" in body
        assert "## Verification" in body


def test_registry_owns_runtime_procedures_without_eager_preload() -> None:
    agent = _text(AGENT)
    registry = _text(REGISTRY)

    assert "skills:\n" not in agent.partition("---")[2].partition("---")[0]
    for skill in (
        "nw-solution-architect-auto-consult",
        "nw-solution-architect-full-design",
        "nw-solution-architect-formal-verification",
    ):
        assert skill in registry


def test_registry_preserves_each_legacy_eager_skill_once_as_phase_loading() -> None:
    registry = _text(REGISTRY)
    phase = registry.partition("  nw-solution-architect:\n")[2].partition(
        "    on_demand:\n"
    )[0]

    for skill in (
        "nw-architecture-patterns",
        "nw-architectural-styles-tradeoffs",
        "nw-security-by-design",
        "nw-domain-driven-design",
        "nw-formal-verification-tlaplus",
        "nw-sa-critique-dimensions",
        "nw-code-analysis-port",
        "nw-cross-cutting-invariants",
    ):
        assert phase.count(f"      {skill}:") == 1


def test_reviewer_inherits_only_the_architect_lenses() -> None:
    reviewer = _text(REVIEWER)

    assert "Invoke Skill(nw-algebraic-design-protocol) ON-TRIGGER" in reviewer
    assert "Invoke Skill(nw-certainty-by-construction) ON-TRIGGER" in reviewer
    assert "Invoke Skill(nw-stress-analysis) ON-TRIGGER" in reviewer
    for procedure in (
        "nw-solution-architect-auto-consult",
        "nw-solution-architect-full-design",
        "nw-solution-architect-formal-verification",
    ):
        assert f"Invoke Skill({procedure}) ON-TRIGGER" not in reviewer
