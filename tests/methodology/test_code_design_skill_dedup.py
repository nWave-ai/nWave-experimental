"""Structural gate — code-design SSOT dedup (absorbed into nwave-flow-v2-enforcement).

Feature: nwave-flow-v2-enforcement (absorbed architect-owns-code-design;
former F-SOLUTION-ARCHITECT-OWNS-CODE-DESIGN-CRAFTER-EXECUTES).
Slice-01 (@walking-skeleton): the shared OO code-design Skill is the extracted
SSOT for OO anti-smell knowledge.

This is a structural / methodology gate. The SUT is the methodology-file corpus
(agent .md + Skill SKILL.md); the driving port is the filesystem read of those
files (the legitimate structural-gate driving surface for an infra-only
methodology feature). Python + filesystem only — no subprocess, no git
(genericita / target-machine-agnosticism mandate, ARCH_TECH_DEBT.md
Architectural Constraints).

Slice-01 (OO), slice-02 (FP) and slice-03 (anti-bloat: Invariant 1)
assertions are all landed (per-slice JIT authoring, ADR-025 / ADR-029 D3).

DESIGN driving surface for slice-01: feature-delta.md
"Wave: DESIGN / [REF] Driving Surface / slice-01".
Content boundary for nw-code-design-oo: feature-delta.md
"Wave: DESIGN / [REF] Content boundary: OO" — Object Calisthenics +
RPP Smell Taxonomy + Effect Isolation.
"""

from __future__ import annotations

from pathlib import Path


# REPO root: tests/methodology/test_*.py -> parents[2] == repo root.
REPO = Path(__file__).parents[2]

# The curated OO code-design Skill — single SSOT for OO anti-smell knowledge.
OO_SKILL = REPO / "nWave/skills/nw-code-design-oo/SKILL.md"

# Canonical OO code-design section headings the DESIGN content boundary requires
# (feature-delta "Content boundary: OO"). Presence of the heading, not exact
# prose, is the contract — the curator may phrase the body freely.
REQUIRED_OO_SECTIONS = (
    "Object Calisthenics",
    "RPP Smell Taxonomy",
    "Effect Isolation",
)


# --- Assertion 1: the OO skill exists and carries the design-only catalog -----


def test_oo_code_design_skill_file_exists() -> None:
    """The curated OO code-design Skill exists as a repo-tracked SSOT file."""
    assert OO_SKILL.is_file(), (
        f"nw-code-design-oo SKILL.md not found at {OO_SKILL.relative_to(REPO)} — "
        "slice-01 requires the curated OO code-design SSOT to exist."
    )


def test_oo_code_design_skill_has_valid_frontmatter_name() -> None:
    """The OO skill frontmatter declares name: nw-code-design-oo."""
    text = OO_SKILL.read_text(encoding="utf-8") if OO_SKILL.is_file() else ""
    assert "name: nw-code-design-oo" in text, (
        "nw-code-design-oo SKILL.md must carry frontmatter `name: nw-code-design-oo` "
        "so the architect on-demand reference resolves to it."
    )


def test_oo_code_design_skill_contains_required_catalog_sections() -> None:
    """The OO skill contains the canonical design-only catalog headings.

    Asserts the presence of each required section heading (Object Calisthenics,
    RPP Smell Taxonomy, Effect Isolation) per the DESIGN content boundary — the
    catalog the architect needs to design smell-free domain types.
    """
    text = OO_SKILL.read_text(encoding="utf-8") if OO_SKILL.is_file() else ""
    missing = [section for section in REQUIRED_OO_SECTIONS if section not in text]
    assert not missing, (
        f"nw-code-design-oo SKILL.md is missing required catalog section(s): "
        f"{missing}. The OO code-design SSOT must carry the full design-only "
        f"anti-smell catalog (Object Calisthenics, RPP smell taxonomy, "
        f"effect isolation)."
    )


# =============================================================================
# slice-02 (FP) — per-slice JIT authoring (ADR-029 D3).
#
# slice-02 value: "A solution architect selecting the FP paradigm loads the
# shared FP code-design skill (algebra-driven design, domain modelling with
# types, effect isolation) from the same SSOT, gaining the same design quality
# as the FP crafter — without duplicating prose." (feature-delta Slice Plan.)
#
# DESIGN driving surface: feature-delta.md "Wave: DESIGN / [REF] Driving
# Surface / slice-02". Content boundary: feature-delta.md "Content boundary: FP".
# =============================================================================

# The curated FP code-design Skill — single SSOT for FP design knowledge.
FP_SKILL = REPO / "nWave/skills/nw-code-design-fp/SKILL.md"

# Canonical FP code-design section headings the DESIGN content boundary requires
# (feature-delta "Content boundary: FP" + slice-02 value statement). Presence of
# the heading, not exact prose, is the contract — the curator may phrase the body
# freely. Chosen to mirror how slice-01 (OO) picked Object Calisthenics / RPP
# Smell Taxonomy / Effect Isolation:
#   1. "Algebra-Driven Design"        <- from nw-fp-algebra-driven-design
#   2. "Domain Modelling with Types"  <- from nw-fp-domain-modeling (illegal
#                                        states unrepresentable / smart ctors)
#   3. "Railway"                      <- from nw-fp-domain-modeling §Error-Track
#                                        Pipelines (Railway Pattern) — effect /
#                                        error-track isolation
REQUIRED_FP_SECTIONS = (
    "Algebra-Driven Design",
    "Domain Modelling with Types",
    "Railway",
)


# --- Assertion 1: the FP skill exists and carries the design-only catalog -----


def test_fp_code_design_skill_file_exists() -> None:
    """The curated FP code-design Skill exists as a repo-tracked SSOT file."""
    assert FP_SKILL.is_file(), (
        f"nw-code-design-fp SKILL.md not found at {FP_SKILL.relative_to(REPO)} — "
        "slice-02 requires the curated FP code-design SSOT to exist."
    )


def test_fp_code_design_skill_has_valid_frontmatter_name() -> None:
    """The FP skill frontmatter declares name: nw-code-design-fp."""
    text = FP_SKILL.read_text(encoding="utf-8") if FP_SKILL.is_file() else ""
    assert "name: nw-code-design-fp" in text, (
        "nw-code-design-fp SKILL.md must carry frontmatter `name: nw-code-design-fp` "
        "so the architect on-demand reference resolves to it."
    )


def test_fp_code_design_skill_contains_required_catalog_sections() -> None:
    """The FP skill contains the canonical design-only catalog headings.

    Asserts the presence of each required section heading (Algebra-Driven Design,
    Domain Modelling with Types, Railway) per the DESIGN content boundary — the
    catalog the architect needs to design FP domain models with the same quality
    as the FP crafter.
    """
    text = FP_SKILL.read_text(encoding="utf-8") if FP_SKILL.is_file() else ""
    missing = [section for section in REQUIRED_FP_SECTIONS if section not in text]
    assert not missing, (
        f"nw-code-design-fp SKILL.md is missing required catalog section(s): "
        f"{missing}. The FP code-design SSOT must carry the full design-only "
        f"catalog (algebra-driven design, domain modelling with types, "
        f"railway/error-track isolation)."
    )


# =============================================================================
# slice-03 (anti-bloat dedup gate) — per-slice JIT authoring (ADR-029 D3).
#
# slice-03 value: "A verbatim copy of code-design knowledge in a crafter skill
# is rejected mechanically." (feature-delta Slice Plan.)
#
# DESIGN driving surface: feature-delta.md
# "Wave: DESIGN / [REF] slice-03 anti-bloat structural gate".
#
# Two assertions:
#  A. Invariant 1 (OO): no OO skill ## heading verbatim-copied into agent body.
#     [GREEN guard — already clean, no bloat in agents]
#  B. Invariant 1 (FP): no FP skill ## heading verbatim-copied into agent body.
#     [GREEN guard — already clean, no bloat in agents]
# =============================================================================

# Agent bodies checked for Invariant 1 (OO): must NOT contain verbatim
# ## headings from nw-code-design-oo.
OO_AGENT_BODIES = (
    REPO / "nWave/agents/nw-solution-architect.md",
    REPO / "nWave/agents/nw-software-crafter.md",
)

# Agent bodies checked for Invariant 1 (FP): must NOT contain verbatim
# ## headings from nw-code-design-fp.
FP_AGENT_BODIES = (
    REPO / "nWave/agents/nw-solution-architect.md",
    REPO / "nWave/agents/nw-functional-software-crafter.md",
)

# --- Assertion A: Invariant 1 (OO) — no verbatim OO heading in agent bodies --


def test_no_agent_body_duplicates_oo_design_knowledge() -> None:
    """No agent body contains verbatim ## section headings from nw-code-design-oo.

    Invariant 1 (OO): a verbatim copy of any top-level ## heading from the
    curated OO skill (Object Calisthenics, RPP Smell Taxonomy, Effect Isolation)
    appearing in an agent body is bloat — the knowledge lives in the skill SSOT,
    not inline in the agent.

    Classification: GREEN guard (agents are already clean — no verbatim headings
    were found in any agent body at slice-03 authoring).
    """
    violations: list[str] = []
    oo_headings = tuple(f"## {s}" for s in REQUIRED_OO_SECTIONS)
    for agent_path in OO_AGENT_BODIES:
        if not agent_path.is_file():
            continue
        body = agent_path.read_text(encoding="utf-8")
        for heading in oo_headings:
            if heading in body:
                violations.append(f"{agent_path.name}: contains verbatim '{heading}'")
    assert not violations, (
        "Agent body(ies) contain verbatim OO code-design skill headings — "
        "bloat detected (Invariant 1). Move knowledge to nw-code-design-oo "
        "SSOT and replace with a cross-reference:\n" + "\n".join(violations)
    )


# --- Assertion B: Invariant 1 (FP) — no verbatim FP heading in agent bodies --


def test_no_agent_body_duplicates_fp_design_knowledge() -> None:
    """No agent body contains verbatim ## section headings from nw-code-design-fp.

    Invariant 1 (FP): same invariant as OO, applied to the FP catalog headings
    (Algebra-Driven Design, Domain Modelling with Types, Railway).

    Classification: GREEN guard (agents are already clean — no verbatim headings
    were found in any agent body at slice-03 authoring).
    """
    violations: list[str] = []
    fp_headings = tuple(f"## {s}" for s in REQUIRED_FP_SECTIONS)
    for agent_path in FP_AGENT_BODIES:
        if not agent_path.is_file():
            continue
        body = agent_path.read_text(encoding="utf-8")
        for heading in fp_headings:
            if heading in body:
                violations.append(f"{agent_path.name}: contains verbatim '{heading}'")
    assert not violations, (
        "Agent body(ies) contain verbatim FP code-design skill headings — "
        "bloat detected (Invariant 1). Move knowledge to nw-code-design-fp "
        "SSOT and replace with a cross-reference:\n" + "\n".join(violations)
    )
