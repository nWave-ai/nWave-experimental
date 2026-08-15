"""K4 Auto DESIGN consult -- bounded terminal branch, not full DESIGN (2026-08-12).

Confirmed defect (K4 empirical, ADR-SSOT-002 SS3/5/12): the installed Auto
Unresolved path dispatched a bare DESIGN consult with the full Human DESIGN
prompt. Root's prompt never signalled a bounded consult, and
nw-solution-architect.md carried no terminal branch to recognize one; the
consult ran the full requirements-analysis workflow (TaskCreate, C4,
component-manifest, peer reviewer, feature-delta), spent ~660s/53
tools/138k tokens, wrote nothing, and returned no Covered reference --
Architecture readiness never resolved.

Tests verify, anchored on nw-solution-architect.md's own runtime instruction
surface (Route contract, Auto branch) in agreement with nw-auto/SKILL.md's
"## DESIGN consult -- first bytes" and "## Architecture readiness" sections:
(a) the Auto branch is a sole-owner section preceding the Human route anchor,
    uses the exact AUTO-ARCHITECTURE-CONSULT/-ROOT input grammar and the
    ARCHITECTURE-COVERED/ARCHITECTURE-BLOCKED result grammar, and targets the
    durable brief.md feature-section heading, never feature-delta
(b) the branch text never leaks the later full-workflow phase markers, and
    the full Human workflow still lives, unchanged, after the Human anchor
(c) the escalation rule names the three specialist agents and forbids both
    dispatching them and speculative escalation
(d) nw-auto/SKILL.md forwards the resolved architecture authority as the
    first bytes of BOTH sibling prompts, and NoImpact requires the same
    citation form as Covered -- never free prose
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

ROUTE_ANCHOR = "## Route contract"
HUMAN_ANCHOR = "**Human route:**"

AUTO_HEADER_PAIR = (
    "AUTO-ARCHITECTURE-CONSULT: <bounded-subject>\n"
    "AUTO-ARCHITECTURE-ROOT: <absolute-root>\n"
    "AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>"
)
COVERED_TOKEN = "ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>"
BLOCKED_TOKEN = "ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>"
NO_IMPACT_TOKEN = (
    "ARCHITECTURE-NO-IMPACT: <repo-relative-permanent-path>#<section-anchor>"
)


def _architect_body() -> str:
    return (AGENTS_DIR / "nw-solution-architect.md").read_text(encoding="utf-8")


def _auto_body() -> str:
    return (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _architect_branch_section(body: str) -> str:
    return body[body.index(ROUTE_ANCHOR) : body.index(HUMAN_ANCHOR)]


def _norm(text: str) -> str:
    return " ".join(text.split())


class TestAutoConsultBranchGrammarAndTarget:
    """(a) exact input/result grammars, sole ownership, durable-target heading."""

    def test_branch_precedes_human_route_with_exact_grammars_and_durable_target(self):
        body = _architect_body()
        assert body.count(ROUTE_ANCHOR) == 1, "Route contract must be a sole owner"
        assert body.index(ROUTE_ANCHOR) < body.index("## Core Principles")
        assert body.index(ROUTE_ANCHOR) < body.index(HUMAN_ANCHOR)

        section = _architect_branch_section(body)
        assert AUTO_HEADER_PAIR in section, "Input header lines are not adjacent/exact"
        assert COVERED_TOKEN in section, "Covered result grammar missing/inexact"
        assert BLOCKED_TOKEN in section, "Blocked result grammar missing/inexact"

        normalized = _norm(section)
        for token in (
            "It is NOT DESIGN-wave completion",
            "## Feature: <bounded-subject> — Auto Architecture Consult",
            "Reuse decisions",
            "Prefactoring assessment",
            "Boundaries and ports",
            "Paradigm",
            "Delivery obligations",
            "Escalation",
            "docs/product/architecture/brief.md",
            "create the file if absent",
            "exactly one new permanent ADR",
            "never both",
            "Never `docs/feature/",
            "no write in that case",
        ):
            assert token in normalized, f"Missing durable-target projection: {token!r}"

    def test_branch_forbids_full_design_wave_work(self):
        section = _norm(_architect_branch_section(_architect_body()))
        for forbidden in (
            "TaskCreate/task plan",
            "`feature-delta.md`",
            "C4 diagrams",
            "`component-manifest.yaml`",
            "peer reviewer dispatch",
            "fan-out to another agent",
            "no global find/glob",
        ):
            assert forbidden in section, f"Did not forbid: {forbidden}"


class TestLegacyFullWorkflowStaysOutsideTheBranch:
    """(b) branch content never absorbs the later full-workflow phase text."""

    def test_full_workflow_phase_markers_absent_before_human_anchor(self):
        body = _architect_body()
        section = _architect_branch_section(body)
        for phase_marker in (
            "1. **Mode Selection**",
            "2. **Multi-Architect Context**",
            "3. **Requirements Analysis**",
            "6. **Architecture Design**",
            "8. **Peer Review and Handoff**",
        ):
            assert phase_marker not in section, (
                f"Legacy full-workflow phase leaked into the Auto branch: {phase_marker!r}"
            )

        remainder = body[body.index(HUMAN_ANCHOR) :]
        assert "1. **Mode Selection**" in remainder, (
            "Full Human workflow must remain intact after the Human route anchor"
        )


class TestEscalationNamesSpecialistsWithoutDispatch:
    """(c) BLOCKED escalation names the three lenses; never dispatches, never speculates."""

    def test_escalation_names_specialists_and_forbids_dispatch(self):
        section = _norm(_architect_branch_section(_architect_body()))
        for token in (
            "nw-ddd-architect",
            "nw-system-designer",
            "nw-platform-architect",
            "never dispatch it yourself",
            "never escalate speculatively",
        ):
            assert token in section, f"Missing escalation projection: {token!r}"


class TestNwAutoForwardsAuthorityAndNoImpactCitationForm:
    """(d) root resolves one authority and forwards it to dispatched roles."""

    def test_consult_header_grammar_and_sibling_forwarding_and_no_impact_form(self):
        body = _auto_body()
        consult_start = body.index("## Architecture readiness — shared M/L prefix")
        floor_start = body.index("## M/L route — shared reuse floor")
        assert consult_start < floor_start

        consult_section = body[consult_start:floor_start]
        assert AUTO_HEADER_PAIR in consult_section
        assert COVERED_TOKEN in consult_section
        assert BLOCKED_TOKEN in consult_section
        normalized_consult = _norm(consult_section)
        assert "Covered/NoImpact" in normalized_consult
        assert "Unresolved" in normalized_consult

        route = _norm(body[floor_start : body.index("## Examiner input isolation")])
        assert "Forwards architecture authority line" in route
        assert "Receives architecture line + charter path" in route
        assert "## L route" not in body
