"""Typed domain vocabulary for f-design-wave-migration Gherkin ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum / frozen value, so the composition
methods consume typed parameters (no raw ``str`` where an enum exists). The
``Skill`` enum lets one step template range over the two shipped skills (DSL
emergence over an enum, not a decorator per skill).

These types are TEST-LOCAL except the deliberate ``DESConfig`` driving-port read
in the slice-02 AT-6 composition root (a production config port — the same port
the original plain-pytest AT-6 drove). No other production module is imported at
the step boundary for its business logic.
"""

from __future__ import annotations

from enum import Enum


class Skill(Enum):
    """The two REAL shipped skill files the prose-contract ATs read.

    The driving port for every prose scenario = the filesystem read of one of
    these canonical shipped files. The enum is the typed coercion target for the
    ``the shipped <skill> skill`` step template, so the DSL ranges over the
    vocabulary instead of proliferating one decorator per skill.
    """

    DISTILL = "nw-distill"
    DELIVER = "nw-deliver"


# The literal heading whose ABSENCE row 7b keys the DESIGN-absent advisory off
# (brief §3a Observe: "Test for the literal heading ## Wave: DESIGN /
# [REF] Code-Design"). slice-01.
DESIGN_SECTION_HEADING: str = "[REF] Code-Design"

# Row 7b's discriminating anchor: the wave it PROPOSEs when DESIGN is absent.
# /nw-design appears nowhere else in nw-distill, so finding it proves row 7b.
NW_DESIGN_WAVE: str = "/nw-design"

# Row 7c's discriminating anchor: the wave it PROPOSEs to split an over-large
# feature. /nw-discuss appears nowhere else in nw-distill, so finding it proves
# row 7c (the only sub-step that proposes splitting an over-large feature).
# slice-02.
NW_DISCUSS_WAVE: str = "/nw-discuss"

# The config knob name DD-3 fixes for the total-AT advisory threshold (slice-02
# AT-6 / C3). Distinct locus from carpaccio_slice_max (config.yaml atdd_pure.).
THRESHOLD_KEY: str = "feature_total_at_advisory_threshold"

# The named anchor the slice-03 keystone establishes — a sibling grep-cites THIS
# literal (DESIGN §:330, :350). slice-03.
PATTERN_ANCHOR: str = "## Advisory-Skip-Gate Pattern (Tier-A)"

# The five Tier-A closed-option ESC slots a sibling binds per trigger
# (DESIGN §:351-359). slice-03.
FIVE_SLOTS: tuple[str, ...] = ("NAME", "RISK", "PROPOSE", "ASK", "PROCEED")


class DesignMatrix(Enum):
    """The two nw-distill Graceful-Degradation matrices slice-04 reconciles.

    The skill carries the DESIGN-absent BLOCK veto in TWO separate matrices; R-3
    and R-4 must be witnessed independently (reconciling only one leaves the
    never-blocks violation alive one matrix over — ADR-DWM-001 §Decision). The
    enum value is the matrix's heading anchor (durable content, never a line no).
    """

    # R-4 — first matrix ("warn vs block").
    WARN_VS_BLOCK = "## Graceful Degradation Matrix (warn vs block)"
    # R-3 — second matrix ("for Missing Upstream Artifacts").
    MISSING_UPSTREAM = "## Graceful Degradation for Missing Upstream Artifacts"
