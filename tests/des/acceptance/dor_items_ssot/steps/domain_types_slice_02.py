"""Typed domain vocabulary for dor-items-ssot slice-02 (Mandate-12).

slice-02 closes the LIVE enforcement hole at the artifact the reviewer actually
loads: ``nWave/skills/nw-dor-validation/SKILL.md``. Today that skill claims
"8 Items" (``:10``) and enumerates Items 1-8 WITHOUT Item 9 (Outcome-KPIs), so a
reviewer following the loaded skill silently drops the Outcome-KPIs hard gate
(AD-55). slice-02's production GREEN re-renders the skill to present the
canonical nine consistent with the SSOT (DISCUSS D-1 / D-3, DESIGN DDD-4
authoritative-transcription).

This module pins, as typed constants, the cross-artifact contract the slice-02
ATs assert over the REAL shipped skill content:

  - the readiness-item count the skill must present (nine), reusing the slice-01
    canonical list as the single source of truth (no second copy);
  - the Outcome-KPIs item the loaded skill must now carry (Item 9);
  - the forbidden ``nWave/data/`` literal the skill's SSOT pointer must AVOID
    (``scripts/validation/validate_no_data_refs.py`` forbids it in any
    ``nWave/{agents,skills,tasks}/*.md``), and the allowed pointer tokens the
    skill may use instead (the bare SSOT filename + the standalone reader cite).

The cross-artifact pattern mirrors the sibling
``fix_design_reuse_first_gate_cli`` slice-05 ``skill_assets.py``: a real shipped
skill file is the SUT, structural-content assertions verify the human-facing
copy, example-only (no PBT -- the contract is a fixed closed shape, Mandate
9/11).
"""

from __future__ import annotations

from dataclasses import dataclass

# Reuse the slice-01 canonical list as the SINGLE source of truth -- slice-02
# does NOT restate the nine items (that would itself be the drift this feature
# exists to kill). The skill-presentation contract is "the loaded skill presents
# THESE nine".
from .domain_types import (
    CANONICAL_READINESS_ITEM_COUNT,
    CANONICAL_READINESS_ITEMS,
    JOB_TRACEABILITY_GATE,
)


# The single readiness item the loaded skill drops today (Item 9). Naming it
# explicitly makes the live-hole closure the slice-02 ATs verify unmistakable.
OUTCOME_KPIS_ITEM: str = (
    "Outcome KPIs defined with measurable targets and a stated baseline "
    "(current-state value the target is measured against)"
)

# The stale count claim the skill carries today and must stop carrying.
STALE_ITEM_COUNT_CLAIM: str = "8 Items"

# The canonical count claim the GREEN skill must carry instead.
CANONICAL_ITEM_COUNT_CLAIM: str = "9 Items"

# The forbidden literal: `validate_no_data_refs.py` rejects any
# ``nWave/data/`` reference in framework `.md` files. The skill's SSOT pointer
# MUST NOT contain it -- the pointer names the SSOT by its bare filename and/or
# cites the standalone reader instead.
FORBIDDEN_DATA_PREFIX: str = "nWave/data/"

# Allowed pointer tokens the GREEN skill MAY use to cite the SSOT without the
# forbidden prefix: the bare SSOT filename and the standalone reader path.
SSOT_FILENAME_TOKEN: str = "dor-items.yaml"
SSOT_READER_TOKEN: str = "scripts/cli/read_dor_items.py"


@dataclass(frozen=True)
class LoadedSkillView:
    """The reviewer-loaded DoR-validation skill's port-exposed content surface.

    Port-exposed observable shape only (Mandate 8): the structural facts a
    reviewer-or-drift-gate reads off the shipped skill text -- the readiness
    items the skill enumerates, the count it claims, whether it carries the
    Outcome-KPIs item, and whether its SSOT pointer avoids the forbidden
    literal. Never an internal parser struct.
    """

    enumerated_items: tuple[str, ...]
    claims_stale_count: bool
    claims_canonical_count: bool
    presents_outcome_kpis_item: bool
    ssot_pointer_present: bool
    ssot_pointer_uses_forbidden_prefix: bool

    @property
    def enumerated_item_count(self) -> int:
        return len(self.enumerated_items)


__all__ = [
    "CANONICAL_ITEM_COUNT_CLAIM",
    "CANONICAL_READINESS_ITEMS",
    "CANONICAL_READINESS_ITEM_COUNT",
    "FORBIDDEN_DATA_PREFIX",
    "JOB_TRACEABILITY_GATE",
    "OUTCOME_KPIS_ITEM",
    "SSOT_FILENAME_TOKEN",
    "SSOT_READER_TOKEN",
    "STALE_ITEM_COUNT_CLAIM",
    "LoadedSkillView",
]
