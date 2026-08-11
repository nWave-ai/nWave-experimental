"""Focused D/I/E proof for the role-skill wiring lane (2026-08-08).

Bounded to the two confirmed defects from
docs/analysis/2026-08-08-installed-role-skill-wiring-audit.md:

1. nw-ddd-architect-reviewer loads the algebraic-design/certainty-by-
   construction pair as lazy ON-TRIGGER skills in its Skill-Loading-Strategy
   table, not in frontmatter (consistent with peer architect/reviewer roles).
2. The 8 language-specific nw-pbt-* skills remain distributed by their
   skill-local ownership, while nw-acceptance-designer selects exactly one
   from its body at authoring time instead of preloading all eight.

D = declared ownership, I = installed/resolvable, E = emitted (a
Skill-Loading-Strategy table row that actually instructs a Read). R
(mechanically read) is explicitly out of scope for this lane -- see the joint
installed provider probe.
"""

from __future__ import annotations

from pathlib import Path

from scripts.shared.agent_catalog import (
    build_ownership_map,
    is_public_skill,
    load_public_agents,
)
from scripts.shared.frontmatter import parse_frontmatter_file


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
AGENTS_DIR = NWAVE_DIR / "agents"
SKILLS_DIR = NWAVE_DIR / "skills"

PBT_LANGUAGE_SKILLS = [
    "nw-pbt-python",
    "nw-pbt-go",
    "nw-pbt-rust",
    "nw-pbt-haskell",
    "nw-pbt-jvm",
    "nw-pbt-dotnet",
    "nw-pbt-typescript",
    "nw-pbt-erlang-elixir",
]

CRAFTER_AGENT_FILES = [
    "nw-software-crafter.md",
    "nw-functional-software-crafter.md",
]

BASELINE_PAIR = ["nw-algebraic-design-protocol", "nw-certainty-by-construction"]


def _frontmatter(agent_filename: str) -> dict:
    metadata, _ = parse_frontmatter_file(AGENTS_DIR / agent_filename)
    assert metadata is not None, f"{agent_filename} has no parseable frontmatter"
    return metadata


class TestDddArchitectReviewerLoadsBaselineOnTrigger:
    """Fix A: nw-ddd-architect-reviewer loads baseline pair as lazy ON-TRIGGER skills."""

    def test_frontmatter_absent_baseline_pair(self):
        skills = _frontmatter("nw-ddd-architect-reviewer.md").get("skills") or []
        preloaded = [s for s in BASELINE_PAIR if s in skills]
        assert preloaded == [], (
            f"nw-ddd-architect-reviewer.md frontmatter preloaded {preloaded}; "
            f"baseline pair must be lazy ON-TRIGGER, not host-preloaded"
        )

    def test_skill_loading_table_emits_a_read_row_for_each(self):
        body = (AGENTS_DIR / "nw-ddd-architect-reviewer.md").read_text(encoding="utf-8")
        missing = [s for s in BASELINE_PAIR if f"Read `{s}` ON-TRIGGER" not in body]
        assert missing == [], (
            f"nw-ddd-architect-reviewer.md body has no imperative "
            f'"Read `{{skill}}` ON-TRIGGER" row for {missing}'
        )


class TestAcceptanceDesignerLoadsLanguagePbtOnDemand:
    """Language PBT deep dives are distributed but never frontmatter-preloaded."""

    def test_skill_loading_table_emits_a_language_conditional_read_row(self):
        skills = _frontmatter("nw-acceptance-designer.md").get("skills") or []
        preloaded = [s for s in PBT_LANGUAGE_SKILLS if s in skills]
        assert preloaded == [], f"language PBT deep dives were preloaded: {preloaded}"

        public_agents = load_public_agents(NWAVE_DIR)
        ownership = build_ownership_map(AGENTS_DIR)
        retained = [
            skill
            for skill in PBT_LANGUAGE_SKILLS
            if is_public_skill(skill, public_agents, ownership_map=ownership)
        ]
        assert retained == PBT_LANGUAGE_SKILLS, (
            f"public catalog API dropped on-demand PBT deep dives: retained={retained}"
        )

        body = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(encoding="utf-8")
        assert "nw-pbt-{" in body or all(s in body for s in PBT_LANGUAGE_SKILLS), (
            "nw-acceptance-designer.md body has no Skill-Loading-Strategy row "
            "that Reads a nw-pbt-{language} skill -- catalogued without "
            "emission reproduces the exact 'catalogued != wired' trap"
        )
        assert "Read exactly ONE deep dive per feature" in body
        assert "never all eight" in body

    def test_pbt_skill_frontmatter_keeps_non_runtime_base_owner_hint(self):
        """CONTRACT_SHAPE: bounded-change. Distribution ownership stays on each skill."""
        changed = []
        for skill in PBT_LANGUAGE_SKILLS:
            metadata, _ = parse_frontmatter_file(SKILLS_DIR / skill / "SKILL.md")
            assert metadata is not None, f"{skill}/SKILL.md has no frontmatter"
            if metadata.get("agent") != "nw-functional-software-crafter":
                changed.append((skill, metadata.get("agent")))
        assert changed == [], f"skill-local non-runtime owner hints changed: {changed}"


class TestThinAutoRoleRoutes:
    """The existing roles expose thin Auto without changing Human routes."""

    def test_acceptance_designer_emits_only_examiner_safe_inputs(self):
        """CONTRACT_SHAPE: bounded-change. Auto ATD returns a thin typed handoff."""
        body = (AGENTS_DIR / "nw-acceptance-designer.md").read_text(encoding="utf-8")
        route = " ".join(
            body[
                body.index("## Route contract") : body.index("## Language Convention")
            ].split()
        )
        for token in (
            "authoritative terminal branch",
            "des code-fact query.* SUBJECT --root ROOT",
            "load each generated Read row",
            "when its trigger fires",
            "never preload",
            "never all eight PBT deep dives",
            "thin `DeliveryContract`",
            "selected `paradigm`",
            "expectation charter, and the user-surface start recipe",
            "never code facts, acceptance tests",
            "test command",
            "source fallback",
            "Do not run the Human TaskCreate, Phase 0-4",
        ):
            assert token in route

    def test_user_examiner_accepts_exactly_expectation_and_start_recipe(self):
        """CONTRACT_SHAPE: bounded-change. Auto EXAMINE stops before Human recording."""
        body = (AGENTS_DIR / "nw-user-examiner.md").read_text(encoding="utf-8")
        route = " ".join(
            body[
                body.index("## Route contract") : body.index("## Hard Boundary")
            ].split()
        )
        examiner_isolation = " ".join(route.split())
        for token in (
            "Human route",
            "existing EXAMINE workflow below is unchanged",
            "Thin Auto M/L route",
            "exactly the expectation charter",
            "user-surface start recipe",
            "code facts",
            "acceptance tests",
            "test command",
            "source fallback",
            "After Step 5",
            "STOP before Human-only Step 6",
            "never append or record a verdict",
        ):
            assert token in examiner_isolation


class TestUserExaminerAutoRouteIsBoundedNotExhaustive:
    """Auto EXAMINE samples equivalence classes instead of exhaustively re-probing."""

    @staticmethod
    def _route_text():
        body = (AGENTS_DIR / "nw-user-examiner.md").read_text(encoding="utf-8")
        return " ".join(
            body[
                body.index("## Route contract") : body.index("## Hard Boundary")
            ].split()
        )

    def test_auto_route_bounds_positive_journeys_to_one_representative_each(self):
        """CONTRACT_SHAPE: bounded-change. One probe per distinct positive journey, not per phrasing."""
        route = self._route_text()
        assert "one" in route and "representative" in route
        assert "distinct positive user journey" in route

    def test_auto_route_bounds_negative_rows_to_exactly_one_probe(self):
        """CONTRACT_SHAPE: bounded-change. No repeated attempts at the same must-NOT-happen row."""
        route = self._route_text()
        assert "probe per explicit negative oracle row" in route
        assert "never more than one attempt" in route

    def test_auto_route_bounds_determinism_check_to_one_repeat_call(self):
        """CONTRACT_SHAPE: bounded-change. Idempotency/determinism gets one repeat, not a sweep."""
        route = self._route_text()
        assert "repeated call" in route
        assert "determinism" in route or "idempotency" in route

    def test_auto_route_stops_at_first_fail(self):
        """CONTRACT_SHAPE: bounded-change. No curiosity probing after a charter row is violated."""
        route = self._route_text()
        assert "STOP at the first FAIL" in route
        assert "no curiosity probes" in route

    def test_auto_route_declares_a_ten_call_target_with_named_excess(self):
        """CONTRACT_SHAPE: bounded-change. Live overrun was 26 calls; the bound must be explicit and auditable."""
        route = self._route_text()
        assert "10 CLI/API tool calls" in route
        assert "state in your report exactly which" in route

    def test_auto_route_bound_does_not_leak_into_human_route(self):
        """CONTRACT_SHAPE: bounded-change. Human route keeps richer exploration, unbounded."""
        body = (AGENTS_DIR / "nw-user-examiner.md").read_text(encoding="utf-8")
        assert "Auto route only" in body
        assert "Human route below keeps its richer" in body


class TestAutoRolesAreSinglePassNoContinuation:
    """K4 overhead slice SSOT: Auto's first role result is terminal -- no
    SendMessage/resume/retry/correction within the same run.

    CONTRACT_SHAPE: bounded-change
    """

    def test_route_boundaries_declare_the_single_pass_no_send_message_rule(self):
        body = (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")
        route_boundaries = " ".join(body[body.index("## Route boundaries") :].split())
        for token in (
            "single-pass",
            "first result of each dispatched role",
            "is terminal",
            "SendMessage",
            "resume",
            "retry",
            "correction",
            "separately measured new run",
        ):
            assert token in route_boundaries


class TestDddReviewerUsesCodeAnalysisPort:
    """Structural review evidence goes through the code-analysis port."""

    def test_reviewer_has_no_tsunami_tool_dependency_or_raw_search_recipe(self):
        """CONTRACT_SHAPE: bounded-change. DDD evidence uses one executable port argv."""
        body = (AGENTS_DIR / "nw-ddd-architect-reviewer.md").read_text(encoding="utf-8")
        frontmatter = body.split("---\n", 2)[1]
        assert "mcp__tsunami" not in frontmatter
        assert "nw-code-analysis-port" in body
        assert "des code-fact query.callers-of AtCompletionLedger --root tests" in body
        assert 'does not invent an "18 sites" claim' in body
        for raw_recipe in ("grep -rn", "grep -rln", "xargs grep", "graphify"):
            assert raw_recipe not in body.lower()


class TestCraftersDoNotAuthorLanguagePbt:
    """No crafter may declare or emit a language-specific PBT authoring skill.

    PBT ownership belongs exclusively to acceptance-designer; crafters
    consume property obligations but do not author tests.
    """

    def test_no_crafter_declares_any_pbt_language_skill(self):
        for agent_file in CRAFTER_AGENT_FILES:
            skills = _frontmatter(agent_file).get("skills") or []
            leaked = [s for s in PBT_LANGUAGE_SKILLS if s in skills]
            assert leaked == [], f"{agent_file} frontmatter declares {leaked}"

    def test_no_crafter_body_mentions_a_pbt_language_skill(self):
        for agent_file in CRAFTER_AGENT_FILES:
            body = (AGENTS_DIR / agent_file).read_text(encoding="utf-8")
            leaked = [s for s in PBT_LANGUAGE_SKILLS if s in body]
            assert leaked == [], f"{agent_file} body mentions {leaked}"

    def test_ownership_map_never_assigns_pbt_skill_to_a_crafter(self):
        ownership = build_ownership_map(AGENTS_DIR)
        crafter_names = {
            f.removeprefix("nw-").removesuffix(".md") for f in CRAFTER_AGENT_FILES
        }
        for skill in PBT_LANGUAGE_SKILLS:
            owners = ownership.get(skill, set())
            leaked = owners & crafter_names
            assert leaked == set(), f"{skill} owned by crafter(s) {leaked}"
