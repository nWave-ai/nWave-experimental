"""DESIGN admission must preserve existing construction/refinement doctrine."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ARCHITECT = ROOT / "nWave/agents/nw-solution-architect.md"
DESIGN = ROOT / "nWave/skills/nw-design/SKILL.md"
CERTAINTY = ROOT / "nWave/skills/nw-certainty-by-construction/SKILL.md"
ALGEBRA = ROOT / "nWave/skills/nw-algebraic-design-protocol/SKILL.md"


def _compact(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _plain(path: Path) -> str:
    return _compact(path).replace("`", "")


def test_covered_requires_constructive_refinement_witness() -> None:
    """A durable authority is not covered until its public path is constructible."""
    body = _plain(ARCHITECT)

    assert "Constructive-refinement admission" in body
    assert (
        "admitted input -> public constructor/producer -> consumer -> public driving/observation port"
        in body
    )
    assert "unseeded constructor cycle" in body
    assert "model -> runtime-symbol mapping" in body
    assert "model-only" in body
    assert body.index("Constructive-refinement admission") < body.index(
        "Return exactly one line, nothing else:"
    )


def test_covered_locator_is_read_back_and_derived_from_a_real_heading() -> None:
    """A task-derived anchor cannot be admitted as an architecture authority."""
    architect = _plain(ARCHITECT)
    auto = _plain(ROOT / "nWave/skills/nw-solution-architect-auto-consult/SKILL.md")
    full = _plain(ROOT / "nWave/skills/nw-solution-architect-full-design/SKILL.md")

    for body in (architect, auto, full):
        lower = body.lower()
        assert (
            "read back the target permanent authority after its final write/edit"
            in lower
        )
        assert (
            "derive the section-anchor from an actually present markdown heading"
            in lower
        )
        assert "never invent an anchor from a task name or summary" in lower
        assert "missing path or heading returns architecture-blocked" in lower


def test_covered_requires_an_exhaustive_four_claim_matrix() -> None:
    """COVERED cannot elide liveness behind safety or reachability prose."""
    body = _plain(ARCHITECT)

    assert "Constructive-closure matrix" in body
    for row in (
        "safety: PASS | BLOCKED",
        "inhabitation: PASS | BLOCKED",
        "public reachability: PASS | BLOCKED",
        "liveness: APPLICABLE | NOT_APPLICABLE | BLOCKED",
    ):
        assert row in body
    assert "temporal property, fairness assumptions and public observation" in body
    assert "bounded/synchronous reason" in body
    assert "omitting any row returns architecture-blocked" in body.lower()


def test_available_tla_requires_an_executed_model_cfg_and_tlc_evidence() -> None:
    """A proposed TLC argv is not an executed temporal proof."""
    formal = _plain(
        ROOT / "nWave/skills/nw-solution-architect-formal-verification/SKILL.md"
    )

    assert ".tla model and .cfg configuration" in formal
    assert "actually pass both files to TLC" in formal
    assert "literal argv, exit status and result" in formal
    assert "intended/future argv" in formal
    assert "ARCHITECTURE-BLOCKED" in formal


def test_formal_tool_absence_offers_once_then_keeps_design_on_explicit_fallback() -> (
    None
):
    """Formal tooling improves evidence; it is not a prerequisite for DESIGN."""
    formal = _plain(
        ROOT / "nWave/skills/nw-solution-architect-formal-verification/SKILL.md"
    )

    assert "offer installation once" in formal
    assert (
        "on decline record formal tools unavailable -- prose-algebra fallback" in formal
    )
    assert "missing tooling never invents a proof or blocks all DESIGN" in formal


def test_auto_route_partition_keeps_malformed_repair_out_of_full_design() -> None:
    """Base and canonical repair are Auto; malformed repair is terminally blocked."""
    body = _plain(ARCHITECT)

    assert "base envelope is exactly the three lines" in body
    assert "canonical repair adds exactly AUTO-ARCHITECTURE-REJECTION" in body
    assert "<<'NW_REJECTION'" in _compact(ARCHITECT)
    assert "bare NW_REJECTION terminator" in body
    assert "malformed repair returns ARCHITECTURE-BLOCKED, never Full DESIGN" in body
    assert "Every other mandate is Full DESIGN" in body


def test_red_to_green_accepts_verified_design_model_not_unimplemented_runtime() -> None:
    """A complete refinement obligation can cover DESIGN before implementation."""
    architect = _plain(ARCHITECT)
    formal = _plain(
        ROOT / "nWave/skills/nw-solution-architect-formal-verification/SKILL.md"
    )
    design = _plain(DESIGN)

    for body in (architect, formal, design):
        assert "RED_TO_GREEN" in body
        assert "mapping/refinement obligation" in body
        assert "declared limits" in body
    assert "DESIGN may be ARCHITECTURE-COVERED" in architect
    assert "never runtime coverage" in formal


def test_full_design_preserves_installed_schema_and_compiler_label_grammar() -> None:
    """Extraction cannot weaken the closed RED_TO_GREEN compiler contract."""
    full = _compact(ROOT / "nWave/skills/nw-solution-architect-full-design/SKILL.md")

    assert (
        "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/nWave/schemas/thin-delivery-contract.schema.json"
        in full
    )
    assert "N. **TOKEN**" in full
    assert "exact closed obligation enum" in full


def test_auto_budget_cannot_disarm_triggered_design_lenses() -> None:
    """Auto's six repository-fact calls exclude required lens/formal work."""
    body = _compact(ARCHITECT)

    assert (
        "A triggered lens load, formal probe, and formal run are not fact calls" in body
    )
    assert (
        "`no skill preload` forbids unrelated eager context, never an applicable trigger"
        in body
    )
    assert "algebraic-design-protocol" in body
    assert "certainty-by-construction" in body


def test_design_keeps_safety_inhabitation_reachability_and_liveness_distinct() -> None:
    """Safe construction is not misreported as public progress or liveness."""
    design = _compact(DESIGN)
    certainty = _compact(CERTAINTY)
    algebra = _compact(ALGEBRA)

    assert "**safety** excludes an invalid state" in design
    assert (
        "**inhabitation** proves an intended valid value can be constructed" in design
    )
    assert "**public reachability** proves its producer-to-consumer path" in design
    assert "**liveness** proves eventual progress" in design
    assert "valid-state inhabitation" in certainty
    assert "construction graph must be acyclic" in algebra


def test_formal_trigger_and_refinement_limits_are_declared() -> None:
    """Formal results are required where applicable, but retain their scope."""
    body = _compact(ARCHITECT)

    assert (
        "Agda: local totality, inhabitation, canonicalization, or preservation" in body
    )
    assert (
        "TLA+/TLC: state-machine reachability, liveness, concurrency, or recovery"
        in body
    )
    assert "When the triggered tool is available, execute it" in body
    assert "A formal result without this mapping is model-only" in body
