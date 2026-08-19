"""Projection + regression-scanner tests for the gate-steering redirect
(2026-08-19).

Ale's standing directive: gates/guards/hooks/validators are LAST RESORT.
Every skill/agent instruction that steered an agent toward "add a gate /
guard / validator / hook / check" for SAFETY must instead steer toward
construction first (GDP-0, `nw-cross-cutting-invariants`
`gate:design-principles-gdp-1-9` / `construction:moves-catalogue`) — name
the producer that could make the unsafe action unrepresentable, and only
admit a hook with a recorded reason.

The verified defect class (found by corpus grep, not hypothesised): agent-
builder-family assets recommending "safety via frontmatter fields + hooks"
as the FIX for embedded safety prose, with no GDP-0 framing and no
last-resort qualifier. Two duplicate skill copies existed
(`nw-ab-critique-dimensions` / `nw-abr-critique-dimensions`) plus
`nw-review-workflow` — all three carried the identical unfixed line and are
now individually asserted below (a projection test on one duplicate would
not have caught the sibling regressing back).

`test_corpus_has_no_unallowlisted_safety_hook_steering` is the durable
regression gate: broader phrase families (generic "add a gate/check/lint")
were surveyed across `nWave/skills/*/SKILL.md`, `nWave/agents/*.md`,
`nWave/tasks/nw/*.md` and found already GDP-0-aligned or legitimate
PRODUCT-GATE/LEGIT-LAST-RESORT uses (GDP-10: no incident, no new rule) — so
only the verified safety+hook proximity pattern is gated here, not a
speculative broader one.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

AGENT_BUILDER_AGENT = ROOT / "nWave/agents/nw-agent-builder.md"
AB_ANTI_PATTERNS = ROOT / "nWave/skills/nw-ab-anti-patterns/SKILL.md"
AB_CRITIQUE_DIMENSIONS = ROOT / "nWave/skills/nw-ab-critique-dimensions/SKILL.md"
ABR_CRITIQUE_DIMENSIONS = ROOT / "nWave/skills/nw-abr-critique-dimensions/SKILL.md"
AB_VALIDATE_SPEC = ROOT / "nWave/skills/nw-ab-validate-spec/SKILL.md"
AB_MIGRATE_MONOLITH = ROOT / "nWave/skills/nw-ab-migrate-monolith/SKILL.md"
AB_VALIDATION_CHECKLIST = ROOT / "nWave/skills/nw-ab-validation-checklist/SKILL.md"
FORGE_TASK = ROOT / "nWave/tasks/nw/forge.md"
FORGE_SKILL = ROOT / "nWave/skills/nw-forge/SKILL.md"
REVIEW_WORKFLOW = ROOT / "nWave/skills/nw-review-workflow/SKILL.md"
ROOT_WHY_SKILL = ROOT / "nWave/skills/nw-root-why/SKILL.md"
BUGFIX_SKILL = ROOT / "nWave/skills/nw-bugfix/SKILL.md"
CROSS_CUTTING = ROOT / "nWave/skills/nw-cross-cutting-invariants/SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _compact(path: Path) -> str:
    return " ".join(_text(path).split())


def test_agent_builder_safety_principle_steers_construction_first() -> None:
    compact = _compact(AGENT_BUILDER_AGENT)
    assert "Platform safety by construction (GDP-0)" in compact
    assert "which producer makes the unsafe action unrepresentable" in compact
    assert "a hook is last resort, admitted only with a recorded reason" in compact


def test_ab_anti_patterns_table_steers_construction_first() -> None:
    compact = _compact(AB_ANTI_PATTERNS)
    assert "Use frontmatter fields and hooks" not in compact
    assert "Construct safety first" in compact
    assert "hooks last resort (GDP-0)" in compact


def test_ab_critique_dimensions_dimension_4_steers_construction_first() -> None:
    compact = _compact(AB_CRITIQUE_DIMENSIONS)
    assert "Safety Implementation by Construction (GDP-0)" in compact
    assert "did the spec construct it away, or reach for a check" in compact
    assert "No prose-based security layers (use hooks)" not in compact


def test_abr_critique_dimensions_sibling_copy_also_steers_construction_first() -> None:
    """The reviewer-side duplicate must carry the identical fix — a
    projection test on the twin skill alone would not catch this one
    regressing back to the unfixed phrasing."""
    compact = _compact(ABR_CRITIQUE_DIMENSIONS)
    assert "Safety Implementation by Construction (GDP-0)" in compact
    assert "did the spec construct it away, or reach for a check" in compact
    assert "No prose-based security layers (use hooks)" not in compact


def test_ab_validate_spec_item_7_steers_construction_first() -> None:
    compact = _compact(AB_VALIDATE_SPEC)
    assert "Safety by construction (GDP-0)" in compact
    assert "safety via frontmatter fields + hooks, not prose" not in compact
    assert "construction-can't-cover reason" in compact


def test_ab_migrate_monolith_remove_duplication_steers_construction_first() -> None:
    compact = _compact(AB_MIGRATE_MONOLITH)
    assert "safety/security prose → frontmatter+hooks" not in compact
    assert "construction first (frontmatter tool surface, typed grammar)" in compact
    assert "GDP-0" in compact


def test_ab_validation_checklist_item_7_steers_construction_first() -> None:
    compact = _compact(AB_VALIDATION_CHECKLIST)
    assert "safety via frontmatter + hooks, not prose" not in compact
    assert "Safety by construction (GDP-0)" in compact


def test_forge_task_and_skill_success_criteria_steer_construction_first() -> None:
    for path in (FORGE_TASK, FORGE_SKILL):
        compact = _compact(path)
        assert (
            "Safety via platform features (frontmatter/hooks), not prose" not in compact
        )
        assert "Safety by construction first" in compact
        assert "hooks last resort with a recorded reason (GDP-0)" in compact


def test_review_workflow_checklist_item_8_steers_construction_first() -> None:
    compact = _compact(REVIEW_WORKFLOW)
    assert "Platform safety**: Via frontmatter/hooks, not prose" not in compact
    assert "Platform safety by construction (GDP-0)" in compact


def test_root_why_retrospective_step_names_the_producer() -> None:
    compact = _compact(ROOT_WHY_SKILL)
    assert (
        "the root cause names the producer/type that admitted the failing state (GDP-0)"
        in compact
    )
    assert "a fix that adds a check instead is a symptom patch" in compact


def test_bugfix_rca_step_names_the_producer() -> None:
    compact = _compact(BUGFIX_SKILL)
    assert (
        "naming the producer or type that admitted the wrong state (GDP-0)" in compact
    )
    assert "A gate/check is not the root cause unless" in compact


def test_cross_cutting_invariants_carries_construction_moves_catalogue() -> None:
    text = _text(CROSS_CUTTING)
    compact = _compact(CROSS_CUTTING)
    assert "## `construction:moves-catalogue`" in text
    for move in (
        "Compile the derivable fields",
        "Give the author the check at authoring time",
        "Type the invalid value away",
        "One writer for shared state",
        "Pristine environments",
        "Producer-emitted envelope",
    ):
        assert move in compact
    # Every move example names a concrete, grep-able repo artifact (GDP-8:
    # no claimed producer without a pointer) rather than a bare assertion.
    assert "des dispatch" in compact
    assert "des charter-scaffold" in compact
    assert "_charter_resolution" in compact
    assert "verify-fresh-clone" in compact
    assert "des resolve-charters" in compact
    gdp_section_index = text.index("## `gate:design-principles-gdp-1-9`")
    catalogue_index = text.index("## `construction:moves-catalogue`")
    next_section_index = text.index("## `gate:predicate-needs-its-own-enumerator`")
    assert gdp_section_index < catalogue_index < next_section_index


# ---------------------------------------------------------------------------
# Corpus-wide regression scanner
# ---------------------------------------------------------------------------

CORPUS_GLOBS = (
    "nWave/skills/*/SKILL.md",
    "nWave/agents/*.md",
    "nWave/tasks/nw/*.md",
)

# Verified defect class: a line pairs "safety"/"security" with "hook(s)"
# within loose proximity, in either order, without also naming GDP-0 as the
# governing discipline. Every current corpus hit satisfies this (see the
# per-file projection tests above); the allowlist stays empty by
# construction (GDP-10 — no observed LEGIT/PRODUCT exception yet). Add an
# entry only with a cited reason, keyed by (relative-path, line-number).
SAFETY_HOOK_PROXIMITY = re.compile(
    r"(?i)(safety|security).{0,60}hooks?|hooks?.{0,60}(safety|security)"
)

ALLOWLIST: dict[tuple[str, int], str] = {
    # (relative_path, line_number): "reason this is LEGIT-LAST-RESORT or PRODUCT-GATE"
}


def _corpus_files() -> list[Path]:
    files: list[Path] = []
    for pattern in CORPUS_GLOBS:
        files.extend(sorted(ROOT.glob(pattern)))
    return files


def test_corpus_has_no_unallowlisted_safety_hook_steering() -> None:
    violations: list[str] = []
    for path in _corpus_files():
        rel = str(path.relative_to(ROOT))
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not SAFETY_HOOK_PROXIMITY.search(line):
                continue
            if "GDP-0" in line:
                continue
            reason = ALLOWLIST.get((rel, lineno))
            if reason is not None:
                continue
            violations.append(f"{rel}:{lineno}: {line.strip()}")

    assert not violations, (
        "Safety/security steered toward hooks without GDP-0 construction-"
        "first framing (WHAT). Fix at the site: name the producer that "
        "could make the unsafe action unrepresentable (tool surface, typed "
        "grammar, producer-emitted envelope) before a hook; cite GDP-0 on "
        "the same line (WHY: gates are last resort, per "
        "nw-cross-cutting-invariants `gate:design-principles-gdp-1-9`). If "
        "the hit is a genuine LEGIT-LAST-RESORT or PRODUCT-GATE passage, "
        "add it to ALLOWLIST in this test with a one-line reason (HOW), "
        "never silence the scanner globally.\n" + "\n".join(violations)
    )
