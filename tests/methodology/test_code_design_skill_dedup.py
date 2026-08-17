"""Structural gate — code-design SSOT dedup (absorbed into nwave-flow-v2-enforcement).

Feature: nwave-flow-v2-enforcement (absorbed architect-owns-code-design;
former F-SOLUTION-ARCHITECT-OWNS-CODE-DESIGN-CRAFTER-EXECUTES).
Slice-01 (@walking-skeleton): the shared OO code-design Skill is the extracted
SSOT, and the solution architect references it from its on-demand Skill Loading
Strategy table under the OO paradigm branch.

This is a structural / methodology gate. The SUT is the methodology-file corpus
(agent .md + Skill SKILL.md); the driving port is the filesystem read of those
files (the legitimate structural-gate driving surface for an infra-only
methodology feature). Python + filesystem only — no subprocess, no git
(genericita / target-machine-agnosticism mandate, ARCH_TECH_DEBT.md
Architectural Constraints).

atdd_pure: these scenarios are active-RED. They RUN and raise AssertionError
because slice-01's production artifacts (the curated OO Skill file + the
architect on-demand reference) do not yet exist — DELIVER makes them GREEN.
Slice-01 (OO), slice-02 (FP) and slice-03 (anti-bloat: Invariant 1 + Invariant 2)
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

# The solution architect agent spec that must reference the OO skill on-demand.
ARCHITECT_SPEC = REPO / "nWave/agents/nw-solution-architect.md"

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


# --- Assertion 2: the architect references the OO skill (OO paradigm branch) --


def test_architect_references_oo_code_design_skill() -> None:
    """The architect on-demand Skill Loading Strategy table references the OO skill.

    Observable effect (K1, OO branch): a solution architect on an OO project can
    load the shared OO code-design SSOT from its on-demand table — the design
    knowledge is reachable, not duplicated inline.
    """
    spec = ARCHITECT_SPEC.read_text(encoding="utf-8")
    assert "nw-code-design-oo" in spec, (
        "nw-solution-architect.md must reference nw-code-design-oo in its "
        "On-Demand Skill Loading Strategy table (OO paradigm branch) so the "
        "architect can load the shared OO code-design SSOT."
    )


# =============================================================================
# slice-02 (FP) — per-slice JIT authoring (ADR-029 D3). These scenarios are
# active-RED: they RUN and raise AssertionError because slice-02's production
# artifacts (the curated FP Skill file + the architect FP on-demand reference +
# the functional crafter skills entry) do not yet exist — DELIVER makes them
# GREEN. slice-03 (anti-bloat dedup gate: Invariant 1 + Invariant 2 /
# SHARED_SECTIONS) remains ABSENT from disk until slice-03 enters.
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

# The functional crafter agent spec that must reference the FP skill.
FP_CRAFTER_SPEC = REPO / "nWave/agents/nw-functional-software-crafter.md"

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


# --- Assertion 2: the architect references the FP skill (FP paradigm branch) ---


def test_architect_references_fp_code_design_skill() -> None:
    """The architect on-demand Skill Loading Strategy table references the FP skill.

    Observable effect (K1, FP branch): a solution architect on an FP project can
    load the shared FP code-design SSOT from its on-demand table — the design
    knowledge is reachable, not duplicated inline.
    """
    spec = ARCHITECT_SPEC.read_text(encoding="utf-8")
    assert "nw-code-design-fp" in spec, (
        "nw-solution-architect.md must reference nw-code-design-fp in its "
        "On-Demand Skill Loading Strategy table (FP paradigm branch) so the "
        "architect can load the shared FP code-design SSOT."
    )


# --- Assertion 3: the functional crafter references the FP skill ---------------


def test_fp_crafter_references_shared_fp_skill() -> None:
    """The functional crafter agent spec references the shared FP skill.

    Observable effect: nw-functional-software-crafter shares the same FP
    code-design SSOT as the architect (single source, no prose duplication) —
    K2/K3 (share, not copy) satisfied for the FP branch.
    """
    spec = FP_CRAFTER_SPEC.read_text(encoding="utf-8")
    assert "nw-code-design-fp" in spec, (
        "nw-functional-software-crafter.md must reference nw-code-design-fp "
        "(reachable via the discipline's Mandatory lens resolution table) so "
        "the FP crafter and the architect share the same FP code-design SSOT."
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
# Four assertions:
#  A. OO crafter reference: nw-software-crafter references nw-code-design-oo
#     (symmetry with the FP crafter wired in slice-02). [active-RED]
#  B. Invariant 1 (OO): no OO skill ## heading verbatim-copied into agent body.
#     [GREEN guard — already clean, no bloat in agents]
#  C. Invariant 1 (FP): no FP skill ## heading verbatim-copied into agent body.
#     [GREEN guard — already clean, no bloat in agents]
#  D. Invariant 2 (anti-3rd-copy): nw-quality-framework SKILL.md must
#     cross-reference nw-code-design-oo for the Object Calisthenics section.
#     [active-RED — QF has the heading but no cross-ref yet]
# =============================================================================

# The OO software crafter agent spec that must reference the OO skill.
OO_CRAFTER_SPEC = REPO / "nWave/agents/nw-software-crafter.md"

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

# nw-quality-framework skill — the third copy the bloat invariant targets.
QUALITY_FRAMEWORK_SKILL = REPO / "nWave/skills/nw-quality-framework/SKILL.md"

# SHARED_SECTIONS: heading fragment → curated SSOT skill name.
# For each row, the referencing file (value[0]) must NOT hold the verbatim
# heading (key) without also cross-referencing the SSOT name (value[1]).
SHARED_SECTIONS: dict[str, tuple[Path, str]] = {
    "## Object Calisthenics": (QUALITY_FRAMEWORK_SKILL, "nw-code-design-oo"),
}


# --- Assertion A: the OO crafter references the OO skill ----------------------


def test_software_crafter_references_shared_oo_skill() -> None:
    """The OO software crafter agent spec references the shared OO code-design skill.

    Observable effect (symmetry with FP branch, slice-02): nw-software-crafter
    references nw-code-design-oo in its Skill Loading Strategy so the OO crafter
    and the architect share the same OO code-design SSOT — K2/K3 (share, not
    copy) satisfied for the OO branch.

    active-RED: nw-software-crafter.md does not reference nw-code-design-oo yet.
    DELIVER adds the reference.
    """
    spec = OO_CRAFTER_SPEC.read_text(encoding="utf-8")
    assert "nw-code-design-oo" in spec, (
        "nw-software-crafter.md must reference nw-code-design-oo "
        "(reachable via the discipline's Mandatory lens resolution table) so "
        "the OO crafter and the architect share the same OO code-design SSOT."
    )


# --- Assertion B: Invariant 1 (OO) — no verbatim OO heading in agent bodies --


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


# --- Assertion C: Invariant 1 (FP) — no verbatim FP heading in agent bodies --


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


# --- Assertion D: Invariant 2 — anti-3rd-copy (SHARED_SECTIONS) ---------------


def test_crafter_skill_crossrefs_not_duplicates_shared_section() -> None:
    """nw-quality-framework must cross-reference nw-code-design-oo for its
    Object Calisthenics section (Invariant 2: anti-3rd-copy).

    The SHARED_SECTIONS map records that nw-quality-framework/SKILL.md holds a
    section whose heading substring-matches '## Object Calisthenics'.  This
    section must cross-reference nw-code-design-oo (the curated SSOT) instead
    of being a standalone verbatim third copy.

    active-RED: nw-quality-framework/SKILL.md:121 has
    '## Object Calisthenics (Application + Domain Layers)' and currently
    contains NO reference to nw-code-design-oo.  DELIVER trims the duplicated
    prose and adds the cross-reference to make this assertion GREEN.
    """
    violations: list[str] = []
    for heading_fragment, (ref_path, ssot_name) in SHARED_SECTIONS.items():
        if not ref_path.is_file():
            continue
        text = ref_path.read_text(encoding="utf-8")
        # The file contains the heading (or a heading that begins with it)
        # AND does NOT cross-reference the SSOT name.
        heading_present = any(
            line.startswith(heading_fragment) for line in text.splitlines()
        )
        ssot_referenced = ssot_name in text
        if heading_present and not ssot_referenced:
            violations.append(
                f"{ref_path.name}: contains '{heading_fragment}' but does not "
                f"cross-reference '{ssot_name}' (the curated SSOT) — Invariant 2 "
                f"(anti-3rd-copy) violated."
            )
    assert not violations, (
        "Skill file(s) duplicate a shared code-design section without "
        "cross-referencing the curated SSOT (Invariant 2).  Add a reference to "
        "the SSOT skill name and trim the standalone verbatim copy:\n"
        + "\n".join(violations)
    )
