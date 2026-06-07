"""Framework-asset composition root for slice-03 (cross-artifact checks).

F-DESIGN-REUSE-FIRST-GATE slice-03 (PARKED). DDD-8 (R1 normative source),
DDD-4 (reviewer veto). Mandate-12 + Pillar 3.

slice-03 is a cross-artifact slice: the SUT is the relationship between three
real repository assets --

  - the normative constants in
    ``scripts/validation/validate_feature_delta.py``
    (``REUSE_ANALYSIS_HEADING`` / ``REUSE_ANALYSIS_COLUMNS``),
  - the human-facing copy in ``nWave/skills/nw-design/SKILL.md``
    (the Reuse Analysis step + template), and
  - the veto critique dimension in
    ``nWave/agents/nw-solution-architect-reviewer.md``.

Layer 3 (framework-asset acceptance): the assets are read from the real
repository tree (not a tmp_path fixture -- the contract under test IS the
shipped asset). Example-only, no PBT (Mandate 9/11): each check is a single
normative-source identity assertion.

Business logic lives here as the single source of truth; step bodies delegate
to ``FrameworkAssetComposition`` methods and never inline logic (Mandate-12
criterion 3).

RED scaffold note (Mandate 7): on master the nw-design skill template still
spells the decision ``CREATE NEW`` (space) and carries no invocation
directive, and the reviewer carries no reuse-first critique dimension. The
slice-03 crafter EXTENDS all three assets. The composition methods below read
the live assets; the assertions FAIL on master (skill uses the space
spelling; reviewer lacks the dimension) and PASS once slice-03 lands -- a
deliberate missing-functionality RED. Imports resolve cleanly: the constants
are themselves DISTILL scaffolds present in ``validate_feature_delta.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Production normative source -- the canonical heading + column constant
# (DDD-8 / R1). These are DISTILL scaffolds on master; slice-01 keeps them as
# the ONE normative source the skill template must match.
from scripts.validation.validate_feature_delta import (
    REUSE_ANALYSIS_COLUMNS,
    REUSE_ANALYSIS_HEADING,
)


# Repository root -- four parents up from this file
# (.../distill/pending-slices/steps/framework_assets.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]

_NW_DESIGN_SKILL = _REPO_ROOT / "nWave" / "skills" / "nw-design" / "SKILL.md"
_REVIEWER_AGENT = _REPO_ROOT / "nWave" / "agents" / "nw-solution-architect-reviewer.md"


@dataclass
class SkillTemplateView:
    """The Reuse Analysis template the nw-design skill emits.

    ``heading`` is the canonical H2 heading the skill template carries.
    ``columns`` is the ordered tuple of column names in the template's GFM
    table header. ``uses_create_new_token`` is True iff the template spells
    the new-path decision ``CREATE_NEW`` (underscore). ``uses_legacy_spelling``
    is True iff the template still carries the legacy ``CREATE NEW`` (space).
    """

    heading: str
    columns: tuple[str, ...]
    uses_create_new_token: bool
    uses_legacy_spelling: bool


@dataclass
class ReviewerDimensionView:
    """The reviewer's reuse-first critique dimension.

    ``flags_unjustified_create_new`` is True iff the reviewer agent's critique
    dimensions name the veto over a CREATE_NEW whose justification is judged
    invalid. ``flags_silently_omitted_overlap`` is True iff they name the veto
    over an overlapping component judged to be silently omitted from the
    table (DDD-4 -- the judgment no parser can make).
    """

    flags_unjustified_create_new: bool
    flags_silently_omitted_overlap: bool


@dataclass
class FrameworkAssetComposition:
    """Production composition root over the live repository framework assets.

    The assets are the shipped files themselves -- this slice's contract is
    that the human-facing skill copy and the reviewer agent stay in lockstep
    with the normative constant. ``capture_universe`` snapshots the assets'
    bytes so the cross-artifact check proves it is read-only (Mandate 8).
    """

    nw_design_skill: Path = field(default=_NW_DESIGN_SKILL)
    reviewer_agent: Path = field(default=_REVIEWER_AGENT)

    # --- normative source ----------------------------------------------------

    @property
    def canonical_heading(self) -> str:
        """The normative Reuse Analysis heading constant (DDD-8)."""
        return REUSE_ANALYSIS_HEADING

    @property
    def canonical_columns(self) -> tuple[str, ...]:
        """The normative REUSE_ANALYSIS_COLUMNS constant (DDD-8)."""
        return REUSE_ANALYSIS_COLUMNS

    # --- skill template view -------------------------------------------------

    def read_skill_template(self) -> SkillTemplateView:
        """Parse the nw-design skill's Reuse Analysis template.

        Locates the ``## Reuse Analysis`` template block, extracts its GFM
        table header columns, and records whether the decision token is the
        canonical ``CREATE_NEW`` or the legacy ``CREATE NEW`` spelling.
        """
        text = self.nw_design_skill.read_text(encoding="utf-8")
        return _parse_skill_template(text)

    # --- reviewer dimension view --------------------------------------------

    def read_reviewer_dimension(self) -> ReviewerDimensionView:
        """Parse the reviewer agent's reuse-first critique dimension."""
        text = self.reviewer_agent.read_text(encoding="utf-8")
        return _parse_reviewer_dimension(text)

    # --- universe ------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Port-exposed snapshot for assert_state_delta (Mandate 8)."""
        return {
            "nw_design_skill.bytes": self.nw_design_skill.read_bytes(),
            "reviewer_agent.bytes": self.reviewer_agent.read_bytes(),
        }


# --- pure parsers -----------------------------------------------------------
# Keep each composition method a single delegation (Mandate-12 criterion 3).


def _parse_skill_template(text: str) -> SkillTemplateView:
    """Extract the Reuse Analysis template shape from the nw-design skill text.

    The skill carries the canonical ``## Reuse Analysis`` H2 followed by a
    five-column GFM table. The template's header row is the first GFM table
    row after that heading whose first cell is the first canonical column.
    """
    lines = text.splitlines()
    heading = ""
    columns: tuple[str, ...] = ()
    for idx, raw in enumerate(lines):
        if raw.strip() == REUSE_ANALYSIS_HEADING:
            heading = raw.strip()
            columns = _first_table_header(lines[idx + 1 :])
            break
    return SkillTemplateView(
        heading=heading,
        columns=columns,
        uses_create_new_token="CREATE_NEW" in text,
        uses_legacy_spelling="CREATE NEW" in text,
    )


def _first_table_header(lines: list[str]) -> tuple[str, ...]:
    """Return the columns of the first GFM table header in ``lines``."""
    for raw in lines:
        stripped = raw.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            return tuple(cells)
    return ()


def _parse_reviewer_dimension(text: str) -> ReviewerDimensionView:
    """Detect the reuse-first veto dimension in the reviewer agent text.

    The slice-03 crafter adds a critique dimension naming both veto items:
    an invalid / unjustified ``CREATE_NEW`` justification, and an overlapping
    component silently omitted from the Reuse Analysis table.
    """
    lowered = text.lower()
    return ReviewerDimensionView(
        flags_unjustified_create_new=(
            "create_new" in lowered and "justification" in lowered
        ),
        flags_silently_omitted_overlap=(
            "silently omitted" in lowered or "omitted overlapping" in lowered
        ),
    )
