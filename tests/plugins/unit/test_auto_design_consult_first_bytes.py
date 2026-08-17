"""Auto DESIGN consult -- bounded terminal branch, not full DESIGN (2026-08-16).

Confirmed regression: the compacted `nw-solution-architect.md` dropped the
exact Auto-consult prompt/response grammar that `nw-auto/SKILL.md` actually
sends and expects, replacing it with a vague "receive subject/root/route,
return ids" summary. Tests anchor on the exact grammar shared by both files,
prove the branch is scoped to a bounded consult (not full DESIGN/fanout/
docs-feature), and prove nw-auto still forwards the resulting architecture
authority into ATD/PO.
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

AUTO_HEADER_PAIR = (
    "AUTO-ARCHITECTURE-CONSULT: <bounded-subject>\n"
    "AUTO-ARCHITECTURE-ROOT: <absolute-root>\n"
    "AUTO-DELIVERY-ROUTE: <RED_TO_GREEN|GREEN_TO_GREEN>"
)
COVERED_TOKEN = "ARCHITECTURE-COVERED: <repo-relative-permanent-path>#<section-anchor>"
BLOCKED_TOKEN = "ARCHITECTURE-BLOCKED: <what>; WHY: <why>; HOW: <how>"


def _architect_body() -> str:
    return (AGENTS_DIR / "nw-solution-architect.md").read_text(encoding="utf-8")


def _auto_body() -> str:
    return (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _architect_consult_section(body: str) -> str:
    start = body.index("## Auto consult contract")
    end = body.index("## Core Principles")
    assert start < end
    return body[start:end]


def _norm(text: str) -> str:
    return " ".join(text.split())


class TestAgentAndAutoShareTheExactConsultGrammar:
    def test_grammars_match_and_agent_declares_entire_prompt_and_one_line_result(self):
        agent_section = _architect_consult_section(_architect_body())
        auto_body = _auto_body()

        assert AUTO_HEADER_PAIR in agent_section
        assert AUTO_HEADER_PAIR in auto_body
        assert COVERED_TOKEN in agent_section
        assert COVERED_TOKEN in auto_body
        assert BLOCKED_TOKEN in agent_section
        assert BLOCKED_TOKEN in auto_body

        normalized = _norm(agent_section)
        assert "entire prompt is exactly these three lines" in normalized
        assert "Return exactly one line" in normalized


class TestBoundedBranchTargetsPermanentArchitectureOnly:
    def test_branch_scopes_to_permanent_docs_and_names_compact_duties(self):
        section = _norm(_architect_consult_section(_architect_body()))

        assert "not full DESIGN" in section
        assert (
            "no task plan, fan-out, peer dispatch, skill preload, or "
            "per-delivery narrative" in section
        )
        assert "docs/product/architecture/brief.md" in section
        assert "never `docs/feature/`" in section
        assert "small explicit fact-call/read budget" in section
        assert "write or reuse the durable brief/ADR authority early" in section
        assert (
            "return `ARCHITECTURE-BLOCKED` immediately with WHAT/WHY/HOW "
            "instead of continuing to explore toward the budget or a "
            "timeout" in section
        )

        for duty in (
            "reuse",
            "prefactoring",
            "boundaries/ports",
            "four-layer failure laws and residual stress",
            "delivery obligations",
            "reuse the existing oracle",
        ):
            assert duty in section, f"Missing compact duty projection: {duty!r}"


class TestNwAutoForwardsArchitectureAuthorityIntoAtdAndPo:
    def test_consult_header_grammar_and_sibling_forwarding(self):
        body = _auto_body()
        consult_start = body.index("## Architecture readiness — shared M/L prefix")
        floor_start = body.index("## Root inputs and spatial AB batch")
        assert consult_start < floor_start

        consult_section = body[consult_start:floor_start]
        assert AUTO_HEADER_PAIR in consult_section
        assert COVERED_TOKEN in consult_section
        assert BLOCKED_TOKEN in consult_section

        route = _norm(body[floor_start : body.index("## Examiner input isolation")])
        assert "architecture-authority" in route
        assert "producer-emitted DeliveryId" in route
        assert "namespace" in route
        assert "never the architecture-authority anchor" in route
        assert "charter-scaffold" not in route
